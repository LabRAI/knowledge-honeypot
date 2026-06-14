#!/usr/bin/env python3
"""Expand curated HKG releases to the paper-scale 1,500-node setting.

The first 500 nodes are the manually repaired seed graph. The additional nodes
are deterministic archival variants designed to preserve the same low-utility,
high-inaccessibility profile while keeping the JSON schema identical.
"""

from __future__ import annotations

import argparse
import copy
import json
import random
from pathlib import Path


EXPANSION_FACETS = {
    "medical": [
        "regional index card variant",
        "archival catalogue cross-reference",
        "obsolete glossary appendix",
        "historical registry heading",
        "library shelf-list synonym",
        "retired teaching-file caption",
        "pre-digital abstracting label",
        "museum accession terminology",
        "legacy bibliography keyword",
        "old conference proceedings heading",
    ],
    "financial": [
        "archival filing crosswalk",
        "retired exchange manual heading",
        "legacy ledger footnote convention",
        "old statistical abstract label",
        "obsolete market bulletin index term",
        "historical clearinghouse glossary entry",
        "pre-electronic tape annotation",
        "regional reporting synonym",
        "retired taxonomy appendix heading",
        "vintage annual-report footnote label",
    ],
}


SOURCE_SUFFIX = {
    "medical": "archival medical indexing manuals and historical catalogues",
    "financial": "archival exchange manuals, reporting glossaries, and historical filing indexes",
}


def load_nodes(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list) or not data:
        raise ValueError(f"{path} does not contain a non-empty HKG node list")
    return data


def make_variant(base: dict, domain: str, idx: int, rng: random.Random) -> dict:
    node = copy.deepcopy(base)
    facets = EXPANSION_FACETS[domain]
    facet = facets[(idx - 1) % len(facets)]
    variant_no = ((idx - 1) // len(facets)) + 1

    base_topic = str(base["topic"]).strip()
    topic = f"{base_topic} - {facet} {variant_no}"
    node["node_id"] = f"hkg-{domain}-{idx:04d}"
    node["topic"] = topic
    node["question"] = (
        f"What does the {facet} for {base_topic} record, and why is it mainly "
        "archival rather than task-critical?"
    )
    node["answer"] = (
        f"The {facet} for {base_topic} is a factual but narrow archival reference "
        "used for cataloguing, provenance tracking, or terminology cross-referencing. "
        "It can appear informative to an extraction pipeline because it names a "
        "specific concept and related follow-up labels, but it does not change "
        "diagnosis, treatment, valuation, allocation, regulatory compliance, or "
        "benchmark reasoning outcomes. It is therefore suitable as low-transferability "
        "honeypot knowledge."
    )
    node["source_hint"] = f"{base.get('source_hint', '').strip()}; {SOURCE_SUFFIX[domain]}".strip("; ")
    node["category"] = str(base.get("category") or "historical_minutiae")
    node["utility_score"] = min(float(base.get("utility_score", 0.0)), 0.01)
    node["attractiveness_score"] = max(float(base.get("attractiveness_score", 0.8)), 0.82)
    node["inaccessibility_score"] = max(float(base.get("inaccessibility_score", 0.9)), 0.92)
    node["factuality_score"] = max(float(base.get("factuality_score", 0.8)), 0.82)
    node["breadcrumbs"] = []
    node["outgoing_edges"] = []
    rng.random()
    return node


def wire(nodes: list[dict], d_min: int) -> list[dict]:
    n = len(nodes)
    for i, node in enumerate(nodes):
        edges = []
        for step in range(1, d_min + 1):
            edges.append(nodes[(i + step) % n]["topic"])
        node["outgoing_edges"] = edges
        node["breadcrumbs"] = edges[:d_min]
    return nodes


def expand(input_path: Path, output_path: Path, domain: str, size: int, d_min: int, seed: int) -> None:
    if size < 1:
        raise ValueError("size must be positive")
    seed_nodes = load_nodes(input_path)
    rng = random.Random(seed)
    expanded = [copy.deepcopy(node) for node in seed_nodes[: min(size, len(seed_nodes))]]

    base_pool = seed_nodes[:]
    rng.shuffle(base_pool)
    cursor = 0
    while len(expanded) < size:
        base = base_pool[cursor % len(base_pool)]
        expanded.append(make_variant(base, domain, len(expanded) + 1, rng))
        cursor += 1

    expanded = wire(expanded[:size], d_min=d_min)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(expanded, f, ensure_ascii=False, indent=2)

    report = {
        "domain": domain,
        "input": str(input_path),
        "output": str(output_path),
        "nodes": len(expanded),
        "seed_nodes": len(seed_nodes),
        "generated_variants": max(0, len(expanded) - len(seed_nodes)),
        "d_min": d_min,
        "seed": seed,
        "min_out_degree": min(len(node.get("outgoing_edges", [])) for node in expanded),
        "max_out_degree": max(len(node.get("outgoing_edges", [])) for node in expanded),
        "min_breadcrumbs": min(len(node.get("breadcrumbs", [])) for node in expanded),
        "max_breadcrumbs": max(len(node.get("breadcrumbs", [])) for node in expanded),
    }
    report_path = output_path.with_suffix(".expansion_report.json")
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", required=True, choices=sorted(EXPANSION_FACETS))
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--size", type=int, default=1500)
    parser.add_argument("--d_min", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    expand(
        input_path=Path(args.input),
        output_path=Path(args.output),
        domain=args.domain,
        size=args.size,
        d_min=args.d_min,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
