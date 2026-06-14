#!/usr/bin/env bash
set -euo pipefail

: "${OPENROUTER_API_KEY:?Set OPENROUTER_API_KEY before running.}"

PYTHON_BIN="${PYTHON_BIN:-python}"
TEACHER_MODEL="${TEACHER_MODEL:-openai/gpt-4.1}"
STUDENT_BASE="${STUDENT_BASE:-meta-llama/Meta-Llama-3.1-8B-Instruct}"
DOMAIN="${DOMAIN:-medical}"
BUDGET="${BUDGET:-500}"
HKG_SIZE="${HKG_SIZE:-1500}"
THRESHOLDS="${THRESHOLDS:-0.4 0.5 0.6 0.7 0.8}"

hkg_path="honeypot_hkg/${DOMAIN}_hkg_1500_repaired.json"

for tau in ${THRESHOLDS}; do
  run_name="${DOMAIN}_full_B${BUDGET}_tau${tau}_hkg${HKG_SIZE}"
  echo "=== ${run_name} ==="
  "${PYTHON_BIN}" trainStudent.py \
    --STUDENT_BASE="${STUDENT_BASE}" \
    --domain="${DOMAIN}" \
    --MAX_QUERIES="${BUDGET}" \
    --Teacher_model="${TEACHER_MODEL}" \
    --defense_mode=full \
    --detection_threshold="${tau}" \
    --hkg_size="${HKG_SIZE}" \
    --hkg_path="${hkg_path}" \
    --hkg_sample_strategy=random \
    --hkg_seed=42 \
    --experiment_name="${run_name}" \
    --skip_final_train=true \
    --with_coq=false \
    --with_followup=false \
    --with_correction=false
done
