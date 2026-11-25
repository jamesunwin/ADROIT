"""The acceptance gate (the consolidation plan's M4): each journey module's ``SUBSTITUTED`` table, printed after the
run (the release receipt carries it: ``scripts/release_checks.substitutions``)."""
import sys


def pytest_terminal_summary(terminalreporter) -> None:
    rows = [(name.rsplit(".", 1)[1], what, how) for name, module in sorted(sys.modules.items())
            if name.startswith("tests.ui.acceptance.") and isinstance(getattr(module, "SUBSTITUTED", None), dict)
            for what, how in module.SUBSTITUTED.items()]
    if rows:
        terminalreporter.write_sep("-", "what the journeys substitute")
        for journey, what, how in rows:
            terminalreporter.write_line(f"SUBSTITUTED | {journey} | {what} | {how}")
