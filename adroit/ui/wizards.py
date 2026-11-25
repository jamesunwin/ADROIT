"""The workbench's wizards (DM15): one per track and input, each ending in one command-line run.

- **Constrain a model (Track 1):** a field content, a Lagrangian, an idea in words (paid, behind
  the budget gate), a typed model to scan, or DM8's coefficient derivation for a
  bespoke model (paid, behind the budget gate).
- **Signal best fits (Track 2):** a search with events (a built-in one, or a signal record from Add a signal),
  the library's space and/or the user's models.
- **Explain a signal (the single-idea report):** one model as the explanation of one anomaly.
- **Add a signal (the anomaly record):** the template, the consistency check, and the drafter
  (paid, behind the budget gate).

Each wizard writes its YAML input into a fresh run folder, launches the
command (``engine.launch``) and opens the live view; with the page's "Add to the batch" switch on, the
prepared request joins the batch draft instead (``batch``), to run later one after another with others.
"""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

import yaml
from nicegui import app, ui

from adroit.experiments import anomaly, registry
from adroit.ui import engine, field_editor, forms, submission
from adroit.ui.pages import budget_form, header, inside, model_select, rel

_logger = logging.getLogger(__name__)

def _start(root: Path, kind: str, title: str, inputs: dict[str, str], build, budget: float = 0.0,
           approval: str = "", batch: bool | None = None) -> None:
    """Write the inputs into a new folder, build the command from their paths, launch, and go live. ``approval``: how
    the budget was approved (``forms.BudgetCheck.approval``), kept on the job. ``batch``: whether the request joins
    the batch draft, as the caller captured it (OL-03: a Scan's check runs before this); None reads the switch now."""
    folder = forms.new_folder(root, kind, title)
    paths = {}
    for name, text in inputs.items():
        try:
            yaml.safe_load(text)
        except yaml.YAMLError as error:
            ui.notify(f"{name}: not valid YAML ({error.__class__.__name__})")
            return
        paths[name] = folder / f"{name}.yaml"
        paths[name].write_text(text)
    try:
        command = build(folder, paths)
        if (app.storage.client.get("batch") if batch is None else batch):
            from adroit.ui import batch
            batch.add_to_draft(root, command, folder, title, budget)
            submission.go("/batches")
            return
        job = engine.launch(command, folder, title, confirmed_budget=budget, approval=approval)
    except (ValueError, engine.BudgetNotConfirmed) as error:
        ui.notify(str(error))
        return
    submission.go(f"/live?path={rel(root, job.folder)}")


def batch_switch() -> None:
    """The page's "Add to the batch" switch: on, a request joins the batch draft instead of starting (``batch``)."""
    app.storage.client["batch"] = False
    ui.switch("Add to the batch instead of running now", value=False,
              on_change=lambda e: app.storage.client.__setitem__("batch", bool(e.value))).props("dense") \
        .mark("batch_switch")


def _checked_output(command: list[str]) -> list[str]:
    """A command whose file output would replace a file is refused before it starts (``forms.output_clash``;
    ValueError, which the launch shows); a batch checks its requests together as well."""
    clash = forms.output_clash(command)
    if clash:
        raise ValueError(clash)
    return command


def _gate(check) -> forms.BudgetCheck | None:
    """The budget gate's approval (its amount, and how it was ticked), or None, with its reason shown."""
    verdict = check()
    if not verdict.ok:
        ui.notify(verdict.message)
        return None
    return verdict


def _coverage_form():
    from adroit.ui.style import hint
    enabled = ui.checkbox("Check finer thermal coverage (optional)", value=False)
    ui.label("Re-samples the plane between grid points to be sure no thermal solution is missed; slower.") \
        .classes("text-sm text-gray-600")
    with ui.row().bind_visibility_from(enabled, "value"):
        depth = hint(ui.number("refinement depth", value=1, min=1, max=3, step=1), "1: halve each cell once")
        budget = hint(ui.number("maximum relic-search evaluations", value=250, min=1, max=10000, step=50),
                      "stops refining after this many relic calculations")
        strategy = ui.select({"uniform":"Uniform refinement", "adaptive":"Adaptive cell refinement"},
                             value="uniform", label="refinement method")
        exploration = ui.number("minimum adaptive exploration depth", value=1, min=1, max=3, step=1)
    return lambda: (int(depth.value) if enabled.value else 0, int(budget.value),
                   strategy.value if enabled.value else "uniform", int(exploration.value))


def _data_choices(selected: list[str] | None = None) -> tuple[ui.select, ui.select]:
    """The data a scan uses: the reviewed private limits (``selected``: those to start with, such as a constraint
    survey's verified limits, kept only where they are offered) and the pinned experimental profile."""
    from adroit.ui.experimental_review import limit_options
    from adroit.ui.experimental_profiles import selector
    from adroit.ui.style import section, term
    with section("Data the scan uses", "By default every packaged search ADROIT knows. Add limits you reviewed "
                 "yourself, or choose a profile that adds or replaces some."):
        offered=limit_options()
        personal_limits=ui.select(offered,multiple=True,value=[r for r in selected or [] if r in offered],
                                  label='Reviewed private limits for this run').classes('w-full')
        with ui.row().classes('items-center gap-2 w-full no-wrap'):
            profile=selector()
            term('profile')
        ui.link('Review, activate or roll back experimental profiles','/experiments/profiles').classes('text-sm')
    return personal_limits,profile


def _saved_model_picker(catalog: str) -> None:
    """A model from the personal library, to scan in the panel below."""
    from adroit.ui.model_library import LOADING, filled_later, options
    with ui.row().classes('items-end gap-3 w-full'):
        saved=ui.select({catalog:LOADING} if catalog else {},value=catalog or None,
                        label='A model from my library').classes('flex-grow')
        filled_later(saved,lambda:options('track1'))                    # off the event loop (OL-01)
        def select_saved():
            from urllib.parse import urlencode
            if saved.value:
                ui.navigate.to('/new/track1?'+urlencode({'catalog':saved.value}))
        ui.button('Load it',on_click=select_saved).props('outline')
    ui.link('Or make a model from TeX, a screenshot, words or a paper','/models/intake').classes('text-sm')


def _portal_panel(root: Path, personal_limits: ui.select, profile: ui.select, selected: str = '') -> None:
    """A literature benchmark from the portal library: its reviewed scan setup, then the scan."""
    from adroit.parameter_space import library
    ui.label("A benchmark model from the literature, scanned in the plane its papers plot. You get a study with its "
             "verdict, the plane's plot and every constraint ($0).").classes("text-gray-700")
    choice = ui.select({e.id: e.title if e.family.lower() in e.title.lower() else f"{e.title} ({e.family})"
                        for e in library.ENTRIES},
                       value=selected if selected in {e.id for e in library.ENTRIES} else library.ENTRIES[0].id,
                       label="portal").classes("w-full")
    portal_review={}

    @ui.refreshable
    def portal_setup():
        from adroit.parameter_space.scan_setup import model_relations,preview,setup_identity
        entry=library.entry(choice.value)
        setup=preview(entry.model_class,entry.point,entry.x,entry.y,entry.mediator_ratio,
                      coupling_relations=model_relations(None,entry.id,entry.x,entry.y))
        portal_review.update(id=entry.id,token=setup_identity(entry.spec(),entry.model_class,entry.point,setup))
        ui.label(entry.benchmark).classes('text-sm text-gray-700')
        with ui.expansion('Portal scan setup: active coordinates, fixed values and parameter relations').classes('w-full'):
            ui.code(yaml.safe_dump(setup.model_dump(mode='json'),sort_keys=False,allow_unicode=True),language='yaml')

    portal_setup()
    choice.on_value_change(lambda _:portal_setup.refresh())
    lit_p = ui.checkbox("search arXiv for prior work on this model (free; contacts arxiv.org; adds a reading list to the "
                        "report)", value=False)
    from adroit.ui.halo import halo_section
    ui.label("The halo").classes("text-base font-medium mt-2")
    halo_p = halo_section("track1", mark="portal-halo")
    coverage_p = _coverage_form()

    def scan_portal():
        if portal_review.get('id')!=choice.value:
            ui.notify('review the selected portal setup before scanning')
            return
        _start(root,'track1',choice.value,{},lambda f,p:forms.portal_command(choice.value,f,lit_p.value,
            *coverage_p(),reviewed_scan_hash=portal_review['token'],private_limits=list(personal_limits.value or []),profile=profile.value,
            **halo_p()))

    ui.button("Scan the portal",on_click=submission.once(scan_portal)).props("color=primary")


def _derive_panel(root: Path) -> None:
    """DM8's coefficient derivation for a bespoke model (paid, behind the budget gate)."""
    ui.label("For a model no engine covers: a language model derives its couplings to nucleons (DirectDM's Wilson "
             "coefficients) and a second, independent model checks them; they must agree before any limit is "
             "computed. You get its direct-detection limits in every experiment (paid).").classes("text-gray-700")
    derive_spec = ui.textarea("A typed model without a derivation (YAML), or leave empty").classes(
        "w-full font-mono").props("rows=10")
    derive_words = ui.textarea("Or the model in words (the intake agent types it first)").classes("w-full").props("rows=3")
    from adroit.core.pricing import PRIMARY_MODELS
    deriver = model_select("the deriver (paid)")
    derive_checker = ui.select({**{k: f"an independent check by {v}" for k, v in PRIMARY_MODELS.items()},
                                "none": "no second derivation (unchecked)"}, value="gpt-5.6-sol",
                               label="the checker (a different model)").classes("w-96")
    derive_check = budget_form(models=(deriver, derive_checker))

    def derive() -> None:
        approved = _gate(derive_check)
        if approved is None:
            return
        budget = approved.amount
        typed = derive_spec.value.strip()
        _start(root, "lagrangian", "derive", {"model": derive_spec.value} if typed else {},
               lambda f, p: forms.derive_command(f, budget, p.get("model"), "" if typed else derive_words.value,
                                                 derive_checker.value, deriver.value), budget, approved.approval)

    ui.button("Derive and compute", on_click=submission.once(derive)).props("color=primary")


def _words_panel(root: Path) -> None:
    """An idea in words for the model builder (paid, behind the budget gate)."""
    ui.label("Describe the idea in words; a language model proposes field contents, and ADROIT builds and audits each "
             "model. You get a list of models to review and approve for a scan (paid).").classes("text-gray-700")
    text = ui.textarea(placeholder="e.g. Majorana dark matter coupled to right-handed muons through a charged scalar") \
        .classes("w-full").props("rows=4")
    n = ui.number("how many models to propose", value=4, min=1, max=6)
    builder = model_select("the model builder (paid)")
    check = budget_form(models=(builder,))

    def words() -> None:
        approved = _gate(check)
        if approved is not None:
            budget = approved.amount
            _start(root, "idea", text.value[:40] or "idea", {},
                   lambda f, p: forms.idea_command("text", text.value, f, models=int(n.value), budget=budget,
                                                   model=builder.value),
                   budget, approved.approval)

    ui.button("Propose models", on_click=submission.once(words)).props("color=primary")


def _scan_panel(root: Path, preset: str, catalog: str, personal_limits: ui.select,
                profile: ui.select, discovery: str = '') -> None:
    """A typed model to scan: its scan setup shown as soon as there is a model, then Scan. Pressing Scan accepts the
    setup shown (the owner, 2026-11-22: a separate "Review scan setup" button read as optional and blocked the scan
    when it was not pressed); the setup run is the one computed when Scan is pressed, from what the page shows, and its
    hash goes to the run as the reviewed setup."""
    from adroit.ui.style import hint
    _saved_model_picker(catalog)
    ui.label("A typed model (YAML) with values for its couplings, or one loaded from your library. Its scan setup is "
             "shown below; edit it if you wish, then Scan: you get a study with the verdict, the plane's plot and every "
             "constraint.").classes("text-gray-700")
    spec = ui.textarea(value=preset,placeholder="paste a typed model (YAML), or load one from your library above") \
        .classes("w-full font-mono").props("rows=14")
    with ui.expansion("Advanced: axis strings").classes("w-full"):
        with ui.row():
            x = hint(ui.input("x axis", value="",placeholder="the model's default"),
                     "parameter:low:high:log:points, e.g. m_chi:10:1000:log:24; empty for the default")
            y = hint(ui.input("y axis", value="",placeholder="the model's default"), "as the x axis")
    ratio = hint(ui.number("m_med / m_chi",value=0,min=0), "tie the mediator's mass to the dark matter's; 0: independent")
    lit = ui.checkbox("search arXiv for prior work on this model (free; contacts arxiv.org)", value=False)
    from adroit.ui.halo import halo_section
    ui.label("The halo").classes("text-base font-medium mt-2")
    halo = halo_section("track1")
    coverage = _coverage_form()
    pinned = _survey_pin(discovery)
    shown={'version':0}
    summary=ui.column().classes('w-full')

    def current():
        return (spec.value,x.value,y.value,float(ratio.value or 0))

    async def show(_=None) -> None:
        """The setup of the model and axes as they stand, shown (no button: the owner, 2026-11-22). Its computation and
        its setup check run off the page's event loop (UO-06's addendum: a cold check had frozen the page for 78.6 s).
        An answer is applied only if the inputs are still the ones it was computed for, compared value by value (the auditor's
        OL-04: an old preview had written its axes over one still being typed), else it is computed again for the
        inputs now; any failure is shown in the card by name, never left "working…" (OL-05)."""
        from nicegui import run
        shown['version']+=1
        mine=shown['version']
        shown.pop('invalid',None)
        summary.clear()
        if not spec.value.strip():
            return
        inputs=current()
        with summary:
            ui.label('working out the scan setup…').classes('text-sm text-gray-600').mark('scan_setup_pending')
        try:
            model,setup,token=await run.io_bound(forms.review_scan,*inputs)
        except Exception as error:                   # noqa: BLE001 - named in the card (OL-05), and logged
            if mine==shown['version']:
                _logger.warning('the scan setup could not be worked out', exc_info=True)
                summary.clear()
                with summary:
                    expected=isinstance(error,(ValueError,KeyError,TypeError,yaml.YAMLError))
                    ui.label(str(error) if expected else f'the scan setup could not be worked out: '
                             f'{type(error).__name__}: {error}').classes('text-red-700').mark('scan_setup_error')
            return
        if mine!=shown['version']:
            return                                   # a newer computation is running
        if current()!=inputs:
            await show()                             # typed meanwhile (OL-04): computed again, nothing overwritten
            return
        summary.clear()
        x.value,y.value=forms.axis_text(setup.x),forms.axis_text(setup.y)
        checked=current()
        with summary:
            card=_shown_setup(model,setup,x,y,ratio,shown)
        with card:
            ui.label('checking the setup… (the first check of a model can take a minute; the page stays usable)') \
                .classes('text-sm text-gray-600').mark('setup_check_pending')
        try:
            check=await run.io_bound(_track1_check,root,model,checked[1],checked[2],checked[3],token,
                                     list(personal_limits.value or []),profile.value)
        except Exception as error:                   # noqa: BLE001 - named in the card (OL-05), and logged
            if mine==shown['version']:
                _logger.warning('the setup check failed', exc_info=True)
                card.clear()
                with card:
                    ui.label(f'the setup check could not be completed: {type(error).__name__}: {error}. Edit the '
                             'model or the axes to try again, or reload the page.').classes('text-red-700') \
                        .mark('setup_check_error')
            return
        if mine!=shown['version']:
            return                                   # a newer computation is running
        if current()!=checked:
            await show()                             # changed during the check (R7-03): checked again, never left
            return                                   # "checking the setup…"
        card.clear()
        with card:
            from adroit.ui.setup_check import render
            render(check)

    async def scan_model() -> None:
        from nicegui import run
        from adroit.orchestrator.model_approval import model_identity
        # every choice as it stood when Scan was pressed (the auditor's OL-03: the halo, literature, coverage and survey pin
        # had been read after the check, so a change made during it entered the run)
        inputs=(spec.value,x.value,y.value,float(ratio.value or 0),list(personal_limits.value or []),profile.value)
        literature,depth,halo_choice=lit.value,coverage(),halo()
        survey=discovery if pinned() else ''
        to_batch=bool(app.storage.client.get("batch"))
        try:
            model,token=await run.io_bound(_ready_to_scan,root,catalog,*inputs,shown.get('invalid'))
        except (ValueError,KeyError,TypeError,yaml.YAMLError) as error:
            ui.notify(str(error))
            return
        _start(root,"track1","model",{'model':inputs[0]},
            lambda f,p:forms.track1_command(catalog or p['model'],f,inputs[1],inputs[2],literature,
                coverage_depth=depth[0],coverage_budget=depth[1],
                coverage_strategy=depth[2],coverage_exploration=depth[3],
                approved_model_hash=model_identity(model),mediator_ratio=inputs[3],reviewed_scan_hash=token,
                private_limits=inputs[4],profile=inputs[5],**halo_choice,discovery=survey),batch=to_batch)

    for field in (spec,x,y):
        field.on('blur',show)
    ratio.on_value_change(show)
    ui.button("Scan",on_click=submission.once(scan_model)).mark('run_model_scan').props('color=primary')
    ui.timer(0.01,show,once=True)


def _shown_setup(model,setup,x,y,ratio,shown):
    """The scan setup as it will run: its table editor (an edit applies at once, and Scan runs it) and its YAML;
    returns the column the setup check is shown in. Scan accepts what is shown; an invalid table stops it (S18-08)."""
    ui.label("Scan setup: active coordinates, fixed values and parameter relations").classes("font-medium")
    state=ui.label("Scan runs this setup: pressing Scan accepts it").classes("text-sm text-gray-700").mark('scan_state')

    def edited(ax,ay,r) -> None:
        x.value,y.value=forms.axis_text(ax.model_dump()),forms.axis_text(ay.model_dump())
        ratio.value=r or 0
        shown.pop('invalid',None)
        state.text="edited: Scan runs the edited setup"
        state.classes(replace="text-sm text-gray-700")

    def invalid(reason) -> None:          # an invalid table never runs (S18-08)
        shown.update(invalid=reason)
        state.text=f"the table is invalid ({reason}): correct it before scanning"
        state.classes(replace="text-sm text-red-700")
    from adroit.ui.scan_editor import scan_editor
    scan_editor(setup,edited,invalid)
    with ui.expansion("Advanced: the setup as YAML").classes("w-full"):
        ui.code(yaml.safe_dump(setup.model_dump(mode='json'),sort_keys=False,allow_unicode=True),language='yaml')
    return ui.column().classes('w-full')


def _ready_to_scan(root,catalog,model_text,x,y,ratio,personal_limits,profile,invalid=None):
    """The model and the token of the setup Scan runs, computed from the inputs as they stood when Scan was pressed
    (pressing Scan accepts it: the owner, 2026-11-22); run off the event loop. ValueError if the table is invalid, the
    model differs from the saved one, or the check is blocked."""
    if invalid:
        raise ValueError(f"the scan table is invalid ({invalid}): correct it before scanning")
    model,setup,token=forms.review_scan(model_text,x,y,ratio)
    if catalog:
        from adroit.library.personal import Catalog
        Catalog().verify_calculation(catalog,model,'track1')
    check=_track1_check(root,model,x,y,ratio,token,personal_limits,profile)
    if check.blocked:
        raise ValueError("the setup check is blocked: "+next(i.message for i in check.items if i.severity=='blocking'))
    return model,token


def _track1_check(root,model,x,y,ratio,token,personal_limits,profile):
    """The Track 1 setup check (``orchestrator.setup_check``) from plain values, so that it can run in a worker thread."""
    from adroit.orchestrator.setup_check import check_track1
    from adroit.library.experimental_profiles import selected
    chosen=selected(profile) if profile!='none' else ''
    return check_track1(model,x,y,ratio,token,list(personal_limits),chosen,root=root)


def _survey_pin(discovery: str):
    """A constraint survey's frozen assessment, when the survey's page sent the user here (``discovery``): said, and
    pinned to the run unless unticked. Returns whether it is pinned."""
    if not discovery:
        return lambda: False
    box = ui.checkbox("Use the constraint survey's assessment (" + discovery.split('@')[0] + "): the limits it found "
                      "that are not resolved keep allowed points pending, never excluded", value=True).mark('survey_pin')
    return lambda: bool(box.value)


def track1(root: Path, model: str = "",catalog: str = '',portal: str = '',limits: str = '',discovery: str = '',
           survey: str = '') -> None:
    """The Constrain a model (Track 1) wizard: where the model comes from (the library, your own, or built from
    fields, a Lagrangian or words), then the scan; or a coefficient derivation. ``limits`` (comma-separated private
    limits) and ``discovery`` (a frozen survey assessment) come from a constraint survey's "Proceed" (JU1), with
    ``survey`` (its session) for a model file it surveyed: My model is then that model as the survey recorded it
    (AL5-03)."""
    header("Constrain a model",
           "Check a dark matter model against every search ADROIT knows. Take one from the library or your own, or "
           "build one; scanning it finds where it gives the observed relic density, and which constraints exclude it "
           "there.",
           facts=("$0 to scan", "building from words is paid", "result: a study and its verdict"),
           details=("Published curves stay hard cuts at their stated confidence level, not inferred likelihoods.",
                    "Private limits and profiles are used only when you select them here; old results keep theirs.",
                    "Building from fields or a Lagrangian gives an audited model, not a verdict: approve it on its "
                    "study's page to scan it."),
           subtitle="Track 1")
    batch_switch()
    preset = inside(root, model).read_text() if model else ""
    if catalog:
        from adroit.library.personal import Catalog, MissingRevision
        try:
            preset=yaml.safe_dump(Catalog().load(catalog).spec.model_dump(mode='json'),sort_keys=False,allow_unicode=True)
        except MissingRevision as error:          # a deleted model: said, and the page offered without it
            ui.label(str(error)).classes("text-orange-800").mark("model_not_found")
            catalog = ""
    elif survey:
        preset=_surveyed_model(survey)
    personal_limits,profile=_data_choices([r for r in limits.split(',') if r])
    ui.label("Choose where the model comes from").classes("text-lg font-medium mt-2")
    with ui.tabs().props("align=left outside-arrows mobile-arrows no-caps").classes("w-full") as tabs:
        t_portal, t_scan, t_fields, t_lag, t_text, t_derive = (
            ui.tab("A library model"), ui.tab("My model"), ui.tab("Build from fields"),
            ui.tab("Build from a Lagrangian"), ui.tab("Build from words (paid)"), ui.tab("Derive couplings (paid)"))
    with ui.tab_panels(tabs, value=t_scan if preset else t_portal).classes("w-full"):
        with ui.tab_panel(t_portal):
            _portal_panel(root,personal_limits,profile,portal)
        with ui.tab_panel(t_fields):
            _fields_panel(root)
        with ui.tab_panel(t_lag):
            ui.label("A typed Lagrangian (YAML): checked for gauge and Lorentz invariance, hermiticity and missing terms. "
                     "You get a study with the audit; approve the model there to scan it ($0).").classes("text-gray-700")
            lag = ui.textarea(placeholder="a typed model (YAML): its fields and terms").classes("w-full font-mono") \
                .props("rows=12")
            ui.button("Audit", on_click=submission.once(lambda: _start(
                root, "idea", "lagrangian", {"lagrangian": lag.value},
                lambda f, p: forms.idea_command("lagrangian", str(p["lagrangian"]), f)))).props("color=primary")
        with ui.tab_panel(t_derive):
            _derive_panel(root)
        with ui.tab_panel(t_text):
            _words_panel(root)
        with ui.tab_panel(t_scan):
            _scan_panel(root,preset,catalog,personal_limits,profile,discovery)


def _surveyed_model(session: str) -> str:
    """The typed model a constraint survey recorded (its session's, checked against the session's integrity hash), as
    My model's YAML; "" with the reason said where it cannot be read, so nothing else is offered in its place."""
    from adroit.orchestrator.constraint_discovery import Discovery
    try:
        spec = Discovery().session(session).spec
    except (OSError, ValueError, KeyError, TypeError) as error:
        ui.label(f"The constraint survey's model cannot be read ({error}): load it in My model before scanning, and "
                 "the survey's assessment applies only if it is that model.").classes("text-orange-800") \
            .mark("survey_model_unreadable")
        return ""
    ui.label(f"The model this constraint survey assessed: {spec.name}, below in My model.").classes("text-sm") \
        .mark("survey_model")
    return yaml.safe_dump(spec.model_dump(mode="json"), sort_keys=False, allow_unicode=True)


def _fields_panel(root: Path) -> None:
    """Build from fields: the form (or its YAML), the operators to include, and the build."""
    ui.label("List the new fields; ADROIT writes the most general Lagrangian they allow and audits it. You get a study "
             "with the model to review; approve it there to scan it ($0).").classes("text-gray-700")
    current = field_editor.editor()
    eft = ui.select({4: "renormalizable only", 5: "with dimension-5 operators", 6: "with dimension-6 operators"},
                    value=4, label="operators to include")

    def build() -> None:
        text = current()
        if text is not None:
            _start(root, "idea", "fields", {"fields": text},
                   lambda f, p: forms.idea_command("fields", str(p["fields"]), f, eft=eft.value))
    ui.button("Build and audit", on_click=submission.once(build)).props("color=primary")


def _experiment(selected: str=''):
    names = registry.signal_search_names()
    from adroit.ui.experimental_profiles import search_options
    private=search_options('signal')
    from adroit.library.experimental import ExperimentalCatalog
    from adroit.orchestrator.anomaly_intake import readiness
    catalog=ExperimentalCatalog()
    confirmed={}
    for path in catalog.path('confirmations').glob('*.json'):
        try:
            receipt=readiness('anomaly:'+path.stem,catalog)
            confirmed[receipt.reference]='Confirmed exploratory input: '+receipt.interpretation.record.name
        except (ValueError,OSError):
            continue
    if selected and selected not in [*confirmed,*private,*names]:
        raise ValueError('selected anomaly is not confirmed and calculable')
    choice = ui.select({**{n: n for n in names}, **confirmed,**private,"record": "a signal record (a file; Add a signal)"}, value=selected or names[0],
                       label="the search with events").classes("w-96")
    path = ui.input("the record's path").classes("w-96").bind_visibility_from(choice, "value",
                                                                            backward=lambda v: v == "record")
    unverified = ui.checkbox("accept a record no person has verified").bind_visibility_from(
        choice, "value", backward=lambda v: v == "record")
    def get_experiment():return f"record:{path.value}" if choice.value=='record' else choice.value
    get_experiment.selector=choice
    return get_experiment,unverified


def track2(root: Path,catalog: str = '',anomaly: str='') -> None:
    """The Signal best fits (Track 2) wizard (restructured, the owner, 2026-11-18: the signal best fits plan):
    the signal the only input it needs; what will be searched, said; the halo models; your own models, optional and
    folded; the options folded away; and the run."""
    header("Signal best fits",
           "Give a search that saw events: ADROIT fits every interaction of its library to them (the non-relativistic "
           "operators and the Lagrangians, isoscalar and isovector, across masses), ranks them by how well they explain "
           "the events once the searches that saw nothing are included, and gives the global significance over "
           "everything it tried. Your own models can be compared too.",
           facts=("$0", "result: a ranked study; promote a candidate from it"),
           details=('The raw ranking and significance use non-relativistic operators; a fitted point is checked as a '
                    'physical model separately ("eligibility"), and excluding one point does not exclude a model.',),
           subtitle="Track 2")
    batch_switch()
    sig = _signal_section(anomaly)
    _searched_card(sig.experiment)
    from adroit.ui.halo import halo_section
    from adroit.ui.style import section
    with section("The halo models", "Each search's own published halo by default; one fixed common benchmark for the "
                 "fit, the null searches and every comparison able to use it; or the halo models compared, each run "
                 "and ranked together."):
        halo = halo_section("track2")
    search = _agent_section()
    cand = _candidates_section(catalog)
    opt = _options_section(root)

    def lines(box) -> list[str]:
        return [v.strip() for v in (box.value or '').splitlines() if v.strip()]

    def go() -> None:
        from adroit.ui.model_library import STANDARD, choice_yaml
        chosen = list(cand.saved.value or [])
        standard = [k for k in chosen if k.startswith(STANDARD)]          # each written as its typed model (JU1)
        inputs = ({"model": cand.model.value} if cand.model.value.strip() else {}) | {
            "standard_" + k.removeprefix(STANDARD): choice_yaml(k) for k in standard}
        personal = [k for k in chosen if not k.startswith(STANDARD)]
        paid = None
        if search.agent.value:
            paid = _gate(search.gate)
            if paid is None:
                return
        agent = ({"agent": True, "agent_rounds": int(search.rounds.value or 3), "agent_model": search.model.value,
                  "budget": paid.amount} if paid else {})
        _start(root, "signal", sig.experiment(), inputs, lambda f, p: forms.signal_command(
            sig.experiment(), f, sig.nulls.value, int(opt.toys.value), list(p.values()) + personal,
            cand.masses.value if p or chosen else "", cand.library.value and bool(p or chosen),
            sig.unverified.value, lines(opt.required), lines(opt.preferred), opt.splittings.value, sig.profile.value,
            lines(opt.track1_evidence), int(opt.eligibility_budget.value), opt.eligibility.value, **halo(), **agent),
            paid.amount if paid else 0.0, paid.approval if paid else "")

    checked = ui.column().classes("w-full")

    def check() -> None:
        from adroit.orchestrator.setup_check import check_signal
        from adroit.ui.setup_check import render
        checked.clear()
        with checked:
            render(check_signal(sig.experiment(), len(cand.saved.value or []) + bool((cand.model.value or '').strip()),
                                int(opt.toys.value)))
    with ui.row().classes("mt-2"):
        ui.button("Check setup ($0)", on_click=check).props("outline").mark("check_setup")
        ui.button("Fit, combine and rank", on_click=submission.once(go)).props("color=primary")


def _signal_section(anomaly: str) -> SimpleNamespace:
    """1. The signal: an experimental profile, the search with events and the null searches (a profile fixes them)."""
    from adroit.library.experimental_profiles import load
    from adroit.ui.experimental_profiles import search_options, selector
    from adroit.ui.style import section, term
    with section("1. The signal", "The search whose events you want to explain, and the searches that saw nothing."):
        profile=selector()
        chosen=load(profile.value) if profile.value not in ('none','') else None   # '': the active one unreadable (M3)
        experiment, unverified = _experiment(anomaly or (chosen.signal if chosen else ''))
        with ui.row().classes('items-center gap-2 w-full no-wrap'):
            nulls = ui.select([*registry.module_names(),*search_options('null')], multiple=True, label="null experiments",
                              value=["CRESST-III 2019", "CDMSlite Run 2", "PICO-60 C3F8 (2019)", "DEAP-3600 (2019)"]) \
                .classes("w-full")
            term('null searches')
    if chosen:
        nulls.value=chosen.null_modules
    nulls.bind_enabled_from(profile,'value',backward=lambda v:v=='none')
    def profile_changed():
        selected=load(profile.value) if profile.value not in ('none','') else None
        if selected:
            nulls.value=selected.null_modules
            if selected.signal:
                experiment.selector.value=selected.signal
    profile.on_value_change(lambda _:profile_changed())
    return SimpleNamespace(profile=profile, experiment=experiment, unverified=unverified, nulls=nulls)


AGENT_NOTE = ("After the fixed scan, a language model reads the leaders and, in rounds, picks deformations of them "
              "to fit (the other isospin, a mass splitting, a light mediator, a neighbouring operator, a finer mass), "
              "each with its reason. Each is fitted and combined like any candidate, charged one more free parameter, "
              "and joins the ranking only if it beats its parent by ΔAIC > 2; the global significance is recomputed "
              "over everything tried. The model then explains the ranking (its numbers checked against the result). "
              "The fixed scan's ranking and promotion are unchanged. AI can make mistakes.")


def _agent_section() -> SimpleNamespace:
    """How to search: the fixed scan ($0), and optionally the agent-led search after it (paid; ``signal_search``)."""
    from adroit.ui.style import section
    with section("How to search", "The fixed scan above ($0); and, if you choose, an agent-led search after it."):
        agent = ui.checkbox("After the fixed scan, let an agent steer the search (paid)", value=False) \
            .mark("agent_search")
        with ui.column().classes("w-full gap-1").bind_visibility_from(agent, "value"):
            ui.label(AGENT_NOTE).classes("text-sm text-gray-700")
            model = model_select("the agent's model (paid)")
            rounds = ui.number("rounds (at most 5)", value=3, min=1, max=5, format="%d").classes("w-44")
            gate = budget_form("the most the agent may spend ($)", models=(model,))
    return SimpleNamespace(agent=agent, model=model, rounds=rounds, gate=gate)


def _searched_card(experiment) -> None:
    """2. What will be searched, for the search chosen (``experiment()``): the library's space or the collaboration's
    own, how it is ranked, and what the global significance counts (the owner, 2026-11-18: the page had not said)."""
    from adroit.ui.style import section
    with section("2. What will be searched", "Nothing to choose here: the space every run searches, and how it ranks."):
        @ui.refreshable
        def card() -> None:
            ui.label(searched_space(experiment())).classes("text-sm").mark("searched_space")
            ui.label("Each candidate is fitted to the events (its likelihood ratio against the background alone); the "
                     "leading classes are combined with the null searches and ranked by AIC (lowest first; within "
                     "ΔAIC ≤ 2 indistinguishable). The global significance counts every candidate searched (the "
                     "look-elsewhere effect). Your own models, below, are optional and added to the space.") \
                .classes("text-sm text-gray-700")
        card()
    selector = getattr(experiment, "selector", None)
    if selector is not None:
        selector.on_value_change(lambda _: card.refresh())


def searched_space(name: str) -> str:
    """The space Signal best fits searches on ``name`` by default, in words (``signal.model_space``)."""
    from adroit.orchestrator import signal
    try:
        module = registry.load_module(name) if name and not name.startswith("record:") else None
        published = module.model_space() if module is not None else []
    except Exception:                                    # noqa: BLE001 - said as the library's space
        published = []
    if published:
        return f"{len(published)} candidates: the models {name}'s collaboration published (its own model space)."
    space = signal.library_model_space()
    cards = sorted({c.card_id for c in space}, key=lambda c: (c[0], int(c[1:])))
    operators = [c for c in cards if c.startswith("O")]
    lagrangians = [c for c in cards if c.startswith("L")]
    masses = sorted({c.mass_gev for c in space})
    return (f"{len(space)} candidates: the library's {len(operators)} non-relativistic operators ({operators[0]}, "
            f"{operators[1]}–{operators[-1]}) and {len(lagrangians)} Lagrangians ({lagrangians[0]}–{lagrangians[-1]}), "
            f"each isoscalar and isovector, at {len(masses)} masses from {masses[0]:g} GeV to {masses[-1] / 1000:g} "
            "TeV (inelastic splittings under Options).")


def _candidates_section(catalog: str) -> SimpleNamespace:
    """Your own models, optional and folded: standard and saved models, a pasted model, their masses, and whether the
    library's space is searched beside them."""
    from adroit.ui.model_library import LOADING, UNLISTED, filled_later, model_choices, standard_unsupported
    from adroit.ui.style import hint
    with ui.expansion("Also compare your own models (optional)").classes("w-full").mark("own_models"):
        ui.label("Without any, the library's space above is searched. With some, they are fitted at their masses, "
                 "beside the library's space unless you untick it.").classes("text-sm text-gray-600")
        library = ui.checkbox("the library's space as well", value=True)
        saved=ui.select({catalog:LOADING} if catalog else {},multiple=True,value=[catalog] if catalog else [],
                        label='Models to compare (standard and personal library)').classes('w-full')
        filled_later(saved,lambda:model_choices('track2'))   # off the event loop (OL-01); a model not among the
        # choices (deleted, or not runnable) is not kept preselected
        ui.label(UNLISTED).classes('text-xs text-gray-600')
        ui.label(standard_unsupported()).classes('text-xs text-gray-600').mark('standard_unsupported')
        with ui.expansion("Paste a typed model (YAML)").classes("w-full"):
            model = ui.textarea(placeholder="a typed model with its couplings; leave empty for the library alone") \
                .classes("w-full font-mono").props("rows=8")
            ui.link('Or make one from a paper equation','/models/intake').classes('text-sm')
        masses = hint(ui.input("their masses (GeV)", value="5,10,20,50,100,200,500,1000"),
                      "comma-separated; each of your models is fitted at each mass")
    return SimpleNamespace(library=library, saved=saved, model=model, masses=masses)


def _options_section(root: Path) -> SimpleNamespace:
    """3. Options, folded: toys, splittings, model properties, eligibility and saved studies for exact reuse."""
    from adroit.ui.style import hint, term
    with ui.expansion("3. Options (defaults are fine for a first run)").classes("w-full"):
        with ui.row().classes('items-center gap-2'):
            toys = hint(ui.number("background-only simulations", value=200_000, min=1000, step=1000),
                        "experiments with no signal, for the global significance; 200,000 resolve p down to about 1e-5")
            term('background-only simulations')
        splittings=hint(ui.input('Library mass splittings (keV, comma-separated)',value='0'),
                        "inelastic scattering: also fit each library interaction with these splittings")
        ui.label('Model properties: requirements restrict the searched models; preferences only annotate the '
                 'ranking. Write one per line, as reviewed declarations phrase them (e.g. "with Hidden-sector U(1)").') \
            .classes('text-sm text-gray-600')
        required=ui.textarea(label='Required model properties (one statement per line)',value='').classes('w-full').props('rows=3')
        preferred=ui.textarea(label='Preferred model properties (one statement per line)',value='').classes('w-full').props('rows=3')
        with ui.row().classes('items-center gap-3'):
            eligibility=ui.checkbox('Check fitted points as physical models',value=True)
            eligibility_budget=hint(ui.number('Physical candidate assessment budget',value=32,min=1,max=1000),
                                    'at most this many fitted points are checked')
            term('eligibility')
        saved_studies=_track1_studies(root)
        _unoffered(root)
        track1_evidence=ui.textarea('Saved results of constraining a model, for exact reuse (paths, one per line)',value='').classes('w-full')
        if saved_studies:
            pick=ui.select(saved_studies,label='Add a saved Constrain a model study').classes('w-full')
            pick.on_value_change(lambda e: setattr(track1_evidence,'value',
                ((track1_evidence.value or '').rstrip()+'\n'+e.value).strip()) if e.value else None)
    return SimpleNamespace(toys=toys, splittings=splittings, required=required, preferred=preferred,
                           eligibility=eligibility, eligibility_budget=eligibility_budget,
                           track1_evidence=track1_evidence)


def _unoffered(root: Path) -> None:
    """Under a picker of saved studies: how many it could not read (``studies.unoffered``), or nothing."""
    from adroit.orchestrator import studies
    note = studies.unoffered(root)
    if note:
        ui.label(note + '.').classes('text-xs text-orange-800').mark('unoffered_studies')


def _track1_studies(root: Path) -> dict[str, str]:
    """Saved Constrain a model studies, by their result's path, each named as its record read with its result names it
    (``study_headline.listed``: the auditor's DB/VI recheck, DC-01, 2026-11-03, B's result had been offered under A's
    title)."""
    from adroit.orchestrator.study_headline import listed, offered
    return {str(found.path): listed(found) for found in offered(root, ('track1',))}


def single(root: Path) -> None:
    """The Explain a signal wizard: one model against one search with events."""
    from adroit.ui.style import section
    header("Explain a signal",
           "Test one model of your choosing against a signal: fit its masses and couplings to the events, measure its "
           "tension with the searches that saw nothing, and constrain it around the best fit. (Signal best fits ranks "
           "many interactions instead.)",
           facts=("$0", "result: a study with the fit, the tension and the verdict"))
    batch_switch()
    with section("1. The signal"):
        experiment, unverified = _experiment()
    saved, model, loaded = _single_model_section()
    from adroit.ui.halo import halo_section
    with section("The halo", "The preset halo region by default (a point is decided only if it is so over ρ₀, v₀ and "
                 "v_esc's joint 95% region); each experiment's published halo; or one fixed common benchmark (SHM, "
                 "SHM++)."):
        halo = halo_section("single_idea")
    masses, toys, grid, lit, advanced = _single_options_section(model, halo)

    def run() -> None:
        """A library model unchanged runs as its pinned revision, with its approval and derivation; an edited one is a
        new model, refined in the model library first (the external audit's A13, 2026-10-16: the spec alone had
        been submitted, losing the revision, approval and derivation)."""
        from adroit.ui.model_library import STANDARD
        personal = saved.value if saved.value and not saved.value.startswith(STANDARD) else ""   # a standard model runs
        pinned = personal if personal and (model.value or "").strip() == loaded["text"].strip() else ""  # as typed
        if personal and not pinned:
            ui.notify("This library model was edited: an edited model is a new model. Refine it in the model library "
                      "(a new revision, then its approval), then choose that revision here.", multi_line=True)
            ui.navigate.to('/models/intake?' + urlencode({'reference': saved.value}))
            return
        try:
            options, files = advanced()
            forms.advanced_options({**options, **{k: 'file' for k in files}})
        except (ValueError, TypeError) as error:
            ui.notify(str(error))
            return
        inputs = ({} if pinned else {"model": model.value}) | files
        _start(root, "single_idea", "idea", inputs,
               lambda f, p: forms.single_idea_command(pinned or p["model"], experiment(), f, masses.value,
                                                      int(toys.value), int(grid.value), lit.value, unverified.value,
                                                      advanced={**options, **{k: p[k] for k in files}}))
    checked = ui.column().classes("w-full")

    def check() -> None:
        from adroit.orchestrator.model_approval import read_model
        from adroit.orchestrator.setup_check import check_single
        from adroit.ui.setup_check import masses as parse, render
        checked.clear()
        with checked:
            try:
                spec = read_model(yaml.safe_load(model.value or ""))
                render(check_single(spec, experiment(), parse(masses.value), int(toys.value), int(grid.value),
                                    unverified.value, root=root))
            except (ValueError, TypeError, yaml.YAMLError) as error:
                ui.label(f"The setup cannot be checked yet: {error}").classes("text-sm text-red-700")
    with ui.row():
        ui.button("Check setup ($0)", on_click=check).props("outline").mark("check_setup")
        ui.button("Run the study", on_click=submission.once(run)).props("color=primary")


def _single_model_section() -> tuple[ui.select, ui.textarea, dict[str, str]]:
    """2. The model: one from the standard or the personal library (loaded into the editor, its text kept to tell an
    edit) or a typed one."""
    from adroit.ui.model_library import UNLISTED, choice_yaml, filled_later, model_choices, standard_unsupported
    from adroit.ui.style import section
    with section("2. The model", "A model from the standard or your personal library, or a typed model (YAML) with "
                 "values for its couplings."):
        saved = ui.select({}, label="a model from the library").classes("w-full")
        filled_later(saved, lambda: model_choices('track1'))           # off the event loop (OL-01)
        ui.label(UNLISTED).classes('text-xs text-gray-600')
        ui.label(standard_unsupported()).classes('text-xs text-gray-600').mark('standard_unsupported')
        model = ui.textarea(label="the model (YAML, with coupling values)").classes("w-full font-mono").props("rows=12")
        loaded = {"text": ""}

        def load_saved() -> None:
            if saved.value:
                model.value = loaded["text"] = choice_yaml(saved.value)
        saved.on_value_change(lambda _: load_saved())
    return saved, model, loaded


def _single_options_section(model: ui.textarea, halo=None) -> tuple:
    """3. Options: the masses, toys and constraint grid, the arXiv search, and the advanced options folded away."""
    from adroit.ui.style import hint, section, term
    with section("3. Options"):
        with ui.row().classes("items-start gap-4"):
            masses = hint(ui.input("masses (low:high:n or a list, GeV)", value="5:1000:16"),
                          "the dark matter masses fitted, e.g. 5:1000:16 or 10,20,50")
            with ui.row().classes('items-center gap-1 no-wrap'):
                toys = hint(ui.number("background-only simulations", value=20_000, min=1000, step=1000),
                            "experiments with no signal, for the global significance; 20,000 resolve p down to about "
                            "5e-5")
                term('background-only simulations')
            grid = hint(ui.number("constraint grid (n × n)", value=20, min=4, max=60),
                        "the plane constrained around the fit; 20 × 20 is 400 points")
        lit = ui.checkbox("search arXiv for prior work (free; contacts arxiv.org)", value=False)
        from adroit.ui.advanced import advanced_section
        advanced = advanced_section(lambda: model.value, halo)
    return masses, toys, grid, lit, advanced


def anomaly_page(root: Path, record: str = "") -> None:
    """The anomaly record page: the template in an editor with its consistency check, a file on disk (``record``: one
    to check at once, such as a draft the drafter wrote), and the drafter (paid)."""
    header("Add a signal",
           "A signal is a search that saw events. Import its record from the paper (a language model drafts it), or "
           "write it here from the template; check it; once a person has verified every number against the paper, "
           "Signal best fits and Explain a signal can use it.",
           facts=("$0 to write and check", "drafting is paid", "next: Signal best fits, as 'a signal record (a file)'"),
           details=("A limit (a search that saw nothing) is added on Add a limit instead.",))
    batch_switch()
    ui.link("Or upload the paper's table, figure or PDF for a reviewed reading (Add a limit's upload)", '/experiments') \
        .classes('text-sm')
    _draft_section(root)                  # importing from the paper first, writing the record second (JU1)
    _record_editor(root)
    with ui.expansion("Or check a record file on disk", value=bool(record)).classes("w-full"):
        path = ui.input("the record's path", value=record).classes("w-96")
        file_out = ui.column()
        ui.button("Check", on_click=lambda: _check_record(Path(path.value).expanduser(), file_out))
        if record:
            _check_record(Path(record).expanduser(), file_out)


def _check_record(path: Path, target) -> None:
    """A record's consistency check, shown in ``target``: its problems and what a person must still do."""
    target.clear()
    with target:
        try:
            record = anomaly.load(path)
        except Exception as error:  # noqa: BLE001 - shown to the person as the problem
            ui.label(f"not a valid record: {error}").classes("text-red-700")
            return
        problems = anomaly.check(record, path.parent)
        ui.label("verified by " + record.verified_by if record.verified_by.strip() else "a DRAFT: not verified")
        for item in problems or ["no problems found"]:
            ui.label(f"• {item}")
        for item in record.needs_person:
            ui.label(f"• still to do: {item}")


def _record_editor(root: Path) -> None:
    """2. Or write the record: the template in an editor, saved to the runs folder's signal_records and checked."""
    from adroit.ui.style import section
    with section("2. Or write the record", "Every field is explained in its comment. Keep an efficiency CSV in the "
                 "same folder as the saved record if you use one."):
        editor = ui.textarea(value=anomaly.template()).classes("w-full font-mono text-xs").props("rows=24")
        saved_note = ui.label("").classes("text-sm text-gray-600")
        out = ui.column()

        def check_editor() -> None:
            from adroit.orchestrator.runs import slug
            try:
                name = (yaml.safe_load(editor.value) or {}).get("name") or "record"
            except yaml.YAMLError as error:
                ui.notify(f"not valid YAML ({error.__class__.__name__})")
                return
            path = root / "signal_records" / f"{slug(str(name))}.yaml"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(editor.value)
            saved_note.text = f"saved as {path}: use this path in Signal best fits ('a signal record (a file)')"
            _check_record(path, out)
        ui.button("Save and check", on_click=check_editor).props("color=primary")


def _draft_section(root: Path) -> None:
    """1. Import the record from the paper: a language model fills in the template (paid)."""
    from adroit.ui.style import hint, section
    with section("1. Import it from the paper", "A language model reads the paper and fills in the template; a "
                 "person must verify the draft before it is used (paid)."):
        arxiv = ui.input("arXiv identifier", placeholder="e.g. 1304.4279")
        target = hint(ui.input("write the draft to (a new file, optional)").classes("w-96"),
                      "empty: the workbench's signal_records folder, as draft_<arXiv id>_<run>.yaml; an existing file "
                      "is never replaced")
        drafter = model_select("the drafter (paid)")
        gate = budget_form(models=(drafter,))

        def draft() -> None:
            approved = _gate(gate)
            if approved is not None:
                budget = approved.amount
                (root / "signal_records").mkdir(parents=True, exist_ok=True)
                _start(root, "anomaly", f"draft {arxiv.value}", {},
                       lambda f, p: _checked_output(forms.anomaly_draft_command(
                           arxiv.value, Path(target.value).expanduser() if (target.value or "").strip() else
                           forms.draft_record_path(root, arxiv.value, f), budget, drafter.value)),
                       budget, approved.approval)

        ui.button("Draft", on_click=submission.once(draft))
