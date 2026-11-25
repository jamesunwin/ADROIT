"""A personal-library revision as it was written before 2026-11-21, when ``Catalog.save`` checked the structural audit
alone: a model saved then with a missing value, or one its engine does not compute, is legacy data that must stay
readable. Today's ``Catalog.save`` refuses such a model (the auditor's UM-02), so a test that needs one writes it here, with
the usability check of that era (none), never through today's rule."""

from adroit.library import personal


def saved_before_the_rule(catalog: personal.Catalog, spec, approval, **kwargs) -> personal.ModelRevision:
    """``catalog.save`` without the usability check, as it was before 2026-11-21; the revision file is the same format."""
    original = personal.usable
    personal.usable = lambda *a, **k: personal.Usability(ok=True)
    try:
        return catalog.save(spec, approval, **kwargs)
    finally:
        personal.usable = original
