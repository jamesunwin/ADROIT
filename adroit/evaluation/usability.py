"""The analysis of the usability sessions (R-24), as declared in ``docs/usability/protocol.md`` before any session.

Inputs: the paired timers (``assistance_timing.ResearcherSession``, one file a session), the System Usability Scale
answers (one ``SusResponse`` a participant) and, optionally, the opt-in command logs (``usage_log``). Output: a
``UsabilityReport`` and its Markdown. Nothing is imputed: a session that is repeated, unpaired, unfinished,
unattested or unsuccessful is counted and named with why, and left out of the time comparison by the rule of
``assistance_timing.summarize``, applied task by task (repeats counted before any quality filter). The API cost is
every assisted session's. The test is on participants, not tasks: each participant's mean saving over their paired
tasks is one observation, and the signed-rank test needs ``MIN_PARTICIPANTS_FOR_TEST`` of them (the batch audit's
B20-05 and B20-06, 2026-10-20).
"""

from __future__ import annotations

from statistics import median

from pydantic import Field

from adroit.core.state import StrictModel
from adroit.evaluation.assistance_timing import ResearcherSession, summarize
from adroit.evaluation.usage_log import UsageEntry

MIN_PARTICIPANTS_FOR_TEST = 6   # independent participants; below this, descriptive only (the protocol's §6)


class SusResponse(StrictModel):
    """One participant's ten answers to the System Usability Scale (Brooke 1996), each 1 (strongly disagree) to 5."""
    participant: str
    answers: list[int] = Field(min_length=10, max_length=10)


def sus_score(answers: list[int]) -> float:
    """The SUS score, 0–100: odd items contribute (answer − 1), even items (5 − answer); the sum times 2.5."""
    if len(answers) != 10 or any(a not in (1, 2, 3, 4, 5) for a in answers):
        raise ValueError("the SUS has ten answers, each 1 to 5")
    return 2.5 * sum(a - 1 if i % 2 == 0 else 5 - a for i, a in enumerate(answers))


class TaskRow(StrictModel):
    """One task: its pairs' effort saved (manual − assisted active seconds) and each condition's success."""
    task: str
    pairs: int
    seconds_saved: list[float] = Field(default_factory=list)
    median_seconds_saved: float | None = None
    success: dict[str, str] = Field(default_factory=dict)        # condition → "k of n" finished and attested


class CommandRow(StrictModel):
    """One session label's command log: how many commands, their total time, and how many ended in an error."""
    session: str
    commands: int
    seconds: float
    errors: int


class UsabilityReport(StrictModel):
    """The declared analysis (module docstring)."""
    sessions: int
    excluded: dict[str, str] = Field(default_factory=dict)       # session id → why it is out of the comparison
    tasks: list[TaskRow] = Field(default_factory=list)
    pairs: int = 0
    median_seconds_saved: float | None = None
    quartiles_seconds_saved: tuple[float, float] | None = None
    participants: dict[str, float] = Field(default_factory=dict)   # participant → mean seconds saved over tasks
    wilcoxon_p: float | None = None          # two-sided, over participants; only with MIN_PARTICIPANTS_FOR_TEST
    sus: dict[str, float] = Field(default_factory=dict)
    median_sus: float | None = None
    commands: list[CommandRow] = Field(default_factory=list)
    api_cost_usd: float = 0.0                                      # every assisted session's, paired or not
    interpretation: str = ("paired, self-timed active effort of the participants who took part, on these tasks; "
                           "descriptive, not a population estimate; a saving is reported only for pairs that both "
                           "met the task's quality bar")


def _success(sessions: list[ResearcherSession]) -> dict[str, str]:
    done = [s for s in sessions if s.phase == "finished" and s.researcher_attested]
    return {c: f"{sum(bool(s.task_success) for s in done if s.condition == c)} of "
               f"{sum(s.condition == c for s in done)}" for c in ("manual", "assisted")}


def _quartiles(values: list[float]) -> tuple[float, float] | None:
    if len(values) < 2:
        return None
    import numpy as np
    low, high = np.percentile(values, [25, 75])
    return float(low), float(high)


def _wilcoxon(values: list[float]) -> float | None:
    if len(values) < MIN_PARTICIPANTS_FOR_TEST or not any(values):
        return None
    from scipy.stats import wilcoxon
    return float(wilcoxon(values, alternative="two-sided").pvalue)


def _commands(entries: list[UsageEntry]) -> list[CommandRow]:
    rows: dict[str, CommandRow] = {}
    for e in entries:
        row = rows.setdefault(e.session, CommandRow(session=e.session, commands=0, seconds=0.0, errors=0))
        row.commands, row.seconds, row.errors = row.commands + 1, row.seconds + e.seconds, row.errors + (
            e.outcome == "error")
    return [rows[k] for k in sorted(rows)]


def analyse(sessions: list[ResearcherSession], sus: list[SusResponse] | None = None,
            usage: list[UsageEntry] | None = None) -> UsabilityReport:
    """The declared analysis of a set of sessions (module docstring)."""
    sessions = list({s.id: s for s in sessions}.values())
    report = UsabilityReport(sessions=len(sessions))
    saved: list[float] = []
    by_participant: dict[str, list[float]] = {}
    for task in sorted({s.task for s in sessions}):
        group = [s for s in sessions if s.task == task]
        paired = summarize(group)
        report.excluded.update(paired.reasons)
        report.api_cost_usd += paired.api_cost_usd
        saved += paired.paired_seconds_saved
        for pair in paired.pairs:
            by_participant.setdefault(pair["participant"], []).append(pair["seconds_saved"])
        report.tasks.append(TaskRow(task=task, pairs=paired.paired_completed_tasks,
                                    seconds_saved=paired.paired_seconds_saved, success=_success(group),
                                    median_seconds_saved=median(paired.paired_seconds_saved)
                                    if paired.paired_seconds_saved else None))
    report.pairs = len(saved)
    report.median_seconds_saved = median(saved) if saved else None
    report.participants = {who: sum(v) / len(v) for who, v in sorted(by_participant.items())}
    report.quartiles_seconds_saved = _quartiles(saved)
    report.wilcoxon_p = _wilcoxon(list(report.participants.values()))
    report.sus = {r.participant: sus_score(r.answers) for r in sus or []}
    report.median_sus = median(report.sus.values()) if report.sus else None
    report.commands = _commands(usage or [])
    return report


def markdown(report: UsabilityReport) -> str:
    """The report as the protocol's §7 lays it out."""
    def secs(x: float | None) -> str:
        return "—" if x is None else f"{x:.0f} s"
    lines = ["# Usability sessions: the analysis (R-24)", "",
             f"{report.sessions} sessions; {report.pairs} matched pairs in the time comparison; "
             f"{len(report.excluded)} sessions left out of it"
             + (": " + "; ".join(f"{sid} ({why})" for sid, why in report.excluded.items()) if report.excluded else "")
             + ".", "",
             "| task | pairs | effort saved per pair (manual − assisted) | median | success, manual | success, assisted |",
             "|---|---|---|---|---|---|"]
    lines += [f"| {t.task} | {t.pairs} | {', '.join(secs(x) for x in t.seconds_saved) or '—'} | "
              f"{secs(t.median_seconds_saved)} | {t.success.get('manual', '—')} | {t.success.get('assisted', '—')} |"
              for t in report.tasks]
    quart = report.quartiles_seconds_saved
    lines += ["", f"**All pairs (descriptive):** median effort saved {secs(report.median_seconds_saved)}"
              + (f" (quartiles {quart[0]:.0f} s and {quart[1]:.0f} s)" if quart else "") + ".",
              f"**Participants:** {len(report.participants)}, each one observation (the mean of their pairs): "
              + (", ".join(f"{who} {secs(v)}" for who, v in report.participants.items()) or "none")
              + (f"; Wilcoxon signed-rank over participants, two-sided, p = {report.wilcoxon_p:.3g}"
                 if report.wilcoxon_p is not None else
                 f"; no test (fewer than {MIN_PARTICIPANTS_FOR_TEST} participants, or no difference)") + ".",
              "**The System Usability Scale:** " + (", ".join(f"{p} {s:.1f}" for p, s in report.sus.items())
                                                     + f"; median {report.median_sus:.1f}" if report.sus else "none")
              + ".", f"**API cost of every assisted session, paired or not:** ${report.api_cost_usd:.2f}."]
    if report.commands:
        lines += ["", "| session | commands | time in commands | ended in an error |", "|---|---|---|---|"]
        lines += [f"| {c.session or '(no label)'} | {c.commands} | {c.seconds:.0f} s | {c.errors} |"
                  for c in report.commands]
    return "\n".join([*lines, "", f"*{report.interpretation}.*", ""])
