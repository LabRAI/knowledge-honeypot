import argparse
import json
import re
from pathlib import Path
from typing import Dict, List


DOMAIN_KEYWORDS = {
    "medical": [
        "clinical", "anatomy", "physiology", "pathology", "archive", "atlas",
        "specimen", "hospital", "nomenclature", "taxonomy", "register",
        "sanatorium", "plate", "index",
    ],
    "financial": [
        "ledger", "bookkeeping", "archive", "bond", "certificate", "registry",
        "exchange", "clearing", "coupon", "debenture", "taxonomy", "index",
        "memorandum", "schedule",
    ],
}


def relevance_score(text: str, domain: str) -> float:
    low = text.lower()
    hits = sum(1 for kw in DOMAIN_KEYWORDS[domain] if kw in low)
    # Smooth into [0, 1]. HKG nodes intentionally share domain style, so this
    # simple classifier often accepts them; that is the adaptive-attacker tension.
    return min(1.0, 0.18 + hits / max(4, len(DOMAIN_KEYWORDS[domain]) ** 0.5))


def load_records(path: str) -> List[Dict]:
    if path.endswith(".jsonl"):
        with open(path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("records", [])


def analyze(domain: str, input_path: str, output: str, thresholds: List[float]) -> Dict:
    records = load_records(input_path)
    rows = []
    for theta in thresholds:
        accepted = 0
        accepted_hkg = 0
        accepted_real = 0
        rejected_hkg = 0
        rejected_real = 0
        for rec in records:
            text = rec.get("teacher_answer") or rec.get("answer") or ""
            route = rec.get("defense_route") or rec.get("route") or ""
            is_hkg = "hkg" in route
            score = relevance_score(text, domain)
            if score >= theta:
                accepted += 1
                accepted_hkg += int(is_hkg)
                accepted_real += int(not is_hkg)
            else:
                rejected_hkg += int(is_hkg)
                rejected_real += int(not is_hkg)
        rows.append({
            "theta": theta,
            "total": len(records),
            "accepted": accepted,
            "accepted_fraction": accepted / max(1, len(records)),
            "accepted_hkg": accepted_hkg,
            "accepted_real": accepted_real,
            "rejected_hkg": rejected_hkg,
            "rejected_real": rejected_real,
            "hkg_acceptance_rate": accepted_hkg / max(1, accepted_hkg + rejected_hkg),
            "real_rejection_rate": rejected_real / max(1, accepted_real + rejected_real),
        })
    result = {"domain": domain, "input": input_path, "thresholds": rows}
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", required=True, choices=["medical", "financial"])
    parser.add_argument("--input", required=True, help="structured_log.json or honeypot_budget.jsonl")
    parser.add_argument("--output", required=True)
    parser.add_argument("--thresholds", default="0.3,0.5,0.7")
    args = parser.parse_args()
    thresholds = [float(x) for x in re.split(r"[,\s]+", args.thresholds) if x]
    analyze(args.domain, args.input, args.output, thresholds)


if __name__ == "__main__":
    main()
