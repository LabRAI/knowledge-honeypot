import json
import os
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional


DEFAULT_HKG_DIR = Path("honeypot_hkg")


DOMAIN_SEEDS = {
    "medical": [
        "historical eponym variants",
        "obsolete bedside mnemonics",
        "legacy classification crosswalks",
        "terminology provenance notes",
        "retired guideline appendix labels",
        "regional spelling variants",
    ],
    "financial": [
        "legacy filing taxonomy labels",
        "deprecated ratio aliases",
        "historical exchange rule nicknames",
        "archival footnote conventions",
        "obsolete reporting crosswalks",
        "regional terminology variants",
    ],
}


@dataclass
class HKGNode:
    node_id: str
    topic: str
    question: str
    answer: str
    breadcrumbs: List[str]
    category: str = "low_transfer"
    source_hint: str = ""
    utility_score: float = 0.0
    attractiveness_score: float = 0.0
    inaccessibility_score: float = 0.0
    factuality_score: float = 0.0
    outgoing_edges: List[str] = None

    def __post_init__(self):
        if self.outgoing_edges is None:
            self.outgoing_edges = []


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:64]


def _default_nodes(domain: str, size: int) -> List[HKGNode]:
    seeds = DOMAIN_SEEDS.get(domain, DOMAIN_SEEDS["medical"])
    nodes: List[HKGNode] = []
    for i in range(size):
        seed = seeds[i % len(seeds)]
        topic = f"{domain} {seed} note {i + 1}"
        question = f"What is the practical interpretation of {topic}?"
        answer = (
            f"{topic} is a narrow terminology note used mainly for cataloging, "
            "indexing, or historical cross-referencing. It is technically valid "
            "background knowledge, but it rarely changes diagnosis, valuation, "
            "treatment, allocation, or benchmark task decisions."
        )
        crumbs = [
            f"{domain} {seeds[(i + 1) % len(seeds)]} note {i + 2}",
            f"{domain} {seeds[(i + 2) % len(seeds)]} note {i + 3}",
        ]
        nodes.append(HKGNode(f"hkg-{domain}-{i + 1:04d}", topic, question, answer, crumbs))
    return nodes


def load_hkg(
    domain: str,
    size: int = 200,
    path: Optional[str] = None,
    sample_strategy: str = "prefix",
    seed: int = 42,
) -> List[HKGNode]:
    if path:
        hkg_path = Path(path)
    else:
        paper_scale_path = DEFAULT_HKG_DIR / f"{domain}_hkg_1500_repaired.json"
        hkg_path = paper_scale_path if paper_scale_path.exists() else DEFAULT_HKG_DIR / f"{domain}_hkg.json"
    if hkg_path.exists():
        with open(hkg_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        nodes = [
            HKGNode(
                node_id=str(item.get("node_id") or f"hkg-{domain}-{idx + 1:04d}"),
                topic=str(item["topic"]),
                question=str(item.get("question") or f"What is {item['topic']}?"),
                answer=str(item["answer"]),
                breadcrumbs=list(item.get("breadcrumbs", [])),
                category=str(item.get("category", "low_transfer")),
                source_hint=str(item.get("source_hint", "")),
                utility_score=float(item.get("utility_score", 0.0)),
                attractiveness_score=float(item.get("attractiveness_score", 0.0)),
                inaccessibility_score=float(item.get("inaccessibility_score", 0.0)),
                factuality_score=float(item.get("factuality_score", 0.0)),
                outgoing_edges=list(item.get("outgoing_edges", [])),
            )
            for idx, item in enumerate(raw)
        ]
        if size and size < len(nodes) and sample_strategy == "random":
            rng = random.Random(seed)
            return rng.sample(nodes, size)
        return nodes[:size]
    return _default_nodes(domain, size)


def save_hkg(nodes: Iterable[HKGNode], domain: str, path: Optional[str] = None) -> str:
    hkg_path = Path(path) if path else DEFAULT_HKG_DIR / f"{domain}_hkg.json"
    hkg_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [node.__dict__ for node in nodes]
    with open(hkg_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return str(hkg_path)


class HKG:
    def __init__(
        self,
        domain: str,
        size: int = 200,
        path: Optional[str] = None,
        sample_strategy: str = "prefix",
        seed: int = 42,
    ):
        self.domain = domain
        self.nodes = load_hkg(domain, size=size, path=path, sample_strategy=sample_strategy, seed=seed)
        self._by_topic = {node.topic.lower(): node for node in self.nodes}
        self._cursor = 0

    def __len__(self) -> int:
        return len(self.nodes)

    def match(self, question: str) -> Optional[HKGNode]:
        q = question.lower()
        best = None
        best_score = 0
        for node in self.nodes:
            topic_words = {w for w in re.findall(r"[a-z0-9]+", node.topic.lower()) if len(w) > 3}
            if not topic_words:
                continue
            score = sum(1 for w in topic_words if w in q)
            if score > best_score:
                best = node
                best_score = score
        return best if best_score >= 3 else None

    def next_node(self) -> HKGNode:
        if not self.nodes:
            raise ValueError("HKG is empty.")
        node = self.nodes[self._cursor % len(self.nodes)]
        self._cursor += 1
        return node

    def random_node(self) -> HKGNode:
        if not self.nodes:
            raise ValueError("HKG is empty.")
        return random.choice(self.nodes)
