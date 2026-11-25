# direct_prompting_claude-opus-5-5: the held-out half

Commit 60d74b4, 2026-10-02; reason: held-out half (DM10 gate: the owner's rules G1-G5, approved 2026-10-02).

| measure | value |
|---|---|
| Xe (LZ extended window), N = 3 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.40; 1.00; 0.00; 0.00, 29.8; 5 |
| Xe (LZ extended window), N = 5 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.50; 1.00; 0.00; 0.17, 29.7; 6 |
| Xe (LZ extended window), N = 10 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.50; 1.00; 0.00; 0.00, 28.8; 4 |
| Xe (LZ extended window), N = 20 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.20; 1.00; 0.00; 0.60, 28.8; 5 |
| Xe (LZ extended window), N = 50 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.20; 0.40; 0.00; 0.40, 24.4; 5 |
| CaWO4 (CRESST-III), N = 3 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.17; 1.00; 0.00; 0.67, 27.5; 6 |
| CaWO4 (CRESST-III), N = 5 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.33; 1.00; 0.00; 0.67, 28.2; 6 |
| CaWO4 (CRESST-III), N = 10 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.20; 0.80; 0.00; 0.00, 25.8; 5 |
| CaWO4 (CRESST-III), N = 20 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.00; 0.00; 0.00; 0.25, 23.8; 4 |
| CaWO4 (CRESST-III), N = 50 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.00; 0.00; 0.00; 0.20, 27.0; 5 |
| Ge (CDMSlite), N = 3 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.75; 0.88; 0.00; 0.75, 30.0; 8 |
| Ge (CDMSlite), N = 5 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.75; 0.75; 0.25; 0.75, 30.0; 4 |
| Ge (CDMSlite), N = 10 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 1.00; 1.00; 0.20; 0.80, 30.0; 5 |
| Ge (CDMSlite), N = 20 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.33; 0.67; 0.00; 1.00, 26.7; 3 |
| Ge (CDMSlite), N = 50 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.33; 0.67; 0.17; 0.83, 25.7; 6 |
| Ar (DEAP-3600), N = 3 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 1.00; 1.00; 0.00; 0.25, 30.0; 4 |
| Ar (DEAP-3600), N = 5 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 1.00; 1.00; 0.00; 0.20, 30.0; 5 |
| Ar (DEAP-3600), N = 10 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 1.00; 1.00; 0.00; 0.00, 30.0; 3 |
| Ar (DEAP-3600), N = 20 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.80; 1.00; 0.00; 0.20, 30.0; 5 |
| Ar (DEAP-3600), N = 50 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.60; 0.60; 0.00; 0.40, 27.4; 5 |
| all, pairwise | 0.495 |
| all, class | 0.798 |
| all, exact | 0.03 |
| all, ΔAIC set | 0.424 |

Failed cases (50):
- Xe (LZ extended window)|N=3|0: injected L12v@4000, named O01s@4000,d=100
- CaWO4 (CRESST-III)|N=3|0: injected O3v@5, named O11s@2
- Ge (CDMSlite)|N=5|0: injected O1v@5, named O11s@3
- CaWO4 (CRESST-III)|N=10|0: injected O1v@5, named O11s@2
- Xe (LZ extended window)|N=20|0: injected L09s@12, named L03s@14
- CaWO4 (CRESST-III)|N=3|1: injected O9s@3, named O1s@5
- CaWO4 (CRESST-III)|N=5|1: injected O15s@1, named O1s@2
- CaWO4 (CRESST-III)|N=20|1: injected O6v@2, named O11s@2
- Xe (LZ extended window)|N=50|1: injected O01v@4000,d=350, named O01s@1000,d=300
- CaWO4 (CRESST-III)|N=50|1: injected O11v@12, named O11s@3
- Xe (LZ extended window)|N=3|2: injected L10s@100, named L03s@1000
- Xe (LZ extended window)|N=10|2: injected L19v@12, named L04s@10
- CaWO4 (CRESST-III)|N=10|2: injected O5s@8, named O11s@2
- CaWO4 (CRESST-III)|N=20|2: injected O9v@12, named O11s@12
- CaWO4 (CRESST-III)|N=50|2: injected O10v@2, named O1s@3
- Ge (CDMSlite)|N=50|2: injected O1v@3, named O11s@3
- Xe (LZ extended window)|N=5|3: injected L14s@400, named L20s@1000
- Xe (LZ extended window)|N=50|3: injected O01v@1000,d=100, named L09s@1000
- CaWO4 (CRESST-III)|N=50|3: injected O15v@12, named O11s@20
- Xe (LZ extended window)|N=5|4: injected L15v@17, named L01s@40
- CaWO4 (CRESST-III)|N=5|4: injected O6v@5, named O11s@12
- CaWO4 (CRESST-III)|N=10|4: injected O5s@5, named O1s@2
- Xe (LZ extended window)|N=20|4: injected L14v@17, named L03s@14
- Ar (DEAP-3600)|N=20|4: injected O8s@50, named O1s@500
- Xe (LZ extended window)|N=50|4: injected L05v@50, named L03s@30
- CaWO4 (CRESST-III)|N=50|4: injected O10v@20, named O11s@20
- Ge (CDMSlite)|N=50|4: injected O1v@15, named O11s@15
- CaWO4 (CRESST-III)|N=3|5: injected O15s@20, named O11s@20
- CaWO4 (CRESST-III)|N=50|5: injected O14s@8, named O6s@20
- Xe (LZ extended window)|N=5|6: injected L08s@200, named L04s@1000
- CaWO4 (CRESST-III)|N=5|6: injected O1s@5, named O1s@8
- CaWO4 (CRESST-III)|N=10|6: injected O11v@2, named O1s@1
- Xe (LZ extended window)|N=20|6: injected L08s@1000, named O04s@1000,d=100
- CaWO4 (CRESST-III)|N=20|6: injected O5s@2, named O1s@1
- Ge (CDMSlite)|N=20|6: injected O1v@3, named O1s@5
- CaWO4 (CRESST-III)|N=3|7: injected O6s@20, named O11s@20
- Ge (CDMSlite)|N=3|7: injected O1v@3, named O1s@5
- Xe (LZ extended window)|N=20|7: injected L07s@40, named L03s@40
- Ge (CDMSlite)|N=50|7: injected O11s@3, named O1s@3
- Ar (DEAP-3600)|N=50|7: injected O11v@200, named O3s@100

Spent $2.96 of $3.35 (completed requests only).
