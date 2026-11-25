"""Every record carries the reviewer's notes section (the owner, 2026-10-13), new ones included."""

import re

from adroit.constraints import database


def test_every_record_has_a_notes_section() -> None:
    blocks = re.split(r"^  - id: ", database.RECORDS.read_text(), flags=re.M)[1:]
    assert len(blocks) == len(database.records())
    missing = [b.split()[0] for b in blocks if not re.search(r"^    notes:", b, re.M)]
    assert not missing, f"records without a notes section: {missing}"


def test_the_bbn_records_notes_say_where_each_value_is() -> None:
    notes = database.record("sabti-1910.01649-bbn").notes
    assert "Table II, page 10" in notes and "95.4% CL" in notes and "eq. (3.15)" in notes
