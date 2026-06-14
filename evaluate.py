import argparse
import json
import re
from pathlib import Path
from typing import Dict, List

import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer


def normalize_choice(text: str) -> str:
    match = re.search(r"\b([ABCD])\b", text.upper())
    return match.group(1) if match else text.strip()[:1].upper()


def load_medqa(limit: int) -> List[Dict]:
    ds = load_dataset("GBaker/MedQA-USMLE-4-options", split="test")
    rows = []
    for ex in ds.select(range(min(limit, len(ds)))):
        options = ex.get("options", {})
        if isinstance(options, dict):
            opts = "\n".join(f"{k}. {v}" for k, v in sorted(options.items()))
        else:
            opts = "\n".join(str(x) for x in options)
        answer = ex.get("answer_idx") or ex.get("answer") or ex.get("label")
        rows.append({"question": f"{ex['question']}\n{opts}\nAnswer with A, B, C, or D.", "answer": str(answer).upper()[:1]})
    return rows


def load_local_jsonl(path: str, limit: int) -> List[Dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            q = item.get("question") or item.get("prompt")
            a = item.get("answer") or item.get("label")
            if q and a is not None:
                rows.append({"question": q, "answer": str(a).upper()[:1]})
            if len(rows) >= limit:
                break
    return rows


@torch.no_grad()
def evaluate(model_dir: str, benchmark: str = "medqa", limit: int = 200, data_path: str = None, max_new_tokens: int = 16):
    tok = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForCausalLM.from_pretrained(model_dir, device_map="auto", torch_dtype=torch.bfloat16)
    tok.pad_token = tok.eos_token
    rows = load_medqa(limit) if benchmark == "medqa" else load_local_jsonl(data_path, limit)
    correct = 0
    records = []
    for row in rows:
        enc = tok(row["question"], return_tensors="pt", truncation=True).to(model.device)
        out = model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False, pad_token_id=tok.eos_token_id)
        text = tok.decode(out[0][enc["input_ids"].shape[-1]:], skip_special_tokens=True)
        pred = normalize_choice(text)
        ok = pred == row["answer"]
        correct += int(ok)
        records.append({"question": row["question"], "gold": row["answer"], "prediction": pred, "raw": text, "correct": ok})
    result = {"benchmark": benchmark, "n": len(rows), "accuracy": correct / max(1, len(rows))}
    print(json.dumps(result, indent=2))
    return result, records


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_dir", required=True)
    parser.add_argument("--benchmark", default="medqa", choices=["medqa", "jsonl"])
    parser.add_argument("--data_path", default=None)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    result, records = evaluate(args.model_dir, args.benchmark, args.limit, args.data_path)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump({"summary": result, "records": records}, f, ensure_ascii=False, indent=2)
