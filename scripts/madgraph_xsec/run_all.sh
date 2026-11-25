#!/bin/bash
# Regenerate every table from scratch (MG5 process directories are created on first use).
# At most two MG5 jobs run at once; each MadEvent run is single-core (run_mode = 0).
# Total wall time on an M-series Mac (x86 gfortran under Rosetta): roughly 1.5-2 h.
set -e
cd "$(dirname "$0")"
PY="nice -n 10 ${MG5_PYTHON:-$HOME/agentic-dm-tools/.venv-mg5/bin/python}"
LOG=${XSEC_LOGS:-$HOME/agentic-dm-tools/madgraph-xsec/logs}
mkdir -p "$LOG"

# 0. downloads (UFOs must already be in ~/agentic-dm-tools/ufo; PDF grid for the analytic checks)
#    curl -L -O http://feynrules.irmp.ucl.ac.be/raw-attachment/wiki/DMsimp/DMsimp_s_spin1.zip
#    curl -L -O http://feynrules.irmp.ucl.ac.be/raw-attachment/wiki/DMsimp/DMsimp_s_spin0_4f_ybMSbar.zip
#    curl -L -O http://madgraph.phys.ucl.ac.be/Downloads/models/heft.tgz
#    curl -L -O http://lhapdfsets.web.cern.ch/lhapdfsets/current/NNPDF23_lo_as_0130_qed.tar.gz  (-> ~/agentic-dm-tools/lhapdf)
$PY fetch_hxswg.py
$PY fetch_heavy_higgs_limits.py

# 1. spin-1 Z' (two parallel jobs)
$PY zprime_spin1.py vector u d s --suffix A > "$LOG"/zp_A.log 2>&1 &
$PY zprime_spin1.py axial c b --suffix B > "$LOG"/zp_B.log 2>&1
wait

$PY derive_tables.py                       # up-type, down-type, B-L tables from the flavour tables

# 2. spin-0 gg -> S (heft below 50 GeV, loop-induced above); then a denser grid near 2 m_t
( $PY spin0_ggf.py --low-only --suffix A && $PY spin0_ggf.py S_tb S_t S_b --high-only --suffix A ) > "$LOG"/s0_A.log 2>&1 &
$PY spin0_ggf.py P_tb P_t P_b --high-only --suffix B > "$LOG"/s0_B.log 2>&1
wait
M="300 320 335 340 345 350 360 380 400 420"
$PY spin0_ggf.py S_tb S_t S_b --high-only --suffix A --masses $M > "$LOG"/s0_dense_A.log 2>&1 &
$PY spin0_ggf.py P_tb P_t P_b --high-only --suffix B --masses $M > "$LOG"/s0_dense_B.log 2>&1
wait

# 3. inert doublet Drell-Yan pairs  |  associated t tbar S / b bbar S
$PY inert_doublet_dy.py all > "$LOG"/idm_all.log 2>&1 &
$PY assoc_spin0.py > "$LOG"/assoc.log 2>&1
wait

# 4. validation and K-factors
$PY validate.py zprime > "$LOG"/valid_zp.log 2>&1 &
$PY validate.py spin0 > "$LOG"/valid_s0.log 2>&1
wait
$PY validate.py kfactor > "$LOG"/kfactor.log 2>&1        # needs HXSWG JSON + S_tb table (no MG5)
$PY validate.py idm > "$LOG"/valid_idm.log 2>&1          # MSSM slepton/sneutrino cross-check + K (MG5)
$PY twohdma_single.py > "$LOG"/2hdma.log 2>&1            # derived 2HDM+a table (no MG5)
$PY check_2hdma_mg5.py > "$LOG"/check_2hdma.log 2>&1     # 3 loop-induced points with Pseudoscalar_2HDM (MG5)
$PY check_analytic.py > "$LOG"/check_analytic.log 2>&1   # MG5 vs analytic LO for every point (no MG5)
# zprime_nlo.py (aMC@NLO K-factor) is NOT in the chain: it fails ('Poles do not cancel'), see report
echo done
