from adroit.evaluation import citations


def test_both_forms_are_found_in_order() -> None:
    text = r"Z = 3.65\run{docs/dm6/lz_case_xenon.md} and 94.6% (run: docs/dm6_signal.md#2. The gate) then \run{a/b.json}"
    assert citations.citations(text) == ["docs/dm6/lz_case_xenon.md", "docs/dm6_signal.md", "a/b.json"]


def test_a_citation_to_a_missing_file_is_caught(tmp_path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "here.md").write_text("x")
    text = r"\run{docs/here.md#s} \run{docs/gone.md} (run: `docs/here.md`)"
    assert citations.missing(text, tmp_path) == ["docs/gone.md"]


def test_the_real_records_exist() -> None:
    assert citations.missing(r"\run{docs/dm10/gate.md} (run: docs/dm6_signal.md)") == []


def test_several_citations_may_share_the_parentheses() -> None:
    text = "(run: docs/a.md#2. One; run: docs/b.md)\n(run: `docs/c.json`)"
    assert citations.citations(text) == ["docs/a.md", "docs/b.md", "docs/c.json"]
