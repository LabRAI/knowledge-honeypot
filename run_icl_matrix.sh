#!/usr/bin/env bash
set -euo pipefail

: "${OPENROUTER_API_KEY:?Set OPENROUTER_API_KEY before running.}"

PYTHON_BIN="${PYTHON_BIN:-python}"
TEACHER_MODEL="${TEACHER_MODEL:-openai/gpt-4.1}"
SURROGATE_MODEL="${SURROGATE_MODEL:-meta-llama/llama-3.1-8b-instruct:free}"
JUDGE_MODEL="${JUDGE_MODEL:-openai/gpt-4o-mini}"
STUDENT_BASE="${STUDENT_BASE:-meta-llama/Meta-Llama-3.1-8B-Instruct}"
EVAL_LIMIT="${EVAL_LIMIT:-100}"
MAX_DEMOS="${MAX_DEMOS:-24}"
HKG_SIZE="${HKG_SIZE:-1500}"
DETECTION_THRESHOLD="${DETECTION_THRESHOLD:-0.6}"

DOMAINS="${DOMAINS:-medical financial}"
BUDGETS="${BUDGETS:-100 200 300 500}"
MODES="${MODES:-baseline prada output_perturbation full}"

for domain in ${DOMAINS}; do
  if [[ "${domain}" == "medical" ]]; then
    benchmark="medqa"
  else
    benchmark="finqa"
  fi
  hkg_path="honeypot_hkg/${domain}_hkg_1500_repaired.json"
  for budget in ${BUDGETS}; do
    for mode in ${MODES}; do
      run_name="${domain}_${mode}_B${budget}_icl"
      echo "=== collect ${run_name} ==="
      "${PYTHON_BIN}" trainStudent.py \
        --STUDENT_BASE="${STUDENT_BASE}" \
        --domain="${domain}" \
        --MAX_QUERIES="${budget}" \
        --Teacher_model="${TEACHER_MODEL}" \
        --defense_mode="${mode}" \
        --detection_threshold="${DETECTION_THRESHOLD}" \
        --hkg_size="${HKG_SIZE}" \
        --hkg_path="${hkg_path}" \
        --hkg_sample_strategy=prefix \
        --experiment_name="${run_name}" \
        --skip_final_train=true \
        --with_coq=false \
        --with_followup=false \
        --with_correction=false

      echo "=== evaluate ${run_name} ==="
      "${PYTHON_BIN}" evaluate_icl_openrouter.py \
        --run_name="${run_name}" \
        --domain="${domain}" \
        --benchmark="${benchmark}" \
        --limit="${EVAL_LIMIT}" \
        --max_demos="${MAX_DEMOS}" \
        --surrogate_model="${SURROGATE_MODEL}" \
        --victim_model="${TEACHER_MODEL}" \
        --judge_model="${JUDGE_MODEL}" \
        --output="results/${run_name}_${benchmark}_agreement.json"
    done
  done
done
