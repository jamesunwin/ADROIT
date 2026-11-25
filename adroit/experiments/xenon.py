"""The xenon searches through DIAMX: full likelihoods in S1 and S2 (level A).

DIAMX (arXiv:2512.05850; Apache-2.0) models LZ, XENONnT and PandaX-4T from
their public data: the observed events in (S1, S2), the detector response
and efficiencies, and the background models, and it reproduces the
collaborations' published limits from a recoil spectrum. Given a spectrum,
it simulates the signal's distribution in (S1, S2) and runs the profile
likelihood with the backgrounds as nuisance parameters.

This module computes the recoil spectrum with the project's own rates,
writes it in DIAMX's format (events per tonne-year per keV), and runs DIAMX
in its own environment (``diamx_driver.py``), where its templates persist
between calls. Each spectrum is labelled by a hash of its values, so that a
cached template always belongs to the spectrum it was built from.

**Generations** (the auditor's DW recheck, DX-01 and DX-05, 2026-11-12). Every
template and result DIAMX derives is made in a work folder named by the
identity of what it was derived from, a *generation*. DIAMX reads its own
package, the search's configuration and the driver from the generation's
private copy (``stage``, kept in the work folder as ``SNAPSHOT``), the copy
whose bytes named it, never from its installation; the maps DIAMX makes when
they are absent and every CSV it converts are made inside the generation
(``diamx_driver``). Its runtime (its environment's libraries and its
interpreter) is too large to copy and is held by a lease on its files'
records (``runtime_lease``): a generation whose runtime was written while it
ran, even back to the same bytes, is set aside (``quarantine``) with all it
made, and nothing is published from it.

**A run that did not end** (the auditor's DX recheck, DY-03, 2026-11-13). DIAMX
keeps a template or a map by its existence, so one left half-written by a run
that was killed or failed had been read by every later run, which then failed
on it until the generation was removed by hand. Each run now records what the
generation held as it began (``INVENTORY``); a later run that finds the
earlier one's lease left (``LEASE``) removes everything the earlier run made
or changed (``restore``), and DIAMX makes it again. What the generation held
before, every finished run's work, is kept. A run passes its generation's
lock to DIAMX's process, so the lock is held until DIAMX itself has ended.

**Spin-dependent limits** (2026-10-10). Each search's published SD-neutron and
SD-proton limits are read beside its SI limit (``SD_PUBLISHED``): XENONnT's from
its SR0+SR1 data release, LZ's from HEPData, PandaX-4T's digitised from its
Figs. 4 and 5. The module's reference SD limits use Klos et al.'s structure
factors (``NuclearModel.klos``), as XENONnT and PandaX-4T did. LZ used those of
Hoferichter, Menéndez and Schwenk (2020), which ADROIT does not have, so its SD
comparison is another reading in DM3 and gives no validated range. Other
operators keep the full shell-model responses (``conventions``).
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import math
import shutil
import subprocess
import tempfile
import time
import warnings
from pathlib import Path

import numpy as np

from adroit.core.config import get_settings
from adroit.core.dm_state import (CrossSectionKind, DarkMatterParticle, ExpectedSignal,
                                      ExperimentInfo, Fidelity, HaloModel, InteractionModel,
                                      LimitCurve, NuclearModel, PublishedConventions, Target)
from adroit.experiments.base import ExperimentModule, data_folder, element_rates, read_columns
from adroit.physics import targets

ITEM = "DIAMX"
DRIVER = Path(__file__).with_name("diamx_driver.py")
TONNE_YEAR_IN_KG_DAY = 1000.0 * 365.25
ENERGIES_KEV = np.linspace(0.01, 100.0, 200)     # DIAMX's own spectrum grid
TYPICAL_EVENTS = 100.0     # spectra reach DIAMX scaled to this many events (see ``run``)

SEARCHES = {
    "LZ WS2022+WS2024": {
        "config": "lz_ws2024_wimp_config.json", "experiments": ["LZWS2022", "LZWS2024"],
        "published": "lz_ws2024_wimp_ci.csv", "exposure_kg_day": 4.2 * TONNE_YEAR_IN_KG_DAY,
        "references": ["arXiv:2207.03764", "arXiv:2410.17036"]},
    "XENONnT SR0+SR1": {
        "config": "xenonnt_sr0_and_1_wimp_config.json",
        "experiments": ["XENONnTSR0", "XENONnTSR1a", "XENONnTSR1b"],
        "published": "xenonnt_sr1_wimp_ci.csv", "exposure_kg_day": 3.1 * TONNE_YEAR_IN_KG_DAY,
        "references": ["arXiv:2303.14729", "arXiv:2502.18005"]},
    "PandaX-4T Run0+Run1": {
        "config": "pandax4t_run01_wimp_config.json",
        "experiments": ["PandaX4TRun0", "PandaX4TRun1"],
        "published": "pandax4t_run01_wimp_ci.csv", "exposure_kg_day": 1.54 * TONNE_YEAR_IN_KG_DAY,
        "references": ["arXiv:2408.00664"]},
}


SD_MODEL = NuclearModel.klos        # the published SD limits' structure factors (Klos et al. 2013)
SD_PUBLISHED = {
    "LZ WS2022+WS2024": {"item": "LZ WS2022+WS2024 spin-dependent limits (HEPData)", "matched": False,
                         "files": {"SD-neutron": "lz_ws2024_sd_neutron.csv", "SD-proton": "lz_ws2024_sd_proton.csv"},
                         "structure_factors": "the mean of Hoferichter, Menéndez & Schwenk 2020 (arXiv:2007.08529)",
                         "source": "HEPData ins2841863 v2 (doi:10.17182/hepdata.155182.v2), arXiv:2410.17036"},
    "XENONnT SR0+SR1": {"item": "XENONnT SR0+SR1 WIMP data release", "matched": True,
                        "files": {"SD-neutron": "*/SR0+SR1/xenonnt_2025_sd_neutron_wimp.csv",
                                  "SD-proton": "*/SR0+SR1/xenonnt_2025_sd_proton_wimp.csv"},
                        "structure_factors": "the medians of Klos et al. 2013 (arXiv:1304.7684)",
                        "source": "XENONnT data release, doi:10.5281/zenodo.17419967, arXiv:2502.18005"},
    "PandaX-4T Run0+Run1": {"digitised": "pandax4t_2024_fig4_fig5", "matched": True,
                            "keys": {"SD-neutron": "sd_neutron_limit", "SD-proton": "sd_proton_limit"},
                            "structure_factors": "Klos et al. 2013 (the paper's ref. [41])",
                            "source": "arXiv:2408.00664v2, Figs. 4 and 5, digitised from the vector paths"},
}


def _hepdata_limit(path: Path) -> np.ndarray:
    """(mass, σ) rows of a HEPData limit table's "limit" block."""
    rows, inside = [], False
    for line in path.read_text().splitlines():
        if line.startswith("mass,"):
            inside = line.strip() == "mass,limit"
        elif inside and line.strip() and not line.startswith("#"):
            rows.append([float(x) for x in line.split(",")[:2]])
    return np.array(rows)


def sd_published(search: str, kind: CrossSectionKind) -> tuple[np.ndarray, str, bool] | None:
    """(mass, σ) of a search's published SD limit, its source and whether the nuclear input matches the
    module's; None when the release has not been fetched."""
    from adroit.external.fetch import locate
    from adroit.experiments import digitised
    spec = SD_PUBLISHED.get(search)
    if spec is None:
        return None
    if "digitised" in spec:
        curve = digitised.load(spec["digitised"])[spec["keys"][kind.value]]
        table = np.column_stack([curve["mass_gev"], curve["cross_section_cm2"]])
    else:
        folder = locate(spec["item"])
        if folder is None:
            return None
        path = next(folder.glob(spec["files"][kind.value]), None)
        if path is None:
            return None
        table = _hepdata_limit(path) if path.name.startswith("lz_") else \
            np.genfromtxt(path, delimiter=",", names=True)[["mass", "upper_limit"]].tolist()
        table = np.asarray(table, dtype=float)
    return table, spec["source"], spec["matched"]


def signal_scale(signal: ExpectedSignal) -> float:
    """The factor that brings a signal to ``TYPICAL_EVENTS`` expected events."""
    return TYPICAL_EVENTS / signal.total_events


def scaled(signal: ExpectedSignal) -> np.ndarray:
    """The signal's spectrum scaled to ``TYPICAL_EVENTS`` expected events."""
    return np.array(signal.density) * signal_scale(signal)


def spectrum_label(values: np.ndarray) -> int:
    """A stable integer label for a spectrum, from a hash of its values."""
    digest = hashlib.sha256(np.ascontiguousarray(values, dtype=np.float64).tobytes()).hexdigest()
    return int(digest[:12], 16)


class DiamxXenon(ExperimentModule):
    """One xenon search, run through DIAMX."""

    def __init__(self, search: str, batch_size: int = 10_000_000) -> None:
        if search not in SEARCHES:
            raise ValueError(f"unknown search {search!r}; known: {', '.join(SEARCHES)}")
        self.search, self.spec, self.batch_size = search, SEARCHES[search], batch_size
        self.folder = data_folder(ITEM)
        self.python = self.folder.parent / ".venv-diamx" / "bin" / "python"

    @property
    def name(self) -> str:
        """The search's name (a key of ``SEARCHES``)."""
        return self.search

    @property
    def info(self) -> ExperimentInfo:
        """Xenon, the search's exposure, the (S1, S2) observables and DIAMX's profile likelihood."""
        return ExperimentInfo(
            name=self.search, target="Xe", exposure_kg_day=self.spec["exposure_kg_day"],
            energy_window_kev=(float(ENERGIES_KEV[0]), float(ENERGIES_KEV[-1])),
            observables=["S1", "S2"], fidelity=Fidelity.A, background_model=True,
            statistical_method="profile likelihood in (S1, S2), asymptotic (DIAMX)",
            references=[*self.spec["references"], "arXiv:2512.05850 (DIAMX)"])

    def target(self) -> Target:
        """Natural xenon."""
        return targets.target("Xe")

    def conventions(self) -> PublishedConventions:
        """The Standard Halo Model of arXiv:2105.00599 and the Helm form factor, as in the collaborations' analyses."""
        return PublishedConventions(
            halo=HaloModel(), nuclear_model=NuclearModel.helm,
            note="the Standard Halo Model of arXiv:2105.00599 and the Helm form factor, "
                 "as in the collaborations' analyses")

    def published_limits(self) -> list[LimitCurve]:
        """The collaboration's 90% SI limit from DIAMX's data (without the power constraint), and its
        power-constrained SD-neutron and SD-proton limits where published."""
        table = read_columns(self.folder / "diamx" / "data" / self.spec["published"])
        curves = [LimitCurve(experiment=self.search, kind=CrossSectionKind.si,
                             masses_gev=table[:, 0].tolist(), cross_sections_cm2=table[:, 1].tolist(),
                             source=f"DIAMX data/{self.spec['published']}",
                             note="the collaboration's 90% limit without the power constraint")]
        for kind in (CrossSectionKind.sd_neutron, CrossSectionKind.sd_proton):
            found = sd_published(self.search, kind)
            if found is None:
                continue
            sd, source, matched = found
            spec = SD_PUBLISHED[self.search]
            curves.append(LimitCurve(
                experiment=self.search, kind=kind, masses_gev=sd[:, 0].tolist(), cross_sections_cm2=sd[:, 1].tolist(),
                source=source, note=f"the collaboration's power-constrained 90% limit; structure factors: "
                                    f"{spec['structure_factors']}" + ("" if matched else "; NOT the module's (Klos 2013)")))
        return curves

    def reference_limits(self, kind: CrossSectionKind, masses_gev: list[float],
                         workers: int = 1, cl: float = 0.9) -> list[float]:
        """The collaboration's procedure: SD limits with Klos et al.'s structure factors (``SD_MODEL``)."""
        model = SD_MODEL if kind in (CrossSectionKind.sd_neutron, CrossSectionKind.sd_proton) else None
        return self.limits_on(kind, masses_gev, model=model, cl=cl, target=self.published_target(kind))

    def expected_signal(self, particle: DarkMatterParticle, interaction: InteractionModel,
                        halo: HaloModel, model: NuclearModel,
                        target: Target | None = None) -> ExpectedSignal:
        """The recoil spectrum per tonne-year on ``ENERGIES_KEV`` (keVnr), summed over isotopes; ``total_events`` for
        the search's exposure."""
        rate = sum(element_rates(ENERGIES_KEV, particle, interaction, target or self.target(),
                                 halo, model).values())
        per_tonne_year = rate * TONNE_YEAR_IN_KG_DAY
        exposure_t_yr = self.spec["exposure_kg_day"] / TONNE_YEAR_IN_KG_DAY
        return ExpectedSignal(experiment=self.search, interaction_id=interaction.id,
                              particle=particle,
                              total_events=float(np.trapezoid(per_tonne_year, ENERGIES_KEV))
                              * exposure_t_yr,
                              observable=ENERGIES_KEV.tolist(), density=per_tonne_year.tolist())

    def upper_limit(self, signal: ExpectedSignal, cl: float = 0.9) -> float:
        """One spectrum's limit on its rate multiplier, through ``upper_limits`` (one DIAMX run)."""
        return self.upper_limits([signal], cl)[0]

    def upper_limits(self, signals: list[ExpectedSignal], cl: float = 0.9) -> list[float]:
        """Limits on the rate multipliers of several spectra, in one DIAMX run.

        DIAMX returns nothing for a spectrum that puts essentially no events in
        its region of interest; such a spectrum gets no limit (infinity), with
        a warning, rather than stopping the run.
        """
        results = self.run(signals, cl)
        out = []
        for s in signals:
            row = results.get(spectrum_label(scaled(s)))
            if row is None:
                warnings.warn(f"{self.info.name}: DIAMX gave no result for a spectrum at "
                              f"{s.particle.mass_gev:g} GeV; no limit is set", stacklevel=2)
                out.append(math.inf)
            else:
                out.append(row["upper"] * signal_scale(s))
        return out

    def run(self, signals: list[ExpectedSignal], cl: float = 0.9) -> dict[int, dict]:
        """DIAMX's inference for each spectrum, keyed by label.

        Each spectrum is handed over scaled to ``TYPICAL_EVENTS`` expected
        events (``scaled``), so that DIAMX fits multipliers of order one. The
        run reads the generation's private copy of DIAMX (the module docstring);
        a call whose runtime changes while it waits for its generation names the
        generation again, at most ``ATTEMPTS`` times.
        """
        scaled_densities = [scaled(s) for s in signals]
        labels = [spectrum_label(d) for d in scaled_densities]       # in order, repeats kept: the identity
        densities = dict(zip(labels, scaled_densities))
        for _ in range(ATTEMPTS):
            staged = stage(self.folder, self.spec["config"], get_settings().tools_dir / STAGING)
            try:
                found = self._attempt(densities, labels, cl, staged)
            finally:
                shutil.rmtree(staged, ignore_errors=True)            # gone already where it became the snapshot
            if found is not None:
                return found
        raise DiamxInputsChanged(f"{self.search}: DIAMX's runtime changed each of {ATTEMPTS} times its generation "
                                 "was about to run; nothing was run")

    def _attempt(self, densities: dict[int, np.ndarray], labels: list[int], cl: float,
                 staged: Path) -> dict[int, dict] | None:
        """The result of one generation named by ``staged`` and the runtime as it is; None where the generation must
        be named again (its folder set aside while this call waited, or its runtime changed since it was named)."""
        inputs = self._inputs(staged)
        work = get_settings().tools_dir / "diamx-work" / f"{self.spec['config']}-{self.batch_size}-{inputs[:16]}"
        work.mkdir(parents=True, exist_ok=True)
        request, identity = self._request(labels, cl, work, inputs)
        cached = _finished(work / f"result-{identity}.json", densities)
        if cached is not None:                         # a finished result is read without waiting for the lock
            return cached
        # Scan workers can request the same experiment concurrently. DIAMX shares
        # templates; serialize their generation and give every CL a distinct result.
        with (work / "inference.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if not _holds(lock, work / "inference.lock"):
                return None                            # the folder was set aside while this call waited
            lease = runtime_lease(self.python)
            if not self._settled(work, lease) or self._inputs(staged) != inputs:
                return None
            return self._run_locked(densities, request, identity, work, staged, lease, lock)

    def _inputs(self, staged: Path) -> str:
        """The identity of everything DIAMX reads beyond its request: ``diamx_inputs`` of the generation's private
        copy of the driver, the configuration and DIAMX's package (``stage``), and of its runtime. It names the work
        folder (``run``), so that every artifact DIAMX derives from them there (its generated background and signal
        templates, blueice's ``pdf_cache``, its configurations, its maps and converted spectra, its results) is
        derived from these inputs: DIAMX keys its templates by their arguments (an input's path, not its bytes), so a
        template made before an input changed had been reused after it under a new result's identity (the auditor's DV–IE
        recheck, DW-01, 2026-11-11). The copy's files are taken by their names and bytes, so every checkout of the
        same code shares a folder. Before, the identity was taken of the installation, and DIAMX then read the
        installation: an input changed in between was calculated with under the old identity (DX-01)."""
        return hashlib.sha256(json.dumps(diamx_inputs(staged, self.python), sort_keys=True).encode()).hexdigest()

    def _settled(self, work: Path, lease: str) -> bool:
        """Whether the work folder can be used. A run that left its lease (``LEASE``) ended without its end check
        (killed, or failed): where the runtime still matches the lease, what that run made or changed is removed
        (``restore``, DY-03) and True; where it does not, a run interrupted after its runtime changed, or where what the
        run began from cannot be read, the folder is set aside (``quarantine``) and False."""
        left = work / LEASE
        if not left.exists():
            return True
        if left.read_text() == lease:
            if restore(work):
                left.unlink()
                return True
            aside = quarantine(work, "a run in this generation ended without its end check, and the record of what it "
                                     "began from cannot be read")
            warnings.warn(f"{self.search}: a run of a generation ended without its end check and what it began from "
                          f"cannot be read; the generation is set aside in {aside}", stacklevel=3)
            return False
        aside = quarantine(work, "a run in this generation ended without its end check, and DIAMX's runtime has "
                                 "changed since it began")
        warnings.warn(f"{self.search}: DIAMX's runtime changed during an interrupted run of a generation; it is set "
                      f"aside in {aside}", stacklevel=3)
        return False

    def _request(self, labels: list[int], cl: float, work: Path, inputs: str) -> tuple[dict, str]:
        """DIAMX's request for these spectra, and its identity: a hash of the request (its work folder named by the
        inputs) and of the inputs' identity (``_inputs``), the identity under which its result is both looked up and
        written."""
        spectra = work / "spectra"
        request = {"config": self.spec["config"], "experiments": self.spec["experiments"],
                   "labels": labels, "spectra_dir": str(spectra), "batch_size": self.batch_size,
                   "work_dir": str(work), "confidence_level": cl,
                   "run_name": f"run-{spectrum_label(np.array(labels, dtype=float))}"}
        material = hashlib.sha256(json.dumps(request, sort_keys=True).encode())
        material.update(inputs.encode())
        identity = material.hexdigest()
        request["run_name"] = f"run-{identity}"
        return request, identity

    def _run_locked(self, densities: dict[int, np.ndarray], request: dict, identity: str, work: Path,
                    staged: Path, lease: str, lock) -> dict[int, dict]:
        """One run in its generation, under its lock (``lock``, passed to DIAMX's process too, so that the generation
        stays locked until DIAMX has ended, even where this process has not): DIAMX from the generation's snapshot (the
        staged copy, at the generation's first run), what the generation held as it began recorded (``INVENTORY``,
        DY-03), its result published only once the runtime's lease is found unbroken."""
        result_path = work / f"result-{identity}.json"
        cached = _finished(result_path, densities)
        if cached is not None:
            return cached
        snapshot = work / SNAPSHOT
        if not snapshot.exists():
            os.replace(staged, snapshot)               # the bytes that named the generation are those it reads
        spectra = work / "spectra"
        spectra.mkdir(parents=True, exist_ok=True)
        for label, density in densities.items():
            np.savetxt(spectra / f"wimp_{label}GeV.csv",
                       np.column_stack([ENERGIES_KEV, density]), delimiter=",")
        request_path, pending = work / f"request-{identity}.json", work / f"pending-{identity}.json"
        request_path.write_text(json.dumps(request))
        pending.unlink(missing_ok=True)
        partial = work / f"{INVENTORY}.partial"
        partial.write_text(json.dumps(inventory(work)))
        os.replace(partial, work / INVENTORY)          # what the run begins from, before its lease says it began
        (work / LEASE).write_text(lease)
        subprocess.run([str(self.python), str(snapshot / DRIVER.name), str(request_path), str(pending)],
                       check=True, cwd=work, stdin=subprocess.DEVNULL, capture_output=True, env=capped_environment(),
                       pass_fds=(lock.fileno(),))
        if runtime_lease(self.python) != lease:
            aside = quarantine(work, "DIAMX's runtime was written while a run in this generation ran")
            raise DiamxInputsChanged(
                f"{self.search}: DIAMX's runtime (its environment's libraries or its interpreter) was written while "
                f"this generation ran: everything it made is set aside in {aside}, and nothing is published from it. "
                "Run it again")
        (work / LEASE).unlink()
        (work / INVENTORY).unlink(missing_ok=True)
        os.replace(pending, result_path)               # published only now: a reader never sees an unchecked result
        rows = _finished(result_path, densities)
        if rows is None:
            raise RuntimeError(f"DIAMX returned incomplete or nonfinite limits: {result_path}")
        return rows


SNAPSHOT = "snapshot"                 # in a work folder: the generation's copy of the driver, configuration and DIAMX
LEASE = "runtime-lease"               # in a work folder while a run is in it: the runtime's lease when the run began
INVENTORY = "run-inventory.json"      # in a work folder while a run is in it: what the folder held as the run began
MARKS = {LEASE, INVENTORY, f"{INVENTORY}.partial", "inference.lock"}      # a run's own marks: never an artifact
STAGING = "diamx-staging"             # in the tools folder: copies being named (``stage``)
QUARANTINE = "diamx-quarantined"      # in the tools folder: generations set aside (``quarantine``)
ATTEMPTS = 3


def _entries_of(work: Path):
    """(path relative to ``work``, its record) of every file and link in a work folder but a run's marks (``MARKS``):
    the record its device, inode, size, and modification and change times (``file_reads.identity``), links not
    followed."""
    from adroit.core.file_reads import identity
    for directory, subdirs, files in os.walk(work):
        links = [name for name in subdirs if os.path.islink(os.path.join(directory, name))]
        for name in sorted(files) + links:
            path = os.path.join(directory, name)
            relative = os.path.relpath(path, work)
            if relative not in MARKS:
                yield relative, list(identity(os.lstat(path)))


def inventory(work: Path) -> dict[str, list[int]]:
    """What a work folder holds, by ``_entries_of``: written as a run begins (``INVENTORY``)."""
    return dict(_entries_of(work))


def restore(work: Path) -> bool:
    """Remove from a work folder everything a run that ended without its end check made or changed: each file or link
    not in ``INVENTORY`` (what the folder held as the run began), or whose record differs from it (DY-03). A finished
    result (``result-*.json``) is kept: one is published only once its run has ended its check, never during a run.
    Folders are kept. False where ``INVENTORY`` cannot be read, so that nothing can be told apart."""
    try:
        began = json.loads((work / INVENTORY).read_text())
    except (OSError, ValueError):
        return False
    for relative, record in list(_entries_of(work)):
        if began.get(relative) != record and not (os.sep not in relative and relative.startswith("result-")):
            os.unlink(work / relative)
    return True


class DiamxInputsChanged(RuntimeError):
    """DIAMX's runtime changed while a generation ran, or each time one was about to (``DiamxXenon.run``)."""


def stage(folder: Path, config: str, staging: Path) -> Path:
    """A private copy of what a DIAMX run reads beyond its request and its runtime: the driver (``DRIVER``), the
    search's configuration (``config/<config>``) and DIAMX's package (``diamx/``), in a new folder under ``staging``.

    The package's files are those ``tree_identity``'s walk finds (``track1_identity._entries``): a linked folder's
    files under their names through it, a link back into the package and a folder that cannot be listed refused
    (``InputUnreadable``); compiled bytecode and ``__pycache__`` are not copied (Python makes its own), nor a link
    leading nowhere (DIAMX cannot read it either). Each file is copied byte for byte, links followed, so nothing in
    the copy changes when the installation does (DX-01). An APFS volume copies the 4.5 MB package in ~0.05 s."""
    from adroit.orchestrator.track1_identity import _entries
    staging.mkdir(parents=True, exist_ok=True)
    _sweep(staging)
    copy = Path(tempfile.mkdtemp(prefix=f"{os.getpid()}-", dir=staging))
    try:
        shutil.copyfile(DRIVER, copy / DRIVER.name)
        (copy / "config").mkdir()
        if (folder / "config" / config).is_file():
            shutil.copyfile(folder / "config" / config, copy / "config" / config)
        package = folder / "diamx"
        for kind, path, _ in (_entries(package) if package.exists() else []):
            if kind == "file" and path.exists():
                target = copy / "diamx" / path.relative_to(package)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
    except BaseException:
        shutil.rmtree(copy, ignore_errors=True)
        raise
    return copy


def _sweep(staging: Path) -> None:
    """Remove the copies left in ``staging`` by processes that have ended (a call killed while it held one): each
    copy is named by its process's number."""
    for left in staging.iterdir():
        number = left.name.split("-", 1)[0]
        if not number.isdigit():
            continue
        try:
            os.kill(int(number), 0)
        except ProcessLookupError:
            shutil.rmtree(left, ignore_errors=True)
        except PermissionError:
            pass                                       # another user's process holds that number: left alone


def runtime_lease(python: Path) -> str:
    """A digest of the records of DIAMX's runtime's files (``diamx_inputs``' runtime: its environment's libraries and
    its interpreter): each file's name, device, inode, size, and modification and change times, by
    ``track1_identity._entries``' walk. Any write to a file moves its change time, so the lease changes with every
    write, even one that restores the file's bytes (A → B → A), which a digest of the bytes would not see."""
    from adroit.orchestrator.track1_identity import _entries
    digest = hashlib.sha256()
    for root in (python.parent.parent / "lib", python):
        for kind, path, text in (_entries(root) if root.exists() else []):
            try:
                s = path.stat()
                record = f"{kind}\0{path}\0{text}\0{s.st_dev}\0{s.st_ino}\0{s.st_size}\0{s.st_mtime_ns}\0{s.st_ctime_ns}"
            except OSError as error:
                record = f"{kind}\0{path}\0{text}\0{type(error).__name__}"
            digest.update(record.encode() + b"\n")
    return digest.hexdigest()


def quarantine(work: Path, why: str) -> Path:
    """Set a generation's work folder aside under the tools folder's ``QUARANTINE``, with a note of why
    (``QUARANTINED.txt``), and give where. Nothing in it is read again: a later call of the same identity starts a
    new generation in a new folder, and a call waiting on its lock sees it gone (``_holds``)."""
    aside = work.parent.parent / QUARANTINE / f"{work.name}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{os.getpid()}"
    aside.parent.mkdir(parents=True, exist_ok=True)
    os.replace(work, aside)
    (aside / "QUARANTINED.txt").write_text(f"{why}; set aside {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n")
    return aside


def _holds(lock, path: Path) -> bool:
    """Whether the open lock file is still the one at ``path`` (its work folder not set aside, nor replaced)."""
    try:
        here = path.stat()
    except FileNotFoundError:
        return False
    held = os.fstat(lock.fileno())
    return (here.st_dev, here.st_ino) == (held.st_dev, held.st_ino)


def diamx_inputs(snapshot: Path, python: Path) -> dict[str, str]:
    """What DIAMX reads beyond its request, each by ``track1_identity.tree_identity``: a generation's private copy of
    the driver, its configuration and DIAMX's package whole (``stage``: its Python source, the bundled detector data,
    response maps and background templates, and its compiled NEST extension), and its runtime (its environment's
    libraries and its interpreter). Computed at each call, so a change between two calls of one process is seen (an
    operational audit's IA-01, 2026-11-10: a cached limit had survived changed detector data and a changed runtime, a
    warm answer differing from a fresh one). DIAMX's own generated caches (``pdf_cache``, beside the package from its
    setup) and ADROIT's work folder are not in it; the work folder, where a run's caches are made, is named by it
    (``_inputs``, DW-01)."""
    from adroit.orchestrator.track1_identity import tree_identity
    return {"snapshot": tree_identity(snapshot), "runtime": tree_identity(python.parent.parent / "lib"),
            "interpreter": tree_identity(python)}


BUILT = {".so", ".a", ".dylib", ".o"}          # what a machine's own build makes: not a table's input as such
BUILDING = {"CMakeFiles", "cmake_install.cmake"}
GENERATED = "wimp_*GeV.json"     # DIAMX's own example spectra (its .gitignore); the driver gives DIAMX ADROIT's spectra


def diamx_versions(folder: Path, python: Path) -> tuple[list[Path], str]:
    """What a stored limit table's fingerprint takes of ``diamx_inputs``, the same on every machine with the same
    installation (``limit_tables``): the package's files but those its build made there (compiled extensions and
    CMake's files) and DIAMX's generated spectra (``GENERATED``), and the runtime by its Python's version and each
    installed distribution's name and version.

    The package's files are found by the walk ``diamx_inputs`` uses (``track1_identity._entries``): a link to a folder
    is followed, its files taken under their names through it (no link's target, which differs between machines, is
    taken); a link back into the tree and a folder that cannot be listed are refused (``InputUnreadable``). Before, a
    separate walk had passed over linked folders, so data changed behind ``diamx/data -> <a folder>`` had left a
    stored table current (the auditor's DV–IE recheck, DW-02, 2026-11-11). A package with no folder link gives the same
    files as before."""
    from adroit.orchestrator.track1_identity import _entries
    files = sorted(f for kind, f, _ in _entries(folder / "diamx") if kind == "file" and f.is_file()
                   and "__pycache__" not in f.parts and f.suffix not in BUILT | {".pyc"}
                   and not BUILDING & set(f.parts) and not f.match(GENERATED))
    lib = python.parent.parent / "lib"
    runtime = {"python": sorted(p.name for p in lib.glob("python*")),
               "distributions": sorted(p.name for p in lib.glob("python*/site-packages/*.dist-info"))}
    return files, json.dumps(runtime, sort_keys=True)


THREAD_VARIABLES = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
                    "NUMEXPR_NUM_THREADS", "NUMBA_NUM_THREADS", "PJRT_NPROC", "NPROC")


def capped_environment(threads: int | None = None) -> dict[str, str]:
    """The environment for DIAMX's subprocess with every numerical thread pool capped (``numerical_threads``):
    OpenMP, OpenBLAS, MKL, Apple's Accelerate (VECLIB, NumPy's backend on macOS), NumExpr, Numba, XLA's
    multi-threaded Eigen, and JAX's CPU client, whose pool for JIT-compiled loops is sized by ``PJRT_NPROC``
    (``NPROC`` in older jaxlib) and otherwise takes every core: the 3.75 cores measured during R3's runs."""
    n = str(threads or getattr(get_settings(), "numerical_threads", 2))
    env = {**os.environ, **{name: n for name in THREAD_VARIABLES}}
    flags = env.get("XLA_FLAGS", "")
    if "xla_cpu_multi_thread_eigen" not in flags:
        flags = f"{flags} --xla_cpu_multi_thread_eigen=false".strip()
    env["XLA_FLAGS"] = flags
    return env


ROI_FLOOR_KEV = 40.0       # every xenon search here accepts nuclear recoils up to at least this energy
INVISIBLE = 1e-3           # of a spectrum's (scaled) events below ROI_FLOOR_KEV: none DIAMX could see


def _finished(result_path: Path, densities: dict[int, np.ndarray]) -> dict[int, dict] | None:
    """A finished DIAMX result, keyed by label, or None.

    DIAMX skips a spectrum with no events in its S1/S2 region of interest (``update_alea_config_signal``
    returns None), writing no row for it. Such a result counts as finished, and the spectrum gets no limit (∞,
    in ``upper_limits``), only if every missing spectrum has essentially no events below ``ROI_FLOOR_KEV``,
    where each search accepts nuclear recoils: a recoil spectrum DIAMX cannot see. A row DIAMX omitted for any
    other reason leaves the result incomplete, as before; and no limit can never exclude anything."""
    rows = _complete(result_path, set(densities))
    if rows is not None:
        return rows
    try:
        found = {row["label"]: row for row in json.loads(result_path.read_text())}
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not set(found) <= set(densities) or not all(math.isfinite(r["upper"]) and r["upper"] > 0 for r in found.values()):
        return None
    low = ENERGIES_KEV < ROI_FLOOR_KEV
    for label in set(densities) - set(found):
        density = np.nan_to_num(densities[label])
        if np.trapezoid(density[low], ENERGIES_KEV[low]) > INVISIBLE * max(np.trapezoid(density, ENERGIES_KEV), 1e-300):
            return None
    return found


def _complete(result_path: Path, labels: set[int]) -> dict[int, dict] | None:
    """A DIAMX result with a finite, positive limit for every label, keyed by label; else None (missing,
    unreadable, partly written or incomplete)."""
    try:
        rows = json.loads(result_path.read_text())
        if {row["label"] for row in rows} == labels and all(math.isfinite(row["upper"]) and row["upper"] > 0
                                                            for row in rows):
            return {row["label"]: row for row in rows}
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None
