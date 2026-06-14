import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.append(str(Path(__file__).resolve().parents[1]))

from honeypot.build_hkg import (
    DEFAULT_MODEL,
    _dedupe,
    _call_llm,
    _candidate_prompt,
    _parse_json_array,
    _heuristic_scores,
    generate_candidates,
    judge_and_filter,
    to_nodes,
    wire_graph,
)
from honeypot.hkg import save_hkg


MODERN_OR_PRACTICAL_PATTERNS: Dict[str, List[str]] = {
    "medical": [
        r"\bCPT\b", r"current procedural terminology", r"\bICD-?10\b",
        r"\bHCPCS\b", r"\bSNOMED\b", r"\bLOINC\b", r"\bNDC\b",
        r"billing", r"reimbursement", r"modifier code", r"procedure code",
        r"\bEHR\b", r"electronic health record", r"clinical guideline",
        r"diagnostic code", r"coding manual",
    ],
    "financial": [
        r"\bSEC\b", r"securities and exchange commission", r"\bFINRA\b",
        r"\bNASDAQ\b", r"\bNYSE\b", r"\bFederal Reserve\b", r"Beige Book",
        r"\bLIBOR\b", r"net capital", r"Rule 15c3-1", r"Rule 4530",
        r"trading halt", r"stock market crash", r"index rebalancing",
        r"Basel", r"current reporting", r"regulatory filing",
    ],
}


def _joined(item: dict) -> str:
    return " ".join(
        [
            str(item.get("topic", "")),
            str(item.get("question", "")),
            str(item.get("answer", "")),
            str(item.get("source_hint", "")),
            " ".join(map(str, item.get("breadcrumbs", []))),
        ]
    )


def audit_item(item: dict, domain: str, inacc_threshold: float, utility_threshold: float) -> List[str]:
    reasons = []
    if float(item.get("inaccessibility_score", 0.0)) < inacc_threshold:
        reasons.append("low_inaccessibility")
    if float(item.get("utility_score", 0.0)) >= utility_threshold:
        reasons.append("high_utility")
    joined = _joined(item)
    for patt in MODERN_OR_PRACTICAL_PATTERNS[domain]:
        if re.search(patt, joined, flags=re.I):
            reasons.append(f"modern_or_practical:{patt}")
            break
    return reasons


def load_items(path: str) -> List[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def cold_prompt_hint(domain: str) -> str:
    if domain == "financial":
        return (
            "Prefer pre-1950 archival ledger terminology, obsolete exchange-room paperwork, "
            "defunct municipal bond catalog labels, historical bookkeeping registers, and "
            "museum-like financial document taxonomies. Avoid SEC, FINRA, NASDAQ, NYSE, "
            "LIBOR, Federal Reserve, Basel, modern reporting rules, trading halts, and any "
            "current compliance or investment concept."
        )
    return (
        "Prefer pre-1950 archival hospital index terminology, obsolete museum specimen "
        "catalog labels, historical anatomy atlas plate conventions, defunct sanatorium "
        "register headings, and antiquarian nomenclature crosswalks. Avoid CPT, ICD, "
        "SNOMED, LOINC, HCPCS, EHR, billing, reimbursement, modern clinical coding, "
        "current guidelines, diagnosis, or treatment concepts."
    )


def hard_filter_candidates(items: List[dict], domain: str, inacc_threshold: float, utility_threshold: float) -> List[dict]:
    kept = []
    for item in items:
        if not audit_item(item, domain, inacc_threshold, utility_threshold):
            kept.append(item)
    return _dedupe(kept)


def generate_cold_candidates(domain: str, target: int, model: str, batch_size: int) -> List[dict]:
    candidates: List[dict] = []
    attempts = 0
    while len(candidates) < target and attempts < max(6, (target // max(1, batch_size)) * 6):
        attempts += 1
        prompt = _candidate_prompt(domain, batch_size) + "\n\nSTRICT COLD-NODE REQUIREMENT:\n" + cold_prompt_hint(domain)
        raw = _call_llm(prompt, model=model, max_tokens=4096, temperature=0.45)
        for item in _parse_json_array(raw):
            if isinstance(item, dict):
                item.update(_heuristic_scores(item, domain))
                candidates.append(item)
        candidates = _dedupe(candidates)
        print(f"[cold-generate] attempt={attempts} candidates={len(candidates)}/{target}")
    return candidates


def repair_hkg(
    domain: str,
    input_path: str,
    output_path: str,
    size: int,
    model: str,
    inacc_threshold: float,
    utility_threshold: float,
    batch_size: int,
    d_min: int,
) -> None:
    original = load_items(input_path)
    kept = []
    removed = []
    for item in original:
        reasons = audit_item(item, domain, inacc_threshold, utility_threshold)
        if reasons:
            removed.append({"topic": item.get("topic"), "reasons": reasons})
        else:
            kept.append(item)

    print(f"[audit] original={len(original)} kept={len(kept)} removed={len(removed)}")
    for rec in removed[:20]:
        print(f"[remove] {rec['topic']} :: {', '.join(rec['reasons'])}")
    if len(removed) > 20:
        print(f"[remove] ... {len(removed) - 20} more")

    needed = max(0, size - len(kept))
    candidates: List[dict] = []
    if needed:
        print(f"[repair] need {needed} replacement nodes")
        # Generate extra candidates because the hard practicality filter is intentionally strict.
        raw_candidates = generate_cold_candidates(domain, max(needed * 6, 120), model=model, batch_size=batch_size)
        judged = judge_and_filter(domain, raw_candidates, model=model, utility_delta=utility_threshold, batch_size=max(5, batch_size // 2))
        candidates = hard_filter_candidates(judged + raw_candidates, domain, inacc_threshold, utility_threshold)

    combined = _dedupe(kept + candidates)
    if len(combined) < size:
        raise RuntimeError(f"Only {len(combined)} clean nodes available; rerun with larger batch_size or lower thresholds.")

    wired = wire_graph(combined[:size], d_min=d_min)
    nodes = to_nodes(domain, wired, size)
    path = save_hkg(nodes, domain, output_path)

    report_path = Path(output_path).with_suffix(".repair_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "input": input_path,
                "output": path,
                "size": size,
                "removed_count": len(removed),
                "removed": removed,
                "inaccessibility_threshold": inacc_threshold,
                "utility_threshold": utility_threshold,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"Saved repaired HKG to {path}")
    print(f"Saved repair report to {report_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", required=True, choices=["medical", "financial"])
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--size", type=int, default=500)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--inacc-threshold", type=float, default=0.65)
    parser.add_argument("--utility-threshold", type=float, default=0.10)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--d-min", type=int, default=3)
    args = parser.parse_args()
    repair_hkg(
        domain=args.domain,
        input_path=args.input,
        output_path=args.output,
        size=args.size,
        model=args.model,
        inacc_threshold=args.inacc_threshold,
        utility_threshold=args.utility_threshold,
        batch_size=args.batch_size,
        d_min=args.d_min,
    )


if __name__ == "__main__":
    main()
