# DM10 gate: the held-out half

The owner's rules G1–G5 (adopted 2026-10-01), applied once (`docs/dm10/gate.py`).

| rule | suite | held-out run | result | detail |
|---|---|---|---|---|
| G1 | limits | 60d74b4, 2026-10-02 | PASS | 69/69 inside the validated ranges pass (all points: 71/81) |
| G2 | LZ's tables | 1586967, 2026-10-02 | PASS | 95.1% of 304 within 0.3σ (rule: ≥ 90%) |
| G3 | injection | 1586967, 2026-10-02 | PASS | class 95.8% of 384 (rule: ≥ 85%); at N ≥ 20: Xe 94.6%, CaWO4 90.3%, Ge 93.0%, Ar 100.0% (rule: each ≥ 75%) |
| G4 | historical | 1586967, 2026-10-02 | PASS | cdms_ii_ge_2009: significance: agrees |
| G5 | baselines | 1586967, 2026-10-02 | PASS | claude-opus-5-5: system 97.0% against 79.8% on 99 cases (margin +17.2 points; rule: ≥ +10); gpt-5.6-sol: system 94.6% against 75.0% on 56 cases (margin +19.6 points; rule: ≥ +10) |

**5 of 5 rules met**; the gate passes.
