"""Negative controls for "only usable models" (the usable models plan): each takes one part of the repair out of
the source, runs the tests named for it, and requires them to fail; the file is always restored.

    uv run python docs/usable_models/negative_controls.py

Written down here after the auditor's audit (2026-11-21, UM report): the first thirteen controls had been run from a scratch
script only, so they could not be reconstructed. Each control's exact replacement is below. Exit code 0 when every
control is caught.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UM = "adroit/model_building/usable_models.py"
PERSONAL = "adroit/library/personal.py"
IDEAS = "adroit/orchestrator/ideas.py"
LIBRARY = "adroit/ui/model_library.py"
AGENT = "adroit/agents/ideas.py"
GAUGE = "adroit/model_building/gauge_basis.py"
INDICES = "adroit/model_building/indices.py"
DERIVATION = "adroit/library/interactions/derivation.py"
FEYNMAN = "adroit/model_building/feynman.py"
T = "tests/model_building/test_usable_models.py::"
A = "tests/model_building/test_usable_models_audit.py::"
OPEN = "tests/model_building/test_usable_models_open_items.py::"
U = "tests/ui/test_usable_models_ui.py::"
REC = "tests/model_building/test_usable_models_recheck.py::"

# (label, file, exact text, its replacement, the tests that must then fail)
CONTROLS = [
    ("approval refusal", "adroit/orchestrator/model_intake.py",
     "        if not verdict.ok:\n            raise ValueError(NOT_SAVED", "        if False:\n            raise ValueError(NOT_SAVED",
     [U + "test_an_unusable_model_is_not_saved_and_its_missing_values_make_one_that_is"]),
    ("offer filter", "adroit/orchestrator/model_intake.py", "        if verdict.ok:\n            offered.append(c)",
     "        if True:\n            offered.append(c)",
     [U + "test_the_intakes_offer_keeps_only_usable_candidates_whatever_made_them"]),
    ("the builder's gate", IDEAS, "    if not verdict.ok or lost or unsolved:", "    if False:",
     [T + "test_a_proposal_without_a_mass_is_not_offered_and_says_why"]),
    ("inert dark matter", IDEAS, "verdict, lost = usable(spec), inert(spec)", "verdict, lost = usable(spec), ''",
     ["tests/orchestrator/test_completions.py::test_promotion_says_why_no_completion_is_studied_live_check_l9"]),
    ("canonical names", UM, "        found = CANONICAL.get(", "        found = None and CANONICAL.get(",
     [T + "test_the_tau_philic_z_prime_is_offered_usable_with_only_the_couplings_it_asks_for"]),
    ("Dirac-form SM currents", UM, "    spec = _sm_currents(spec)\n", "",
     [T + "test_a_massive_vectors_standard_model_currents_are_written_in_dirac_form"]),
    ("gauge currents", UM, "    spec, notes = _gauge_currents(spec)\n", "    notes = []\n",
     [T + "test_a_gauge_u1_gets_its_currents_from_the_charges_with_one_gauge_coupling"]),
    ("zeroed terms left out", UM, "        if _vanishes(t, zero):", "        if False:",
     [T + "test_the_tau_philic_z_prime_is_offered_usable_with_only_the_couplings_it_asks_for"]),
    ("perturbative bound", UM, "    if c.mass_dimension == 0 and abs(value) > PERTURBATIVE:", "    if False:",
     [T + "test_values_are_given_checked_and_every_other_coupling_is_zero_and_said"]),
    ("Save disabled", LIBRARY, "                save.disable()", "                pass",
     [U + "test_the_review_page_says_it_cannot_run_and_completes_it_with_typed_values"]),
    ("idea study's approval row", "adroit/ui/pages.py", "                if not usable_status(selected):",
     "                if usable_status(selected) and False:",
     ["tests/ui/test_model_approval.py::test_generated_completion_requires_explicit_choice_and_displays_changes"]),
    ("contract mass", PERSONAL, "     # per generation (L-10)\n             and f.name not in contracted]", "]",
     [T + "test_a_mass_its_scalar_potential_contract_states_is_not_missing"]),
    ("promotion names what it does not offer", "adroit/orchestrator/promote.py",
     '            why.setdefault(name, f"proposed by the model builder; {reason}")', "            pass",
     ["tests/orchestrator/test_completions.py::test_promotion_says_why_no_completion_is_studied_live_check_l9"]),
    # the live gate's L-4 and L-5
    ("L-4 marked in the values call", AGENT,
     '+ (f" [all 3 generations of {\' and \'.join(flavours)} alike]" if flavours else "")\n', '+ ""\n',
     [T + "test_a_flavour_universal_coupling_is_marked_for_the_builder_and_stated_in_the_model"]),
    ("L-4 stated in the model", UM, "_universal_notes(spec, kept, couplings) + _number_notes", "_number_notes",
     [T + "test_a_flavour_universal_coupling_is_marked_for_the_builder_and_stated_in_the_model"]),
    ("L-5 the route to the SM", PERSONAL, "        if lost := unreachable(spec):", "        if lost := '':",
     [T + "test_a_dark_sector_with_no_route_to_the_standard_model_is_not_offered"]),
    # The auditor's audit, UM-01 to UM-07
    ("UM-01 the engine's domain at the stated values", PERSONAL, "        elif ready['reference_domain']:",
     "        elif False:",
     [A + "test_a_model_its_engine_refuses_at_its_values_is_not_offered[n-plet below its domain]",
      A + "test_a_model_its_engine_refuses_at_its_values_is_not_offered[coupling below resolution]"]),
    ("UM-01 a zero-valued term joins nothing", UM, "        if _zero_at(t, known):\n            continue\n", "",
     [A + "test_a_zero_valued_portal_is_not_a_route_whatever_engine_maps_it"]),
    ("UM-01 the Track 1 picker", LIBRARY,
     "        if track and run_status(current,track,r.spec,r.derivation):",
     "        if track=='track2' and run_status(current,track,r.spec,r.derivation):",
     [A + "test_a_legacy_revision_its_engine_refuses_is_left_out_of_the_track1_picker"]),
    ("UM-02 every save refuses", PERSONAL,
     "        if not verdict.ok:\n            raise ValueError(NOT_SAVED+'; '.join(verdict.blocking))",
     "        if False:\n            raise ValueError(NOT_SAVED+'; '.join(verdict.blocking))",
     [A + "test_models_import_refuses_a_model_with_missing_couplings"]),
    ("UM-03 a charge rounded twice", UM, "    return near if float(near) == q else Fraction(repr(q))", "    return near",
     [A + "test_a_gauge_current_carries_its_charge_exactly"]),
    ("UM-03 the auditor's |q| mutation", UM, "            k = _charge_formula(q if f.spin == 0.5 else -q, g)",
     "            k = _charge_formula(abs(q) if f.spin == 0.5 else -q, g)",
     [A + "test_a_gauge_current_carries_its_charge_exactly"]),
    ("UM-04 the scalar current's sign", UM, "            k = _charge_formula(q if f.spin == 0.5 else -q, g)",
     "            k = _charge_formula(q, g)",
     [A + "test_a_scalars_u1_charge_has_the_sign_of_its_hypercharge"]),
    ("UM-05 conflicting values", UM, "        elif c.name in conflicts:\n            couplings.append(c)\n", "",
     [A + "test_conflicting_values_are_never_chosen_between"]),
    ("UM-05 values for no model", IDEAS, "        if not 1 <= v.model <= n:", "        if False:",
     [A + "test_values_addressed_to_no_model_are_said"]),
    ("UM-05 unknown names stated", IDEAS,
     '    spec = spec.model_copy(update={"assumptions": list(dict.fromkeys([*spec.assumptions, *problems]))})\n', "",
     [A + "test_a_value_for_no_coupling_is_named_on_the_offered_model"]),
    ("UM-06 an alias that contradicts", UM,
     '                or f.chirality not in ("", chirality) or (one_flavour and f.generations != 1)):', "):",
     [A + "test_a_field_that_contradicts_its_alias_keeps_its_own_name"]),
    ("UM-07 one answer for badge and Save", LIBRARY, "            if not ok:",
     "            if not usable(choice.spec,ready=choice.applicability or None).ok:",
     [U + "test_a_draft_with_an_older_applicability_shows_one_answer_for_its_badge_and_its_save"]),
    # the owner's tightening of the Track 2 exemption (2026-11-21)
    ("Track 2 matching all zero", PERSONAL, "    if any(v!=0 for v in coefficients.values()):",
     "    if True:",
     [A + "test_a_model_whose_own_matching_is_zero_at_its_values_is_not_saved"]),
    # the open items, closed before the release (the owner, 2026-11-21: no deferrals)
    ("L-7 a number-breaking term marked", AGENT,
     '+ (f" [breaks {moved}\'s number: splits {moved} into separate particles]" if moved else ""))', '+ "")',
     [OPEN + "test_a_term_that_breaks_a_complex_fields_number_is_marked_and_the_true_portal_runs"]),
    ("L-7 its value stated", UM, " + _number_notes(spec, kept, couplings)", "",
     [OPEN + "test_a_term_that_breaks_a_complex_fields_number_is_marked_and_the_true_portal_runs"]),
    ("L-1 the potential's sign", UM, '"value": -float(value) if in_v else float(value)', '"value": float(value)',
     [OPEN + "test_the_inert_doublet_is_offered_with_its_potential_in_v_and_its_stated_mass_physical"]),
    ("L-1 the stated mass physical", UM, "    done, mass_notes, mass_problems = physical_mass(done)\n",
     "    mass_notes, mass_problems = [], []\n",
     [OPEN + "test_the_inert_doublet_is_offered_with_its_potential_in_v_and_its_stated_mass_physical"]),
    ("L-1 an impossible physical mass refused", UM,
     "            if x <= 0:                                   # left without a mass, so not offered (as a conflict is)\n"
     "                return _with_mass(spec, f.name, None), [], [",
     "            if x <= 0:                                   # left without a mass, so not offered (as a conflict is)\n"
     "                return spec, [], [",
     [OPEN + "test_a_physical_mass_no_real_lagrangian_mass_gives_is_refused_with_why"]),
    ("L-2 a vacuum's mass not missing", PERSONAL, "    contracted|=vacuum_given(spec)\n", "",
     [OPEN + "test_a_mass_the_vacuum_gives_is_not_called_missing"]),
    ("L-2 the vector's mass from the vacuum", UM,
     "    done, vacuum_notes, vacuum_problems, targets = vacuum_masses(done)\n",
     "    vacuum_notes, vacuum_problems, targets = [], [], {}\n",
     [OPEN + "test_a_higgsed_vector_keeps_its_stated_mass_from_the_vacuum_and_the_dark_higgs_its_own"]),
    ("L-2 the dark Higgs's quartic kept", UM, "    values = {**_seeded_quartics(spec), **values}", "    values = dict(values)",
     [OPEN + "test_a_higgsed_vector_keeps_its_stated_mass_from_the_vacuum_and_the_dark_higgs_its_own"]),
    ("L-3 the unique invariant computed", INDICES, "            found = unique_invariant(spec, occ, group)",
     "            found = None",
     [OPEN + "test_the_triplet_doublet_yukawas_take_their_unique_invariant_and_the_model_runs"]),
    ("L-3 a Majorana component's conjugate", GAUGE,
     "    metric = su2_metric(f.charges.su2)\n    return [(gb.comp.weyl_index[(f.name, \"xi\", n)], metric[m, n]) "
     "for n in range(f.charges.su2) if metric[m, n]]",
     "    return [(gb.comp.weyl_index[(f.name, \"xi\", m)], 1.0)]",
     [OPEN + "test_a_majorana_triplets_conjugate_components_conserve_charge_in_every_mass_term"]),
    ("L-6 near-repeats merged", UM, "    said = distinct([*spec.dropped, *not_encoded])",
     "    said = list(dict.fromkeys(x.strip() for x in [*spec.dropped, *not_encoded] if x.strip()))",
     [OPEN + "test_an_omission_said_twice_in_other_words_is_said_once_the_fuller_way"]),
    ("L-6 a dimension said once", UM, "for n in found if n > 4 and n not in named]", "for n in found if n > 4]",
     [T + "test_the_quintuplet_is_offered_with_its_mass_and_its_splitting_is_said_left_out"]),
    ("L-6 the values call sees what is already said", AGENT,
     '        lines.append("Already noted as left out: " + "; ".join(said))', "        pass",
     [OPEN + "test_the_values_call_is_shown_what_the_proposal_already_left_out"]),
    ("phase C the repair round", IDEAS, "    repaired, dropped = _repair_round(idea, agent, failing, dropped)\n",
     "    repaired, dropped = {}, dropped + [_not_offered(m.general.name, r) for _, m, _, _, r in failing]\n",
     [OPEN + "test_a_model_its_values_cannot_run_gets_one_repair_round_that_sees_why"]),
    ("phase C no repair for a structure", IDEAS, "    if any(r.startswith(STRUCTURAL) for r in reasons):",
     "    if False:", [OPEN + "test_a_model_its_structure_stops_gets_no_repair_round"]),
    ("phase C none could be built, said", IDEAS, "    if not result.models and result.dropped:", "    if False:",
     [OPEN + "test_a_repair_that_does_not_help_is_said_with_both_rounds_reasons"]),
    ("phase C the typed-model offer", LIBRARY,
     "        ui.link('Write it as a typed model ($0)','/models/intake').mark('typed_model')", "        pass",
     [U + "test_the_review_page_lists_the_proposals_not_offered"]),
    # The auditor's audit at e567d81, UO-01 to UO-04 (UO-05 and UO-06 deferred)
    ("UO-01 a U(1)'s charge is no route by itself", UM, "    portal = spec.scalar_potential ",
     "    for f in spec.fields:\n        for group, q in f.charges.extra.items():\n"
     "            if snap(q) and group in links:\n                links[f.name].add(group)\n"
     "                links[group].add(f.name)\n    portal = spec.scalar_potential ",
     [REC + "test_a_zero_gauge_coupling_is_no_route_however_the_fields_are_charged"]),
    ("UO-02 a pole found exactly", DERIVATION,
     "    if exact.has(sympy.zoo, sympy.nan, sympy.oo, -sympy.oo) or exact.is_finite is False:", "    if False:",
     [REC + "test_a_matching_with_no_finite_value_is_refused_by_the_gate_and_the_catalog[pole]"]),
    ("UO-02 the gate says it", PERSONAL,
     "        return f'its own matching has no finite value at the stated values: {error}'", "        return ''",
     [REC + "test_a_matching_with_no_finite_value_is_refused_by_the_gate_and_the_catalog[infinity]"]),
    ("UO-03 approval keeps an unchanged parent's matching", "adroit/orchestrator/model_intake.py",
     "        verdict=usable(choice.spec,self.inherited_matching(session_id,d,choice))",
     "        verdict=usable(choice.spec)",
     [U + "test_an_unchanged_track2_model_refined_keeps_its_matching_and_saves"]),
    ("UO-03 the page keeps it too", LIBRARY, "    matching=service.inherited_matching(session,d,choice)",
     "    matching=None", [U + "test_an_unchanged_track2_model_refined_keeps_its_matching_and_saves"]),
    ("UO-04 one answer for every track", LIBRARY, "    if spec is not None and not reasons:", "    if False:",
     [U + "test_old_models_are_ready_only_where_they_can_run_and_the_pickers_agree"]),
    # the second live gate's findings, L-8 to L-10 (plan section 13)
    ("L-8 a saddle climbed out of", UM, "                if climbs == SADDLE_CLIMBS:", "                if True:",
     [OPEN + "test_a_trial_mass_at_a_saddle_is_raised_until_the_dark_matter_has_its_stated_mass"]),
    ("L-9 a right-handed current accepted", FEYNMAN,
     '    if weyl[0] and (fa.chirality != fb.chirality or term.lorentz != "vector"):',
     '    if weyl[0] and (fa.chirality != "L" or fb.chirality != "L" or term.lorentz != "vector"):',
     [OPEN + "test_a_b_minus_l_model_with_its_standard_model_charges_and_right_handed_neutrinos_is_offered"]),
    ("L-9 its sign", FEYNMAN, "        d[eb, ea] += -k\n", "        d[eb, ea] += k\n",
     [OPEN + "test_a_right_handed_fields_current_carries_minus_q_g_on_its_conjugate_block"]),
    ("L-9 the Standard Model's charges asked for", AGENT,
     "- A second exception: when Standard Model fermions carry charge under a new gauged U(1)",
     "- Otherwise: when Standard Model fermions carry charge under a new gauged U(1)",
     [OPEN + "test_a_b_minus_l_model_with_its_standard_model_charges_and_right_handed_neutrinos_is_offered"]),
    ("L-10 one mass kept", UM, "        f = _one_mass(f, notes)\n", "",
     [OPEN + "test_a_field_stating_its_mass_twice_keeps_one_and_says_so"]),
    ("L-10 per-generation masses given", PERSONAL, "f.mass_gev is None and not f.masses_gev     # per generation",
     "f.mass_gev is None     # per generation",
     [OPEN + "test_per_generation_masses_count_as_given_and_the_scotogenic_model_reaches_its_own_reason"]),
    # The auditor's recheck at 5f26f74: UO-07 (severe)
    ("UO-07 a completion failure blocks", IDEAS, "    if not verdict.ok or lost or unsolved:", "    if not verdict.ok or lost:",
     [REC + "test_two_mixed_scalars_have_both_stated_masses_in_the_final_spectrum_or_are_refused"]),
    ("UO-07 the masses solved", UM,
     "            if all(abs(got[key] - m) <= PHYSICAL_TOLERANCE * m for key, m in targets.items()):",
     "            if True:", [REC + "test_two_mixed_scalars_have_both_stated_masses_in_the_final_spectrum_or_are_refused"]),
    ("UO-07 an SM vacuum never rescaled", UM,
     "                   and spec.field(o.field).role is not FieldRole.standard_model})", "                   })",
     [REC + "test_a_standard_model_vacuum_is_never_rescaled"]),
    ("UO-07 an exhausted solve refused", UM,
     '            return spec, notes, [UNSOLVED + f"after {PHYSICAL_STEPS} steps {far[0]}',
     '            return trial, notes, [], targets\n            return spec, notes, [UNSOLVED + f"after '
     '{PHYSICAL_STEPS} steps {far[0]}',
     [REC + "test_a_solve_that_runs_out_of_steps_is_refused_not_claimed"]),
    ("UO-07 the final check compares", UM, "abs(got[(n, s)] - m) > PHYSICAL_TOLERANCE * 10 * m]", "False]",
     [REC + "test_the_final_check_reads_every_target_from_the_final_model"]),
]


def main() -> int:
    """Run every control; the number missed is the exit code's truth (0: all caught)."""
    missed = 0
    for label, path, old, new, tests in CONTROLS:
        p = ROOT / path
        original = p.read_text()
        if original.count(old) != 1:
            print(f"STALE: {label}: the text to replace occurs {original.count(old)} times in {path}")
            missed += 1
            continue
        try:
            p.write_text(original.replace(old, new))
            run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--no-header",
                                  *tests], cwd=ROOT, capture_output=True, text=True)
            caught = run.returncode != 0
        finally:
            p.write_text(original)
        missed += not caught
        print(f"{'caught' if caught else 'MISSED'}: {label}")
    print("all caught" if not missed else f"{missed} not caught")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
