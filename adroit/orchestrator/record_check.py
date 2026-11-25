"""A language model's check of a user-added experimental record, in place of a person's review at the researcher's
choice (the owner, 2026-11-18, the post-review changes item 2).

One check session, one approved cap (``Intake``, in the experimental library). The checking model (Claude Fable 5.1
by default, or GPT-5.6 Sol) answers two questions, whether this is the right limit (correct, current, relevant) and
whether it was imported correctly with its conditions stated, and the review's six checks (``agents.record_check``).
It is given the record's review packet, the source pages its claims cite, the library's records of the same
experiment, and a literature search (arXiv, newest first).

ADROIT decides from the answer, not the model:
- every newer paper the model names is looked up on arXiv; one whose identifier, title or year does not match is
  reported as unconfirmed and is never a reason to reject;
- a confirmed later analysis by the same collaboration (``superseded``) is a major defect; a stronger limit from
  another experiment is a note;
- a failed question or check, or a major defect, fails the check; minor defects are notes.

A passed check signs the result's review as the model's (``experimental_review.approve_by_model``). A failed one is
re-read by the record assistant (the intake agent: ``ExperimentalExtraction``, its own model, under this session's cap)
with the check's report, as a new revision, which is checked again: at most ``retries`` times (two by default). Then
the session comes back to the researcher with each mismatch, who approves the record in person or suggests another
route; a suggestion is a new check session, which applies it first (``instruction``) and is checked once.
"""
from __future__ import annotations

import difflib
import re
from datetime import datetime, timezone
from pathlib import Path

from adroit.core.checkpoint import atomic_json, run_lock
from adroit.core.evidence import content_hash
from adroit.core.record_check import CheckOutcome, CheckRun, Citation, RecordCheck
from adroit.library.experimental import ExperimentalCatalog

SOURCE_CHARS = 60_000          # the source text a check sends at most (its request stays well inside its price tier)
IMAGES = 4                     # page images a check sends at most (an Anthropic model only)
SEARCHED = 25                  # papers the literature search keeps


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _words(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (text or "").lower()))


def same_title(claimed: str, found: str) -> bool:
    """Whether a model's title names the paper arXiv returned (case, punctuation and small differences aside)."""
    a, b = _words(claimed), _words(found)
    return bool(a and b) and (a in b or b in a or difflib.SequenceMatcher(None, a, b).ratio() >= 0.8)


def confirmed(answer, lookup) -> list[Citation]:
    """Each newer paper the model named, looked up on arXiv (``lookup``: ``references.arxiv_lookup``): confirmed only
    where the identifier exists and its title (and year, where both give one) match."""
    from adroit.retrieval.references import Reference
    named = [n for n in answer.newer_results if n.arxiv_id.strip()]
    ids = [re.sub(r"^arxiv:", "", n.arxiv_id.strip(), flags=re.I) for n in named]
    try:
        found = lookup([Reference(kind="arxiv", id=i) for i in ids]) if ids else {}
        failure = ""
    except Exception as error:                                   # noqa: BLE001 - any failure leaves them unconfirmed
        found, failure = {}, f"arXiv could not be asked ({error.__class__.__name__})"
    out = []
    for n, i in zip(named, ids):
        paper = found.get(i)
        if paper is None:
            why = failure or "arXiv has no such identifier"
        elif not same_title(n.title, paper.title):
            why = "the title arXiv gives is another paper's"
        else:
            why = "the year differs" if n.year and paper.year and abs(n.year - paper.year) > 1 else ""
        out.append(Citation(arxiv_id=i, claimed_title=n.title, relation=n.relation, confirmed=not why,
                            found_title=paper.title if paper else "", found_year=paper.year if paper else None,
                            why=why))
    return out


def decide(answer, citations: list[Citation]) -> tuple[list[str], list[str]]:
    """(major defects, notes) from the model's answer and the confirmed citations (module docstring)."""
    from adroit.agents.record_check import CHECKS
    major = [f"{d.what}: the record says {d.record_says or '(nothing)'}; the source says {d.source_says or '(nothing)'}"
             + (f" ({d.location})" if d.location else "") for d in answer.defects if d.severity == "major"]
    notes = [f"{d.what}" + (f" ({d.location})" if d.location else "") for d in answer.defects if d.severity == "minor"]
    for question, label in ((answer.right_limit, "the right limit"), (answer.imported_correctly, "imported correctly")):
        if not question.passed:
            major.append(f"{label}: {question.reason}" + (f" ({question.location})" if question.location else ""))
    # exactly one answer per check (the post-review audit's PR-05: the last of two answers had been kept, so a failed
    # check answered again as passed approved the record): a repeat, or an unknown name, is a failure with its reason
    answered: dict = {}
    for c in answer.checklist:
        answered.setdefault(c.name, []).append(c)
    for name in sorted(set(answered) - set(CHECKS)):
        major.append(f"{name}: not one of the checks asked for")
    for name in CHECKS:
        items = answered.get(name, [])
        if not items:
            major.append(f"{name}: not answered")
        elif len(items) > 1:
            major.append(f"{name}: answered {len(items)} times; each check is answered once")
        elif not items[0].passed:
            item = items[0]
            major.append(f"{name}: {item.reason}" + (f" ({item.location})" if item.location else ""))
    for c in citations:
        if c.confirmed and c.relation == "superseded":
            major.append(f"superseded by a later analysis of the same collaboration: arXiv:{c.arxiv_id} "
                         f"({c.found_title}, {c.found_year})")
        elif c.confirmed and c.relation == "stronger_elsewhere":
            notes.append(f"a stronger limit from another experiment: arXiv:{c.arxiv_id} ({c.found_title}); add it as "
                         "its own record to use it")
        elif not c.confirmed:
            notes.append(f"unconfirmed citation, not used: arXiv:{c.arxiv_id} “{c.claimed_title}” ({c.why})")
    return major, notes


def report(check: RecordCheck) -> str:
    """The check's report, as the record assistant reads it for a re-reading and the researcher reads it."""
    lines = [f"A record check by {check.model} found these problems in result {check.result_id}; correct each from "
             "the sources, keeping every value that is right:"]
    lines += [f"- {m}" for m in check.major]
    lines += [f"- (minor) {n}" for n in check.minor if not n.startswith("unconfirmed")]
    return "\n".join(lines)


class RecordChecker:
    """Record check sessions in the experimental library (module docstring). ``search`` and ``lookup``: the
    literature search and the arXiv lookup (``retrieval.references``); a test gives its own."""

    def __init__(self, catalog: ExperimentalCatalog | None = None, search=None, lookup=None) -> None:
        from adroit.orchestrator.experimental_extraction import ExperimentalExtraction
        from adroit.retrieval import references
        self.catalog = catalog or ExperimentalCatalog()
        self.extraction = ExperimentalExtraction(self.catalog)
        self.budgets = self.extraction.budgets
        self.search = search or references.search_arxiv
        self.lookup = lookup or references.arxiv_lookup

    def start(self, reference: str, result_id: str, budget: float, model: str = "", reanalysis_model: str = "",
              retries: int = 2, instruction: str = "", approval: str = "") -> CheckRun:
        """Open a check session with its approved cap (``approval``: how it was approved) and record what it asks."""
        from adroit.constraints.experimental_review import packet
        from adroit.core.pricing import CHECKER_MODELS, DEFAULT_CHECKER, DEFAULT_PRIMARY, PRIMARY_MODELS
        model, reanalysis_model = model or DEFAULT_CHECKER, reanalysis_model or DEFAULT_PRIMARY
        if model not in CHECKER_MODELS or reanalysis_model not in PRIMARY_MODELS:
            raise ValueError("choose a checking model and a record assistant's model from the workbench's lists")
        if budget <= 0:
            raise ValueError("a record check needs a budget")
        packet(reference, result_id, catalog=self.catalog)           # the record and result exist (refused otherwise)
        s = self.budgets.start(budget, model, approval=approval)
        run = CheckRun(session_id=s.session_id, revision=reference, result_id=result_id, model=model,
                       reanalysis_model=reanalysis_model, retries=retries, instruction=instruction.strip(),
                       created_at=_now())
        atomic_json(self.budgets.folder(s.session_id) / "record_check.json", run.model_dump(mode="json"))
        return run

    def request(self, session: str) -> CheckRun:
        """A check session's request."""
        return CheckRun.model_validate_json((self.budgets.folder(session) / "record_check.json").read_text())

    def outcome(self, session: str) -> CheckOutcome | None:
        """How a check session ended; None while it has not."""
        path = self.budgets.folder(session) / "outcome.json"
        return CheckOutcome.model_validate_json(path.read_text()) if path.exists() else None

    def load(self, check_id: str) -> RecordCheck:
        """A check's receipt, refused if modified."""
        raw = (self.catalog.path(f"checks/{check_id}.json")).read_text()
        check = RecordCheck.model_validate_json(raw)
        if content_hash(check.model_dump(mode="json", exclude={"check_id"})) != check_id:
            raise ValueError("record check receipt modified")
        return check

    def sessions(self, reference: str, result_id: str) -> list[tuple[CheckRun, CheckOutcome | None]]:
        """The check sessions of a result of any revision of this record's lineage, newest first."""
        lineage = self.catalog.load(reference).experiment_id
        found = []
        for path in sorted((self.budgets.catalog.root / "intake").glob("*/record_check.json")):
            try:
                run = CheckRun.model_validate_json(path.read_text())
                if run.result_id == result_id and self.catalog.load(run.revision).experiment_id == lineage:
                    found.append((run, self.outcome(run.session_id)))
            except (OSError, ValueError):
                continue
        return sorted(found, key=lambda pair: pair[0].created_at, reverse=True)

    def run(self, session: str, llm_for=None) -> CheckOutcome:
        """Check, re-read and check again as the session's request says (module docstring); ``llm_for(model)``: a
        test's client for a model (live: each budgeted against this session's cap)."""
        from adroit.agents.budget import BudgetExceeded
        run = self.request(session)
        revision, checks, revisions = run.revision, [], [run.revision]
        try:
            if run.instruction:
                revision = self.reanalyse(run, revision, run.instruction, llm_for)
                revisions.append(revision)
            previous = ""
            for round_ in range(run.retries + 1):
                check = self.check(run, revision, round_, previous, llm_for)
                checks.append(check.check_id)
                previous = check.check_id
                if check.passed:
                    return self._approved(run, check, checks, revisions)
                if round_ == run.retries:
                    return self._finish(run, "needs_you", checks, revisions, check=check,
                                        why="the record check and the record assistant did not agree")
                revision = self.reanalyse(run, revision, report(check), llm_for)
                revisions.append(revision)
        except (BudgetExceeded, ValueError, RuntimeError, OSError) as error:
            return self._finish(run, "stopped", checks, revisions, why=str(error))
        raise AssertionError("unreachable: the last round returns")

    def _approved(self, run: CheckRun, check: RecordCheck, checks: list[str], revisions: list[str]) -> CheckOutcome:
        from adroit.constraints.experimental_review import approve_by_model
        try:
            review = approve_by_model(check, self.catalog)
        except ValueError as error:
            return self._finish(run, "needs_you", checks, revisions, check=check, why=str(error))
        return self._finish(run, "approved", checks, revisions, check=check, review_id=review.review_id)

    def _finish(self, run: CheckRun, status: str, checks: list[str], revisions: list[str], check=None,
                review_id: str = "", why: str = "") -> CheckOutcome:
        outcome = CheckOutcome(session_id=run.session_id, status=status, checks=checks, revisions=revisions,
                               final_revision=revisions[-1], result_id=run.result_id, review_id=review_id,
                               mismatches=check.major if check else [], notes=check.minor if check else [], why=why,
                               finished_at=_now())
        atomic_json(self.budgets.folder(run.session_id) / "outcome.json", outcome.model_dump(mode="json"))
        return outcome

    def check(self, run: CheckRun, revision: str, round_: int, previous: str = "", llm_for=None) -> RecordCheck:
        """One check of ``revision``'s result (module docstring), its receipt stored."""
        from adroit.agents import record_check as agent
        from adroit.constraints.experimental_review import packet
        value = packet(revision, run.result_id, catalog=self.catalog)
        sources, images = self.sources(revision, value, run.model)
        library = self.library(revision)
        literature = self.literature(revision)
        with run_lock(self.budgets.folder(run.session_id)):
            llm = self._client(run.session_id, run.model, llm_for)
            answer = agent.check(llm, run.model, {k: value[k] for k in ("revision", "result_id", "keys", "scientific",
                                                                        "warnings", "differences")},
                                 sources, library, literature, images)
        citations = confirmed(answer, self.lookup)
        major, minor = decide(answer, citations)
        body = dict(session_id=run.session_id, revision=revision, result_id=run.result_id, keys=value["keys"],
                    scientific_sha256=value["scientific_sha256"], model=run.model, round=round_, created_at=_now(),
                    answer=answer.model_dump(mode="json"), citations=[c.model_dump(mode="json") for c in citations],
                    search={k: v for k, v in literature.items() if k != "papers"} | {
                        "found": [p["arxiv_id"] for p in literature.get("papers", [])]},
                    library=[entry["reference"] for entry in library], major=major, minor=minor, passed=not major,
                    previous_check=previous)
        check = RecordCheck(check_id=content_hash(body), **body)
        with run_lock(self.catalog.root):
            atomic_json(self.catalog.path(f"checks/{check.check_id}.json"), check.model_dump(mode="json"))
        return check

    def _client(self, session: str, model: str, llm_for):
        """The checking model's client, budgeted against the session's cap; a test's fake where given."""
        from adroit.agents.llm import BudgetedLLMClient, FakeLLMClient, LLMClient, OpenAIClient
        from adroit.agents.record_check import MAX_OUTPUT
        if llm_for is not None:
            llm = llm_for(model)
            if not isinstance(llm, FakeLLMClient):
                raise ValueError("a live record check must use the session budget")
            return llm
        s = self.budgets.session(session)
        client = OpenAIClient if model.startswith("gpt-") else LLMClient
        llm = BudgetedLLMClient(client(model=model, max_tokens=MAX_OUTPUT), account=self.budgets.account(s),
                                ledger_path=self.budgets.folder(session) / "paid.jsonl")
        self.budgets.clients.append(llm)                 # its requests: the run's own (``RunRequests``)
        return llm

    def reanalyse(self, run: CheckRun, revision: str, instructions: str, llm_for=None) -> str:
        """The record assistant re-reads the record's sources with ``instructions`` (a check's report, or the
        researcher's suggestion) under this session's cap, with its own model: the new revision."""
        vision = not run.reanalysis_model.startswith("gpt-")
        scope = self.extraction.start(revision, 0, run.reanalysis_model, vision=vision, budget_session=run.session_id,
                                      own_model=True)
        step = None
        for batch in range(len(scope.batches)):
            llm = llm_for(run.reanalysis_model) if llm_for is not None else None
            step = self.extraction.step(scope.session_id, batch, instructions=instructions, llm=llm)
        if step is None:
            raise ValueError("the record has no source to re-read")
        if not any(r.result_id == run.result_id for r in self.catalog.load(step.output_revision).dossier.results):
            raise ValueError(f"the re-read record no longer has the result {run.result_id}")
        return step.output_revision

    def sources(self, revision: str, value: dict, model: str) -> tuple[list[dict], list[Path]]:
        """The source pages (and table rows) the selected claims cite, with each cited source's first page, at most
        ``SOURCE_CHARS`` of text; page images of the pages a figure was read from (an Anthropic model, at most
        ``IMAGES``)."""
        from adroit.orchestrator.experimental_extraction import source_units
        cited = [s for c in value["scientific"]["claims"] for s in c.get("sources", [])]
        pages = {(s["asset_sha256"], s.get("page")) for s in cited} | {(s["asset_sha256"], 1) for s in cited}
        rows = {(s["asset_sha256"], s.get("row")) for s in cited if s.get("row")}
        visual = {(s["asset_sha256"], s.get("page")) for s in cited if s.get("method") == "visual"}
        anthropic = not model.startswith("gpt-")
        units = source_units(self.catalog, revision, vision=anthropic)
        chosen = [u for u in units if (u.asset_sha256, u.page) in pages or any(
            a == u.asset_sha256 and u.row_low and u.row_low <= r <= u.row_high for a, r in rows)]
        out, size, images = [], 0, []
        for u in chosen:
            text = u.text[:max(0, SOURCE_CHARS - size)]
            size += len(text)
            out.append({"unit_id": u.unit_id, "source": u.source_name, "page": u.page, "rows": [u.row_low, u.row_high]
                        if u.row_low else None, "text": text, "truncated": len(text) < len(u.text)})
            if anthropic and u.image and (u.asset_sha256, u.page) in visual and len(images) < IMAGES:
                images.append(self.catalog.asset_path(u.image))
        return out, images

    def library(self, revision: str) -> list[dict]:
        """The library's other records of the same experiment (collaboration or detector, or a shared reference)."""
        from adroit.library.records_index import source_ids
        this = self.catalog.load(revision)
        names = {x.strip().lower() for x in (this.dossier.collaboration, this.dossier.detector) if x and x.strip()}
        ids = set(source_ids(*this.dossier.references))
        found, _ = self.catalog.listing()
        latest = {}
        for r in found:
            if r.experiment_id == this.experiment_id:
                continue
            mine = {x.strip().lower() for x in (r.dossier.collaboration, r.dossier.detector) if x and x.strip()}
            if names & mine or ids & set(source_ids(*r.dossier.references)):
                latest[r.experiment_id] = r                 # each lineage's newest revision, by the listing's order
        return [{"reference": r.reference, "title": r.dossier.title, "collaboration": r.dossier.collaboration,
                 "detector": r.dossier.detector, "analysis": r.dossier.analysis,
                 "publication_date": str(r.dossier.publication_date or ""), "references": r.dossier.references,
                 "results": [{"result_id": x.result_id, "kind": x.kind} for x in r.dossier.results]}
                for r in list(latest.values())[:20]]

    def literature(self, revision: str) -> dict:
        """arXiv's newest papers on the record's experiment (its collaboration, detector and "dark matter"), or why
        the search failed: the check then says it compared against the library and the model's own knowledge."""
        this = self.catalog.load(revision).dossier
        query = " ".join(dict.fromkeys(x for x in (this.collaboration, this.detector, "dark matter") if x))
        at = _now()
        try:
            papers = self.search(query, SEARCHED)
        except Exception as error:                               # noqa: BLE001 - the check goes on without it
            return {"query": query, "searched_at": at, "papers": [], "error": f"{error.__class__.__name__}: {error}"}
        return {"query": query, "searched_at": at, "papers": [
            {"arxiv_id": p.id, "title": p.title, "authors": p.authors[:3], "year": p.year, "submitted": p.note,
             "abstract": p.abstract[:600]} for p in papers[:SEARCHED]]}
