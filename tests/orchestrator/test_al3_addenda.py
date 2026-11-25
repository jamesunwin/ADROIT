"""The two addenda to the audit loop's cycle 3, repaired in cycle 4 (2026-11-16; the AL3 repair record of 2026-11-15).

The provider keys (``audit/claude_audit_2026-11-16_cycle3_addendum_security.md``):
- AL3-25: a key is stripped and checked where it is read; a command's error output never holds a configured key.
- AL3-26: only the provider's own endpoint is used unless another is allowed explicitly; the host is named.
- AL3-27: ``.env`` is read, never exported; no program ADROIT starts is given a credential.
- AL3-28: the export's check sees a key after a letter, a digit or ``%20``, folded, or of another service, and the
  workbench's downloads are checked too.
- AL3-29: the settings hold the keys as ``SecretStr``.
- AL3-30: copies of ``.env`` are ignored; no command shows a frame's variables; the wording.

Every key here is a fake sentinel made in the test; no real key or ``.env`` is read, no provider is called.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from adroit.core import config

FAKE_A = "sk-ant-api03-FAKE-" + "Ab1" * 20
FAKE_O = "sk-proj-FAKE" + "Cd2" * 20
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A fake ``.env`` of the test's own, read as the project's (only the reader is pointed at it: the project root,
    which data paths are cached against, is left alone); the settings read afresh, and restored after."""
    from adroit.agents import llm
    monkeypatch.setattr(config, "dotenv_file", lambda: dict(config._dotenv_at(str(tmp_path / ".env"))))
    monkeypatch.setattr(llm, "get_settings",        # the suite's frozen copy replaced by these, its runs kept here
                        lambda: config.get_settings().model_copy(update={"runs_dir": tmp_path / "runs"}))
    for name in config.PROVIDER_VARIABLES + ("ADROIT_ALLOWED_ENDPOINTS",):
        monkeypatch.delenv(name, raising=False)
    config.get_settings.cache_clear()
    config._dotenv_at.cache_clear()

    def write(text: str) -> None:
        (tmp_path / ".env").write_text(text)
        config.get_settings.cache_clear()
        config._dotenv_at.cache_clear()
    yield write
    config.get_settings.cache_clear()
    config._dotenv_at.cache_clear()


# --- AL3-27, AL3-29 ---------------------------------------------------------------------------------------------

def test_the_env_file_is_read_and_never_exported(project) -> None:
    project(f"ANTHROPIC_API_KEY={FAKE_A}\nOPENAI_API_KEY={FAKE_O}\nADROIT_EMBEDDINGS=hash\n")
    settings = config.get_settings()
    assert settings.anthropic_api_key.get_secret_value() == FAKE_A and settings.openai_api_key.get_secret_value() == FAKE_O
    assert "ANTHROPIC_API_KEY" not in os.environ and "OPENAI_API_KEY" not in os.environ
    assert config.env("EMBEDDINGS") == "hash"                        # a setting of .env still reaches ADROIT
    assert FAKE_A not in repr(settings) and FAKE_A not in settings.model_dump_json()           # AL3-29


def test_a_key_in_the_environment_is_taken_out_of_it_once_read(project, monkeypatch) -> None:
    project("")
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_A)
    monkeypatch.setenv("SOME_SERVICE_TOKEN", "fake-token-value")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-test")
    assert config.get_settings().anthropic_api_key.get_secret_value() == FAKE_A
    assert "ANTHROPIC_API_KEY" not in os.environ and "SOME_SERVICE_TOKEN" not in os.environ
    assert os.environ.get("ANTHROPIC_MODEL") == "claude-test"        # not a credential: left as it is


def test_no_program_adroit_starts_is_given_a_credential(project, monkeypatch) -> None:
    """DIAMX's launcher is not edited (``xenon.py``'s bytes are in the xenon modules' limit tables' fingerprint): like
    the protected packages', its environment is clean because it reads the settings, which take the credentials out of
    the process's environment, before it builds it. Every other launch site passes ``child_environment``."""
    project(f"ANTHROPIC_API_KEY={FAKE_A}\n")
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_O)                     # in the environment before the settings are read
    monkeypatch.setenv("SOME_SERVICE_TOKEN", "fake-token-value")
    from adroit.experiments import xenon
    capped = xenon.capped_environment()
    assert not [k for k in capped if config.CREDENTIAL.search(k) or k in config.PROVIDER_VARIABLES]
    assert FAKE_A not in capped.values() and FAKE_O not in capped.values()
    monkeypatch.setenv("LATER_API_KEY", "fake-later-value")          # set after the settings were read
    child = config.child_environment({"EXTRA_SECRET": "fake", "OMP_NUM_THREADS": "2", "ANTHROPIC_BASE_URL": "x"})
    assert not [k for k in child if config.CREDENTIAL.search(k) or k in config.PROVIDER_VARIABLES]
    assert child["OMP_NUM_THREADS"] == "2" and FAKE_A not in child.values()
    run = config.run_environment({"ADROIT_JOB_FOLDER": "f"})        # ADROIT's own run from the workbench: given them
    assert run["ANTHROPIC_API_KEY"] == FAKE_A and run["OPENAI_API_KEY"] == FAKE_O and "LATER_API_KEY" not in run


def test_a_child_started_by_a_launch_site_holds_no_key(project, tmp_path, monkeypatch) -> None:
    import subprocess
    import sys
    project(f"ANTHROPIC_API_KEY={FAKE_A}\n")
    config.get_settings()
    monkeypatch.setenv("LATER_API_KEY", "fake-later-value")          # set after the settings were read
    code = "import os; print(sorted(k for k in os.environ if 'API_KEY' in k))"
    found = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60,
                           env=config.child_environment(), check=True)
    assert found.stdout.strip() == "[]"


# --- AL3-25 -------------------------------------------------------------------------------------------------------

def test_a_key_with_surrounding_whitespace_is_stripped(project) -> None:
    project(f'ANTHROPIC_API_KEY="{FAKE_A} "\n')
    from adroit.agents import llm
    client = llm.LLMClient(model="claude-opus-5-5")
    assert config.get_settings().anthropic_api_key.get_secret_value() == FAKE_A and client.missing_credentials == ""


@pytest.mark.parametrize("bad", [FAKE_A[:20] + " " + FAKE_A[20:], FAKE_A[:20] + "\x00" + FAKE_A[20:],
                                 FAKE_A[:20] + "\t" + FAKE_A[20:], "\u201c" + FAKE_A + "\u201d",
                                 FAKE_A[:20] + "\u00e9" + FAKE_A[20:]],
                         ids=["space", "nul", "tab", "typographic quotes", "non-ascii"])   # no key in an id; AL4-14(a)
def test_a_key_holding_a_space_or_a_control_character_is_refused_by_its_name(project, bad) -> None:
    from adroit.agents import llm
    client = llm.LLMClient(model="claude-opus-5-5", api_key=bad)
    assert "ANTHROPIC_API_KEY" in client.missing_credentials and bad.split()[0][:10] not in client.missing_credentials
    with pytest.raises(llm.MissingCredentials) as refused:
        llm._dispatch(client, {"model": "claude-opus-5-5"}, lambda **k: pytest.fail("sent"))
    assert FAKE_A[:20] not in str(refused.value)


def test_a_commands_error_output_never_holds_a_configured_key(project, capsys) -> None:
    project(f"ANTHROPIC_API_KEY={FAKE_A}\n")
    config.get_settings()
    from adroit.orchestrator import cli

    app = cli._Commands(pretty_exceptions_show_locals=False)

    @app.command()
    def boom() -> None:
        raise RuntimeError(f"Illegal header value b'{FAKE_A} '")

    @app.command()
    def other() -> None:
        pass
    with pytest.raises(SystemExit) as stopped:
        app(["boom"])
    err = capsys.readouterr().err
    assert stopped.value.code == 1 and "RuntimeError" in err and "<ANTHROPIC_API_KEY>" in err and FAKE_A not in err


# --- AL3-26 -------------------------------------------------------------------------------------------------------

def test_another_endpoint_is_refused_unless_allowed(project, monkeypatch) -> None:
    project(f"ANTHROPIC_API_KEY={FAKE_A}\nANTHROPIC_BASE_URL=http://127.0.0.1:9\nOPENAI_API_KEY={FAKE_O}\n"
            "OPENAI_BASE_URL=http://gateway.example/v1\n")
    from adroit.agents import llm
    anthropic_client, openai_client = llm.LLMClient(model="claude-opus-5-5"), llm.OpenAIClient(model="gpt-5.6-sol")
    for client, own in ((anthropic_client, "https://api.anthropic.com"), (openai_client, "https://api.openai.com/v1")):
        assert "BASE_URL points" in client.missing_credentials and "ADROIT_ALLOWED_ENDPOINTS" in client.missing_credentials
        assert str(client._client.base_url).rstrip("/") == own              # never built for the refused one
        with pytest.raises(llm.MissingCredentials):
            llm._dispatch(client, {"model": client.model}, lambda **k: pytest.fail("sent"))
    monkeypatch.setenv("ADROIT_ALLOWED_ENDPOINTS", "http://127.0.0.1:9")
    allowed = llm.LLMClient(model="claude-opus-5-5")
    assert allowed.missing_credentials == "" and str(allowed._client.base_url).rstrip("/") == "http://127.0.0.1:9"
    assert allowed.endpoint == "127.0.0.1:9"


def test_the_host_is_named_beside_the_model_and_the_cost(project, tmp_path) -> None:
    import json
    from types import SimpleNamespace
    from adroit.agents import llm
    project(f"ANTHROPIC_API_KEY={FAKE_A}\n")
    assert " at api.anthropic.com;" in llm.preflight_line("claude-opus-5-5", 0.01, 0.0, 1.0, "api.anthropic.com")
    shown = []
    inner = llm.LLMClient(model="claude-opus-5-5", client=SimpleNamespace(messages=SimpleNamespace(create=None)))
    inner.endpoint = "gateway.example"
    with llm.preflight(shown.append):
        budgeted = llm.BudgetedLLMClient(inner, dollar_budget=1.0, ledger_path=tmp_path / "paid.jsonl")

    def send(**request):
        raise RuntimeError("refused by the stub")
    with pytest.raises(RuntimeError):
        budgeted.request({"model": "claude-opus-5-5", "max_tokens": 10, "messages": [{"role": "user", "content": "x"}]},
                         send)
    assert shown and " at gateway.example;" in shown[0]
    rows = [json.loads(line) for line in (tmp_path / "paid.jsonl").read_text().splitlines()]
    assert rows[0]["state"] == "reserved" and rows[0]["endpoint"] == "gateway.example"


# --- AL3-28 -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text", [FAKE_A, "A" + FAKE_A, "7" + FAKE_A, "%20" + FAKE_A, FAKE_A[:14] + "\n" + FAKE_A[14:],
                                  FAKE_A[:14] + "\\n" + FAKE_A[14:], "hf_" + "Fake0" * 7, "ghp_" + "Fake0" * 7,
                                  "AIza" + "F" * 35, "xai-" + "Fake0" * 7, "x" + "sk-" + "Ab1" * 12],
                         ids=["whole", "after-letter", "after-digit", "after-percent", "folded", "json-folded", "hf",
                              "github", "google", "xai", "long-sk"])   # a test's id holds no key: ids reach command
def test_the_exports_check_sees_a_key_wherever_it_is(text) -> None:     # lines, logs and the exports that record them
    from adroit.evidence import archive
    assert archive.credential_like(text.encode())


def test_the_exports_check_passes_ordinary_words_and_names_more_fields() -> None:
    from adroit.evidence import archive
    assert not archive.credential_like(b"the task-force and risk-assessment-of-everything and disk-usage-statistics-table")
    for field in ("x-api-key", "token", "password", "secret"):
        with pytest.raises(ValueError, match="credentials"):
            archive.refuse_credentials("r.json", ('{"' + field + '": "value"}').encode())


def test_the_workbenchs_downloads_are_checked() -> None:
    from adroit.evidence import exports
    with pytest.raises(ValueError, match="credential-like"):
        exports.archive({"request.json": ('{"note": "' + FAKE_A + '"}').encode()})
    assert exports.archive({"table.csv": b"mass,limit\n10,2\n"})


# --- AL3-30 -------------------------------------------------------------------------------------------------------

def test_copies_of_env_are_ignored_and_the_example_is_not() -> None:
    lines = (ROOT / ".gitignore").read_text().splitlines()
    assert ".env" in lines and ".env.*" in lines and "!.env.example" in lines


def test_no_command_shows_a_frames_variables() -> None:
    """Every Typer app in the package says ``pretty_exceptions_show_locals=False`` itself: the locked Typer's default
    is False, but an older one within ``typer>=0.12`` may not be, so the default is not relied on."""
    import ast
    calls = []
    for path in sorted((ROOT / "adroit").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call) and ast.unparse(node.func) in ("typer.Typer", "Typer"):
                calls.append((path.name, {k.arg: ast.unparse(k.value) for k in node.keywords}))
    assert len(calls) >= 11
    for name, kw in calls:
        assert kw.get("pretty_exceptions_show_locals") == "False", name


def test_the_missing_key_message_speaks_of_the_project_folder() -> None:
    from adroit.agents import llm
    text = llm.missing_key("anthropic")
    assert "ADROIT project folder" in text and "checkout" in text and "ANTHROPIC_API_KEY" in text


# --- AL3-31 -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("x", [-0.69866, -0.70, -0.68, -0.72, -0.60, 1.0])
def test_an_elements_isospin_factor_is_its_isotopes(x) -> None:
    """Xenon's suppression for c_n/c_p = x, as the comparison takes it, against the package's own rate (O₁, 100 GeV,
    5–50 keV; ``rates.differential_rate`` over ``targets.target("Xe")``): within 5% (one Z/A had given 6 × 10⁻⁷ for
    the rate's 1.3 × 10⁻⁴ at −0.70, 10⁻¹¹ at −0.69866)."""
    import numpy as np
    from adroit.core.dm_state import DarkMatterParticle, HaloModel, InteractionModel, NuclearModel, OperatorCoefficient
    from adroit.parameter_space import dd_channels
    from adroit.physics import conventions, rates, targets
    energies, particle, xenon = np.linspace(5.0, 50.0, 181), DarkMatterParticle(mass_gev=100.0), targets.target("Xe")
    c = conventions.c1_from_sigma_si(1e-45, 100.0)

    def total(cp: float, cn: float) -> float:
        layer = list(InteractionModel.model_fields["layer"].annotation)[0]
        interaction = InteractionModel(name="O1", layer=layer,
                                       coefficients=[OperatorCoefficient(operator=1, proton=cp, neutron=cn)])
        rate = rates.differential_rate(energies, particle, interaction, xenon, HaloModel(), NuclearModel.helm).rate
        return float(np.trapezoid(np.asarray(rate), energies))
    true = total(c, x * c) / total(c, c)
    assert dd_channels.element_coupling_squared("Xe", 1.0, x, 100.0) == pytest.approx(true, rel=0.05)


# --- AL3-32 -------------------------------------------------------------------------------------------------------

def test_a_contact_exclusion_through_a_light_mediator_is_undecided(monkeypatch) -> None:
    from adroit.parameter_space import scan
    from adroit.parameter_space.classes import Point, ScalarClass, Spin1Class
    from adroit.parameter_space.portals.higgs import SingletMixing
    from adroit.parameter_space.portals.vector import ChargedZPrime, DarkPhoton
    excluded = scan.DirectDetection(kind="SI", sigma_cm2=1e-44, limit_cm2=1e-46, ratio=100.0, excluded=True)
    allowed = excluded.model_copy(update={"ratio": 0.1, "excluded": False})
    light, heavy = Point(m_chi=20.0, m_med=0.02, g_chi=1e-6, g_q=1e-6), Point(m_chi=20.0, m_med=1.5, g_chi=1e-6, g_q=1e-6)
    for cls in (Spin1Class(), ScalarClass(), ChargedZPrime(charges="Lmu-Ltau"), DarkPhoton()):
        assert scan._light_mediator(cls, light) and not scan._light_mediator(cls, heavy), cls
    assert scan._light_mediator(SingletMixing.model_construct(), light)
    monkeypatch.setattr(scan, "_direct_detection", lambda cls, p, si=(): excluded)
    found = scan.direct_detection(Spin1Class(), light)
    assert found.excluded is None and found.ratio is None and scan.LIGHT_MEDIATOR in found.pending
    assert scan.direct_detection(Spin1Class(), heavy) == excluded                     # at 1.5 GeV, as before
    monkeypatch.setattr(scan, "_direct_detection", lambda cls, p, si=(): allowed)
    kept = scan.direct_detection(Spin1Class(), light)                    # the contact rate is above the true one
    assert kept.excluded is False and kept.ratio is None and not kept.pending


# --- AL3-33 -------------------------------------------------------------------------------------------------------

def test_one_definition_of_the_suns_and_the_dwarfs_speeds() -> None:
    """The Sun's at the core's thermal value for the mass (2.0 × 10⁻⁴ at 200 GeV), the dwarfs' √6 × 10 km/s; Track
    1's scan and Path 2's verdicts take the same (they had used 10⁻³ and 10⁻⁴, 10⁻⁴ and 2 × 10⁻⁵)."""
    from adroit.constraints import speeds, verdicts
    from adroit.parameter_space import scan
    assert speeds.sun_speed(200.0) == pytest.approx(2.0e-4, rel=0.02)
    assert speeds.DWARF_SPEED == pytest.approx(8.17e-5, rel=0.01)
    assert scan.sun_speed is verdicts.sun_speed is speeds.sun_speed and scan.DWARF_SPEED == verdicts.DWARF_SPEED


def test_icecube_reads_the_rate_at_the_suns_speed_for_the_mass(monkeypatch) -> None:
    from types import SimpleNamespace
    from adroit.constraints import capture, speeds
    from adroit.core.dm_state import InteractionModel
    from adroit.parameter_space import scan
    seen = []

    class Model:
        def self_conjugate(self):
            return True

        def sigma_v_today(self, p, speed):
            seen.append(speed)
            return {"b": 1e-26}

        def interaction(self, p):
            return InteractionModel(name="fixture", layer="nonrelativistic", coefficients=[])
    monkeypatch.setattr(capture, "available", lambda: True)
    monkeypatch.setattr(capture, "capture_rate", lambda particle, interaction, halo=None: 1e20)
    scan._icecube(Model(), SimpleNamespace(m_chi=200.0))
    assert seen and seen[0] == pytest.approx(speeds.sun_speed(200.0))


# --- AL3-34 -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("mass", [2.5e4, 4e4, 1e5])
def test_the_higgs_width_above_its_table_follows_the_partial_widths(mass) -> None:
    from adroit.constraints import higgs
    assert float(higgs.width(mass)) == pytest.approx(sum(higgs.partial_widths(mass).values()), rel=1e-9)
    assert float(higgs.width(4e4) / higgs.width(2e4)) == pytest.approx(8.0, rel=0.01)


# --- AL3-35 -------------------------------------------------------------------------------------------------------

def test_the_halo_alternatives_change_the_searchs_own_halo(monkeypatch) -> None:
    """A search published with the older 220/232/544 km/s convention, as CDMS II Si is: the alternative "v0 = 220 km/s"
    is its own halo, unchanged (the default SHM's had been changed instead, whose Earth's speed is not the search's:
    × 1.23 for CDMS II Si)."""
    from types import SimpleNamespace
    from adroit.experiments.base import standard_halo
    from adroit.orchestrator import signal
    own = standard_halo(220.0, 232.0, 544.0)
    module = SimpleNamespace(conventions=lambda: SimpleNamespace(halo=own))
    varied = {}
    monkeypatch.setattr(signal, "fixed_halo", lambda: None)
    monkeypatch.setattr(signal, "_sensitivity", lambda module, c, z, mu, what, halo=None, model=None:
                        varied.__setitem__(what, halo) or "")
    signal._flags(module, SimpleNamespace(card_id=None), 2.0, 1.0)
    assert varied["halo (v0 = 220 km/s)"] == own
    assert varied["halo (v_esc = 600 km/s)"] == own.model_copy(update={"v_esc_km_s": 600.0})


# --- AL3-36 -------------------------------------------------------------------------------------------------------

def test_the_envelope_sorts_its_masses_and_leaves_a_gap_where_a_limit_is_missing() -> None:
    import math
    from types import SimpleNamespace
    from adroit.orchestrator.exclusion import ExclusionResult

    def module(masses, limits):
        return SimpleNamespace(masses_gev=masses, mu_up=limits, experiment="A", omission_reason=lambda i: "")
    result = SimpleNamespace(per_module=[module([1000.0, 100.0, 10.0], [3.0, 2.0, 1.0])])
    _, best, _ = ExclusionResult.envelope(result, [10.0, 100.0, 1000.0], validated_only=False)
    assert list(best) == [1.0, 2.0, 3.0]
    gap = SimpleNamespace(per_module=[module([10.0, 20.0, 30.0], [1.0, math.inf, 1.0])])
    _, best, source = ExclusionResult.envelope(gap, [10.0, 15.0, 20.0, 30.0], validated_only=False)
    assert best[0] == 1.0 and math.isinf(best[1]) and math.isinf(best[2]) and source[1] == source[2] == ""
