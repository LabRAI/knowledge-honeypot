# Code Manifest: Paper Alignment

This manifest maps the current paper draft, including appendix material, to the
code and artifacts in this repository.

## Main Paper

| Paper section | Claim / component | Repository support |
|---|---|---|
| Problem formulation | Attacker performs budget-constrained black-box extraction through query-response collection | [`trainStudent.py`](./trainStudent.py), `select_next`, `run_qa`, checkpointed QA snapshots |
| Knowledge taxonomy | Task-critical vs. low-transferability knowledge | Implemented through HKG candidate scoring in [`honeypot/build_hkg.py`](./honeypot/build_hkg.py) and repair filters in [`honeypot/repair_hkg.py`](./honeypot/repair_hkg.py) |
| HKG construction | Factual, attractive, low-transfer, user-inaccessible nodes | [`honeypot/build_hkg.py`](./honeypot/build_hkg.py), bundled HKGs in [`honeypot_hkg/`](./honeypot_hkg), audit summary in [`HKG_AUDIT_SUMMARY.md`](./HKG_AUDIT_SUMMARY.md) |
| HKG graph structure | Directed internal graph with minimum out-degree | [`honeypot/hkg.py`](./honeypot/hkg.py), `HKGNode`, `HKG.next_node`, repaired HKG JSON files |
| Detection and luring | Suspicion score and breadcrumb-triggered redirection | [`honeypot/honeypot_teacher.py`](./honeypot/honeypot_teacher.py), `HoneypotTeacher.suspicion_score`, `BreadcrumbTemplates` |
| Algorithm 1 | Full API wrapper pipeline | [`trainStudent.py`](./trainStudent.py) calls `HoneypotTeacher.query` through `run_qa` |
| RQ1 main results | Agreement under No Defense, perturbation, PRADA, and KnowledgeTrap | [`run_icl_matrix.sh`](./run_icl_matrix.sh), [`evaluate_icl_openrouter.py`](./evaluate_icl_openrouter.py), generated JSON files under `results/` |
| RQ2 ablation | HKG-only and detection-only variants | `--defense_mode=hkg_only`, `--defense_mode=detection_only`, `--defense_mode=full` in [`trainStudent.py`](./trainStudent.py) |
| RQ3 budget allocation | HKG vs. real-domain query fraction after luring | `*_honeypot_budget.jsonl`, `*_honeypot_summary.json`, [`scripts/make_paper_figures.py`](./scripts/make_paper_figures.py) |
| RQ4 threshold sensitivity | Vary detection threshold `tau` | [`run_sensitivity_threshold.sh`](./run_sensitivity_threshold.sh) |
| RQ4 HKG size sensitivity | Vary `|V_H|` | [`run_sensitivity_hkg_size.sh`](./run_sensitivity_hkg_size.sh), `--hkg_size` |
| RQ5 adaptive attacker | Domain relevance filtering under `theta` | [`adaptive_filter_analysis.py`](./adaptive_filter_analysis.py) |
| Figures | Overview, agreement curves, budget allocation, HKG size | [`scripts/overview_figure.py`](./scripts/overview_figure.py), [`scripts/make_paper_figures.py`](./scripts/make_paper_figures.py), generated figure assets under `figures/` |

## Appendix Alignment

| Appendix item | Repository support | Notes |
|---|---|---|
| Appendix A: theoretical user harmlessness and budget waste | Paper-only proof | No executable code is required; empirical budget logs are produced by `HoneypotTeacher.summary` and `*_honeypot_budget.jsonl`. |
| Appendix B: judge model ablation | [`evaluate_icl_openrouter.py`](./evaluate_icl_openrouter.py) | Use `--judge_model` to swap judges; outputs are written as agreement JSON. |
| Appendix C: probe model / transferability filter | [`honeypot/build_hkg.py`](./honeypot/build_hkg.py), [`honeypot/repair_hkg.py`](./honeypot/repair_hkg.py) | The release includes a low-cost heuristic+LLM scoring path. Paper-scale GPU probe filtering can be plugged in at `judge_and_filter`. |
| Appendix C.2: threshold ablation for `delta` | [`honeypot/build_hkg.py`](./honeypot/build_hkg.py) | Use `--utility_delta` when building HKG candidates. |
| Appendix D: HKG construction cost | Build logs + repair reports | Reproduce by running `build_hkg.py` with target `--size`; API cost depends on chosen generation model. |
| Appendix E: breadcrumb template diversity | [`honeypot/honeypot_teacher.py`](./honeypot/honeypot_teacher.py) | `BreadcrumbTemplates` contains the 20 runtime paraphrase templates. |
| Appendix F: Additional domain HKG details | Same HKG schema and builder/repair API | The bundled release provides paper-scale Medical and Financial HKGs; additional domains use the same JSON schema and runtime wrapper. |
| Appendix G: related work | Paper-only text | No code requirement. |

## Artifact Inventory

| Directory / file | Role |
|---|---|
| [`honeypot_hkg/medical_hkg_1500_repaired.json`](./honeypot_hkg/medical_hkg_1500_repaired.json) | Paper-scale Medical HKG |
| [`honeypot_hkg/financial_hkg_1500_repaired.json`](./honeypot_hkg/financial_hkg_1500_repaired.json) | Paper-scale Financial HKG |
| [`figures/overview_figure.png`](./figures/overview_figure.png) | README overview image |

## Generated Artifacts Not Included In The Upload Release

| Directory | Role |
|---|---|
| `results/` | Agreement metrics, structured logs, budget allocation logs |
| `checkpoint/` | Query-response snapshots and resumable experiment states |
| `TeacherAns/` | Cached victim responses |
| `EQCache/`, `EntityQA/` | Cached entity/question/PPL helpers |
| `logs/`, `__pycache__/` | Runtime logs and Python bytecode |
| `paper/paper_text_extracted.txt` | Local alignment scratch file extracted from the draft PDF |

## Known Scope Notes

- The bundled code is aligned with the Medical and Financial experiments currently
  present in the repository.
- The bundled Medical and Financial HKGs use the paper-scale 1,500-node setting
  with minimum out-degree 3.
- The ICL evaluation path is the low-cost reproduction route used for the current
  repository artifacts. Full LoRA training remains available through
  `trainStudent.py` when `--skip_final_train=false`.
