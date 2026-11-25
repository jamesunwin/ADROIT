"""A calculation left running after its run has ended, on the workbench's pages (a feature audit's ID-01,
2026-11-10; ``tests/ui/test_calculation_ownership.py``)."""

from __future__ import annotations

import signal

import pytest

pytest.importorskip("nicegui")

from nicegui.testing import User  # noqa: E402

from tests.ui.test_calculation_ownership import left  # noqa: E402,F401  (the fixture)


async def test_the_live_view_and_activity_offer_cancel_for_a_calculation_left_running(user: User, left):  # noqa: F811
    """The pages: the live view names the calculation and shows Cancel although the run has ended; Activity's card
    offers Cancel, which stops it, and the live view then hides both."""
    import asyncio
    from adroit.ui.app import build_pages
    folder, process = left
    build_pages(folder.parent)
    await user.open("/live?path=scan")
    await user.should_see(marker="cancel_run")
    await user.should_see("Its calculation still runs")
    await user.open("/activity")
    await user.should_see(marker="cancel_left")
    user.find(marker="cancel_left").click()
    assert process.wait(timeout=10) == -signal.SIGTERM
    await user.open("/live?path=scan")
    await asyncio.sleep(1.3)
    await user.should_not_see(marker="cancel_run")
    await user.should_not_see("Its calculation still runs")
