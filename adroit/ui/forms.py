"""The workbench's typed forms and the commands they launch (DM15). Pure: no interface code.

Every wizard ends in one command-line call, so the workbench and the command
line run the same code and a run can be repeated from its ``job.json``. The
gate forms:
- **a budget:** a paid run starts only after the person types an amount, at
  most the cap, and ticks the confirmation;
- **a model list:** of the models the builder proposed, only those the audit
  found valid can be approved for Track 1;
- **a promotion:** a Path 2 candidate or its degeneracy class becomes
  studies inside its run.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from adroit.core.state import StrictModel
from adroit.orchestrator.runs import slug, unique_folder

CAP_USD = 10.0                    # the most one workbench launch may spend (the owner's daily testing budget)
TRACK1_INPUTS = ("fields", "lagrangian", "text")


class BudgetCheck(StrictModel):
    """The budget gate's answer: whether the run may start, the message, and the approved amount."""
    ok: bool
    message: str
    amount: float = 0.0
    # how the box was ticked, where it was (``pages.auto_tick``): "auto", by the auto-approve setting with the default
    # models chosen (``core.workbench_settings``); "click", by the person; "" where the gate did not say
    approval: str = ""


def check_budget(amount: float | None, confirmed: bool, cap: float = CAP_USD) -> BudgetCheck:
    """Whether a paid run may start."""
    if amount is None or amount <= 0:
        return BudgetCheck(ok=False, message="give the most this run may spend, in dollars")
    if amount > cap:
        return BudgetCheck(ok=False, message=f"at most ${cap:.2f} from the workbench")
    if not confirmed:
        return BudgetCheck(ok=False, message=f"tick the box to approve spending up to ${amount:.2f}")
    return BudgetCheck(ok=True, message=f"approved: up to ${amount:.2f}", amount=float(amount))


def approvable(model) -> bool:
    """A proposed model (DM12's ``ModelResult``) may go to Track 1 only if its audit found it valid."""
    return bool(model.audit.valid)


def approved(models: list, ticks: dict[str, bool]) -> list:
    """The ticked models that may be approved, by name."""
    return [m for m in models if ticks.get(m.spec.name) and approvable(m)]


def new_folder(runs_dir: Path, kind: str, title: str) -> Path:
    """A fresh run folder, created: kind, title, time and a random suffix (``runs.unique_folder``; R18-3)."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return unique_folder(Path(runs_dir), f"{kind}_{slug(title)[:40]}_{stamp}")


def _opt(flag: str, value) -> list[str]:
    return [flag, str(value)] if value not in (None, "", []) else []


def idea_command(source: str, value: str, out: Path, eft: int = 4, models: int = 4, budget: float = 0.0,
                 model: str = "") -> list[str]:
    """Track 1's front end: ``source`` is fields or lagrangian (a YAML file) or text (words; paid)."""
    if source not in TRACK1_INPUTS:
        raise ValueError(f"the input is one of {', '.join(TRACK1_INPUTS)}")
    words = source == "text"
    if words and budget <= 0:
        raise ValueError("an idea in words needs a budget")
    return (["idea", f"--{source}", value, "--eft", str(eft)] + (["--models", str(models)] if words else [])
            + (["--budget", f"{budget:g}"] if words else []) + (_opt("--model", model) if words else [])
            + ["--out", str(out)])


def derive_command(out: Path, budget: float, model: Path | None = None, description: str = "",
                   checker: str = "gpt-5.6-sol", deriver: str = "claude-opus-5-5") -> list[str]:
    """DM8's two-model coefficient derivation (paid): a typed model without a derivation (a YAML file), or the
    model in words; ``checker`` "none" leaves the derivation unchecked."""
    if budget <= 0:
        raise ValueError("deriving the coefficients needs a budget")
    if (model is None) == (not description.strip()):
        raise ValueError("give a typed model or the model in words, not both")
    if checker == deriver:
        raise ValueError("an independent check needs a different model from the deriver (or no check)")
    source = [str(model)] if model is not None else ["--description", description]
    return (["lagrangian", *source, "--derive", "--budget", f"{budget:g}", "--model", deriver, "--checker", checker,
             "--out", str(out)])


def track1_command(model: Path, out: Path, x: str = "", y: str = "",
                   literature: bool = False, parent: Path | None = None, coverage_depth: int = 0,
                   coverage_budget: int = 250, coverage_strategy: str = "uniform", coverage_exploration: int = 1,
                   approved_model_hash: str = "", mediator_ratio: float = 0., reviewed_scan_hash: str = "",private_limits: list[str] | None=None,
                   profile:str|None=None, halo: str = "", halo_family: str = "", discovery: str = "") -> list[str]:
    """Track 1 on a typed model (a YAML file), with its axes, coverage and reviewed hashes; ``halo``: preset,
    published or benchmark (empty: the setting), ``halo_family`` the benchmark's family (``halo_flags``);
    ``discovery`` a frozen constraint-survey assessment (``discovery:SESSION@HASH``) pinned to the run."""
    return (["track1", str(model), "--out", str(out)] + _opt("--x",x) + _opt("--y",y)
            + (["--literature"] if literature else []) + _opt("--parent", parent)
            + _opt("--approved-model-hash",approved_model_hash) + _opt("--ratio",mediator_ratio if mediator_ratio else "")
            + _opt("--reviewed-scan-hash",reviewed_scan_hash)
            + _coverage_options(coverage_depth, coverage_budget, coverage_strategy, coverage_exploration)
            + [arg for ref in private_limits or [] for arg in ('--private-limit',ref)]+_opt('--profile',profile)
            + halo_flags("track1", halo, halo_family) + _opt("--discovery", discovery))


# the halo treatments offered with Track 1 and Explain a signal (``--halo``), and with Track 2 (``adroit signal``)
HALO_CHOICES = {'': 'the setting (default: the preset halo region)',
                'preset': 'the preset halo region (ρ₀, v₀, v_esc over their joint 95% region)',
                'published': "each experiment's published halo (reproduction)",
                'benchmark': 'a fixed common benchmark (every comparison able to use it at one halo; the others named)'}
TRACK2_HALO_CHOICES = {'': "each search's own published halo (default)",
                       'benchmark': 'a fixed common benchmark (the fit, the null limits and every comparison able to use '
                                    'it at one halo; the others named)',
                       'compare': 'compare the halo models: the whole run at each available benchmark (SHM, SHM++), '
                                  'ranked together'}
HALO_TRACKS = {"track1": HALO_CHOICES, "single_idea": HALO_CHOICES, "track2": TRACK2_HALO_CHOICES}


def halo_flags(track: str, halo: str = "", family: str = "") -> list[str]:
    """The command line's halo options for a form's choice (``halo_choice``): ``--halo`` (a treatment the track offers;
    empty, its default) and, for a benchmark of a family other than the default, ``--halo-family``. A family that is
    not available is refused here, before anything is launched, never run as another."""
    from adroit.core import halo_choice
    choices = HALO_TRACKS[track]
    if halo not in choices:
        raise ValueError(f"the halo is one of {', '.join(repr(c) for c in choices)} here, not {halo!r}")
    if halo == "compare" and family and family != halo_choice.DEFAULT_FAMILY:
        raise ValueError("comparing the halo models takes every available family; choose none")
    if family:
        halo_choice.available(family)
        if halo != "benchmark" and family != halo_choice.DEFAULT_FAMILY:
            raise ValueError(f"the {halo_choice.family(family).label} family applies to a fixed benchmark only")
    if halo == "benchmark":
        halo_choice.fixed(family or halo_choice.DEFAULT_FAMILY)          # its benchmark exists
    flags = _opt("--halo", halo)
    return flags + (["--halo-family", family] if halo == "benchmark" and family and
                    family != halo_choice.DEFAULT_FAMILY else [])


def halo_preview(track: str, halo: str = "", family: str = ""):
    """The resolution a form's choice launches with (``halo_choice.resolve``, as the run will resolve it; an empty Track
    1 choice by the setting now), or the reason it cannot launch: (resolution or None, the reason or "")."""
    from adroit.core import halo_choice
    from adroit.parameter_space import halo_region
    try:
        halo_flags(track, halo, family)
        if halo in ("benchmark", "compare"):       # a comparison's first halo: the run its study shows
            value = halo_choice.fixed(family or halo_choice.DEFAULT_FAMILY)
        elif track == "track2":
            value = None
        else:
            value = halo or halo_region.default()
            value = halo_region.HaloPreset() if value == "preset" else value
        return halo_choice.resolve(value, track="track2" if track == "track2" else "track1"), ""
    except (ValueError, halo_choice.UnknownHalo) as error:
        return None, str(error)


def review_scan(model_text: str, x: str = "", y: str = "", mediator_ratio: float = 0., n: int = 20):
    """The same canonical model, engine mapping and axis validation used by execution."""
    import yaml
    from adroit.orchestrator.model_approval import read_model
    from adroit.parameter_space.classify import classify
    from adroit.parameter_space.scan import Axis
    from adroit.parameter_space.scan_setup import model_relations,preview,setup_identity
    def axis(text):
        if not text:
            return None
        parts=text.split(':')
        if not 3<=len(parts)<=5 or (len(parts)>3 and parts[3] not in ('log','lin')):
            raise ValueError("axis format: parameter:low:high[:log|lin][:n]")
        return Axis(parameter=parts[0],low=float(parts[1]),high=float(parts[2]),
                    log=parts[3]!='lin' if len(parts)>3 else True,n=int(parts[4]) if len(parts)>4 else n)
    spec=read_model(yaml.safe_load(model_text))
    cls,point,notes=classify(spec)
    ax,ay=axis(x),axis(y)
    setup=preview(cls,point,ax,ay,mediator_ratio or None,notes=notes,n=n,coupling_relations=model_relations(spec,"",ax,ay))
    token=setup_identity(spec,cls,point,setup)
    return spec,setup,token


def axis_text(data: dict) -> str:
    """A scan axis as ``parameter:low:high:log|lin:n``."""
    return f"{data['parameter']}:{data['low']:.17g}:{data['high']:.17g}:{'log' if data['log'] else 'lin'}:{data['n']}"


def portal_command(entry: str, out: Path, literature: bool = False, coverage_depth: int = 0,
                   coverage_budget: int = 250, coverage_strategy: str = "uniform", coverage_exploration: int = 1,
                   reviewed_scan_hash: str = "",private_limits: list[str] | None=None,profile:str|None=None,
                   halo: str = "", halo_family: str = "") -> list[str]:
    """Track 1 for an entry of the portal library, at its benchmark and in its plane, with its halo choice
    (``halo_flags``)."""
    return (["track1", "--portal", entry, "--out", str(out)] + (["--literature"] if literature else [])
            + _opt("--reviewed-scan-hash",reviewed_scan_hash)
            + _coverage_options(coverage_depth, coverage_budget, coverage_strategy, coverage_exploration)
            + [arg for ref in private_limits or [] for arg in ('--private-limit',ref)]+_opt('--profile',profile)
            + halo_flags("track1", halo, halo_family))


def _coverage_options(depth: int, budget: int, strategy: str = "uniform", exploration: int = 1) -> list[str]:
    if not 0 <= depth <= 3 or not 1 <= budget <= 10000:
        raise ValueError("Coverage depth must be 0–3 and budget 1–10000")
    if strategy not in ("uniform", "adaptive") or (strategy == "adaptive" and not depth):
        raise ValueError("Adaptive coverage requires a positive depth; choose uniform or adaptive")
    if not 1 <= exploration <= 3 or (strategy == "adaptive" and exploration > depth):
        raise ValueError("Adaptive exploration depth must be 1–3 and cannot exceed maximum depth")
    options = ["--coverage-depth", str(depth), "--coverage-budget", str(budget)] if depth else []
    return options + (["--coverage-strategy", strategy, "--coverage-exploration", str(exploration)]
                       if strategy == "adaptive" else [])


def signal_command(experiment: str, out: Path, nulls: list[str] | None = None, toys: int = 200_000,
                   models: list[Path] | None = None, masses: str = "", with_library: bool = False,
                   unverified: bool = False,required_styles: list[str]|None=None,preferred_styles:list[str]|None=None,
                   splittings:str='0',profile:str|None=None,track1_results:list[str]|None=None,
                   eligibility_budget:int=32,eligibility:bool=True, halo: str = "", halo_family: str = "",
                   agent: bool = False, agent_rounds: int = 3, agent_model: str = "", budget: float = 0.0) -> list[str]:
    """Path 2 on a search with events, with the null experiments, the toys, the user's models, the model-property
    requirements and preferences and the halo choice (``halo_flags``: empty, each search's published halo); with
    ``agent``, the agent-led search after it, paid within ``budget``."""
    command = ["signal", "--experiment", experiment, "--toys", str(toys), "--out", str(out)]
    if nulls is not None:
        command += ["--null", ",".join(nulls)]
    for path in models or []:
        command += ["--model", str(path)]
    from adroit.core.model_preferences import parse_preference
    for mode,values in [('required',required_styles),('preferred',preferred_styles)]:
        for value in values or []:
            command+=['--require-style' if mode=='required' else '--prefer-style',parse_preference(value,mode).property]
    if splittings.strip()!='0':
        command+=['--splittings',splittings]
    command+=_opt('--profile',profile)
    for path in track1_results or []:
        command+=['--track1-result',path]
    if eligibility_budget!=32:
        command+=['--eligibility-budget',str(eligibility_budget)]
    if not eligibility:
        command+=['--no-eligibility']
    if agent:
        if budget <= 0:
            raise ValueError("the agent-led search needs a budget")
        command += ["--agent", "--agent-rounds", str(int(agent_rounds)), "--budget", f"{budget:g}"]
        command += ["--agent-model", agent_model] if agent_model else []
    return (command + _opt("--masses", masses) + (["--with-library"] if with_library else [])
            + (["--unverified"] if unverified else []) + halo_flags("track2", halo, halo_family))


def single_idea_command(model: Path, experiment: str, out: Path, masses: str = "5:1000:16", toys: int = 20_000,
                        grid: int = 20, literature: bool = False, unverified: bool = False,
                        parent: Path | None = None, advanced: dict | None = None) -> list[str]:
    """The single-idea study of one model (a YAML file) against one search with events; ``advanced`` holds the
    command line's further options (``ADVANCED``), each left out when absent or at its default."""
    return (["single-idea", str(model), "--experiment", experiment, "--masses", masses, "--toys", str(toys),
             "--grid", str(grid), "--out", str(out)] + (["--literature"] if literature else [])
            + (["--unverified"] if unverified else []) + _opt("--parent", parent) + advanced_options(advanced or {}))


# single-idea's further options: name → (flag, default); a default is never written
ADVANCED = {"nulls": ("--null", "CRESST-III 2019,CDMSlite Run 2,PICO-60 C3F8 (2019),DEAP-3600 (2019)"),
            "profile": ("--profile", ""), "propagation": ("--propagation", ""), "halo": ("--halo", ""),
            "halo_family": ("--halo-family", ""),
            "fit_grid": ("--fit-grid", 33),
            "fit_evaluations": ("--fit-evaluations", 512), "native_joint": ("--native-joint", ""),
            "native_toys": ("--native-toys", 1000), "native_seed": ("--native-seed", 20261007),
            "native_fit_budget": ("--native-fit-budget", 10000), "native_domain": ("--native-domain", "")}
NATIVE_PAIRS = ("DEAP-3600 (2019)", "PICO-60 C3F8 (2019)")


def advanced_options(values: dict) -> list[str]:
    """The flags of the advanced options that differ from the command line's defaults; native options only with a
    native pair."""
    unknown = set(values) - set(ADVANCED)
    if unknown:
        raise ValueError(f"unknown advanced options: {', '.join(sorted(unknown))}")
    native = values.get("native_joint") or ""
    if native and native not in NATIVE_PAIRS:
        raise ValueError(f"the native joint pair is one of {', '.join(NATIVE_PAIRS)}")
    halo_flags("single_idea", values.get("halo") or "", values.get("halo_family") or "")    # refused here, not run
    out = []
    for name, (flag, default) in ADVANCED.items():
        value = values.get(name, default)
        if name.startswith("native_") and name != "native_joint" and not native:
            continue
        if name == "nulls" and "nulls" in values and value == "":
            out += [flag, ""]                 # cleared on purpose: no null experiments, not the defaults (S18-07)
        elif value not in (None, "") and value != default:
            out += [flag, str(value)]
    return out


def native_fit_command(model: Path, domain: Path, out: Path, null: str = "PICO-60 C3F8 (2019)", fit_grid: int = 5,
                       profile_grid: int = 5, evaluations: int = 12000) -> list[str]:
    """The native fit of shared bounded physical parameters to a declared native pair (``adroit native-fit``)."""
    if null not in NATIVE_PAIRS:
        raise ValueError(f"the native pair's null experiment is one of {', '.join(NATIVE_PAIRS)}")
    return ["native-fit", str(model), "--domain", str(domain), "--null", null, "--fit-grid", str(fit_grid),
            "--profile-grid", str(profile_grid), "--evaluations", str(evaluations), "--out", str(out)]


def promote_command(run: Path, which: list[str], budget: float = 0.0, uv_models: int = 3, toys: int = 20_000,
                    grid: int = 16, literature: bool = False, model: str = "", mass_points: int = 9,
                    parent_sha256: str = "") -> list[str]:
    """Promote candidates of a Path 2 run to studies; with a budget, the model builder also proposes completions
    (paid). ``toys``, ``grid`` and ``mass_points`` set each child study's size; ``parent_sha256``, the version of the
    run's result they were chosen from (refused if it has changed: the auditor's CX recheck, CY-02)."""
    return (["promote", str(run), *which, "--toys", str(toys), "--grid", str(grid), "--mass-points", str(mass_points)]
            + (["--parent-sha256", parent_sha256] if parent_sha256 else [])
            + (["--literature"] if literature else [])
            + (["--budget", f"{budget:g}", "--uv-models", str(uv_models), *_opt("--model", model)] if budget > 0 else []))


def anomaly_check_command(record: Path) -> list[str]:
    """The consistency check of an anomaly record."""
    return ["anomaly", "check", str(record)]


def draft_record_path(runs_dir: Path, arxiv: str, job_folder: Path) -> Path:
    """The default file of a signal record drafted from a paper: the runs folder's signal_records, named by the paper
    and the run (its folder's random suffix), so that two drafts of one paper never share a file (the workflow audit's
    WA-05, 2026-10-24: the second had replaced the first, whose page then opened the second)."""
    return Path(runs_dir) / "signal_records" / f"draft_{slug(arxiv)}_{Path(job_folder).name.rsplit('_', 1)[-1]}.yaml"


def file_output(command: list[str]) -> Path | None:
    """The file a command writes outside its run folder (``anomaly draft``'s record), None if its output is its
    folder."""
    if command[:2] == ["anomaly", "draft"] and "--out" in command[:-1]:
        return Path(command[command.index("--out") + 1]).expanduser().resolve()
    return None


def output_clash(command: list[str], others: list[list[str]] = ()) -> str:
    """Why a command's file output would not be its own: a file already there, or another request's file (a batch's
    earlier item); "" if it would. Checked before a launch or a batch, as the command checks again before paying
    (WA-05)."""
    path = file_output(command)
    if path is None:
        return ""
    if path.exists():
        return f"{path} already exists: choose a new file (a draft never replaces another)"
    if any(file_output(other) == path for other in others):
        return f"another request in the batch already writes {path}: give each its own file"
    return ""


def anomaly_draft_command(arxiv: str, out: Path, budget: float, model: str = "") -> list[str]:
    """The drafter of an anomaly record from an arXiv paper (paid)."""
    if budget <= 0:
        raise ValueError("the drafter needs a budget")
    return ["anomaly", "draft", "--arxiv", arxiv, "--out", str(out), "--budget", f"{budget:g}", *_opt("--model", model)]
