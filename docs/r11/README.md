# R11: documentation, code health and release packaging

**Status (2026-10-13): done.** The release runner passes (10 of 10 steps), every documented command and flag
exists (82 commands, 0 findings), and the clean-machine install test passes on Apple Silicon
(a development receipt (clean_install_2026-10-13T004829Z)).

The plan is the release plan, section R11. Each item, what was done, and where it is recorded:

## Documentation

| item | done | where |
|---|---|---|
| `design.md` for the dual-track system | rewritten: tracks, portal library, evidence, certificates, catalogs, reanalysis | `a92b1e6` |
| README: scope and limits, verdict levels, modules, layout | a consolidated "Scope and limits" section (freeze-in, electron recoils and Migdal, LO collider, halo) | `3522f51` |
| the audit brief record, `installation.md`, `dm8_lagrangians.md`, `extension_status.md` | corrected | `a92b1e6` |
| the shipped `vector_mediator.yaml` (L8a) | says its m_χ = 100 GeV is G1's benchmark, which the single-idea scan overrides | `946775a` |
| links into the ignored `audit/` | replaced by tracked summaries in `docs/receipts/` | `a92b1e6` |
| CLI help | a help text on every command and option (161 added); `scripts/check_cli_docs.py` checks every documented `adroit …` call and flag against the CLI: 82 commands, 0 findings | `9ebc9ff`, `046f04e` |
| citations | `docs/citations.md` and `docs/dependencies.bib` checked against each workflow's components; added XENONnT's and LZ's validation data, PDF4LHC21, LHAPDF6 and parton | `21fa543` |

## Code health

| item | done | where |
|---|---|---|
| `ruff check` clean | 1,191 one-line compound statements split in 83 files by a script that rewrites a file only if its syntax tree is unchanged, `dated_report` imported at the top (12 modules), 32 unused imports removed; then the files R10 was editing at the time. The release runner's baseline is 0 | `e1246b7`, `046f04e` |
| functions over 100 lines | none left. The eight longest (`fit_domain` 226 → 43, `wizards.track1` 155 → 33, `intake_page` 131 → 21, `signal.run` 129 → 42, `scan.evaluate` 119 → 53, `approve_panel` 106 → 35, `track1.report` 106 → 34, `single_idea._study` 102 → 39) were split into named steps, and their outputs compared with the previous code's: `fit_domain` on 13 cases (results, the order of likelihood evaluations, checkpoints), `signal.run` on 4 requests, `scan.evaluate` on 66 points, `track1.report` on 70 saved results | `38fa00c` |
| functions over 60 lines | 21 remain, 61–94 lines (mostly NiceGUI page builders, whose length is their layout) | below |
| docstrings | every public function, class and method has one: 428 added outside the fingerprinted physics code (each module's syntax tree, without docstrings, unchanged), and the last 18 in the files the limit tables fingerprint once the tables were final (`halo.py` corrected on the way: no fit profiles the halo). 0 left | `b9daf54`, `3487282` |

The 21 functions of 61–94 lines, longest first: `ui.app.build_pages` (94), `ui.reanalysis.page` (93),
`ui.experimental_review.review_tools` (90) and its `panel` (85), `native_joint.run` (85), `evidence.runtime.capture`
(81), `research_assistance.run` (80), `evidence.observations.point_observations` (80),
`retrieval.source_evidence.gather` (74), `verdict._verdict_from_roots` (72), `model_intake.step` (72),
`physical_eligibility.assess` (70), `evidence.build._adapt` (68), `constraints.experimental_review.plot_packet` (68),
`native_domain.run_domain` (67), `portals.tchannel.coannihilation` (66), `coverage.diagnose` (65),
`single_idea.report` (65), `research_assistance._execute` (64), `dwarf_likelihood.upper_limit` (62),
`cli.single_idea` (61).

## Packaging

| item | done | where |
|---|---|---|
| licence | BSD-3-Clause (the owner's choice, 2026-10-12): `LICENSE`, and `license = "BSD-3-Clause"` with `license-files` in `pyproject.toml` | `046f04e`, `89aa713` |
| version and changelog | 0.1.0 in `pyproject.toml` and `adroit.__version__` (a test keeps them equal); `CHANGELOG.md` by milestone | `89aa713`, `046f04e` |
| tools manifest | the PDF grids used in record derivations (PDF4LHC21_40, NNPDF2.3 LO) fetched by `adroit setup --fetch`; their role, derivation data, keeps them out of Track 1's run identity | `9893c23` |
| clean-machine install test | `scripts/clean_install_test.py`: a fresh clone, an empty tools folder, `uv sync` with the `ui` and `retrieval` extras, `adroit setup --fetch`, the fast suite, one Track 1 and one Track 2 example. **Passed** on arm64 (below) | `68d689c`, receipts | `68d689c` |

## Also fixed on the way

- **A test-isolation bug.** NiceGUI's reset after each UI test drops the page-registering modules from
  `sys.modules` together with their parent packages, including `adroit` itself. A later import then made a second,
  empty `adroit` package, and string-path monkeypatches failed in whatever test ran next. The full suite's
  alphabetical order hid it. `tests/ui/conftest.py` now puts the packages back (`68fd2e0`).

## The gate

| gate item | result | record |
|---|---|---|
| the release runner (R0): ruff clean, all suites and validations green | **passed** on the final code: 10 of 10 steps. Ruff 0 violations; the fast suite 1,922 passed; the slow suite 34; the portal library's validations 17 of 17, 24 of 24, 26 of 26 and 5 of 5 gates; the native PICO certificate; the optional backends; `adroit setup`, 9 of 9 required items present (the first passing run, before the install fixes, is `release_checks_2026-10-12T202602Z`) | a development receipt (release_checks_2026-10-13T004924Z) |
| the clean-machine install receipt | **passed** on arm64: 9 of 9 required items after the documented manual step, the fast suite 1,909 passed (13 skipped for optional tables that were unreachable), the Track 1 and Track 2 examples | a development receipt (clean_install_2026-10-13T004829Z) |
| every documented command and flag exists | **passed**: `scripts/check_cli_docs.py`, 82 commands, 0 findings | `9ebc9ff` |

The release run before (a development receipt (release_checks_2026-10-12T193748Z)) failed two steps, the slow SModelS test
and part 3's gate. Both still expected a coloured partner below its limit (r = 0.46, QCD production alone) to be
allowed, though since the owner's data audit that day it is undecided; they were corrected (`e0c1cd9`).

The receipt's commit reads `4695996+dirty`: the working tree held the owner's record signatures in progress
(`records.yaml` and the R9 packet), which are committed once every record is signed.

## The clean-machine install test: what it found

Six runs (2026-10-12/13), each from a fresh clone into an empty tools folder; every receipt is kept in
`docs/receipts/clean_install_*.md`. Each run stopped at, or reported, something that a clean machine meets and the
development machine (with its hand-built tools) never did. Fixed, in order:

1. **The retrieval extra did not install on an Intel Mac**: torch 2.14 has no x86_64 macOS wheels (`64badcb`).
   Pinning torch 2.2.2 there then exposed that **ADROIT needs NumPy 2** (`numpy.trapezoid`) while declaring
   1.26: it now declares 2.0, and on Intel Macs the extra installs nothing, keeping the hash embedder (`35d999b`).
2. **One failed optional build stopped every later fetch**, and **dmscatter's Makefile raced** under `make -j2`
   (a Fortran module used before it was compiled) (`2c92a12`).
3. **Four required tools were cloned but never built** (DIAMX, DirectDM, the Mu2e scripts; MadGraph's
   environment, needed by the UFO portals), and `adroit setup` called them present. `adroit setup --fetch` now
   builds each with the working versions pinned (`adroit/external/constraints/`), presence means built, and
   each build ends by importing its compiled module (`de6abab`). On the way: compiled code must match its
   interpreter (DIAMX's C++ was built x86_64 into an arm64 environment under an x86_64 uv; py3nj takes
   gfortran's architecture), and `uv pip install -c` fails on a path with spaces. DIAMX's own 15 tests pass in
   the environment built this way.
4. **MadDM's and RAPIDD's versions were descriptions**, which `git checkout` refused; **Capt'n General's
   Makefile raced** like dmscatter's; **Harvard's f_eff host omits an intermediate certificate**, so downloads now
   verify against the system's trust store, as curl and browsers do (`dd86053`).
5. **A missing production table crashed or silenced searches** (the LHC search read a file that was not there;
   mono-Z divided by an invented zero rate; dijets and the singlet's ZZ/WW returned nothing): each now reports
   the point undecided with the missing table as its reason, and the tests that need a table skip without it
   (`9f466f2`, `e23a5ce`).
6. **Under Rosetta, DIAMX cannot run**: an x86_64 Python on Apple Silicon (this machine's Homebrew uv chooses
   one) gets jaxlib, which needs AVX instructions that Rosetta does not provide. `adroit setup` now warns, and
   the install guide says to use a native Python (`dd4d037`). The x86_64 run (`clean_install_2026-10-13T001302Z`)
   built every other tool and failed only where DIAMX is needed (44 of 45 test failures, both examples). A real
   Intel Mac has AVX; it could not be tested here.

**Not fixed, external:** FeynRules' site (the inert doublet's UFO, the DMsimp models behind the MadGraph
production tables) was unreachable throughout, and CERN's twiki (the SUSY Working Group's and Higgs Working
Group's tables) intermittently. `adroit setup --fetch` reports each with its error and carries on; rerun it
when they are back.

**Retried (2026-10-13), into an empty tools folder:**
- **CERN's twiki is back.** Its retry found three faults of ADROIT's own, now fixed:
  - ten build commands left a path unquoted, which a folder named with parentheses broke ("My Mac (…)");
  - the SUSY item fetched four of the nine pages its table builder reads;
  - the builder crashed on an optional HEPi table that was not fetched.

  A fresh fetch now builds every SUSY table byte-identical to the working tools folder, except the two optional
  HEPi slepton tables, which nothing uses. The Higgs Working Group's YR4 spreadsheet is identical too.
  `tests/external/test_manifest.py` checks every build command with such a path, and the page list.
- **FeynRules is still down.** Its server accepts the connection but drops the TLS handshake
  (`SSL_ERROR_SYSCALL`), a fault on its side. A fresh install cannot fetch the inert doublet's UFO or the DMsimp
  models until it recovers. WimPyDD and LZ's extended window are browser-only downloads by their sites' choice (the
second, required, is the documented manual step the test performs).
