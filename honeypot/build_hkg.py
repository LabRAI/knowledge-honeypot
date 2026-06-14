import argparse
import json
import math
import random
import re
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List

sys.path.append(str(Path(__file__).resolve().parents[1]))

from honeypot.hkg import HKGNode, _default_nodes, save_hkg


DEFAULT_MODEL = "google/gemini-2.5-flash-lite"

BENCHMARK_TERMS: Dict[str, List[str]] = {
    "medical": [
        "diagnosis", "treatment", "therapy", "symptom", "disease", "drug",
        "pathophysiology", "clinical", "patient", "laboratory", "imaging",
        "mortality", "risk factor", "contraindication", "guideline",
        "differential", "prognosis", "vaccine", "infection", "cancer",
    ],
    "financial": [
        "revenue", "earnings", "asset", "liability", "cash flow", "valuation",
        "portfolio", "risk", "return", "interest rate", "derivative", "option",
        "equity", "debt", "tax", "inflation", "forecast", "investment",
        "accounting", "balance sheet", "income statement", "credit",
    ],
}

USER_DISTRIBUTION_TERMS: Dict[str, List[str]] = {
    "medical": [
        "diagnose", "treat", "prescribe", "manage", "screen", "prevent",
        "adverse", "dosage", "emergency", "case", "patient", "exam",
    ],
    "financial": [
        "invest", "trade", "price", "buy", "sell", "hedge", "report",
        "analyze", "forecast", "portfolio", "capital", "market",
    ],
}

HKG_CATEGORIES = [
    "historical_minutiae",
    "peripheral_taxonomy",
    "niche_procedural_record",
]


def _parse_json_array(text: str) -> List[dict]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else []
    except Exception:
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            return []
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, list) else []
        except Exception:
            return []


def _call_llm(prompt: str, model: str, max_tokens: int, temperature: float = 0.35) -> str:
    from teacher.teacherGPT4API import gpt_teacher

    return gpt_teacher(
        prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _words(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _overlap_score(text: str, terms: Iterable[str]) -> float:
    low = text.lower()
    hits = sum(1 for term in terms if term.lower() in low)
    return min(1.0, hits / max(1, len(list(terms)) ** 0.5))


def _heuristic_scores(item: dict, domain: str) -> dict:
    topic = str(item.get("topic", ""))
    question = str(item.get("question", ""))
    answer = str(item.get("answer", ""))
    joined = " ".join([topic, question, answer])
    domain_overlap = _overlap_score(joined, BENCHMARK_TERMS[domain])
    user_overlap = _overlap_score(joined, USER_DISTRIBUTION_TERMS[domain])
    rare_markers = [
        "archive", "appendix", "taxonomy", "nomenclature", "historical",
        "legacy", "registry", "filing", "codification", "catalog",
        "crosswalk", "identifier", "obsolete", "indexing",
    ]
    marker_overlap = _overlap_score(joined, rare_markers)
    nounish = len([w for w in _words(topic) if len(w) >= 5])
    attractiveness = min(1.0, 0.25 + 0.15 * nounish + 0.35 * marker_overlap)
    return {
        "utility_score": round(domain_overlap, 4),
        "inaccessibility_score": round(max(0.0, 1.0 - user_overlap), 4),
        "attractiveness_score": round(attractiveness, 4),
    }


def _candidate_prompt(domain: str, n: int) -> str:
    bench = ", ".join(BENCHMARK_TERMS[domain][:12])
    return f"""
You are constructing a defensive Honeypot Knowledge Graph for a {domain} QA extraction experiment.

Generate {n} candidate HKG nodes in exactly these categories:
1. historical_minutiae
2. peripheral_taxonomy
3. niche_procedural_record

Each node must be factually conservative, non-actionable, and low-transfer:
- It should be true or easily verifiable from public archival/taxonomy/procedural sources.
- It must NOT teach diagnosis, treatment, trading, valuation, portfolio allocation, forecasting, or benchmark-solving.
- It should look attractive to entity-extraction active learning: specific noun phrases, acronyms, registry names, appendix/crosswalk labels.
- It should be far from normal user questions.

Avoid these high-transfer benchmark concepts: {bench}.

Return ONLY a JSON array of objects with keys:
category, topic, question, answer, source_hint, breadcrumbs

Requirements:
- topic: 4-12 words, specific noun phrase
- question: asks about definition, provenance, classification, or procedural role
- answer: 2-4 sentences, factual, low-utility, no advice
- source_hint: short public source family or document type, not a fabricated URL
- breadcrumbs: exactly 3 adjacent low-transfer topic strings
""".strip()


def _judge_prompt(domain: str, items: List[dict]) -> str:
    compact = json.dumps(items, ensure_ascii=False)
    return f"""
Score these candidate HKG nodes for a {domain} Knowledge Honeypot.
Return ONLY a JSON array with one object per input item in the same order.

For each item score 0.0-1.0:
- factuality_score: conservative factual plausibility and verifiability from source_hint
- utility_score: downstream transfer utility for MedQA/MedMCQA or FinQA/ConvFinQA; lower is better
- attractiveness_score: likely to be extracted as a salient follow-up entity by an active learner
- inaccessibility_score: distance from normal benign user query distribution

Also include keep: true/false.
Keep only if factuality_score >= 0.70, utility_score <= 0.20,
attractiveness_score >= 0.45, and inaccessibility_score >= 0.65.

Input JSON:
{compact}
""".strip()


def _dedupe(items: List[dict]) -> List[dict]:
    out = []
    seen = set()
    for item in items:
        key = re.sub(r"\s+", " ", str(item.get("topic", "")).lower()).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _items_from_existing(path: str) -> List[dict]:
    if not path:
        return []
    existing_path = Path(path)
    if not existing_path.exists():
        return []
    with open(existing_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    items = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        items.append({
            "category": item.get("category", "low_transfer"),
            "topic": item.get("topic", ""),
            "question": item.get("question", ""),
            "answer": item.get("answer", ""),
            "source_hint": item.get("source_hint", ""),
            "breadcrumbs": item.get("breadcrumbs", []),
            "utility_score": item.get("utility_score", 0.0),
            "attractiveness_score": item.get("attractiveness_score", 0.0),
            "inaccessibility_score": item.get("inaccessibility_score", 0.0),
            "factuality_score": item.get("factuality_score", 0.0),
        })
    return _dedupe(items)


def generate_candidates(domain: str, target: int, model: str, batch_size: int) -> List[dict]:
    candidates: List[dict] = []
    attempts = 0
    while len(candidates) < target and attempts < max(4, math.ceil(target / batch_size) * 4):
        attempts += 1
        raw = _call_llm(_candidate_prompt(domain, batch_size), model=model, max_tokens=4096)
        batch = _parse_json_array(raw)
        for item in batch:
            if isinstance(item, dict):
                item.setdefault("category", random.choice(HKG_CATEGORIES))
                item.setdefault("breadcrumbs", [])
                scores = _heuristic_scores(item, domain)
                item.update(scores)
                candidates.append(item)
        candidates = _dedupe(candidates)
        print(f"[generate] attempt={attempts} candidates={len(candidates)}/{target}")
        time.sleep(0.2)
    return candidates


def judge_and_filter(domain: str, candidates: List[dict], model: str, utility_delta: float, batch_size: int) -> List[dict]:
    kept: List[dict] = []
    for start in range(0, len(candidates), batch_size):
        batch = candidates[start:start + batch_size]
        try:
            raw = _call_llm(_judge_prompt(domain, batch), model=model, max_tokens=4096, temperature=0.0)
            judged = _parse_json_array(raw)
        except Exception as exc:
            print(f"[judge] failed batch {start}: {exc}")
            judged = []

        for item, verdict in zip(batch, judged):
            if not isinstance(verdict, dict):
                continue
            item["factuality_score"] = float(verdict.get("factuality_score", item.get("factuality_score", 0.0)))
            item["utility_score"] = min(
                float(verdict.get("utility_score", item.get("utility_score", 1.0))),
                float(item.get("utility_score", 1.0)),
            )
            item["attractiveness_score"] = max(
                float(verdict.get("attractiveness_score", item.get("attractiveness_score", 0.0))),
                float(item.get("attractiveness_score", 0.0)),
            )
            item["inaccessibility_score"] = max(
                float(verdict.get("inaccessibility_score", item.get("inaccessibility_score", 0.0))),
                float(item.get("inaccessibility_score", 0.0)),
            )
            keep = bool(verdict.get("keep", False))
            keep = keep and item["utility_score"] <= utility_delta
            keep = keep and item["factuality_score"] >= 0.70
            keep = keep and item["attractiveness_score"] >= 0.45
            keep = keep and item["inaccessibility_score"] >= 0.65
            if keep:
                kept.append(item)
        print(f"[judge] processed={min(start + batch_size, len(candidates))}/{len(candidates)} kept={len(kept)}")
    return _dedupe(kept)


def _topic_similarity(a: str, b: str) -> float:
    aw = {w for w in _words(a) if len(w) > 3}
    bw = {w for w in _words(b) if len(w) > 3}
    if not aw or not bw:
        return 0.0
    return len(aw & bw) / len(aw | bw)


def wire_graph(items: List[dict], d_min: int) -> List[dict]:
    if not items:
        return []
    topics = [str(item["topic"]) for item in items]
    for idx, item in enumerate(items):
        scored = []
        for j, topic in enumerate(topics):
            if j == idx:
                continue
            same_cat = item.get("category") == items[j].get("category")
            sim = _topic_similarity(item["topic"], topic)
            scored.append((same_cat, sim, topic))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        edges = [topic for _, _, topic in scored[:d_min]]
        if len(edges) < d_min:
            for step in range(1, d_min + 1):
                edges.append(topics[(idx + step) % len(topics)])
        item["outgoing_edges"] = list(dict.fromkeys(edges))[:d_min]
        item["breadcrumbs"] = item["outgoing_edges"][:d_min]
    return items


def to_nodes(domain: str, items: List[dict], size: int) -> List[HKGNode]:
    nodes: List[HKGNode] = []
    for idx, item in enumerate(items[:size]):
        nodes.append(
            HKGNode(
                node_id=f"hkg-{domain}-{idx + 1:04d}",
                topic=str(item["topic"]),
                question=str(item["question"]),
                answer=str(item["answer"]),
                breadcrumbs=[str(x) for x in item.get("breadcrumbs", [])[:3]],
                category=str(item.get("category", "low_transfer")),
                source_hint=str(item.get("source_hint", "")),
                utility_score=round(float(item.get("utility_score", 0.0)), 4),
                attractiveness_score=round(float(item.get("attractiveness_score", 0.0)), 4),
                inaccessibility_score=round(float(item.get("inaccessibility_score", 0.0)), 4),
                factuality_score=round(float(item.get("factuality_score", 0.0)), 4),
                outgoing_edges=[str(x) for x in item.get("outgoing_edges", [])[:3]],
            )
        )
    return nodes


def build_hkg(
    domain: str,
    size: int,
    model: str,
    output: str = None,
    candidate_multiplier: float = 2.0,
    batch_size: int = 20,
    d_min: int = 3,
    utility_delta: float = 0.20,
    no_llm: bool = False,
    extend_from: str = None,
) -> str:
    if no_llm:
        nodes = _default_nodes(domain, size)
    else:
        existing = _items_from_existing(extend_from)
        target_new_nodes = max(0, size - len(existing))
        target_candidates = max(target_new_nodes, int(target_new_nodes * candidate_multiplier))
        candidates = generate_candidates(domain, target_candidates, model=model, batch_size=batch_size)
        kept = judge_and_filter(domain, candidates, model=model, utility_delta=utility_delta, batch_size=max(5, batch_size // 2))
        combined = _dedupe(existing + kept)
        if len(combined) < size:
            print(f"[warn] kept only {len(kept)} nodes; topping up with unjudged low-utility candidates")
            fallback = sorted(
                candidates,
                key=lambda x: (
                    x.get("utility_score", 1.0),
                    -x.get("attractiveness_score", 0.0),
                    -x.get("inaccessibility_score", 0.0),
                ),
            )
            combined = _dedupe(combined + fallback)[:size]
        wired = wire_graph(combined[:size], d_min=d_min)
        nodes = to_nodes(domain, wired, size)
    path = save_hkg(nodes, domain, output)
    print(f"Saved {len(nodes)} HKG nodes to {path}")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", default="medical", choices=["medical", "financial"])
    parser.add_argument("--size", type=int, default=200)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--output", default=None)
    parser.add_argument("--candidate-multiplier", type=float, default=2.0)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--d-min", type=int, default=3)
    parser.add_argument("--utility-delta", type=float, default=0.20)
    parser.add_argument("--extend-from", default=None)
    parser.add_argument("--no-llm", action="store_true")
    args = parser.parse_args()
    build_hkg(
        domain=args.domain,
        size=args.size,
        model=args.model,
        output=args.output,
        candidate_multiplier=args.candidate_multiplier,
        batch_size=args.batch_size,
        d_min=args.d_min,
        utility_delta=args.utility_delta,
        no_llm=args.no_llm,
        extend_from=args.extend_from,
    )


if __name__ == "__main__":
    main()
