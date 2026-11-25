"""The finder of the documentation the public release must keep (``scripts/public_release_docs.py``)."""

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FINDER = runpy.run_path(str(ROOT / "scripts" / "public_release_docs.py"))
mentions, resolve, tracked_docs, sources = (FINDER[n] for n in ("mentions", "resolve", "tracked_docs", "sources"))

TRACKED = ["docs/dm3/validation_results.json", "docs/dm13/a.yaml", "docs/dm13/b.yaml",
           "docs/receipts/clean_install_1.md", "docs/receipts/other.md", "docs/notes.md"]


def test_a_path_written_as_one_string_is_found():
    assert ("docs/notes.md", False) in mentions('see "docs/notes.md" for the reason')


def test_a_path_built_in_pieces_is_found():
    found = mentions('STORE = Path(__file__).parents[2] / "docs" / "dm3" / "validation_results.json"')
    assert ("docs/dm3/validation_results.json", False) in found


def test_a_name_bound_to_the_docs_folder_is_followed_in_the_same_file():
    found = mentions('DOCS = ROOT / "docs"\nx = DOCS / "dm13" / "a.yaml"\n')
    assert ("docs/dm13/a.yaml", False) in found


def test_a_part_that_is_not_a_string_keeps_the_fixed_prefix_and_is_marked_cut():
    found = mentions('out = ROOT / "docs" / "receipts" / f"clean_install_{stamp}.md"')
    assert ("docs/receipts/clean_install_", True) in found


def test_files_folders_and_unmatched_mentions_are_kept_apart():
    required, folders, review, unmatched = resolve(
        {("docs/dm3/validation_results.json", False), ("docs/dm13", False),
         ("docs/receipts/clean_install_", True), ("docs/gone.md", False), ("docs", False)}, TRACKED)
    assert required == {"docs/dm3/validation_results.json", "docs/receipts/clean_install_1.md"}
    assert folders == {"docs/dm13": 2}
    assert unmatched == {"docs/gone.md"}
    assert len(review) == 1


def test_a_glob_takes_every_file_it_matches():
    required, *_ = resolve({("docs/dm13/*.yaml", False)}, TRACKED)
    assert required == {"docs/dm13/a.yaml", "docs/dm13/b.yaml"}


def test_on_this_repository_the_files_the_code_reads_are_kept():
    tracked = tracked_docs()
    found: set[tuple[str, bool]] = set()
    for source in sources():
        found |= mentions(source.read_text(errors="replace"))
    required, folders, _, _ = resolve(found, tracked)
    assert {"docs/dm3/validation_results.json", "docs/halo_constraint_support.md",
            "docs/version_matrix.md", "docs/dm6/lz_case.json"} <= required
    assert {"docs/dm10/results", "docs/dm13", "docs/examples"} <= set(folders)
