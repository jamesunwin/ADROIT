# direct_prompting_claude-opus-5-5: the development half

Commit 210de00+dirty, 2026-10-01; reason: development half, stopped at the budget after 78 of 101 cases.

| measure | value |
|---|---|
| Xe (LZ extended window), N = 3 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.80; 1.00; 0.00; 0.20, 30.0; 5 |
| Xe (LZ extended window), N = 5 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.50; 1.00; 0.00; 0.00, 30.0; 4 |
| Xe (LZ extended window), N = 10 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.50; 1.00; 0.17; 0.17, 24.7; 6 |
| Xe (LZ extended window), N = 20 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.40; 1.00; 0.00; 0.40, 29.6; 5 |
| Xe (LZ extended window), N = 50 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.20; 0.40; 0.00; 0.20, 24.6; 5 |
| CaWO4 (CRESST-III), N = 3 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.50; 1.00; 0.25; 0.75, 29.2; 4 |
| CaWO4 (CRESST-III), N = 5 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.75; 1.00; 0.25; 0.25, 28.0; 4 |
| CaWO4 (CRESST-III), N = 10 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.00; 1.00; 0.00; 0.20, 22.4; 5 |
| CaWO4 (CRESST-III), N = 20 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.00; 0.00; 0.00; 0.17, 27.3; 6 |
| CaWO4 (CRESST-III), N = 50 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.40; 0.40; 0.00; 0.00, 24.2; 5 |
| Ge (CDMSlite), N = 3 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.50; 0.50; 0.00; 0.50, 30.0; 2 |
| Ge (CDMSlite), N = 5 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.50; 0.67; 0.00; 0.67, 28.7; 6 |
| Ge (CDMSlite), N = 10 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.60; 0.80; 0.20; 0.80, 29.6; 5 |
| Ge (CDMSlite), N = 20 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.00; 0.29; 0.00; 0.71, 26.4; 7 |
| Ge (CDMSlite), N = 50 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.50; 0.50; 0.25; 0.75, 24.2; 4 |
| Ar (DEAP-3600), N = 3 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 1.00; 1.00; 0.00; 0.20, 30.0; 5 |
| all, pairwise | 0.423 |
| all, class | 0.705 |
| all, exact | 0.064 |
| all, ΔAIC set | 0.372 |

Failed cases (45):
- Xe (LZ extended window)|N=3|9: injected L19v@14, named L01s@30
- Xe (LZ extended window)|N=5|2: injected L08v@10, named L04s@12
- Xe (LZ extended window)|N=5|7: injected L05v@14, named L03s@10
- Xe (LZ extended window)|N=10|1: injected O04v@400,d=100, named O01s@1000,d=100
- Xe (LZ extended window)|N=10|7: injected L08s@12, named L03s@14
- Xe (LZ extended window)|N=10|8: injected L11s@200, named O01s@1000,d=50
- Xe (LZ extended window)|N=20|2: injected L11s@100, named L01s@200
- Xe (LZ extended window)|N=20|5: injected L10v@12, named L04s@14
- Xe (LZ extended window)|N=20|8: injected L08s@400, named L04s@1000
- Xe (LZ extended window)|N=50|0: injected L11v@400, named L04s@200
- Xe (LZ extended window)|N=50|2: injected L13s@400, named L03s@1000
- Xe (LZ extended window)|N=50|7: injected O04v@400,d=0, named L03s@200
- Xe (LZ extended window)|N=50|8: injected L13s@21, named L03s@21
- CaWO4 (CRESST-III)|N=3|6: injected O8v@12, named O11s@3
- CaWO4 (CRESST-III)|N=3|8: injected O3s@1, named O1s@1
- CaWO4 (CRESST-III)|N=5|8: injected O6v@1, named O11s@5
- CaWO4 (CRESST-III)|N=10|1: injected O13v@1, named O11s@1
- CaWO4 (CRESST-III)|N=10|5: injected O7v@1, named O1s@1
- CaWO4 (CRESST-III)|N=10|7: injected O5s@3, named O1s@1
- CaWO4 (CRESST-III)|N=10|8: injected O15v@2, named O11s@2
- CaWO4 (CRESST-III)|N=10|9: injected O4s@8, named O6s@8
- CaWO4 (CRESST-III)|N=20|0: injected O9v@1, named O1s@2
- CaWO4 (CRESST-III)|N=20|3: injected O4s@5, named O1s@20
- CaWO4 (CRESST-III)|N=20|4: injected O13v@3, named O1s@3
- CaWO4 (CRESST-III)|N=20|5: injected O4v@3, named O11s@2
- CaWO4 (CRESST-III)|N=20|7: injected O6v@8, named O11s@20
- CaWO4 (CRESST-III)|N=20|8: injected O10s@2, named O11s@3
- CaWO4 (CRESST-III)|N=50|6: injected O10v@5, named O11s@8
- CaWO4 (CRESST-III)|N=50|8: injected O13v@2, named O11s@2
- CaWO4 (CRESST-III)|N=50|9: injected O11v@12, named O11s@3
- Ge (CDMSlite)|N=3|9: injected O5v@3, named O1s@5
- Ge (CDMSlite)|N=5|1: injected O1v@3, named O1s@5
- Ge (CDMSlite)|N=5|3: injected O8v@7, named O1s@15
- Ge (CDMSlite)|N=5|9: injected O11v@3, named O1s@5
- Ge (CDMSlite)|N=10|0: injected O8v@10, named O11s@10
- Ge (CDMSlite)|N=10|6: injected O1s@5, named O11s@3
- Ge (CDMSlite)|N=20|0: injected O5v@15, named O11s@10
- Ge (CDMSlite)|N=20|2: injected O11s@7, named O1s@15
- Ge (CDMSlite)|N=20|3: injected O5s@7, named O10s@7
- Ge (CDMSlite)|N=20|4: injected O1v@15, named O11s@15

Spent $2.52 of $2.50.
