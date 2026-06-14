#!/usr/bin/env bash
set -euo pipefail

: "${OPENROUTER_API_KEY:?Set OPENROUTER_API_KEY before running.}"

PYTHON_BIN="${PYTHON_BIN:-python}"
TEACHER_MODEL="${TEACHER_MODEL:-openai/gpt-4o-mini}"
STUDENT_BASE="${STUDENT_BASE:-meta-llama/Meta-Llama-3.1-8B-Instruct}"
HKG_SIZE="${HKG_SIZE:-1500}"
DETECTION_THRESHOLD="${DETECTION_THRESHOLD:-0.6}"

DOMAINS="${DOMAINS:-medical financial}"
BUDGETS="${BUDGETS:-100 200 300 500}"
MODES="${MODES:-baseline detection_only hkg_only full}"

for domain in ${DOMAINS}; do
  hkg_path="honeypot_hkg/${domain}_hkg_1500_repaired.json"
  for budget in ${BUDGETS}; do
    for mode in ${MODES}; do
      run_name="${domain}_${mode}_B${budget}"
      echo "=== ${run_name} ==="
      "${PYTHON_BIN}" trainStudent.py \
        --STUDENT_BASE="${STUDENT_BASE}" \
        --domain="${domain}" \
        --MAX_QUERIES="${budget}" \
        --Teacher_model="${TEACHER_MODEL}" \
        --defense_mode="${mode}" \
        --detection_threshold="${DETECTION_THRESHOLD}" \
        --hkg_size="${HKG_SIZE}" \
        --hkg_path="${hkg_path}" \
        --experiment_name="${run_name}"
    done
  done
done
