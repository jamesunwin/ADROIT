"""The ADROIT command line: the two pipelines.

    adroit exclude L10 --isospin s --masses 10,100,1000   # Path 1: a library card's exclusion limits
    adroit signal --experiment "LZ extended window (2026)"   # Path 2: explain a search's events
    adroit lagrangian docs/dm8/v1_model.yaml                 # Path 1 for a bespoke model (DM8)
    adroit agents docs/dm6/lz_case.json --budget 2           # DM9's agents on a finished result (paid)
    adroit eval injection                                    # DM10: a suite's development half
    adroit idea --fields model.yaml --eft 6                  # DM12: most general Lagrangian and audit
    adroit track1 model.yaml --x m_med:10:10000 --y m_chi:1:2000   # DM13: scan, verdict, plots (--literature: arXiv)
    adroit portals                                           # the portal library (18 portals, 3 DM13 models)
    adroit track1 --portal higgs_portal_scalar               # one portal at its benchmark, in its plane
    adroit anomaly check my_search.yaml                      # DM14: an anomaly record's consistency
    adroit signal --experiment record:my_search.yaml --model m.yaml   # DM14: a user's model in Path 2
    adroit single-idea m.yaml --experiment "CDMS II Si (2013)"         # DM14: one idea against an anomaly
    adroit promote runs/signal_X class:0                     # DM14: recursion into Track 1 studies
    adroit studies                                           # DM14: every study, as a tree
    adroit setup                                             # DM11: external tools and data, and their licences
    adroit workbench                                         # DM15: the two tracks in a local web page

Environment: ``ADROIT_RUNS_DIR`` points the results at another directory (see
:mod:`adroit.core.config`). The inherited pipeline's commands (run, resume,
report, bench, ui, brief, export) were retired with it at DM6; the tag
``pre-retirement`` holds them.
"""

from __future__ import annotations

from pathlib import Path
from functools import wraps
import json
import math
from uuid import uuid4

import typer

from adroit.core.config import get_settings
from adroit.core.receipts import BUDGET_STOPPED
from adroit.evidence.cli import app as evidence_app
from adroit.theory.cli import app as theory_app
from adroit.constraints.review_cli import register as register_review_commands
from adroit.orchestrator.catalog_cli import app as catalog_app
from adroit.orchestrator.experimental_cli import app as experimental_app
from adroit.orchestrator.discovery_cli import app as discovery_app
from adroit.orchestrator.reanalysis_cli import app as reanalysis_app
from adroit.orchestrator.fog_cli import app as fog_app
from adroit.orchestrator.ledger_cli import app as ledger_app      # a paid journal's recovery (D-7)

class _Commands(typer.Typer):
    """The command line. A missing external input (a data release, ``experiments.base.DataUnavailable``, or a tool,
    ``fetch.MissingInput``) ends a command with what is missing and the setup command that supplies it, and exit
    status 1, not a traceback (the release audit's PR23-02, 2026-10-23); a provider's missing API key, with the
    variable to set, exit status 2 (``llm.MissingCredentials``; the workflow audit's WA-04, 2026-10-24); any other
    error is shown as it is, its traceback with every configured key's text replaced by its variable's name, exit
    status 1 (the security addendum's AL3-25, 2026-11-16: a key a provider's library had refused was printed whole).
    No app shows a frame's variables (``pretty_exceptions_show_locals=False``: AL3-30)."""

    def __call__(self, *args, **kwargs):
        from adroit.agents.llm import MissingCredentials
        from adroit.core.durable import DamagedRecord
        from adroit.experiments.base import DataUnavailable
        from adroit.external.fetch import MissingInput
        from adroit.orchestrator.stops import INPUT_STOPPED
        try:
            return super().__call__(*args, **kwargs)
        except (MissingInput, DataUnavailable) as error:
            typer.echo(f"Error: {_missing(error)}", err=True)
            raise SystemExit(1) from None
        except MissingCredentials as error:
            typer.echo(f"Error: {error}", err=True)
            raise SystemExit(INPUT_STOPPED) from None
        except DamagedRecord as error:              # a record the command depends on cannot be read (M3)
            typer.echo(f"Error: {error}", err=True)
            raise SystemExit(1) from None
        except Exception as error:      # any other: its traceback as it is, but no configured key's text (AL3-25)
            import traceback
            text = "".join(traceback.format_exception(error))
            try:
                from adroit.core.config import redacted
                text = redacted(text)
            except Exception:           # noqa: BLE001 - the settings themselves failed: nothing was read to hide
                pass
            typer.echo(text.rstrip("\n"), err=True)
            raise SystemExit(1) from None


def _missing(error: Exception) -> str:
    """A missing input's message, with the setup command for a data release (``DataUnavailable`` names the manifest
    item as ``fetch(<name>)``; experiments/base.py is left as it is, since the stored limit tables and the native
    certificate fingerprint it)."""
    import ast
    import re
    from adroit.external import fetch
    found = re.search(r"fetch\((.+)\)$", str(error))
    if found is None:
        return str(error)
    try:
        item = ast.literal_eval(found.group(1))
        return f"the data release {item!r} is not installed: {fetch.how_to_get(item)}"
    except (ValueError, SyntaxError, KeyError):
        return str(error)


app = _Commands(pretty_exceptions_show_locals=False, help="ADROIT: Agentic Dark matter Reinterpretation and Operator Inference Toolkit", add_completion=False)
app.add_typer(evidence_app, name="evidence")
app.add_typer(theory_app, name="theory")
app.add_typer(catalog_app,name='models')
app.add_typer(experimental_app,name='experiments')
app.add_typer(reanalysis_app,name='reanalyse')
app.add_typer(discovery_app,name='constraints')
app.add_typer(fog_app,name='fog')
app.add_typer(ledger_app,name='ledger')


@app.callback()
def _usage(ctx: typer.Context) -> None:
    # the usability sessions' opt-in command log (ADROIT_USAGE_LOG; off by default): a command's name and time only
    from adroit.evaluation import usage_log
    usage_log.begin(ctx)


def _runs_dir() -> Path:
    return get_settings().runs_dir


def _stop_folder(destination) -> Path:
    """Where a budget stop's partial artifact goes: the command's output folder; beside it, ``<stem>_budget_stop``,
    where the command's output is a file (``anomaly draft``'s YAML record: a stop had made a directory of that name,
    and the record could not then be written there); without one, a new folder in runs/."""
    if not destination:
        return _runs_dir() / f"budget_stop_{uuid4().hex}"
    path = Path(destination)
    return path.with_name(f"{path.stem}_budget_stop") if path.suffix.lower() in (".yaml", ".yml", ".json") else path


def _budget_boundary(function):
    """Show each paid request's preflight (hard rule 6: the model, the hard cap and the reserved cost, before
    dispatch); write a partial command artifact when a request cannot fit the budget, and exit with the
    budget-stop code (3), so that a script never reads a stopped command as a success."""
    from adroit.orchestrator.preflight import paid_command
    shown = paid_command(function)

    @wraps(function)
    def guarded(*args, **kwargs):
        from adroit.agents.llm import BudgetExceeded
        try:
            return shown(*args, **kwargs)
        except BudgetExceeded as error:
            import json
            from adroit.evidence.build import publish
            from adroit.orchestrator.preflight import run_attempt
            folder = _stop_folder(kwargs.get("out"))
            folder.mkdir(parents=True, exist_ok=True)
            result = {"status": "budget_stopped", "command": function.__name__,
                      "committed_usd": error.spent, "budget_usd": error.budget,
                      "next_request_reservation_usd": error.required,
                      "paid_response_ledger": error.ledger_path, **_committed_parts(error),
                      **({"attempt": run_attempt()} if run_attempt() else {})}   # its run (DE-01)
            text = f"{error}. Partial results: {folder}; paid responses: {error.ledger_path}"
            # whole or not at all (the cost is read from it), its report bound to it (the auditor's CY recheck, CZ-02)
            publish(folder / "result.json", json.dumps(result, ensure_ascii=False, allow_nan=True).encode(), result,
                    lambda envelope: text + "\n", evidence=False)
            typer.echo(text)
            raise typer.Exit(BUDGET_STOPPED) from None
    return guarded


@app.command()
def reassess(study: str = typer.Argument(..., help="a saved study's folder"),
             out: str = typer.Option("", "--out", help="folder for the new study (default: <study>_reassessed)"),
             budget: int = typer.Option(12, "--budget", min=1, max=64,
                                        help="Constrain a model: full calculations per reassessed point")) -> None:
    """Calculate what a saved study lacks, nothing else, into a new child study: Explain a signal, the signal
    requirement on its plane; Constrain a model, the halo work of each thermal point whose halo coverage is incomplete,
    its saved evaluation reused (docs/validation_and_audits.md). $0."""
    from adroit.orchestrator.reassess import next_free, reassess as run
    source = Path(study)
    folder, report = run(source, Path(out) if out else next_free(source.with_name(source.name + "_reassessed")),
                         budget)
    typer.echo(report[:4000])
    typer.echo(f"written to {folder}")


@app.command()
def exclude(card: str = typer.Argument(..., help="a library card: O1, L10, M_vector, ..."),
            isospin: str = typer.Option("", "--isospin",
                                        help="s or v for an operator or Lagrangian card, at unit coupling 1/m_v²"),
            values: str = typer.Option("", "--values", help="card parameters, as name=value,name=value"),
            masses: str = typer.Option("10,30,100,300,1000", "--masses", help="GeV, comma-separated"),
            splitting: float = typer.Option(0.0, "--splitting", help="mass splitting δ in keV"),
            modules_: str = typer.Option("", "--modules",
                                         help="experiment modules, comma-separated (default: all)"),
            out: str = typer.Option("", "--out", help="folder for the result (default: runs/exclusion_<card>)")) -> None:
    """Path 1 (DM5): a library card's limits in every experiment module, a plot and a report. $0."""
    from adroit.orchestrator import runs
    folder, report = runs.exclusion(card, isospin, runs.parse_values(values),
                                    [float(m) for m in runs.parse_list(masses)], splitting,
                                    runs.parse_list(modules_), Path(out) if out else None)
    typer.echo(report)
    typer.echo(f"written to {folder}")


@app.command()
def signal(experiment: str = typer.Option(..., "--experiment",
                                          help="the search whose events to explain, e.g. 'LZ extended window (2026)'"),
           null_modules: str = typer.Option(
               "CRESST-III 2019,CDMSlite Run 2,PICO-60 C3F8 (2019),DEAP-3600 (2019)",
               "--null", help="null experiments to combine with, comma-separated"),
           leaders: int = typer.Option(8, "--leaders", help="degeneracy classes carried forward"),
           toys: int = typer.Option(200_000, "--toys", help="background-only toys"),
           model: list[Path] = typer.Option([], "--model", help="a user's typed model (YAML), repeatable (DM14)"),
           masses: str = typer.Option("", "--masses", help="the users' models' masses: low:high:n (logarithmic), or "
                                                           "comma-separated (GeV)"),
           with_library: bool = typer.Option(False, "--with-library", help="the library's space beside --model"),
           unverified: bool = typer.Option(False, "--unverified", help="accept records no person has verified"),
           require_style: list[str] = typer.Option([], "--require-style", help="any required model property statement, repeatable; needs reviewed/numerical evidence"),
           prefer_style: list[str] = typer.Option([], "--prefer-style", help="annotate preferred properties without changing fit ranking"),
           splittings: str = typer.Option('0','--splittings',help='library mass splittings in keV, comma-separated; signed'),
           profile: str = typer.Option('','--profile',help='pinned experimental profile; default active, none for packaged defaults'),
           track1_result:list[Path]=typer.Option([],'--track1-result',help='saved Track1 result for exact current point reuse; otherwise recompute'),
           eligibility_budget:int=typer.Option(32,'--eligibility-budget',min=1,max=1000,help='maximum additional physical candidate assessments'),
           no_eligibility:bool=typer.Option(False,'--no-eligibility',help='retain NR-only reference; physical eligibility stays pending'),
           halo: str = typer.Option("", "--halo", help="published (the default: each search's own published halo for its fit and its null limits, a difference noted), benchmark (one fixed common benchmark of --halo-family for the fit, the toys, the null limits, the flags, the complementary verdicts and the eligibility points; a search with no halo variation is refused) or compare (the halo models compared: the whole run at each available family's benchmark, ranked together, the global significance over every halo)"),
           halo_family: str = typer.Option("", "--halo-family", help="the halo family of --halo benchmark: shm (the Standard Halo Model at arXiv:2105.00599's recommended values; the default); shm-plus-plus (SHM++ at Table I of arXiv:1810.11468, a fixed benchmark only); shm-lmc is not implemented yet and is refused"),
           agent: bool = typer.Option(False, "--agent", help="after the fixed scan, the agent-led search: a language model chooses deformations of the leaders to fit, in rounds; each is charged one more free parameter and joins only if it beats its parent by ΔAIC > 2; the global significance is recomputed over everything tried (paid: needs --budget)"),
           agent_rounds: int = typer.Option(3, "--agent-rounds", min=1, max=5, help="with --agent: the most rounds"),
           agent_model: str = typer.Option("", "--agent-model", help="with --agent: the agent's model (default Claude Opus 5.5)"),
           budget: float = typer.Option(0.0, "--budget", help="dollars: with --agent, the most its language model may spend"),
           out: str = typer.Option("", "--out", help="folder (default: runs/signal_<experiment>)")) -> None:
    """Path 2 (DM6): fit a model space (or users' models) to a search's events and rank the candidates. $0; with
    --agent the agent-led search after it is paid: calls a language model behind the budget gate."""
    from adroit.orchestrator import runs
    from adroit.orchestrator.signal import UserModel
    search = _agent_search(agent, agent_rounds, agent_model, budget)
    mass_list = _masses(masses)
    user_models = [UserModel(spec=_spec(path), derivation=_derivation(path), masses_gev=mass_list,
                    catalog_reference=_catalog_reference(path)) for path in model]
    try:
        from adroit.core.model_preferences import parse_preference
        preferences=[parse_preference(t,'required') for t in require_style]+[parse_preference(t,'preferred') for t in prefer_style]
        from adroit.library.experimental_profiles import selected
        from adroit.core.eligibility import EligibilitySettings
        profile_reference=selected(profile)
        splitting_values=[float(v) for v in runs.parse_list(splittings)]
        import math
        if not splitting_values or len(set(splitting_values))!=len(splitting_values) or any(not math.isfinite(v) for v in splitting_values):
            raise ValueError('mass splittings must be distinct finite numbers')
        folder, report = runs.signal(experiment, runs.parse_list(null_modules), leaders, toys,
                                     Path(out) if out else None, user_models, with_library, unverified,
                                     **({'model_preferences':preferences} if preferences else {}),
                                     **({'splittings_kev':splitting_values} if splitting_values!=[0.0] else {}),
                                     **({'experimental_profile':profile_reference} if profile_reference else {}),
                                     **({'track1_results':[str(p) for p in track1_result]} if track1_result else {}),
                                     **({'eligibility_settings':EligibilitySettings(enabled=not no_eligibility,max_candidates=eligibility_budget)}
                                        if no_eligibility or eligibility_budget!=32 else {}),
                                     **(_track2_halos(halo, halo_family) if halo or halo_family else {}),
                                     **({'search': search} if search else {}))
    except ValueError as error:
        raise typer.BadParameter(str(error)) from None
    typer.echo(report)
    typer.echo(f"written to {folder}")
    if search:
        from adroit.orchestrator.preflight import spent_text
        typer.echo(spent_text(search[1]))


def _agent_search(agent: bool, rounds: int, model: str, budget: float):
    """(settings, budgeted client) of the agent-led search (``signal_search``), or None without ``--agent``."""
    if not agent:
        if budget:
            raise typer.BadParameter("--budget pays the agent-led search: give --agent, or no --budget")
        return None
    from adroit.core.pricing import DEFAULT_PRIMARY, PRIMARY_MODELS
    model = model or DEFAULT_PRIMARY
    if model not in PRIMARY_MODELS:
        raise typer.BadParameter(f"--agent-model is one of {', '.join(PRIMARY_MODELS)}")
    if budget <= 0:
        raise typer.BadParameter("--agent needs --budget: the most its language model may spend")
    from adroit.agents.llm import BudgetedLLMClient, client_for
    from adroit.orchestrator.preflight import job_ledger
    from adroit.orchestrator.signal_search import SearchSettings
    return (SearchSettings(model=model, rounds=rounds),
            BudgetedLLMClient(client_for(model), dollar_budget=budget, ledger_path=job_ledger()))


def _spec(path: Path):
    """A typed model from YAML: the model itself, or under 'spec' (DM8's files)."""
    import yaml
    from adroit.orchestrator.model_approval import read_model
    try:
        if str(path).startswith('catalog:'):
            from adroit.library.personal import Catalog
            return Catalog().load(str(path)).spec
        return read_model(yaml.safe_load(path.read_text()))
    except ValueError as error:          # a refused model is a usage error, not a traceback (the audit's phase 4)
        raise typer.BadParameter(f"{path}: {error}") from None


def _catalog_reference(path: Path) -> str:
    """The pinned catalog revision a model comes from: a ``catalog:`` reference, or a YAML (the model library's
    export) naming one in ``catalog_reference`` whose model and derivation are that revision's. A YAML naming a
    revision it no longer matches, or one this library does not hold, is refused rather than run unpinned (the
    external audit's A13, 2026-10-16: the reference had been ignored, losing the revision, approval and derivation)."""
    import yaml
    if str(path).startswith('catalog:'):
        return str(path)
    data = yaml.safe_load(path.read_text())
    reference = data.get("catalog_reference", "") if isinstance(data, dict) else ""
    if not reference:
        return ""
    from adroit.library.personal import Catalog
    try:
        revision = Catalog().load(reference)
    except (KeyError, OSError, ValueError) as error:
        raise typer.BadParameter(f"{path} names {reference}, which this model library cannot load ({error}): import "
                                 "it, or remove catalog_reference to run the model unpinned") from None
    try:
        same = _spec(path) == revision.spec and _derivation(path) == revision.derivation
    except ValueError as error:                      # its own approval refuses a changed model
        raise typer.BadParameter(f"{path} names {reference}: {error}") from None
    if not same:
        raise typer.BadParameter(f"{path} names {reference} but its model differs from that revision: an edited "
                                 "model is a new model, so save it as a new revision in the model library and approve "
                                 "it, or remove catalog_reference")
    return reference


def _derivation(path: Path):
    """DM8's derivation in a model's YAML, if it has one."""
    import yaml
    from adroit.library.interactions.derivation import Derivation
    if str(path).startswith('catalog:'):
        from adroit.library.personal import Catalog
        return Catalog().load(str(path)).derivation
    data = yaml.safe_load(path.read_text())
    return Derivation.model_validate(data["derivation"]) if "derivation" in data else None


def _not_a_parameter(error: ValueError) -> None:
    """Re-raise a provider's missing key as itself, not as an invalid option (``_Commands`` says what to set)."""
    from adroit.agents.llm import MissingCredentials
    if isinstance(error, MissingCredentials):
        raise error


def _committed_parts(error) -> dict:
    """A budget stop's committed dollars as its paid ledger splits them, settled and still reserved for requests
    whose bill is not known (the workflow audit's WA-03, 2026-10-24: the committed $0.40 of an unsettled reservation
    had been shown as spent); nothing where the ledger does not account for every committed dollar (the command's
    clients kept more than one ledger). A provider's own cap (``BudgetAccount.provider_caps``) stops with that
    provider's commitment, less than the command's: the record then keeps the whole command's commitment, split, and
    the stopping cap's apart (``cap_committed_usd``); before M2 it kept the provider's alone, unsplit, so the run read
    as "up to" the provider's dollars and the other provider's were lost."""
    from adroit.agents.budget import read_ledger, settled_and_uncertain
    try:
        settled, uncertain = settled_and_uncertain(read_ledger(Path(error.ledger_path)))
    except (TypeError, ValueError, OSError, KeyError):
        return {}
    whole = settled + uncertain
    if whole + 1e-9 < error.spent:
        return {}
    parts = {"settled_usd": settled, "uncertain_usd": uncertain}
    if whole - error.spent > 1e-9:
        parts.update(committed_usd=whole, cap_committed_usd=error.spent)
    return parts


@app.command()
@_budget_boundary
def lagrangian(model_file: Path = typer.Argument(None, metavar="MODEL",
                                                 help="YAML with 'spec' (a ModelSpec) and 'derivation' (its Wilson "
                                                      "coefficients); optional 'masses_gev' and 'modules'. With "
                                                      "--derive, a model without a derivation"),
               numerical_check: bool = typer.Option(False, "--numerical-check",
                                                    help="check the derivation against MadDM (installed in the tools folder)"),
               derive: bool = typer.Option(False, "--derive", help="derive the Wilson coefficients with a language "
                                           "model (paid), checked by an independent second derivation"),
               description: str = typer.Option("", "--description", help="with --derive: the model in words, typed "
                                               "first by the intake agent (instead of MODEL)"),
               budget: float = typer.Option(0.0, "--budget", help="dollars, with --derive: one hard cap for every call"),
               model: str = typer.Option("claude-opus-5-5", "--model", help="with --derive: the deriver (and intake)"),
               checker: str = typer.Option("gpt-5.6-sol", "--checker", help="with --derive: the second derivation's "
                                           "model; 'none' leaves the derivation unchecked"),
               out: str = typer.Option("", "--out", help="folder (default: runs/lagrangian_<model name>)")) -> None:
    """Path 1 for a bespoke model (DM8): checks, DirectDM, the library match, the limits, the contract. $0 for a
    given derivation; with --derive (paid, opt-in) the deriver and an independent checker derive the
    coefficients, which must agree at the nucleon level before anything is computed."""
    from adroit.orchestrator import runs
    if not derive:
        if model_file is None or description:
            raise typer.BadParameter("give MODEL (a model with its derivation); --description needs --derive")
        folder, report = runs.lagrangian(model_file.read_text(), numerical_check, Path(out) if out else None,
                                         model_file.stem)
    else:
        if budget <= 0 or (model_file is None) == (not description):
            raise typer.BadParameter("--derive needs --budget (dollars) and one of MODEL or --description")
        from adroit.agents.budget import BudgetAccount
        from adroit.agents.llm import BudgetedLLMClient, LLMClient, OpenAIClient
        from adroit.orchestrator.preflight import job_ledger, show
        account = BudgetAccount(budget)

        def client(name: str):
            inner = OpenAIClient(model=name) if name.startswith("gpt-") else LLMClient(model=name, max_tokens=8192)
            return BudgetedLLMClient(inner, account=account, ledger_path=job_ledger())
        if checker.strip() == model.strip():
            raise typer.BadParameter("an independent check needs a different model from the deriver (or --checker none)")
        primary = client(model)
        second = None if checker.strip().lower() == "none" else client(checker)
        show(f"checker: {checker if second else 'none (the derivation is not independently checked)'}; "
             "the same hard cap covers both models")
        try:
            folder, report = runs.lagrangian(model_file.read_text() if model_file else "", numerical_check,
                                             Path(out) if out else None, model_file.stem if model_file else "model",
                                             description=description, primary=primary, checker=second,
                                             deriver=model, checker_model=checker if second else "")
        except ValueError as error:
            _not_a_parameter(error)
            raise typer.BadParameter(str(error)) from None
    typer.echo(report)
    typer.echo(f"written to {folder}")


@app.command()
@_budget_boundary
def agents(result_file: Path = typer.Argument(..., help="a result.json: Path 2 (signal), Track 1, single-idea, or "
                                              "bespoke Path 1 (lagrangian)"),
           budget: float = typer.Option(..., "--budget", help="dollars: the agents call a language model"),
           model: str = typer.Option("claude-opus-5-5", "--model", help="the language model the agents call"),
           out: str = typer.Option("", "--out", help="folder (default: runs/agents_<file stem>)")) -> None:
    """DM9 on a finished result: the constraint scout and the assumption audit (and, for Path 2, the variant
    agent). Paid."""
    from adroit.agents.llm import BudgetedLLMClient, client_for
    from adroit.orchestrator import agents as dm9
    from adroit.retrieval.references import ReferenceCache
    from adroit.evidence.version import resolve
    found = resolve(result_file, evidence=False)         # a fresh selection: the version saved now, read once
    try:
        data = found.data()
        kind, typed = dm9.read_result(data)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from None
    request, tools = dm9.AgentRequest(model=model), dm9.Tools(cache=ReferenceCache())
    rehearsal = dm9.rehearse(kind, typed, model, request, tools)
    typer.echo(dm9.plan_text(rehearsal, budget))
    if budget < rehearsal.largest:
        typer.echo(f"Not started, $0 spent: raise --budget to at least ${rehearsal.largest:.2f} "
                   f"(${rehearsal.suggested_cap():.2f} is likely to finish).")
        raise typer.Exit(BUDGET_STOPPED)
    from adroit.orchestrator.preflight import job_ledger, spent_text
    llm = BudgetedLLMClient(client_for(model), dollar_budget=budget, ledger_path=job_ledger())
    result = dm9.RUNNERS[kind](typed, llm, request, tools)
    folder = Path(out) if out else _runs_dir() / f"agents_{result_file.stem}"
    folder.mkdir(parents=True, exist_ok=True)
    from adroit.evidence.build import publish                  # each whole (M3), the report bound to it (CZ-02)
    from adroit.evidence.version import as_found
    read = as_found(f"It is an advisory reading of {result_file} as found: its result, SHA-256 "
                    f"{found.result_sha256}, read once.")
    publish(folder / "result.json", result.model_dump_json(indent=1).encode(), result,
            lambda envelope: dm9.report(result) + read, evidence=False)
    typer.echo(dm9.report(result) + read)
    typer.echo(f"{spent_text(llm)}; unconfirmed references in the report: {len(result.report_unverified)}; "
               f"written to {folder}")
    if result.stopped:
        typer.echo(f"stopped by the budget; paid responses: {llm.ledger_path}")
        raise typer.Exit(BUDGET_STOPPED)


@app.command(name="eval")
def evaluate(suite: str = typer.Argument(..., help="a suite: injection, lz_tables, limits, historical (DM10); "
                                                   "model_zoo (G0)"),
             held_out: bool = typer.Option(False, "--held-out", help="the held-out half: only to confirm a change"),
             reason: str = typer.Option("", "--reason", help="why the held-out half is run (required with it)"),
             limit: int = typer.Option(0, "--limit", help="run only the first N cases (0: all)"),
             out: str = typer.Option("", "--out", help="store for a development run (default: runs/eval; "
                                                       "docs/dm10/results to add it to the tracked record)")) -> None:
    """DM10: run one half of an evaluation suite. A development run is added to runs/eval/<suite>.jsonl
    (or --out); a held-out run to the tracked docs/dm10/results and its ledger. $0."""
    from adroit.evaluation import core
    from adroit.evaluation.suites import suites
    available = suites()
    if suite not in available:
        raise typer.BadParameter(f"suites: {', '.join(available)}")
    if held_out and out:
        raise typer.BadParameter("a held-out run is recorded in docs/dm10/results, which the gate reads: drop --out")
    half = core.Half.held_out if held_out else core.Half.development
    store = None if held_out else Path(out) if out else _runs_dir() / "eval"
    try:
        result = core.run(available[suite], half, reason, limit or None, results_dir=store)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from None
    typer.echo(core.report(result))
    typer.echo(f"added to {(store or core.RESULTS) / f'{suite}.jsonl'}")


@app.command()
@_budget_boundary
def idea(fields: Path = typer.Option(None, "--fields", help="YAML: a model's fields; builds the most general Lagrangian"),
         lagrangian: Path = typer.Option(None, "--lagrangian", help="YAML: a typed Lagrangian (ModelSpec) to audit"),
         lagrangian_text: str = typer.Option("", "--lagrangian-text", help="a Lagrangian in words (DM8's intake; paid)"),
         text: str = typer.Option("", "--text", help="an idea in words (the model builder; paid)"),
         eft: int = typer.Option(4, "--eft", help="4: renormalizable only; 5 or 6: add the dark matter's EFT operators"),
         models: int = typer.Option(4, "--models", help="how many models the builder proposes (from --text)"),
         budget: float = typer.Option(0.0, "--budget", help="dollars, for the paid inputs (words)"),
         model: str = typer.Option("claude-opus-5-5", "--model", help="the language model for the inputs in words "
                                   "(--text, --lagrangian-text)"),
         catalog_draft: bool = typer.Option(False, "--catalog-draft",
                                            help="also put each valid model in the catalog as an unapproved draft"),
         out: str = typer.Option("", "--out", help="folder (default: runs/idea_<name>)")) -> None:
    """Track 1 (DM12): a field content, a Lagrangian or an idea → valid models, their Lagrangians and audits; each
    valid model is written as models/<name>.yaml, which `adroit track1` runs."""
    import yaml
    from adroit.core.model_spec import ModelSpec
    from adroit.orchestrator import ideas, runs
    spec = lambda path: ModelSpec.model_validate({"phase": "unbroken", **yaml.safe_load(path.read_text())})  # noqa: E731
    request = ideas.IdeaRequest(fields_spec=spec(fields) if fields else None,
                                lagrangian_spec=spec(lagrangian) if lagrangian else None,
                                lagrangian_text=lagrangian_text, text=text, eft_dimension=eft, models=models)
    llm = None
    if lagrangian_text or text:
        if budget <= 0:
            raise typer.BadParameter("words need a language model: give --budget (dollars)")
        from adroit.agents.llm import BudgetedLLMClient, client_for
        from adroit.orchestrator.preflight import job_ledger
        llm = BudgetedLLMClient(client_for(model), dollar_budget=budget, ledger_path=job_ledger())
    name = (fields or lagrangian).stem if (fields or lagrangian) else (text or lagrangian_text)[:40]
    try:
        folder, report = runs.idea(request, llm, Path(out) if out else None, name, catalog_draft)
    except ValueError as error:
        _not_a_parameter(error)
        raise typer.BadParameter(str(error)) from None
    typer.echo(report)
    from adroit.orchestrator.preflight import spent_text
    typer.echo(f"written to {folder}" + (f"; {spent_text(llm)}" if llm else ""))


def _axis(text: str):
    """parameter:low:high[:log|lin][:n], e.g. m_med:10:10000:log:24."""
    from adroit.parameter_space.scan import Axis
    parts = text.split(":")
    if len(parts) < 3:
        raise typer.BadParameter(f"an axis is parameter:low:high[:log|lin][:n]; got {text!r}")
    return Axis(parameter=parts[0], low=float(parts[1]), high=float(parts[2]),
                log=(parts[3] if len(parts) > 3 else "log") == "log", n=int(parts[4]) if len(parts) > 4 else 24)


@app.command()
def track1(ctx: typer.Context, model: Path = typer.Argument(None, help="YAML: a typed model (ModelSpec) with coupling values"),
           profile: str = typer.Option('','--profile',help='pinned experimental profile; default active, none for packaged defaults'),
           portal: str = typer.Option("", "--portal", help="an entry of the portal library (adroit portals)"),
           x: str = typer.Option("", "--x", help="parameter:low:high[:log|lin][:n] (default: the portal's plane)"),
           y: str = typer.Option("", "--y", help="parameter:low:high[:log|lin][:n]"),
           ratio: float = typer.Option(0.0, "--ratio", help="fix m_med = ratio × m_χ at every point"),
           literature: bool = typer.Option(False, "--literature",
                                         help="search arXiv for prior work (contacts arxiv.org; off unless asked)"),
           no_literature: bool = typer.Option(False, "--no-literature", hidden=True,
                                              help="the default: no arXiv search (kept for older scripts)"),
           unverified: bool = typer.Option(False, "--unverified", help="use records no person has verified yet"),
           propagation: str = typer.Option("", "--propagation", help="charged cosmic rays (antiprotons): conservative, central or aggressive (alias relaxed); default the setting ADROIT_CR_PROPAGATION, else conservative. Stronger models only flag"),
           halo: str = typer.Option("", "--halo", help="the halo every point is evaluated over: preset (the owner's working region: rho0, v0 and v_esc over their joint 95% region; a point is decided only if it is so throughout), published (each experiment's published halo, the reproduction mode) or benchmark (one fixed common benchmark of --halo-family, every comparison able to use it at that halo, the others named); default the setting ADROIT_HALO_REGION, else preset"),
           halo_family: str = typer.Option("", "--halo-family", help="the halo family of --halo benchmark: shm (the Standard Halo Model at arXiv:2105.00599's recommended values; the default); shm-plus-plus (SHM++ at Table I of arXiv:1810.11468, a fixed benchmark only); shm-lmc is not implemented yet and is refused"),
           likelihood: bool = typer.Option(False, "--likelihood", help="also the combined-likelihood verdict"),
           exact_limits: bool = typer.Option(False, "--exact-limits", help="compute every direct-detection limit directly, "
                                             "without the precomputed tables of the xenon searches, CDMSlite and "
                                             "PICO-60 (slower; the verdicts are the same)"),
           relic_theory: float = typer.Option(0.10, "--relic-theory", help="relative theory uncertainty on Ωh²"),
           theory: float = typer.Option(0.0, "--theory", help="relative theory uncertainty δ on each prediction, profiled as a log-normal nuisance (κ = ln(1 + δ))"),
           coverage_depth: int = typer.Option(0, "--coverage-depth", min=0, max=3, help="optional finer relic sampling (0: off)"),
           coverage_budget: int = typer.Option(250, "--coverage-budget", min=1, max=10000, help="cap on coverage-search density evaluations"),
           coverage_strategy: str = typer.Option("uniform", "--coverage-strategy", help="uniform or adaptive cell refinement"),
           coverage_exploration: int = typer.Option(1, "--coverage-exploration", min=1, max=3, help="minimum adaptive exploration depth"),
           resume: bool = typer.Option(False, "--resume", help="continue matching checkpoints in --out"),
           approved_model_hash: str = typer.Option("", "--approved-model-hash", help="require the exact model reviewed at approval"),
           reviewed_scan_hash: str = typer.Option("", "--reviewed-scan-hash", help="require the reviewed engine, fixed values and scan setup"),
           private_limit: list[str] = typer.Option([],"--private-limit",help="pinned reviewed private-limit reference; repeat for independent selected inputs"),
           discovery: str = typer.Option("", "--discovery", help="a frozen constraint-discovery assessment (discovery:SESSION@HASH, from adroit constraints coverage): its unresolved relevant constraints keep allowed points pending"),
           parent: str = typer.Option("", "--parent", help="the study this one comes from (DM14)"),
           out: str = typer.Option("", "--out", help="folder (default: runs/track1_<model>)")) -> None:
    """Track 1 (DM13): validity, the parameter scan, the verdict on the thermal-relic contour, plots, literature. $0."""
    if resume and not out:
        raise typer.BadParameter("--resume requires --out")
    if resume and not portal and model is None:
        _track1_resume(ctx, out, parent)
        return
    if not portal and model is None:
        raise typer.BadParameter("give a model file or --portal ID")
    if portal and approved_model_hash:
        raise typer.BadParameter("model approval applies to a supplied model file, not a portal benchmark")
    changes = {**_track1_inputs(literature and not no_literature, unverified, exact_limits, propagation, profile, private_limit,
                                reviewed_scan_hash),
               **_track1_scan(coverage_depth, coverage_budget, coverage_strategy, coverage_exploration,
                              likelihood, relic_theory, theory, x, y, ratio)}
    if discovery:
        changes["discovery"] = discovery
    if halo or halo_family:
        changes["halo"] = _halo_option(halo, halo_family)
    request = _track1_request(model, portal, approved_model_hash, changes)
    from adroit.orchestrator import runs
    try:
        folder, report = runs.track1(request, Path(out) if out else None, portal or model.stem,
                                     Path(parent) if parent else None, resume=resume)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from None
    typer.echo(report)
    typer.echo(f"written to {folder}")


# a resumed run keeps its saved request: any of these given on the command line is refused, not ignored
_TRACK1_SETTINGS = ("x", "y", "ratio", "literature", "no_literature", "unverified", "propagation", "likelihood", "exact_limits",
                    "relic_theory", "theory", "coverage_depth", "coverage_budget", "coverage_strategy",
                    "coverage_exploration", "approved_model_hash", "reviewed_scan_hash", "private_limit", "profile",
                    "discovery", "halo", "halo_family")


def _track1_resume(ctx: typer.Context, out: str, parent: str) -> None:
    """Continue the Track 1 run in ``out`` from its saved request, refusing any scientific setting given anew."""
    from adroit.orchestrator import runs
    from adroit.orchestrator.track1 import saved_request
    if any(getattr(ctx.get_parameter_source(name), "name", "") == "COMMANDLINE" for name in _TRACK1_SETTINGS):
        raise typer.BadParameter("Resume uses the saved request; do not override its scientific settings")
    try:
        request = saved_request(Path(out))
        folder, report = runs.track1(request, Path(out), request.spec.name,
                                     Path(parent) if parent else None, resume=True)
    except (ValueError, OSError) as error:
        from adroit.evidence.archive import readable
        raise typer.BadParameter(readable(error)) from None
    typer.echo(report)
    typer.echo(f"written to {folder}")


def _track2_halos(value: str, family: str = "") -> dict:
    """Track 2's ``--halo`` as the run's keyword: ``halos``, every available family's benchmark (compare; the SHM's
    first), or ``halo`` (``_track2_halo``)."""
    if value.strip().lower() != "compare":
        return {"halo": _track2_halo(value, family)}
    from adroit.core import halo_choice
    if family and family != halo_choice.DEFAULT_FAMILY:
        raise typer.BadParameter("--halo compare takes every available family; give no --halo-family")
    order = [halo_choice.DEFAULT_FAMILY] + [f for f, v in halo_choice.FAMILIES.items()
                                            if v.available and f != halo_choice.DEFAULT_FAMILY]
    return {"halos": [halo_choice.fixed(f) for f in order]}


def _track2_halo(value: str, family: str = ""):
    """Track 2's ``--halo``: published (each search's own published halo, its default; None) or benchmark (the fixed
    common benchmark of ``--halo-family``)."""
    if value.strip().lower() not in ("published", "benchmark"):
        if value.strip().lower() == "preset":
            raise typer.BadParameter("Track 2 has no halo region: --halo is published or benchmark")
        raise typer.BadParameter("--halo is published or benchmark" +
                                 (" (--halo-family chooses the family of --halo benchmark)" if family else ""))
    chosen = _halo_option(value, family)
    return chosen if not isinstance(chosen, str) else None


def _halo_option(value: str, family: str = ""):
    """The ``--halo`` choice: the preset region, the published halos, or the fixed common benchmark of the family
    (``--halo-family``, the SHM by default; SHM++ a benchmark only; a family not implemented yet is refused, never run
    as another)."""
    from adroit.core import halo_choice
    from adroit.parameter_space.halo_region import PUBLISHED, HaloPreset
    choice, family = value.strip().lower(), family.strip().lower()
    try:
        if family:
            halo_choice.available(family)
        if choice not in ("preset", PUBLISHED, "benchmark"):
            raise typer.BadParameter("--halo is preset, published or benchmark" +
                                     (" (--halo-family chooses the family of --halo benchmark)" if family else ""))
        if choice == "benchmark":
            return halo_choice.fixed(family or halo_choice.DEFAULT_FAMILY)
    except halo_choice.UnknownHalo as error:
        raise typer.BadParameter(str(error)) from None
    if family and family != halo_choice.DEFAULT_FAMILY:
        raise typer.BadParameter(f"--halo-family {family} applies to --halo benchmark")
    return HaloPreset() if choice == "preset" else PUBLISHED


def _track1_inputs(literature: bool, unverified: bool, exact_limits: bool, propagation: str, profile: str,
                   private_limit: list[str], reviewed_scan_hash: str) -> dict:
    """A Track 1 request's evidence settings: the literature, unverified records, exact limits, the cosmic-ray
    propagation model, the experimental profile, private limits and the reviewed scan's identity."""
    changes = {"literature": literature, "unverified_records": unverified}
    if exact_limits:
        changes["exact_limits"] = True
    if propagation:
        from adroit.constraints.propagation import normalise
        try:
            changes["propagation"] = normalise(propagation)
        except ValueError as error:
            raise typer.BadParameter(str(error)) from None
    from adroit.library.experimental_profiles import selected
    profile_reference=selected(profile)
    if profile_reference:
        changes['experimental_profile']=profile_reference
    if private_limit:
        changes['private_limits']=private_limit
    if reviewed_scan_hash:
        changes['reviewed_scan_sha256']=reviewed_scan_hash
    return changes


def _track1_scan(coverage_depth: int, coverage_budget: int, coverage_strategy: str, coverage_exploration: int,
                 likelihood: bool, relic_theory: float, theory: float, x: str, y: str, ratio: float) -> dict:
    """A Track 1 request's scan settings, checked: the relic contour's coverage refinement, the combined
    likelihood's theory uncertainties, the plane's axes and a fixed ratio m_med/m_χ."""
    if coverage_strategy not in ("uniform", "adaptive") or (coverage_strategy == "adaptive" and not coverage_depth):
        raise typer.BadParameter("Choose uniform or adaptive; adaptive requires --coverage-depth greater than 0")
    if coverage_strategy == "adaptive" and coverage_exploration > coverage_depth:
        raise typer.BadParameter("Adaptive exploration depth cannot exceed coverage depth")
    changes = {}
    if coverage_depth:
        from adroit.parameter_space.coverage import CoverageSettings
        changes["coverage"] = CoverageSettings(refinement_depth=coverage_depth, max_evaluations=coverage_budget,
                                               strategy=coverage_strategy, exploration_depth=coverage_exploration)
    if likelihood:
        from adroit.parameter_space.likelihood import LikelihoodSettings
        changes["likelihood"] = LikelihoodSettings(relic_theory=relic_theory, prediction_theory=theory)
    if x:
        changes["x"] = _axis(x)
    if y:
        changes["y"] = _axis(y)
    if ratio:
        changes["mediator_ratio"] = ratio
    return changes


def _track1_request(model: Path | None, portal: str, approved_model_hash: str, changes: dict):
    """The typed Track 1 request: a portal at its benchmark, or a model file checked against its approval."""
    from adroit.orchestrator.track1 import Track1Request, for_portal
    try:
        typed_spec = _spec(model) if not portal else None
        if typed_spec is not None:
            from adroit.orchestrator.model_approval import verify_identity
            verify_identity(typed_spec,approved_model_hash)
        return for_portal(portal, **changes) if portal else Track1Request(
            spec=typed_spec, x=changes.get("x"), y=changes.get("y"),
            approved_model_sha256=approved_model_hash,
            catalog_reference=_catalog_reference(model),
            **{k: v for k, v in changes.items() if k not in ("x", "y")})
    except (KeyError,ValueError) as error:
        raise typer.BadParameter(str(error)) from None


@app.command()
def portals() -> None:
    """The portal library: benchmark models of thermal dark matter, each runnable with track1 --portal. $0."""
    from adroit.parameter_space import library
    typer.echo(library.listing())


anomaly_app = typer.Typer(pretty_exceptions_show_locals=False, help="DM14: anomaly records, Track 2's input", add_completion=False)
app.add_typer(anomaly_app, name="anomaly")


@anomaly_app.command("template")
def anomaly_template(out: Path = typer.Option(None, "--out", help="write the template here")) -> None:
    """A blank anomaly record, every field explained. $0."""
    from adroit.experiments.anomaly import template
    if out:
        from adroit.core.durable import write_atomic
        write_atomic(out, template())           # its own entry, never through a link there (DJ-01's class)
        typer.echo(f"written to {out}")
    else:
        typer.echo(template())


@anomaly_app.command("check")
def anomaly_check(record: Path = typer.Argument(..., help="an anomaly record (YAML)")) -> None:
    """An anomaly record's consistency, before any fit: problems, and whether a person has verified it. $0."""
    import yaml
    from adroit.experiments import anomaly
    r, incomplete = anomaly.read(record)
    if r is None:
        typer.echo("not a valid record yet; the fields to give or correct:")
        typer.echo("\n".join(f"- {p}" for p in incomplete))
        try:
            todo = (yaml.safe_load(record.read_text()) or {}).get("needs_person", [])
        except (yaml.YAMLError, AttributeError):
            todo = []
        for item in todo if isinstance(todo, list) else []:
            typer.echo(f"- still to do: {item}")
        raise typer.Exit(1)
    problems = anomaly.check(r, record.parent)
    typer.echo(f"{r.name}: " + (f"verified by {r.verified_by}" if r.verified_by.strip() else "a DRAFT (no verified_by)"))
    typer.echo("\n".join(f"- {p}" for p in problems) or "no problems found")
    for item in r.needs_person:
        typer.echo(f"- still to do: {item}")
    if problems:
        raise typer.Exit(1)


@anomaly_app.command("draft")
@_budget_boundary
def anomaly_draft(out: Path = typer.Option(..., "--out", help="the draft record (YAML)"),
                  pdf: Path = typer.Option(None, "--pdf", help="the paper as a PDF"),
                  arxiv: str = typer.Option("", "--arxiv", help="the paper's arXiv identifier (fetched)"),
                  budget: float = typer.Option(0.0, "--budget", help="dollars (the drafter is a language model)"),
                  model: str = typer.Option("claude-opus-5-5", "--model", help="the drafting language model")) -> None:
    """A draft record from a paper, for a person to verify (paid, opt-in). An existing --out is refused before
    anything is paid for, and the draft is written only where no file is: a draft never replaces another."""
    if budget <= 0 or not (pdf or arxiv):
        raise typer.BadParameter("give --pdf or --arxiv, and --budget (dollars)")
    if out.exists():
        raise typer.BadParameter(f"{out} already exists: choose a new file (a draft never replaces another)")
    from adroit.agents.anomaly import AnomalyDrafter, to_yaml
    from adroit.agents.llm import BudgetedLLMClient, client_for
    from adroit.orchestrator.preflight import job_ledger, spent_text
    from adroit.retrieval import corpus
    text = corpus.extract_pdf_text(pdf) if pdf else corpus.fetch_arxiv_pdf_text(arxiv)
    llm = BudgetedLLMClient(client_for(model), dollar_budget=budget, ledger_path=job_ledger())
    draft = AnomalyDrafter(llm, model).run(text, f"arXiv:{arxiv}" if arxiv else pdf.name)
    _write_new(out, to_yaml(draft))
    typer.echo(f"written to {out} (a draft: a person must verify it); {spent_text(llm)}")
    for item in draft.needs_person:
        typer.echo(f"- still to do: {item}")


def _write_new(path: Path, text: str) -> None:
    """Write a command's file output only where no file is (another run may have written one since the command
    began: the workflow audit's WA-05, 2026-10-24, two drafts of one paper had shared one file, and the first run's
    page then showed the second draft); in a workbench job, its identity (path and sha256) is kept in the job's
    folder (``preflight.JOB_OUTPUT``), so that the run's page opens the file only while it is still what the run
    wrote."""
    import hashlib
    from adroit.core.durable import write_new
    from adroit.orchestrator.preflight import JOB_OUTPUT, job_folder
    data = text.encode()
    try:                                        # whole, as every new file a command promises (DM-02): never part of one
        write_new(path, data)
    except FileExistsError:
        raise typer.BadParameter(f"{path} was written by another run meanwhile; this draft is not saved "
                                 "(its paid answer is in the paid ledger)") from None
    folder = job_folder()
    if folder is not None:
        from adroit.core.durable import write_atomic
        write_atomic(folder / JOB_OUTPUT, json.dumps({"path": str(path.resolve()),
                                                      "sha256": hashlib.sha256(data).hexdigest()}, indent=1))


def _masses(text: str) -> list[float]:
    """low:high:n (logarithmic), or comma-separated masses; a message, not a traceback, for anything else (the audit
    loop's AL1-14, 2026-11-14: ``signal --masses 10:60:6`` had ended in a ValueError)."""
    import numpy as np
    try:
        if ":" in text:
            low, high, n = text.split(":")
            found = np.geomspace(float(low), float(high), int(n)).tolist()
        else:
            found = [float(m) for m in text.split(",") if m.strip()]
    except ValueError:
        raise typer.BadParameter(f"{text!r}: give low:high:n (n masses spaced logarithmically) or comma-separated "
                                 "masses in GeV", param_hint="--masses") from None
    if not all(math.isfinite(m) and m > 0 for m in found):
        raise typer.BadParameter(f"{text!r}: every mass must be a positive number of GeV", param_hint="--masses")
    return found


@app.command(name="single-idea")
def single_idea(ctx: typer.Context,
                model: Path = typer.Argument(None, help="YAML: a user's typed model (with its derivation if any)"),
                experiment: str = typer.Option("", "--experiment", help="a signal search, or record:<path> (required "
                                               "with a model)"),
                request_file: Path | None = typer.Option(None, "--request", help="a saved single-idea request (JSON), "
                    "as a promotion writes each completion that waits for your choice: run as saved, its halo and "
                    "every setting its own; give no model or setting with it (--out and --parent aside)"),
                request_sha256: str = typer.Option("", "--request-sha256", help="with --request: the SHA-256 of the "
                    "request as it was offered; refused if the file now holds another"),
                masses: str = typer.Option("5:1000:16", "--masses", help="low:high:n, or comma-separated (GeV)"),
                null_modules: str = typer.Option(
                    "CRESST-III 2019,CDMSlite Run 2,PICO-60 C3F8 (2019),DEAP-3600 (2019)", "--null",
                    help="null experiments to combine with, comma-separated"),
                toys: int = typer.Option(20_000, "--toys",
                    help="background-only toys for the global significance over the masses"),
                grid: int = typer.Option(20, "--grid", help="Track 1's plane: n × n"),
                fit_grid: int = typer.Option(33, "--fit-grid", min=9, max=129,
                    help="bounded physical likelihood's coarse resolution"),
                fit_evaluations: int = typer.Option(512, "--fit-evaluations", min=5, max=5000,
                    help="cap on spectrum evaluations per bounded physical fit (not dollars)"),
                native_joint: str = typer.Option("", "--native-joint",
                    help="native joint null search: DEAP-3600 (2019) or PICO-60 C3F8 (2019)"),
                native_toys: int = typer.Option(1000, "--native-toys", min=1, max=100000,
                    help="background-only toys calibrating the native joint statistic q₀ (with --native-joint)"),
                native_seed: int = typer.Option(20261007, "--native-seed", min=0,
                    help="random seed of the native toys (fixes them for reproduction)"),
                native_fit_budget: int = typer.Option(10000, "--native-fit-budget", min=1,max=1000000,
                    help="cap on native calibration toy fits (not dollars)"),
                native_domain: Path | None = typer.Option(None, "--native-domain",
                    help="YAML named physical domain; separate uncalibrated multiparameter fit"),
                literature: bool = typer.Option(False, "--literature",
                                         help="search arXiv for prior work (contacts arxiv.org; off unless asked)"),
                no_literature: bool = typer.Option(False, "--no-literature", hidden=True,
                                                   help="the default: no arXiv search (kept for older scripts)"),
                unverified: bool = typer.Option(False, "--unverified", help="accept an unverified anomaly record"),
                propagation: str = typer.Option("", "--propagation", help="charged cosmic rays (antiprotons): conservative, central or aggressive (alias relaxed); default the setting, else conservative"),
                halo: str = typer.Option("", "--halo", help="the halo every point is evaluated over: preset (the owner's working region: rho0, v0 and v_esc over their joint 95% region; a point is decided only if it is so throughout), published (each experiment's published halo, the reproduction mode), or benchmark (one fixed common benchmark of --halo-family for the fit, the null comparisons, the band and the plane alike); default the setting ADROIT_HALO_REGION, else preset (its band and Track 1 plane; its fit at each search's published halo)"),
                halo_family: str = typer.Option("", "--halo-family", help="the halo family of --halo benchmark: shm (the Standard Halo Model at arXiv:2105.00599's recommended values; the default); shm-plus-plus (SHM++ at Table I of arXiv:1810.11468, a fixed benchmark only); shm-lmc is not implemented yet and is refused"),
                profile: str = typer.Option('','--profile',help='pinned experimental profile; default active, none for packaged defaults'),
                discovery: str = typer.Option("", "--discovery", help="a frozen constraint-discovery assessment (discovery:SESSION@HASH): its unresolved relevant constraints keep allowed points pending"),
                parent: str = typer.Option("", "--parent", help="the study this one comes from"),
                out: str = typer.Option("", "--out", help="folder (default: runs/single_idea_<model>_<experiment>)")) -> None:
    """DM14: one idea as the explanation of an anomaly: fit, tension, best-fit band and Track 1 around it. $0."""
    if request_file is not None:
        _saved_single_idea(ctx, request_file, out, parent, request_sha256)
        return
    if request_sha256:
        raise typer.BadParameter("--request-sha256 names a saved request's identity: give it with --request")
    if model is None:
        raise typer.BadParameter("give a model file, or --request with a saved request")
    if not experiment:
        raise typer.BadParameter("give the signal search (--experiment) the model is to explain")
    from adroit.orchestrator import runs
    from adroit.orchestrator.single_idea import SingleIdeaRequest
    from adroit.parameter_space.physical_fit import FitSettings
    from adroit.parameter_space.native_joint import JointSettings
    from adroit.core.fit_domain import PhysicalDomain
    import yaml
    if native_domain is not None and not native_joint:
        raise typer.BadParameter("--native-domain requires --native-joint")
    domain = PhysicalDomain.model_validate(yaml.safe_load(native_domain.read_text())) if native_domain else None
    from adroit.library.experimental_profiles import selected
    profile_reference=selected(profile)
    request = SingleIdeaRequest(experiment=experiment, spec=_spec(model), derivation=_derivation(model),
                                catalog_reference=_catalog_reference(model),
                                experimental_profile=profile_reference,
                                masses_gev=_masses(masses), null_modules=runs.parse_list(null_modules), toys=toys,
                                grid=grid, literature=literature and not no_literature, unverified_records=unverified,
                                physical_fit_settings=FitSettings(grid=fit_grid,max_evaluations=fit_evaluations),
                                native_joint=JointSettings(null_experiment=native_joint,toys=native_toys,
                                    seed=native_seed,max_toy_fits=native_fit_budget,domain=domain) if native_joint else None)
    _single_idea_run(request, propagation, discovery, halo, out, parent, halo_family)


def _saved_single_idea(ctx: typer.Context, path: Path, out: str, parent: str, expected: str = "") -> None:
    """Run the single-idea request saved in ``path`` as saved (``promote._offer``'s completion that waited for the
    researcher's choice): its halo (a fixed benchmark's whole snapshot, the region with its budgets) and every setting
    its own, checked as a fresh run checks them, never resolved again from the current defaults. A model or setting
    given on the command line with it is refused, not applied (the auditor's HB recheck, HC-02, 2026-11-11: the offered
    command had named the model, the search and the masses alone, so the study ran at the current default halo, not
    its parent's SHM++). With ``expected`` (``--request-sha256``, which an offered command names), the file read must
    hold the request offered, else nothing runs (the auditor's HC recheck, HD-02, 2026-11-12: a later offer had been written
    over an earlier one's file); without it, the file is run as a request of its own."""
    import hashlib
    from pydantic import ValidationError
    from adroit.orchestrator.reanalysis import refused
    from adroit.orchestrator.single_idea import SingleIdeaRequest
    given = [name for name in ctx.params if name not in ("request_file", "request_sha256", "out", "parent")
             and getattr(ctx.get_parameter_source(name), "name", "") == "COMMANDLINE"]
    if given:
        raise typer.BadParameter("a saved request is run as saved: give no model or setting with --request (given: "
                                 + ", ".join(given) + ")")
    try:
        data = path.read_bytes()                                      # read once: what is checked is what runs
    except OSError as error:
        raise typer.BadParameter(f"{path}: {error.strerror or error}") from None
    if expected and (found := hashlib.sha256(data).hexdigest()) != expected.lower():
        raise typer.BadParameter(f"{path} is not the request offered (its SHA-256 is {found[:12]}…, the offer's "
                                 f"{expected[:12]}…): nothing is run")
    try:
        request = SingleIdeaRequest.model_validate_json(data)
    except ValidationError as error:
        raise typer.BadParameter(f"{path}: {refused(error)}") from None
    _single_idea_run(request, "", "", "", out, parent)


def _single_idea_run(request, propagation: str, discovery: str, halo: str, out: str, parent: str,
                     halo_family: str = "") -> None:
    """Run the single-idea request with its cosmic-ray propagation, discovery assessment and halo, if given, and
    print its report."""
    from adroit.orchestrator import runs
    if propagation:
        from adroit.constraints.propagation import normalise
        try:
            request = request.model_copy(update={"propagation": normalise(propagation)})
        except ValueError as error:
            raise typer.BadParameter(str(error)) from None
    if discovery:
        request = request.model_copy(update={"discovery": discovery})
    if halo or halo_family:
        request = request.model_copy(update={"halo": _halo_option(halo, halo_family)})
    try:
        folder, report = runs.single_idea(request, Path(out) if out else None, Path(parent) if parent else None)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from None
    typer.echo(report)
    typer.echo(f"written to {folder}")


@app.command(name="native-fit", hidden=True)    # withdrawn from 1.0.0 (the owner's JU1): kept for 1.0.2, not listed
def native_fit(model: Path = typer.Argument(..., help="typed physical model YAML"),
               domain: Path = typer.Option(...,"--domain",help="named physical domain YAML"),
               null_experiment: str = typer.Option("PICO-60 C3F8 (2019)","--null",
                   help="the native pair's null experiment: PICO-60 C3F8 (2019) or DEAP-3600 (2019)"),
               fit_grid: int = typer.Option(5,"--fit-grid",min=3,max=17,
                   help="coarse points per free coordinate (a 2n − 1 fine search checks it)"),
               profile_grid: int = typer.Option(5,"--profile-grid",min=3,max=17,
                   help="points along each continuous coordinate's profile likelihood"),
               evaluations: int = typer.Option(12000,"--evaluations",min=5,max=100000,
                   help="cap on likelihood evaluations, each a direct physical prediction (not dollars)"),
               resume: bool = typer.Option(False,"--resume",help="continue matching checkpoints in --out"),
               out: Path = typer.Option(...,"--out",help="folder for the result, its evidence and report.md")) -> None:
    """Fit shared bounded physical parameters to the declared native pair. $0; no calibrated p."""
    import yaml
    from adroit.core.fit_domain import PhysicalDomain, DomainFitSettings
    from adroit.orchestrator.native_fit import NativeFitRequest, run_reported
    from adroit.parameter_space.classify import classify
    from adroit.parameter_space.native_joint import JointSettings
    try:
        spec = _spec(model)
        physical_domain = PhysicalDomain.model_validate(yaml.safe_load(domain.read_text()))
        _, point, _ = classify(spec)
        mass_axis = next((c for c in physical_domain.coordinates if c.parameter=='m_chi'),None)
        if mass_axis is not None and mass_axis.values is None:
            raise ValueError("native m_chi requires discrete values")
        masses = mass_axis.values if mass_axis else [physical_domain.fixed.get('m_chi',point.m_chi)]
        request = NativeFitRequest(spec=spec,masses_gev=masses,settings=JointSettings(
            null_experiment=null_experiment,domain=physical_domain,
            domain_settings=DomainFitSettings(grid=fit_grid,profile_grid=profile_grid,max_evaluations=evaluations)))
        _, report = run_reported(request,out,resume=resume)
    except (ValueError,OSError) as error:
        raise typer.BadParameter(str(error)) from None
    typer.echo(report)       # the report of the result it computed, as written: never the file read again (DB-02)
    typer.echo(f"written to {out}")


@app.command()
@_budget_boundary
def promote(run: Path = typer.Argument(..., help="a Path 2 run's folder"),
            which: list[str] = typer.Argument(..., help="candidate labels, or class:N for a degeneracy class"),
            toys: int = typer.Option(20_000, "--toys",
                help="background-only toys for each child study's global significance"),
            grid: int = typer.Option(16, "--grid", help="each child's Track 1 plane: n × n"),
            literature: bool = typer.Option(False, "--literature",
                                     help="search arXiv in the children (contacts arxiv.org; off unless asked)"),
            no_literature: bool = typer.Option(False, "--no-literature", hidden=True,
                                               help="the default: no arXiv search (kept for older scripts)"),
            mass_span: float = typer.Option(4., "--mass-span", min=1.,
                help="promotion masses span m/span to m*span"),
            mass_points: int = typer.Option(9, "--mass-points", min=1,
                help="number of promoted physical mass points"),
            native_joint: str = typer.Option("", "--native-joint",
                help="native joint null search: DEAP-3600 (2019) or PICO-60 C3F8 (2019)"),
            native_toys: int = typer.Option(1000, "--native-toys", min=1, max=100000,
                help="background-only toys calibrating the native joint statistic q₀ (with --native-joint)"),
            native_seed: int = typer.Option(20261007, "--native-seed", min=0,
                help="random seed of the native toys (fixes them for reproduction)"),
            native_fit_budget: int = typer.Option(10000, "--native-fit-budget", min=1, max=1000000,
                help="cap on native calibration toy fits (not dollars)"),
            budget: float = typer.Option(0.0, "--budget", help="dollars: the model builder proposes completions"),
            uv_models: int = typer.Option(3, "--uv-models",
                help="with --budget: how many completions the model builder proposes for each candidate"),
            include_excluded:bool=typer.Option(False,'--include-excluded',help='explicit follow-up of alternative branches from an excluded fitted point'),
            parent_sha256: str = typer.Option("", "--parent-sha256",
                help="the SHA-256 of the run's result the candidates were chosen from: refused if it has changed"),
            model: str = typer.Option("claude-opus-5-5", "--model", help="the model builder's language model")) -> None:
    """DM14: promote Path 2 candidates to studies (their models' single-idea studies), as the run's children.

    $0; with --budget the model builder is paid: calls a language model behind the budget gate."""
    from adroit.orchestrator import runs
    from adroit.orchestrator.single_idea import grid_range
    from adroit.parameter_space.native_joint import JointSettings
    low, high = grid_range()
    if not low <= grid <= high:                 # refused here, never by each child after the parent's work
        raise typer.BadParameter(f"each child's Track 1 plane is between {low} × {low} and {high} × {high}",
                                 param_hint="--grid")
    options = {"toys": toys, "grid": grid, "literature": literature and not no_literature,
               "span": mass_span, "masses": mass_points}
    if include_excluded:
        options['include_excluded']=True
    if native_joint:
        options["native_joint"] = JointSettings(null_experiment=native_joint, toys=native_toys,
            seed=native_seed, max_toy_fits=native_fit_budget).model_dump(mode="json")
    from adroit.orchestrator.promote import ParentChanged, parent_result, refuse_halo
    try:                           # refused before anything is reserved or computed; promote checks both again
        refuse_halo(parent_result(run, parent_sha256)[0], options)            # its children's halo (HC-03)
    except ParentChanged as error:
        raise typer.BadParameter(str(error), param_hint="--parent-sha256") from None
    except ValueError as error:
        raise typer.BadParameter(str(error)) from None
    llm = None
    if budget > 0:
        from adroit.agents.llm import BudgetedLLMClient, client_for
        from adroit.orchestrator.preflight import job_ledger
        llm = BudgetedLLMClient(client_for(model), dollar_budget=budget, ledger_path=job_ledger())
    try:
        folder, report = runs.promote(run, which, options,
                                      llm, uv_models, parent_sha256=parent_sha256)
    except KeyError as error:
        raise typer.BadParameter(str(error)) from None
    except ParentChanged as error:
        raise typer.BadParameter(str(error), param_hint="--parent-sha256") from None
    typer.echo(report)
    _point_to_promotion(runs.promotion_record(run, which))
    from adroit.orchestrator.preflight import spent_text
    typer.echo(f"children written under {folder / 'children'}" + (f"; {spent_text(llm)}" if llm else ""))


def _point_to_promotion(record: Path) -> None:
    """In a workbench job, the promotion's record (its path and SHA-256, ``preflight.JOB_OUTPUT``), which the job's page
    reads to say what was made, or why nothing was (the owner, 2026-11-19: a promotion that made no study had said
    "each promoted model is its own study")."""
    import hashlib
    from adroit.orchestrator.preflight import JOB_OUTPUT, job_folder
    folder = job_folder()
    if folder is None:
        return
    from adroit.core.durable import write_atomic
    try:
        sha = hashlib.sha256(record.read_bytes()).hexdigest()
    except OSError:
        return                                   # the page then says it cannot read what was made
    write_atomic(folder / JOB_OUTPUT, json.dumps({"path": str(record.resolve()), "sha256": sha}, indent=1))


@app.command(name="studies")
def studies_tree(root: Path = typer.Argument(None, help="default: the runs directory")) -> None:
    """DM14: every study under a folder, as the tree of parents and children, with costs; the total counts each
    identifiable paid request once (D-6). Each line is of one study record read with its result
    and its result as one version (``study_headline.held``: read as one checked transaction): a record describing
    another version is named so, without its date and cost (the auditor's DB/VI recheck, DC-01, 2026-11-03: A's title and
    cost had been listed beside B's result). $0."""
    from adroit.evidence.version import Unsettled
    from adroit.orchestrator import accounting, studies, study_headline
    base = root or _runs_dir()
    costs = []
    for depth, listed_as in studies.tree(base):
        try:
            found = study_headline.held(Path(listed_as.folder))
        except Unsettled:
            typer.echo(f"{'  ' * depth}- [{listed_as.kind}] {Path(listed_as.folder).name} (its files changed each time "
                       f"they were read): its date and cost are not shown: {listed_as.folder}")
            continue
        if found.record_state not in study_headline.SHOWN:
            typer.echo(f"{'  ' * depth}- [{found.kind or listed_as.kind}] {study_headline.listed(found)}: its date and "
                       f"cost are not shown: {listed_as.folder}")
            continue
        s = found.study()
        c = accounting.held_cost(found)                    # the pages' figure (``list_cost``)
        costs.append(c)
        shown = accounting.short_line(c)
        typer.echo(f"{'  ' * depth}- [{s.kind}] {s.title} ({s.created}{', ' + shown if shown else ''}): {s.folder}")
    for path, why in studies.unreadable(base):
        typer.echo(f"unreadable, not listed: {path} ({why})")
    for path, why in studies.inconsistent(base):
        typer.echo(f"links loop or disagree, listed once: {path} ({why})")
    typer.echo("total: " + accounting.total_text(accounting.total(costs)))


@app.command(name="native-coverage")
def native_coverage(request: Path = typer.Argument(...,help="JSON CoverageRequest; explicit model and nuisance grid"),
                    out: Path = typer.Option(...,"--out",help="folder for the request, result.json and report.md")) -> None:
    """Check native discovery false-positive rates by nested simulation. $0; finite grid only."""
    from adroit.orchestrator.native_coverage import CoverageRequest, run_reported
    parsed = CoverageRequest.model_validate_json(request.read_text())
    result, report = run_reported(parsed,out)
    typer.echo(report)       # of the result it holds, as its exit is (DB-02)
    if not result.complete:
        raise typer.Exit(1)


@app.command(name="assist")
@_budget_boundary
def assist(request: Path = typer.Argument(...,help="JSON AssistanceRequest; original typed inputs/results"),
           out: Path = typer.Option(...,"--out",help="folder for the request, result.json and report.md"),
           budget: float = typer.Option(0.,"--budget",min=0.,help="dollars; zero uses deterministic templates"),
           provider: str = typer.Option("anthropic","--provider",help="anthropic or openai (with --budget)"),
           model: str = typer.Option("claude-opus-5-5","--model",help="the assistant's language model (with --budget)"),
           fetch_sources: bool = typer.Option(False,"--fetch-sources",
                                              help="read up to four cited arXiv papers into the evidence (network)"),
           execute_plan: bool = typer.Option(False,"--execute-plan",help="run the plan's permitted deterministic step "
                                             "(a single-idea study or coverage check) on the original typed inputs"),
           goal: str = typer.Option("Review this study and plan the next supported calculation","--goal",
                                    help="the goal, when REQUEST is a single-idea study's folder")) -> None:
    """Optional clarification, primary-source gathering, planning and checked review.

    Paid with a positive --budget: calls a language model behind the budget gate; $0 with --budget 0."""
    from adroit.orchestrator.research_assistance import AssistanceRequest,run,report
    if request.is_dir():
        from adroit.evidence.version import resolve
        from adroit.orchestrator.single_idea import SingleIdeaResult
        found=resolve(request,evidence=False)           # a fresh selection: the study's result read once
        if found.content is None:
            raise typer.BadParameter(f"{request}: no readable saved result")
        result=SingleIdeaResult.model_validate_json(found.content)
        parsed=AssistanceRequest(goal=goal,study=result.request,result=result,source_sha256=found.result_sha256)
    else:
        parsed=AssistanceRequest.model_validate_json(request.read_text())
    llm=None
    if budget>0:
        from adroit.agents.llm import LLMClient,OpenAIClient,BudgetedLLMClient
        if provider not in {"anthropic","openai"}:
            raise typer.BadParameter("provider must be anthropic or openai")
        client=(LLMClient(model=model,max_tokens=4096) if provider=="anthropic" else
                OpenAIClient(model=model,max_tokens=4096,reasoning_effort="low"))
        from adroit.orchestrator.preflight import job_ledger
        llm=BudgetedLLMClient(client,dollar_budget=budget,ledger_path=job_ledger(out/"budget.jsonl"))
    result=run(parsed,out,llm=llm,model=model if llm else "",fetch_sources=fetch_sources,execute_plan=execute_plan)
    typer.echo(report(result))
    if result.status!="complete":
        raise typer.Exit(1)


session_app=typer.Typer(pretty_exceptions_show_locals=False, help="Researcher-controlled paired timers; no time-saving claims from automated latency")
app.add_typer(session_app,name="assist-session")


@session_app.command(name="start")
def session_start(path: Path,participant: str,task: str,input_hash: str,condition: str,
                  assistance_result: Path | None = typer.Option(None,"--assistance-result",
                      help="the assisted run's AssistanceResult JSON, whose API cost is recorded (same input hash)")) -> None:
    """Start one manual/assisted active-effort record. $0.

    PATH is the new session file; INPUT_HASH the task input's SHA-256; CONDITION manual or assisted."""
    from adroit.evaluation.assistance_timing import start,save
    if condition not in {"manual","assisted"}:
        raise typer.BadParameter("condition must be manual or assisted")
    if path.exists():
        raise typer.BadParameter("session destination already exists")
    session=start(participant,task,input_hash,condition)
    if assistance_result:
        from adroit.core.assistance import AssistanceResult
        result=AssistanceResult.model_validate_json(assistance_result.read_text())
        if condition!="assisted" or result.input_hash!=input_hash:
            raise typer.BadParameter("assistance cost must belong to this assisted input identity")
        session.api_cost_usd=result.api_cost_usd
    try:
        save(session,path,new=True)
    except FileExistsError:
        raise typer.BadParameter("session destination already exists: another was started there meanwhile") from None


@session_app.command(name="mark")
def session_mark(path: Path,action: str,attest: bool=typer.Option(False,"--attest",
                     help="attest that the timed effort is your own active work (needed to finish)"),
                 success: bool | None=typer.Option(None,"--success/--unsuccessful",
                     help="with finish: whether the task met its quality bar (needed to finish)")) -> None:
    """Pause/resume/finish; finishing requires attested researcher effort and quality. $0."""
    from adroit.evaluation.assistance_timing import ResearcherSession,transition,save
    if action not in {"pause","resume","finish"}:
        raise typer.BadParameter("action must be pause, resume or finish")
    save(transition(ResearcherSession.model_validate_json(path.read_text()),action,
        attest=attest,success=success if action=="finish" else None),path)


@session_app.command(name="summary")
def session_summary(folder: Path) -> None:
    """Summarize only matched, successful and researcher-attested task pairs. $0."""
    from adroit.evaluation.assistance_timing import ResearcherSession,summarize
    typer.echo(summarize([ResearcherSession.model_validate_json(p.read_text()) for p in sorted(folder.glob("*.json"))]).model_dump_json(indent=2))


@session_app.command(name="report")
def session_report(folder: Path,
                   sus: Path | None = typer.Option(None, "--sus", help="a JSON list of System Usability Scale answers, "
                                                   "each {participant, answers: ten integers 1-5}"),
                   usage: list[Path] | None = typer.Option(None, "--usage", help="an opt-in command log "
                                                           "(ADROIT_USAGE_LOG); repeatable"),
                   out: Path | None = typer.Option(None, "--out", help="also write the report as Markdown here; an "
                                                   "existing file is refused")) -> None:
    """The usability sessions' declared analysis (docs/usability/protocol.md): paired effort and success task by task,
    the System Usability Scale and the command logs. FOLDER holds the session files. $0."""
    import json
    from adroit.evaluation import usability, usage_log
    from adroit.evaluation.assistance_timing import ResearcherSession
    if out is not None and out.exists():
        raise typer.BadParameter(f"{out} exists; choose a new file")
    try:
        sessions = [ResearcherSession.model_validate_json(p.read_text()) for p in sorted(folder.glob("*.json"))]
        answers = [usability.SusResponse.model_validate(x) for x in json.loads(sus.read_text())] if sus else []
        entries = [e for path in usage or [] for e in usage_log.read(path)]
        text = usability.markdown(usability.analyse(sessions, answers, entries))
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error)) from None
    if out is not None:                         # a new file, never over one written since the check above (the auditor's DL
        from adroit.core.durable import write_new           # recheck, DM-02, 2026-11-07: another report written
        try:                                                # meanwhile had been replaced by this one)
            write_new(out, text)
        except FileExistsError:
            raise typer.BadParameter(f"{out} was written by another report meanwhile: that file is left as it is, and "
                                     "this report was not saved; choose a new file") from None
    typer.echo(text)


@app.command()
def workbench(port: int = typer.Option(8765, "--port", help="local port: the page is served at 127.0.0.1:<port>"),
              no_browser: bool = typer.Option(False, "--no-browser", help="do not open a browser"),
              classic: bool = typer.Option(False, "--classic", help="DM11's page (the three paths only)")) -> None:
    """DM15: the workbench for the two tracks, in a local browser page (this machine only)."""
    if classic:
        from adroit.workbench import server
        server.serve(_runs_dir(), port, open_browser=not no_browser)
        return
    try:
        from adroit.ui import app as workbench_app
    except ImportError:
        raise typer.BadParameter("the workbench needs NiceGUI: uv sync --extra ui (or use --classic)") from None
    workbench_app.serve(_runs_dir(), port, show=not no_browser)


records_app = typer.Typer(pretty_exceptions_show_locals=False, help="the curated constraint records: review and verification", add_completion=False)
app.add_typer(records_app, name="records")
register_review_commands(records_app)


@records_app.command("list")
def records_list(unverified: bool = typer.Option(False, "--unverified", help="only the records awaiting verification")) -> None:
    """Every record: verified or awaiting verification, its class and source. $0."""
    from adroit.constraints import database
    for r in database.records():
        if unverified and r.usable:
            continue
        from adroit.constraints.review_identity import signature_status
        status=signature_status(r)
        state = f"verified {r.verified_on} by {r.verified_by} ({status.state})" if r.usable else f"AWAITS VERIFICATION ({status.state})"
        typer.echo(f"{r.id:32s} {r.constraint_class.value:18s} {state}")
    records = database.records()
    verified = sum(r.usable for r in records)
    typer.echo(f"\nVerified: {verified} of {len(records)} records; {len(records) - verified} await a person's "
               "verification (pending, never excluding, unless a run asks for --unverified).")


@records_app.command("show")
def records_show(record_id: str = typer.Argument(..., help="a record's id (adroit records list)"),
                 plot: Path = typer.Option(None, "--plot", help="draw the record's curves into this PNG")) -> None:
    """One record: source, quantity, data, assumptions, checks, and its figure's page. $0."""
    from adroit.constraints import database, review
    from adroit.constraints.review_identity import signature_status
    try:
        r = database.record(record_id)
    except KeyError as error:
        raise typer.BadParameter(str(error)) from None
    typer.echo(f"{r.name}\n  id: {r.id}\n  source: {r.source}\n  quantity: {r.quantity}")
    typer.echo(f"  review binding: {signature_status(r).state}: {signature_status(r).reason}")
    if r.figure:
        paper = f"arXiv:{r.figure.arxiv}" if review.on_arxiv(r) else r.source
        typer.echo(f"  compare with: {paper}, {r.figure.label}, page {r.figure.page}")
    for key, value in r.data.items():
        typer.echo(f"  {key} = {value}")
    for line in r.assumptions:
        typer.echo(f"  assumption: {line}")
    for line in r.checks:
        typer.echo(f"  check: {line}")
    typer.echo(f"  {len(review.curves(r))} curve(s); " + (f"verified {r.verified_on} by {r.verified_by}" if r.usable
                                                          else "awaits a person's verification"))
    if plot:
        done = review.plot(r, plot)
        typer.echo(f"plot: {done}" if done else "no curves to draw")


@records_app.command("fetch-sources")
def records_fetch() -> None:
    """Fetch every record's source paper (arXiv PDF) into the tools folder, for the workbench's review page. $0."""
    from adroit.constraints import database, review
    for r in database.records():
        if r.figure is None:
            typer.echo(f"{r.id}: no figure reference")
        elif not review.on_arxiv(r):
            where = review.source_path(r)
            typer.echo(f"{r.id}: " + (str(where) if where.exists() else
                                      f"not an arXiv paper ({r.source}): put its PDF at {where} by hand"))
        else:
            try:
                typer.echo(f"{r.id}: {review.fetch_source(r)}")
            except OSError as error:                  # one paper unavailable: the others are still fetched
                typer.echo(f"{r.id}: not fetched ({type(error).__name__}: {error})")


@records_app.command("verify")
def records_verify(record_id: str = typer.Argument(..., help="a record's id"),
                   by: str = typer.Option(..., "--by", help="your name, as it will be written into the record"),
                   yes: bool = typer.Option(False, "--yes", help="skip the confirmation"),
                   expected_hash: str = typer.Option("","--expected-hash",help="scientific payload shown when reviewed")) -> None:
    """Record that you have compared this record with its source and accept it (writes records.yaml). $0."""
    from adroit.constraints import database, review
    try:
        r = database.record(record_id)
    except KeyError as error:
        raise typer.BadParameter(str(error)) from None
    if not yes and not typer.confirm(f"Verify {r.id} ({r.name}) as {by}?"):
        raise typer.Abort()
    try:
        review.verify(record_id, by,expected_sha256=expected_hash)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from None
    typer.echo(f"{record_id}: verified by {by}")


@app.command()
def crosscheck(portal: str = typer.Argument(..., help="inert_doublet, higgs_portal_scalar or b_minus_l"),
               m_chi: float = typer.Option(None, "--m-chi", help="dark-matter mass m_χ in GeV (default: the benchmark's)"),
               m_med: float = typer.Option(None, "--m-med", help="mediator mass in GeV; inert_doublet: M_H± "
                                           "(default: the benchmark's)"),
               g_chi: float = typer.Option(None, "--g-chi", help="dark-matter coupling; higgs_portal_scalar: λ_hs, "
                                           "inert_doublet: λ₃₄₅ (default: the benchmark's)"),
               g_q: float = typer.Option(None, "--g-q", help="b_minus_l: g_BL; inert_doublet: M_A₀ − M_H₀ in GeV "
                                         "(default: the benchmark's)"),
               g_l: float = typer.Option(None, "--g-l", help="lepton coupling slot; not a parameter of these three "
                                         "portals (default: the benchmark's)")) -> None:
    """ADROIT's Ωh² beside micrOMEGAs's (built in the tools folder), at the portal's benchmark or a given point. $0."""
    from adroit.parameter_space import crosscheck as cc, library
    try:
        point = library.entry(portal).point
    except KeyError as error:
        raise typer.BadParameter(str(error)) from None
    changes = {k: v for k, v in dict(m_chi=m_chi, m_med=m_med, g_chi=g_chi, g_q=g_q, g_l=g_l).items() if v is not None}
    try:
        result = cc.crosscheck(portal, point.model_copy(update=changes))
    except KeyError as error:
        raise typer.BadParameter(str(error)) from None
    ratio = f"{result.ratio:.3f}" if result.ratio else "—"
    typer.echo(f"{portal} at {result.point.model_dump()}:\n  ADROIT Ωh² = {result.adroit}\n  {result.version} "
               f"({result.model}) Ωh² = {result.micromegas}\n  ratio {ratio}" + (f"\n  error: {result.error}" if result.error else ""))


@app.command(name="setup")
def setup(fetch_missing: bool = typer.Option(False, "--fetch", help="fetch (and build) every missing automatic item"),
          only: str = typer.Option("", "--only", help="one item, by its name in the manifest"),
          milestone: str = typer.Option("", "--milestone", help="the items one milestone uses, e.g. DM3")) -> None:
    """Every external tool and data set: present or missing, what to do, and its licence. Exits 1 when a
    required item is missing. $0."""
    from adroit.external import setup as setup_
    try:
        statuses = setup_.run(fetch_missing=fetch_missing, only=only or None, milestone=milestone or None)
    except KeyError as error:
        raise typer.BadParameter(str(error)) from None
    typer.echo(setup_.report(statuses))
    if any(s.required and not s.present for s in statuses):
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
