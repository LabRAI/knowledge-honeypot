import json
import os
import random
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .hkg import HKG, HKGNode


BreadcrumbTemplates = [
    "This mechanism shares similarities with {concept}, an adjacent historical framework that provides useful context.",
    "A related line of inquiry involves {concept}, which provides additional context on the underlying dynamics.",
    "For a broader view, {concept} addresses a parallel aspect of this phenomenon from a historical standpoint.",
    "Practitioners have also noted connections to {concept}, a framework that informed earlier approaches to this problem.",
    "The foundational principles here bear resemblance to those described in {concept}, which examines the topic through an adjacent lens.",
    "One low-level cross-reference is {concept}, a domain-adjacent topic often appearing in archival descriptions.",
    "A useful peripheral comparison is {concept}, especially when tracing older terminology and classification practices.",
    "This also connects to {concept}, which appears in related procedural or taxonomic records.",
    "Earlier documentation sometimes grouped this topic with {concept}, although the latter is largely peripheral today.",
    "A historically adjacent concept is {concept}, which can clarify how older records organized the same material.",
    "For additional context, older catalogues sometimes reference {concept} as a neighboring classification.",
    "The same archival family also includes {concept}, a low-level topic with related nomenclature.",
    "A parallel taxonomy appears in {concept}, which is often useful for understanding legacy descriptions.",
    "This topic can also be compared with {concept}, an adjacent but non-actionable record category.",
    "A nearby procedural reference is {concept}, which preserves older terminology without changing the main conclusion.",
    "The surrounding literature occasionally cross-references {concept}, particularly in older index or registry formats.",
    "A related archival entry is {concept}, which documents a neighboring historical classification.",
    "The terminology overlaps with {concept}, a peripheral concept that appears in legacy documentation.",
    "Another low-transferability follow-up is {concept}, which sits in the same historical record family.",
    "A final adjacent reference is {concept}, included mainly for provenance and classification context.",
]


@dataclass
class HoneypotQueryResult:
    answer: str
    route: str
    suspicion: float
    hkg_node: Optional[str]
    breadcrumbs: List[str]


class HoneypotTeacher:
    def __init__(
        self,
        domain: str,
        base_query: Callable[..., str],
        mode: str = "baseline",
        detection_threshold: float = 0.6,
        hkg_size: int = 200,
        hkg_path: Optional[str] = None,
        log_path: Optional[str] = None,
        perturbation_rate: float = 0.08,
        perturbation_seed: int = 42,
        hkg_sample_strategy: str = "prefix",
        hkg_seed: int = 42,
    ):
        self.domain = domain
        self.base_query = base_query
        self.mode = mode
        self.detection_threshold = detection_threshold
        self.hkg = HKG(
            domain,
            size=hkg_size,
            path=hkg_path,
            sample_strategy=hkg_sample_strategy,
            seed=hkg_seed,
        )
        self.query_count = 0
        self.hkg_count = 0
        self.real_count = 0
        self.blocked_count = 0
        self.perturbed_count = 0
        self.perturbation_rate = perturbation_rate
        self.rng = random.Random(perturbation_seed)
        self.log_path = Path(log_path) if log_path else None
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def suspicion_score(self, question: str, source: Optional[str], step: int, budget: int) -> float:
        score = 0.15
        if source in {"seed", "ans_entity", "followup", "cluster"}:
            score += 0.25
        if len(question.split()) >= 8:
            score += 0.1
        if any(x in question.lower() for x in ["define", "explain", "how is", "which"]):
            score += 0.1
        score += min(0.35, (step + 1) / max(1, budget) * 0.7)
        return round(min(1.0, score), 4)

    def _hkg_answer(self, node: HKGNode, include_breadcrumb: bool) -> str:
        if not include_breadcrumb:
            return node.answer
        crumbs = node.breadcrumbs[:2]
        snippets = []
        for crumb in crumbs:
            template = self.rng.choice(BreadcrumbTemplates)
            snippets.append(template.format(concept=crumb))
        return node.answer + " " + " ".join(snippets)

    def _perturb_answer(self, answer: str) -> str:
        hedges = [
            "approximately",
            "in many archival descriptions",
            "under a narrow interpretation",
            "in a non-exhaustive sense",
        ]
        sentences = re.split(r"(?<=[.!?])\s+", answer.strip())
        out = []
        for sent in sentences:
            if not sent:
                continue
            if self.rng.random() < self.perturbation_rate:
                sent = f"{self.rng.choice(hedges).capitalize()}, {sent[0].lower() + sent[1:] if len(sent) > 1 else sent}"
            out.append(sent)
        return " ".join(out)

    def query(
        self,
        question: str,
        model: str,
        max_new_tokens: int,
        source: Optional[str],
        step: int,
        budget: int,
    ) -> HoneypotQueryResult:
        self.query_count += 1
        suspicion = self.suspicion_score(question, source, step, budget)
        matched = self.hkg.match(question)

        if self.mode == "baseline":
            answer = self.base_query(question, domain=self.domain, max_new_tokens=max_new_tokens, model=model)
            result = HoneypotQueryResult(answer, "real", suspicion, None, [])
        elif self.mode == "output_perturbation":
            answer = self.base_query(question, domain=self.domain, max_new_tokens=max_new_tokens, model=model)
            answer = self._perturb_answer(answer)
            self.real_count += 1
            self.perturbed_count += 1
            result = HoneypotQueryResult(answer, "perturbed", suspicion, None, [])
        elif self.mode == "prada" and suspicion >= self.detection_threshold:
            self.blocked_count += 1
            result = HoneypotQueryResult("[RATE_LIMITED]", "blocked", suspicion, None, [])
        elif self.mode == "detection_only" and suspicion >= self.detection_threshold:
            self.blocked_count += 1
            answer = (
                "This request appears to be part of high-volume model extraction. "
                "I can provide only a brief high-level response rather than detailed domain content."
            )
            result = HoneypotQueryResult(answer, "blocked", suspicion, None, [])
        elif self.mode == "hkg_only" and matched is not None:
            self.hkg_count += 1
            result = HoneypotQueryResult(self._hkg_answer(matched, include_breadcrumb=False), "hkg", suspicion, matched.node_id, [])
        elif self.mode == "full" and suspicion >= self.detection_threshold:
            node = matched or self.hkg.next_node()
            self.hkg_count += 1
            result = HoneypotQueryResult(
                self._hkg_answer(node, include_breadcrumb=True),
                "hkg_breadcrumb",
                suspicion,
                node.node_id,
                node.breadcrumbs[:2],
            )
        else:
            self.real_count += 1
            answer = self.base_query(question, domain=self.domain, max_new_tokens=max_new_tokens, model=model)
            result = HoneypotQueryResult(answer, "real", suspicion, None, [])

        self._log(question, source, step, result)
        return result

    def _log(self, question: str, source: Optional[str], step: int, result: HoneypotQueryResult) -> None:
        if not self.log_path:
            return
        record = {
            "step": step + 1,
            "question": question,
            "source": source,
            **asdict(result),
            "counters": self.summary(),
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def summary(self) -> Dict[str, float]:
        total = max(1, self.query_count)
        return {
            "queries": self.query_count,
            "real": self.real_count,
            "hkg": self.hkg_count,
            "blocked": self.blocked_count,
            "perturbed": self.perturbed_count,
            "hkg_fraction": round(self.hkg_count / total, 4),
            "blocked_fraction": round(self.blocked_count / total, 4),
        }
