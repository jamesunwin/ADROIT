# The Intel test (the batch plan's §8, 2026-10-20)

ADROIT is developed on Apple silicon; a native Intel (x86_64) run cannot be made here.

- **On Intel, natively:** `.github/workflows/intel.yml` runs ruff and the fast suite on GitHub's Intel macOS runner
  (`macos-15-intel`, the last Intel image: macOS 13's was retired in December 2025, and GitHub ends Intel macOS
  runners when macOS 15's image is retired in autumn 2027) on every push and on demand, with uv 0.11.26 and Python
  3.12 as here. It needs no secret and spends nothing. The runner has no tools folder and no `data/external`, so a
  test that needs one of their items skips there, naming it: by its module's own marker, or by the shared
  `@pytest.mark.needs(...)` (`tests/conftest.py`'s `NEEDS`, each item checked by the package's own availability
  function: DIAMX, the CRESST-III and CDMSlite releases, Yellin's optimum interval code, the B16 solar model, PPPC,
  the PDG's R ratio, DarkCast, the SUSY and MadGraph production tables, MadGraph, the UFO models and DirectDM). A test
  that checks a refusal or a pending outcome without a tool carries no marker and runs there.
- **Under Rosetta, here (emulated, recorded as such):** the fast suite in an x86_64 environment (`uv`'s x86_64 Python,
  which the x86_64 `uv` picks), at the commit and with the result below. DIAMX's JAX cannot run under Rosetta (it needs
  AVX), so the xenon likelihoods are not exercised there, as `adroit setup` warns.
- **Without the tools, here (the runner's conditions, B20-08, 2026-10-20):** the fast suite on this machine (arm64)
  with an empty tools folder (`ADROIT_TOOLS_DIR`), no `data/external` and the network refused (a dead proxy), as the
  runner has them. The workflow's comment had said that every test needing the tools skips by its own marker; 117
  failed. Leaving out one item of the tools folder at a time, with everything else present, gave each of those tests
  what it needs, and each now carries it. Ten more had passed only by downloading the B16 solar model, which a scan
  point fetches when it is missing (`constraints.capture.solar_model`); they now skip without it, so no fast test
  reaches the network. Two tests were split so that their tool-independent halves run without the tools: the missing
  production table's undecided searches (`test_resonances.py`; the mono-Z half needs the UFO models) and the
  `lagrangian --derive` refusals (`test_cli.py`; the derivation needs DirectDM).

A native Intel receipt still needs the owner's push: the run without the tools is on Apple silicon and is not one.

| run | commit | result |
|---|---|---|
| Rosetta (x86_64 under Rosetta 2, this machine; CPython 3.12 x86_64, 2026-10-20) | `34b8557` (`evidence-upkeep` before the long-function split; the split moves no number, see the CHANGELOG) | the fast suite: 3,119 passed, 3 skipped, none failed (34 min) |
| without the tools, before (arm64, this machine; empty tools folder, no `data/external`, 2026-10-20) | `51e4b2f` | the fast suite: 117 failed, 2,897 passed, 139 skipped (11.5 min) |
| without the tools, after (the same, and the network refused) | `ci-markers` (B20-08) | the fast suite: none failed, 2,889 passed, 266 skipped; two tests more than before, the splits (10 min) |
| without the tools, on the release candidate (the same conditions; 13 newer tests marked first, `deb3993`) | `8dabc93` | the fast suite: none failed, 2,970 passed, 292 skipped (10 min) |
