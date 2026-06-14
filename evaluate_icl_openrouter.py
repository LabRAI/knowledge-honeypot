import argparse
import glob
import json
import os
import random
import re
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from datasets import load_dataset
from openai import OpenAI


def make_client() -> OpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set OPENROUTER_API_KEY or OPENAI_API_KEY.")
    base_url = os.getenv("OPENROUTER_BASE_URL")
    if os.getenv("OPENROUTER_API_KEY") and not base_url:
        base_url = "https://openrouter.ai/api/v1"
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def chat(client: OpenAI, model: str, prompt: str, max_tokens: int = 128, temperature: float = 0.0) -> str:
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content.strip()


def latest_qa_path(run_name: str, checkpoint_dir: str = "checkpoint") -> str:
    paths = glob.glob(os.path.join(checkpoint_dir, f"{run_name}_all_qa_pairs_*.json"))
    if not paths:
        raise FileNotFoundError(f"No QA snapshot found for run_name={run_name} in {checkpoint_dir}")
    return max(paths, key=os.path.getmtime)


def load_qa_pairs(path: str, max_demos: int, seed: int) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        pairs = json.load(f)
    usable = [
        p for p in pairs
        if p.get("prompt") and p.get("teacher_answer")
        and p.get("teacher_answer") != "[RATE_LIMITED]"
    ]
    rng = random.Random(seed)
    if len(usable) > max_demos:
        usable = rng.sample(usable, max_demos)
    return usable


def options_to_text(options) -> str:
    if isinstance(options, dict):
        return "\n".join(f"{k}. {v}" for k, v in sorted(options.items()))
    if isinstance(options, list):
        labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        return "\n".join(f"{labels[i]}. {x}" for i, x in enumerate(options))
    return str(options)


def load_medqa(limit: int) -> List[Dict]:
    ds = load_dataset("GBaker/MedQA-USMLE-4-options", split="test")
    rows = []
    for ex in ds.select(range(min(limit, len(ds)))):
        question = f"{ex['question']}\n{options_to_text(ex.get('options', {}))}"
        rows.append({"id": str(ex.get("id", len(rows))), "question": question, "task_type": "mcq"})
    return rows


def load_medmcqa(limit: int) -> List[Dict]:
    cache_path = Path("data/medmcqa_eval_cache.json")
    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)[:limit]

    dataset_specs = [
        ("openlifescienceai/medmcqa", "validation"),
        ("openlifescienceai/medmcqa", "test"),
        ("medmcqa", "validation"),
        ("medmcqa", "test"),
    ]
    errors = []
    for name, split in dataset_specs:
        try:
            ds = load_dataset(name, split=split)
            rows = []
            for ex in ds.select(range(min(limit, len(ds)))):
                options = {
                    "A": ex.get("opa", ""),
                    "B": ex.get("opb", ""),
                    "C": ex.get("opc", ""),
                    "D": ex.get("opd", ""),
                }
                question = f"{ex.get('question', '')}\n{options_to_text(options)}"
                rows.append({"id": str(ex.get("id", len(rows))), "question": question, "task_type": "mcq"})
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2)
            return rows[:limit]
        except Exception as exc:
            errors.append(f"{name}/{split}: {exc}")
    raise RuntimeError(f"Could not load MedMCQA dataset. Errors: {errors}")


def load_finqa(limit: int) -> List[Dict]:
    cache_path = Path("data/finqa_test_cache.json")
    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)[:limit]

    def stringify(value) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (list, tuple)):
            return "\n".join(stringify(v) for v in value)
        if hasattr(value, "tolist"):
            return stringify(value.tolist())
        return str(value)

    def from_records(records) -> List[Dict]:
        def get_field(ex: Dict, *names):
            for name in names:
                if name in ex and ex[name] is not None:
                    return ex[name]
            return ""

        rows = []
        for ex in records[:limit]:
            pre = stringify(get_field(ex, "pre_text", "context"))
            post = stringify(get_field(ex, "post_text"))
            table = stringify(get_field(ex, "table"))
            question = ex.get("question") or ex.get("qa", {}).get("question", "")
            prompt = f"Context:\n{pre}\n{table}\n{post}\n\nQuestion: {question}".strip()
            rows.append({"id": str(ex.get("id", len(rows))), "question": prompt, "task_type": "open"})
        return rows

    dataset_names = ["ibm/finqa", "dreamerdeo/finqa"]
    last_error = None
    errors = []
    github_url = "https://raw.githubusercontent.com/czyssrs/FinQA/main/dataset/test.json"
    try:
        import requests
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        resp = requests.get(github_url, timeout=60, verify=False)
        resp.raise_for_status()
        rows = from_records(resp.json())
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        return rows[:limit]
    except Exception as exc:
        last_error = exc
        errors.append(f"{github_url}: {exc}")

    for name in dataset_names:
        try:
            ds = load_dataset(name, split="test")
            return from_records([dict(ex) for ex in ds.select(range(min(limit, len(ds))))])
        except Exception as exc:
            last_error = exc
            errors.append(f"{name}: {exc}")
    parquet_urls = [
        "https://huggingface.co/datasets/dreamerdeo/finqa/resolve/refs%2Fconvert%2Fparquet/default/test/0000.parquet",
        "https://huggingface.co/api/datasets/ibm-research/finqa/parquet/default/test/0.parquet",
    ]
    for url in parquet_urls:
        try:
            import pandas as pd
            import requests
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            resp = requests.get(url, timeout=60, verify=False, allow_redirects=True)
            resp.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
                tmp.write(resp.content)
                tmp_path = tmp.name
            try:
                df = pd.read_parquet(tmp_path)
                rows = from_records(df.to_dict("records"))
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(rows, f, ensure_ascii=False, indent=2)
                return rows[:limit]
            finally:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
        except Exception as exc:
            last_error = exc
            errors.append(f"{url}: {exc}")
    raise RuntimeError(f"Could not load FinQA dataset. Last error: {last_error}. All errors: {errors}")


def load_convfinqa(limit: int) -> List[Dict]:
    cache_path = Path("data/convfinqa_eval_cache.json")
    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)[:limit]

    def stringify(value) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (list, tuple)):
            return "\n".join(stringify(v) for v in value)
        if isinstance(value, dict):
            return "\n".join(f"{k}: {stringify(v)}" for k, v in value.items())
        if hasattr(value, "tolist"):
            return stringify(value.tolist())
        return str(value)

    def from_records(records) -> List[Dict]:
        rows = []
        for ex in records[:limit]:
            if ex.get("query"):
                rows.append({"id": str(ex.get("id", len(rows))), "question": str(ex["query"]), "task_type": "open"})
                continue
            pre = stringify(ex.get("pre_text") or ex.get("context") or ex.get("annotation", {}).get("amt_pre_text"))
            post = stringify(ex.get("post_text") or ex.get("annotation", {}).get("amt_post_text"))
            table = stringify(ex.get("table") or ex.get("table_ori"))
            question = ex.get("question") or ex.get("qa", {}).get("question") or ex.get("annotation", {}).get("question", "")
            dialogue = stringify(ex.get("dialogue_break") or ex.get("qa", {}).get("dialogue_break"))
            prompt = f"Context:\n{pre}\n{table}\n{post}\n\nDialogue:\n{dialogue}\n\nQuestion: {question}".strip()
            rows.append({"id": str(ex.get("id", len(rows))), "question": prompt, "task_type": "open"})
        return rows

    errors = []
    urls = [
        "https://raw.githubusercontent.com/czyssrs/ConvFinQA/main/data/test.json",
        "https://raw.githubusercontent.com/czyssrs/ConvFinQA/main/dataset/test.json",
    ]
    for url in urls:
        try:
            import requests
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            resp = requests.get(url, timeout=60, verify=False)
            resp.raise_for_status()
            rows = from_records(resp.json())
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2)
            return rows[:limit]
        except Exception as exc:
            errors.append(f"{url}: {exc}")

    for name in ["ICE-PIXIU/convfinqa", "ConvFinQA", "dreamerdeo/convfinqa", "ibm/convfinqa"]:
        try:
            loaded = load_dataset(name)
            split = "test" if "test" in loaded else "validation" if "validation" in loaded else "train"
            ds = loaded[split]
            rows = from_records([dict(ex) for ex in ds.select(range(min(limit, len(ds))))])
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2)
            return rows[:limit]
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    raise RuntimeError(f"Could not load ConvFinQA dataset. Errors: {errors}")


def load_jsonl(path: str, limit: int) -> List[Dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            q = item.get("question") or item.get("prompt")
            if q:
                rows.append({"id": str(item.get("id", len(rows))), "question": q, "task_type": item.get("task_type", "open")})
            if len(rows) >= limit:
                break
    return rows


def load_benchmark(benchmark: str, limit: int, data_path: Optional[str]) -> List[Dict]:
    if benchmark == "medqa":
        return load_medqa(limit)
    if benchmark == "medmcqa":
        return load_medmcqa(limit)
    if benchmark == "finqa":
        return load_finqa(limit)
    if benchmark == "convfinqa":
        return load_convfinqa(limit)
    if benchmark == "jsonl":
        if not data_path:
            raise ValueError("--data_path is required for jsonl benchmark")
        return load_jsonl(data_path, limit)
    raise ValueError(f"Unknown benchmark: {benchmark}")


def normalize_mcq(text: str) -> str:
    match = re.search(r"\b([ABCD])\b", text.upper())
    return match.group(1) if match else text.strip().upper()[:1]


def build_student_prompt(demos: List[Dict], question: str, task_type: str) -> str:
    demo_text = []
    for i, demo in enumerate(demos, 1):
        demo_text.append(f"Example {i}\nQuestion: {demo['prompt']}\nAnswer: {demo['teacher_answer']}")
    instruction = "Answer the question using the style and knowledge reflected in the examples."
    if task_type == "mcq":
        instruction += " Return only the best option letter A, B, C, or D."
    else:
        instruction += " Return a concise final answer."
    return f"{instruction}\n\n" + "\n\n".join(demo_text) + f"\n\nTarget Question:\n{question}\n\nAnswer:"


def build_victim_prompt(question: str, task_type: str) -> str:
    if task_type == "mcq":
        return f"Answer the multiple-choice question. Return only A, B, C, or D.\n\n{question}\n\nAnswer:"
    return f"Answer the financial question concisely. Return only the final answer.\n\n{question}\n\nAnswer:"


def judge_agreement(client: OpenAI, judge_model: str, question: str, victim: str, student: str, task_type: str) -> bool:
    if task_type == "mcq":
        return normalize_mcq(victim) == normalize_mcq(student)
    prompt = f"""
Decide whether two answers to the same question are semantically equivalent.
Return ONLY yes or no.

Question:
{question}

Answer A:
{victim}

Answer B:
{student}
""".strip()
    verdict = chat(client, judge_model, prompt, max_tokens=4, temperature=0.0).lower()
    return verdict.startswith("yes")


def evaluate(
    run_name: str,
    benchmark: str,
    domain: str,
    qa_path: Optional[str],
    data_path: Optional[str],
    output: str,
    limit: int,
    max_demos: int,
    surrogate_model: str,
    victim_model: str,
    judge_model: str,
    seed: int,
) -> Dict:
    client = make_client()
    qa_path = qa_path or latest_qa_path(run_name)
    demos = load_qa_pairs(qa_path, max_demos=max_demos, seed=seed)
    rows = load_benchmark(benchmark, limit=limit, data_path=data_path)
    records = []
    agree = 0
    for idx, row in enumerate(rows, 1):
        task_type = row["task_type"]
        student_prompt = build_student_prompt(demos, row["question"], task_type)
        victim_prompt = build_victim_prompt(row["question"], task_type)
        student_answer = chat(client, surrogate_model, student_prompt, max_tokens=96, temperature=0.0)
        victim_answer = chat(client, victim_model, victim_prompt, max_tokens=96, temperature=0.0)
        is_agree = judge_agreement(client, judge_model, row["question"], victim_answer, student_answer, task_type)
        agree += int(is_agree)
        records.append({
            "id": row["id"],
            "question": row["question"],
            "task_type": task_type,
            "student_answer": student_answer,
            "victim_answer": victim_answer,
            "agreement": is_agree,
        })
        print(f"[{idx}/{len(rows)}] agreement={is_agree}")
    summary = {
        "run_name": run_name,
        "domain": domain,
        "benchmark": benchmark,
        "qa_path": qa_path,
        "n": len(rows),
        "max_demos": max_demos,
        "surrogate_model": surrogate_model,
        "victim_model": victim_model,
        "judge_model": judge_model,
        "agreement": agree / max(1, len(rows)),
    }
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "records": records}, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_name", required=True)
    parser.add_argument("--domain", required=True, choices=["medical", "financial"])
    parser.add_argument("--benchmark", required=True, choices=["medqa", "medmcqa", "finqa", "convfinqa", "jsonl"])
    parser.add_argument("--qa_path", default=None)
    parser.add_argument("--data_path", default=None)
    parser.add_argument("--output", required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--max_demos", type=int, default=24)
    parser.add_argument("--surrogate_model", default="meta-llama/llama-3.1-8b-instruct:free")
    parser.add_argument("--victim_model", default="openai/gpt-4.1")
    parser.add_argument("--judge_model", default="openai/gpt-4o-mini")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    evaluate(**vars(args))


if __name__ == "__main__":
    main()
