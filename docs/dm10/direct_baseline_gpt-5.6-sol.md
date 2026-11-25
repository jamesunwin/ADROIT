# direct_prompting_gpt-5.6-sol: the development half

Commit df9b14b, 2026-10-02; reason: development half, stopped at the budget after 44 of 101 cases.

| measure | value |
|---|---|
| Xe (LZ extended window), N = 3 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.50; 0.50; 0.00; 0.00, 19.0; 2 |
| Xe (LZ extended window), N = 5 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.50; 1.00; 0.00; 0.00, 17.0; 2 |
| Xe (LZ extended window), N = 10 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.00; 0.67; 0.00; 0.00, 14.0; 3 |
| Xe (LZ extended window), N = 20 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.00; 1.00; 0.00; 0.00, 17.0; 2 |
| Xe (LZ extended window), N = 50 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.00; 0.00; 0.00; 0.00, 12.0; 2 |
| CaWO4 (CRESST-III), N = 3 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.00; 1.00; 0.00; 0.50, 24.0; 2 |
| CaWO4 (CRESST-III), N = 5 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.00; 1.00; 0.00; 0.00, 15.0; 2 |
| CaWO4 (CRESST-III), N = 10 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.00; 0.00; 0.00; 0.00, 12.0; 1 |
| CaWO4 (CRESST-III), N = 20 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.00; 0.00; 0.00; 0.00, 11.0; 2 |
| CaWO4 (CRESST-III), N = 50 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.00; 0.00; 0.00; 0.00, 14.0; 1 |
| Ge (CDMSlite), N = 3 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 1.00; 1.00; 0.00; 1.00, 24.0; 1 |
| Ge (CDMSlite), N = 5 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.00; 0.33; 0.00; 0.33, 30.0; 3 |
| Ge (CDMSlite), N = 10 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.33; 0.67; 0.00; 0.67, 22.0; 3 |
| Ge (CDMSlite), N = 20 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.67; 1.00; 0.00; 0.33, 20.7; 3 |
| Ge (CDMSlite), N = 50 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.50; 0.50; 0.50; 1.00, 16.0; 2 |
| Ar (DEAP-3600), N = 3 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 1.00; 1.00; 0.00; 0.00, 23.3; 3 |
| Ar (DEAP-3600), N = 5 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 1.00; 1.00; 0.00; 0.00, 24.7; 3 |
| Ar (DEAP-3600), N = 10 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 1.00; 1.00; 0.00; 0.33, 21.3; 3 |
| Ar (DEAP-3600), N = 20 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 1.00; 1.00; 0.00; 0.00, 18.0; 2 |
| Ar (DEAP-3600), N = 50 (pairwise; class; exact; ΔAIC set: coverage, mean size; cases) | 0.00; 0.00; 0.00; 0.00, 12.0; 2 |
| all, pairwise | 0.409 |
| all, class | 0.682 |
| all, exact | 0.023 |
| all, ΔAIC set | 0.205 |

Failed cases (26):
- CaWO4 (CRESST-III)|N=5|0: injected O11s@8, named O1s@5
- Xe (LZ extended window)|N=10|0: injected L17s@1000, named O04v@4000,d=0
- Ge (CDMSlite)|N=10|0: injected O8v@10, named O6s@10
- CaWO4 (CRESST-III)|N=20|0: injected O9v@1, named O1s@2
- Xe (LZ extended window)|N=50|0: injected L11v@400, named O01s@4000,d=100
- CaWO4 (CRESST-III)|N=50|0: injected O3s@8, named O6s@20
- Ge (CDMSlite)|N=50|0: injected O5s@15, named O6s@10
- Ar (DEAP-3600)|N=50|0: injected O5s@500, named O15s@1000
- Xe (LZ extended window)|N=3|1: injected O04s@1000,d=150, named O01s@400,d=200
- Ge (CDMSlite)|N=5|1: injected O1v@3, named O11s@5
- Xe (LZ extended window)|N=10|1: injected O04v@400,d=100, named L06s@1000
- CaWO4 (CRESST-III)|N=10|1: injected O13v@1, named O6s@3
- Xe (LZ extended window)|N=20|1: injected L19s@21, named L04s@21
- Ar (DEAP-3600)|N=50|1: injected O8v@1000, named O15s@1000
- Xe (LZ extended window)|N=5|2: injected L08v@10, named L04s@17
- Ge (CDMSlite)|N=5|2: injected O11v@3, named O1s@5
- Xe (LZ extended window)|N=20|2: injected L11s@100, named L03s@4000
- Ge (CDMSlite)|N=20|2: injected O11s@7, named O1s@15
- Xe (LZ extended window)|N=50|2: injected L13s@400, named L03s@200
- CaWO4 (CRESST-III)|N=3|3: injected O12v@12, named O6s@20
- CaWO4 (CRESST-III)|N=5|3: injected O9s@2, named O1s@12
- Ge (CDMSlite)|N=5|3: injected O8v@7, named O1s@15
- Xe (LZ extended window)|N=10|3: injected O04s@4000,d=300, named O01s@400,d=250
- CaWO4 (CRESST-III)|N=20|3: injected O4s@5, named O11s@12
- CaWO4 (CRESST-III)|N=3|4: injected O11s@8, named O6s@8
- Ge (CDMSlite)|N=10|4: injected O5s@3, named O1s@5

Spent $2.56 of $2.50 (completed requests only).
