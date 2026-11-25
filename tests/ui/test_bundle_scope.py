"""The bundle viewer states the widest search's significance first (the auditor's post-review recheck 2, PT-01): an agent
search's study, exported and opened, leads with its own significance and names the global fields as the fixed scan's.
Offline: the toy searches of halo phase 1 and a fake model."""
from __future__ import annotations

from nicegui.testing import User

from adroit.agents.llm import FakeLLMClient
from adroit.agents.signal_search import Interpretation, SearchChoices
from adroit.orchestrator import signal, signal_search
from tests.orchestrator.test_halo_phase1 import _request, toys  # noqa: F401  (the fixture)
from tests.orchestrator.test_signal_search import _published


async def test_an_exported_agent_search_leads_with_its_own_significance(user: User, tmp_path, toys):  # noqa: F811
    from adroit.evidence.archive import export_run
    from adroit.ui.app import build_pages
    fixed = signal.run(_request())
    searched = signal_search.run(fixed, FakeLLMClient([SearchChoices(stop=True, reason="done"),
                                                        Interpretation(text="As given.")]),
                                 signal_search.SearchSettings(rounds=1))
    widened = searched.model_copy(update={"agent_search": searched.agent_search.model_copy(
        update={"global_z": 0.42, "global_p_toys": 0.34})})
    folder = _published(tmp_path, widened)
    bundle = tmp_path / "study.zip"
    export_run(folder, bundle)
    build_pages(tmp_path / "runs")
    await user.open(f"/bundle?path={bundle}")
    await user.should_see("hashes agree")
    await user.should_see("Global significance over everything searched and tried, the agent-led search's variants "
                          "included: 0.42σ (p = 3.40e-01). The global significance given apart (global_z, global_p_toys, "
                          "global_method) is the fixed scan's, over its own candidates.")
