"""The workbench (DM15): the two tracks in a local NiceGUI app.

    adroit workbench                 # http://127.0.0.1:8765, this machine only

The pages are registered by ``build_pages`` (tests register them on a
temporary runs directory). The app listens on 127.0.0.1 only: it has no
authentication and can start runs that spend money (behind the budget gate),
so it answers only requests addressed to it with its own pages' origin
(``local_only``).
"""

from __future__ import annotations

from pathlib import Path

from nicegui import app, ui

from adroit.core.config import get_settings


def build_pages(runs_dir: str | Path | None = None, records_path: str | Path | None = None) -> Path:
    """Register every page on a runs directory; returns it (``records_path``: the records file the review writes)."""
    from adroit.constraints import database, review
    from adroit.ui import style
    style.apply_defaults()
    from adroit.ui import about
    about.build()                     # the running revision, read once at start (``about``)
    root = Path(runs_dir or get_settings().runs_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    style.RUNS_ROOT[:] = [root]
    app.add_static_files("/files", str(root))
    sources = get_settings().tools_dir / review.SOURCES
    if sources.is_dir():
        app.add_static_files("/sources", str(sources))
    target = Path(records_path) if records_path else database.RECORDS
    _result_pages(root, sources if sources.is_dir() else None, target)
    _run_pages(root)
    _library_pages(root)
    return root


def _result_pages(root: Path, sources: Path | None, target: Path) -> None:
    """Home, the studies and a run's live view, and the records."""
    from adroit.ui import pages, records

    @ui.page("/records")
    def records_list(study: str = "") -> None:
        records.records_page(root,study)

    @ui.page("/record")
    def record(id: str = "",study: str = "",task: str = "",sha256: str = "",  # noqa: A002 - the query parameter
               evidence: str = "") -> None:
        records.record_page(root, id, sources, target,study,task,{"sha256":sha256,"evidence":evidence})

    @ui.page("/")
    def home() -> None:
        pages.landing()

    @ui.page("/studies")
    def studies_list() -> None:
        pages.studies_page(root)

    @ui.page("/study")
    def study(path: str = "") -> None:
        pages.study(root, path)

    @ui.page("/study/point")
    def study_point(path: str = "", point: str = "", sha256: str = "", evidence: str = "", report: str = "",
                    record: str = "") -> None:
        from adroit.ui.points import point_page
        point_page(root, {"path": path, "sha256": sha256, "evidence": evidence, "report": report, "record": record},
                   point)

    @ui.page("/live")
    def live(path: str = "") -> None:
        pages.live(root, path)

    @ui.page("/about")
    def about_page() -> None:
        from adroit.ui import about
        about.page()


def _run_pages(root: Path) -> None:
    """The run pages: Constrain a model, Signal best fits, Explain a signal, Add a signal and Reanalyse."""
    from adroit.ui import wizards

    @ui.page("/new/track1")
    def new_track1(model: str = "",catalog:str='',portal:str='',limits:str='',discovery:str='',survey:str='') -> None:
        wizards.track1(root, model,catalog,portal,limits,discovery,survey)

    @ui.page("/new/track2")
    def new_track2(catalog:str='',anomaly:str='') -> None:
        wizards.track2(root,catalog,anomaly)

    @ui.page("/studies/revisit")
    def revisit_page() -> None:
        from adroit.ui.revisit import page
        page(root)

    @ui.page("/activity")
    def activity_page() -> None:
        from adroit.ui.activity import page
        page(root)

    @ui.page("/batches")
    def batches_page() -> None:
        from adroit.ui.batch_page import batches_page as page
        page(root)

    @ui.page("/bundle")
    def bundle_page(path: str = "") -> None:
        from adroit.ui.batch_page import bundle_page as page
        page(path)

    # Native fit (``advanced.native_page``) is not served in 1.0.0: withdrawn by the owner (JU1, 2026-11-16), its
    # purpose unclear from its page; deferred to 1.0.1 (the deferred list, OR-03). Its studies still open.

    @ui.page("/new/single")
    def new_single() -> None:
        wizards.single(root)

    @ui.page("/new/anomaly")
    def new_anomaly(record: str = "") -> None:
        wizards.anomaly_page(root, record)

    @ui.page('/reanalyse')
    def reanalysis(source:str='',reference:str='',target:str='',model_index:int=0,sha256:str='',evidence:str=''):
        from adroit.ui.reanalysis import page
        page(root,source,reference,target,model_index,sha256,evidence)


def _library_pages(root: Path) -> None:
    """The model library, model intake, and Add a limit's library, sessions and profiles."""

    @ui.page('/models')
    def models(view:str='standard'):
        from adroit.ui.model_library import catalog_page
        catalog_page(root,view)

    @ui.page('/models/standard')
    def standard_model(id:str=''):  # noqa: A002 - the query parameter's name
        from adroit.ui.model_library import standard_page
        standard_page(root,id)

    @ui.page('/models/view')
    def model_view(reference:str):
        from adroit.ui.model_library import model_page
        model_page(root,reference)

    @ui.page('/models/intake')
    def model_intake(session:str='',step:str='',reference:str=''):
        from adroit.ui.model_library import intake_page
        intake_page(root,session,step,reference)

    @ui.page('/experiments')
    def experimental_library():
        from adroit.ui.experimental_library import catalog_page
        catalog_page(root)

    @ui.page('/experiments/view')
    def experimental_revision(reference:str):
        from adroit.ui.experimental_library import revision_page
        revision_page(root,reference)

    @ui.page('/experiments/session')
    def experimental_session(session:str):
        from adroit.ui.experimental_assistance import session_page
        session_page(root,session)

    @ui.page('/constraints/discovery')
    def constraint_discovery(session:str):
        from adroit.ui.discovery import session_page
        session_page(root,session)

    @ui.page('/experiments/profiles')
    def experimental_profiles():
        from adroit.ui.experimental_profiles import page
        page(root)


# How long the workbench keeps a page whose connection dropped, for it to reconnect (NiceGUI's ``reconnect_timeout``;
# its pings follow from it: every 0.8 of it, answered within 0.4). At NiceGUI's 3 s, a page whose own thread was busy
# for about eight seconds (a long render, a starved browser) was dropped and forgotten, and reloaded when it
# reconnected, losing what had been typed into its forms (the auditor's CR recheck, 2026-10-27: a promotion's form found
# back at its defaults; reproduced with a page's thread blocked for 8 and 12 s, kept at 30 s for 8, 12 and 20 s).
RECONNECT = 30.0


def serve(runs_dir: str | Path | None = None, port: int = 8765, show: bool = True) -> None:  # pragma: no cover
    """Register the pages and run the workbench on 127.0.0.1 at ``port``, keeping a page ``RECONNECT`` seconds; it
    answers only its own pages on this machine (``local_only``, AL3-10)."""
    from adroit.ui.local_only import LocalOnly
    build_pages(runs_dir)
    app.add_middleware(LocalOnly)
    ui.run(title="ADROIT workbench", host="127.0.0.1", port=port, reload=False, show=show,
           reconnect_timeout=RECONNECT)
