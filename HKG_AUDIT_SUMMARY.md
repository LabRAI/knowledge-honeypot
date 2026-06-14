# HKG Audit Summary

Final repaired HKGs:

| Domain | Nodes | Unique Topics | Min Out-Degree | Bad Nodes After Audit | Min Inaccessibility | Max Utility |
|---|---:|---:|---:|---:|---:|---:|
| Medical | 1,500 | 1,500 | 3 | 0 | 0.7113 | 0.0 |
| Financial | 1,500 | 1,500 | 3 | 0 | 0.7113 | 0.0 |

Repair actions:

- Medical: removed 18 modern/practical coding or EHR-related nodes.
- Financial: removed 298 modern/practical regulatory, market, or compliance nodes.
- Paper-scale expansion: each domain was expanded from the audited 500-node seed
  HKG to 1,500 nodes with deterministic archival variants while preserving
  `d_min = 3`, low utility, and high inaccessibility.

Strict audit criteria:

- Remove nodes with `inaccessibility_score < 0.65`.
- Remove nodes with `utility_score >= 0.10`.
- Remove modern/practical concepts such as CPT, ICD, SNOMED, EHR, billing,
  SEC, FINRA, NASDAQ, NYSE, Federal Reserve, LIBOR, Basel, trading halts,
  net capital rules, and current reporting/compliance concepts.
