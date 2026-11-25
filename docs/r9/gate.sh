#!/bin/bash
# R9 gate (2026-10-13): the README examples under the default (verified) records, then every recorded acceptance
# crossing judged with default and with unverified records. $0, no network (literature skipped).
cd "$(dirname "$0")/../.."
mkdir -p runs/r9_gate
export OMP_NUM_THREADS=2 PJRT_NPROC=2 NPROC=2
log=runs/r9_gate/log.txt
step() { local name="$1"; shift; local t0=$(date +%s); echo "== $name: $*" >> "$log"; nice "$@" > "runs/r9_gate/$name.out" 2>&1; echo "== $name exit $? in $(( $(date +%s) - t0 )) s" >> "$log"; }
step records_list uv run adroit records list
step exclude_L10 uv run adroit exclude L10 --isospin s --masses 10,100,1000 --out runs/r9_gate/exclude_L10
step track1_higgs uv run adroit track1 --portal higgs_portal_scalar --no-literature --out runs/r9_gate/track1_higgs
step track1_axial uv run adroit track1 docs/dm13/axial_mediator.yaml --x m_med:10:10000 --y m_chi:1:2000 --no-literature --out runs/r9_gate/track1_axial
step single_idea uv run adroit single-idea docs/dm13/vector_mediator.yaml --experiment "CDMS II Si (2013)" --masses 5:40:12 --no-literature --out runs/r9_gate/single_idea
step rejudge_r3 uv run python scripts/acceptance_rejudge.py --out runs/r9_gate/rejudge_r3.json --from docs/receipts/r3/acceptance_after.json --all-crossings --entries higgs_portal_scalar higgs_portal_dirac higgs_portal_dirac_cpv higgs_portal_majorana higgs_portal_vector singlet_scalar_mixing dark_photon_dirac dark_photon_scalar inelastic_dark_photon z_portal_vector z_portal_axial z_portal_majorana b_minus_l lmu_minus_ltau alp_portal tchannel_uR_majorana tchannel_uR_dirac lepton_portal_muR dmwg_V1 dmwg_A1 scalar_mediator inert_doublet
step rejudge_extra uv run python scripts/acceptance_rejudge.py --out runs/r9_gate/rejudge_extra.json --from docs/receipts/r3/acceptance_before.json --all-crossings --entries two_hdm_a --multiplets
echo "== done" >> "$log"
