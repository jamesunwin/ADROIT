"""R9: the text corrections the release audit found for nine verified records (a development receipt (record_corrections),
part 2), ready to apply when their verifier re-reads and re-signs them.

Applying a correction changes a record's scientific content, so its signature becomes stale and the record awaits
verification again until it is re-signed (`adroit records verify`). Nothing here is applied without `--apply`.

    uv run python docs/r9/apply_corrections.py            # show each change ($0)
    uv run python docs/r9/apply_corrections.py --apply    # write them into records.yaml, then re-verify each record
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECORDS = ROOT / "adroit" / "constraints" / "data" / "records.yaml"

WIDTH_OLD = "- the minimal width (decays to quarks, leptons and dark matter only)\n"
WIDTH_NEW = ('- "the minimal width (decays to quarks, leptons and dark matter only): implied by the LHC Dark Matter Working '
             'Group recommendation the CMS report cites, not stated in the report itself"\n')
CORRECTIONS: list[tuple[str, str, str]] = [            # (record id, exact old text, new text)
    ("cms-2405.13778-V1", WIDTH_OLD, WIDTH_NEW),       # one YAML anchor (&cms_spin1): also A1, V2 and A2
    ("icecube-1612.05949-sd", "- capture and annihilation in equilibrium in the Sun\n",   # one YAML anchor: also -si
     '- "capture and annihilation in equilibrium in the Sun; the 90% CL curves include the inflation for systematic '
     'uncertainties (conservative); erratum: Eur. Phys. J. C 79 (2019) 214, doi:10.1140/epjc/s10052-019-6702-y"\n'),
    ("fermi-1503.02641-dsph", "annihilation entirely into the named channel (a mixture is compared channel by channel)",
     "annihilation entirely into the named channel (Track 1 uses this record for a pure channel only, and a mixture "
     "goes to the spectral dwarf likelihood, fermi-2311.04982-spectral)"),
    ("lep-hep-ex-0509008-zinv", '{arxiv: "hep-ex/0509008", page: 172, label: "section 7.2.2"}',
     '{arxiv: "hep-ex/0509008", page: 173, label: "section 7.2.2 (the limit is on page 173; the section starts on page 172)"}'),
]


def entry_span(text: str, record_id: str) -> tuple[int, int]:
    start = text.index(f"  - id: {record_id}\n")
    following = text.find("\n  - id: ", start + 1)
    return start, len(text) if following < 0 else following


def main(argv: list[str]) -> int:
    text = RECORDS.read_text()
    changed = text
    for record_id, old, new in CORRECTIONS:
        start, end = entry_span(changed, record_id)
        entry = changed[start:end]
        if new in entry:
            print(f"{record_id}: already applied")
            continue
        if entry.count(old) != 1:
            print(f"{record_id}: the expected text was not found once; the record has changed since R4, so review it by hand")
            return 1
        changed = changed[:start] + entry.replace(old, new) + changed[end:]
        print(f"{record_id}:\n  - {old}\n  + {new}")
    if "--apply" in argv:
        import yaml
        yaml.safe_load(changed)                                   # never write a file that does not parse
        RECORDS.write_text(changed)
        print("written: re-verify each record above with `adroit records verify ID --by NAME`")
    else:
        print("(dry run: add --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
