# R9: record verification: the packet for the person who signs

**Status (2026-10-13): done: every record is verified; the signatures are the owner's.** A record counts as verified only when a person has compared it with its source and signed it; synthetic names never count, and nothing here signs on anyone's behalf. Regenerate this page after any record edit (`docs/r9/packet.py`): each command pins the record's current scientific hash.

Today: **38 of 38 records verified**; 0 await verification. R4's text corrections were applied to the nine records signed earlier (eight entries, since the CMS and IceCube records share text), which made their signatures stale: they are listed first for re-signing, with the three records whose width domains, and the one whose QCD-only production, were corrected on 2026-10-12 after the owner had signed them (docs/widths.md, docs/benchmark_limits.md). `planck-2018-omega` lost its signature when it was corrected to Table 2's Ω_c h² = 0.1200 ± 0.0012 (2026-10-05).

## How to verify one record

```
uv run adroit records review ID         # the source, the page, the data, the scientific hash
uv run adroit records verify ID --by "James Unwin (owner)" --expected-hash HASH
```

Each record has a `notes` section (Markdown) for where each stored value is in its source and anything else a reader should know; notes are outside the signed content, so adding or correcting them never voids a signature. The hash pins exactly what you reviewed: if the record changes before you sign, `verify` refuses. Every source PDF is in the tools folder (`~/agentic-dm-tools/record-sources/`); the workbench's Records page opens each at its cited page.

Aids, which are not verifications:
- `docs/r9/precheck.md`: whether each record's cited figure or table label is on the cited page, and whether its scalar numbers are printed there;
- `docs/r9/portal_dependencies.md`: for each library portal at its benchmark, the constraints that wait for a record, and the verdict each then reaches.

## 1. Re-sign: the records signed before, now corrected (R4's text corrections; the width domains of 2026-10-12)

| record | portals gated | label on page | numbers on page | command | note |
|---|---|---|---|---|---|

## 2. The relic density

| record | portals gated | label on page | numbers on page | command | note |
|---|---|---|---|---|---|
| `planck-2018-omega` | every relic verdict | yes | value = 0.12: yes, sigma = 0.0012: yes | `adroit records verify planck-2018-omega --by "James Unwin (owner)" --expected-hash 8d7b9c8f8d6672af440c6ae8b63347c3cd9f4b5e84b85c4bc8b9cde41ca9b71d` |  |

## 3. The records behind the portals' default verdicts (most portals first)

| record | portals gated | label on page | numbers on page | command | note |
|---|---|---|---|---|---|

## 4. The other records awaiting verification

| record | portals gated | label on page | numbers on page | command | note |
|---|---|---|---|---|---|

## 5. The gate, after the signatures

Run the README's example commands **without** `--unverified` and compare with their documented verdicts:

```
uv run adroit track1 --portal higgs_portal_scalar
uv run adroit track1 docs/dm13/axial_mediator.yaml --x m_med:10:10000 --y m_chi:1:2000
uv run adroit single-idea docs/dm13/vector_mediator.yaml --experiment "CDMS II Si (2013)" --masses 5:40:12
uv run adroit exclude L10 --isospin s --masses 10,100,1000
uv run adroit records list                            # ends with the verified count
```

The smallest set for the README's examples, beyond the re-signed records: `planck-2018-omega`, `planck-2018-pann`, `smodels-3.2.1`, `calore-2202.03076-pbar` and `cms-1806.00843-dijet`.
