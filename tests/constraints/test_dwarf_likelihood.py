"""Independent dense nuisance profiles, likelihood normalisation and source gates."""

from pathlib import Path

import numpy as np
import pytest
from scipy.optimize import brentq

from adroit.constraints import dwarf_likelihood as dl, indirect, spectra


def photons() -> spectra.PhotonSpectrum:
    return spectra.PhotonSpectrum(
        request=spectra.from_rates(100.0, {"b": 1.0}),
        energies_gev=[0.1, 1.0, 10.0, 100.0],
        dnde_per_gev=[1.0, 1.0, 1.0, 0.0],
    )


def dwarf() -> dl.DwarfSED:
    flux = np.linspace(0, 100, 10001)
    return dl.DwarfSED(
        name="analytic",
        log10_j=np.log10(8 * np.pi * 100**2),
        sigma_log10_j=0.15,
        energies_gev=[1.0],
        flux_per_gev=[flux.tolist()],
        loglike=[(-0.5 * (flux - 2) ** 2).tolist()],
    )


def test_profile_matches_independent_dense_j_scan_and_has_no_jacobian():
    row = dwarf()
    z = np.linspace(-1.2, 1.2, 500001)
    for rate in (0.1, 2.0, 5.0, 20.0):
        dense = np.max(-0.5 * (rate * 10**z - 2) ** 2 - 0.5 * (z / 0.15) ** 2)
        assert dl.profile(row, np.array([1.0]), rate) == pytest.approx(dense, abs=2e-5)
    assert dl.profile(row, np.array([1.0]), 0.0) == -2.0
    with pytest.raises(spectra.SpectrumUnavailable, match="bounded"):
        dl.profile(row, np.array([1.0]), 1e8)
    with pytest.raises(ValueError, match="flux"):
        dl.profile(row, np.array([1.0]), -1.0)


def test_upper_branch_includes_positive_best_fit_and_conjugacy():
    row, source = dwarf(), photons()
    limit = dl.upper_limit(source, (row,))
    z = np.linspace(-1.2, 1.2, 200001)
    reference = brentq(
        lambda rate: np.max(-0.5 * (rate * 10**z - 2) ** 2 - 0.5 * (z / 0.15) ** 2) + 2.71 / 2,
        2.0,
        10.0,
    )
    assert limit.best_fit_cm3_s == pytest.approx(2.0, rel=0.002)
    assert limit.upper95_cm3_s == pytest.approx(reference, rel=0.001)
    dirac = dl.upper_limit(source, (row,), self_conjugate=False)
    partial = dl.upper_limit(source, (row,), density_fraction=0.25)
    assert dirac.upper95_cm3_s == pytest.approx(2 * limit.upper95_cm3_s, rel=1e-5)
    assert partial.upper95_cm3_s == pytest.approx(16 * limit.upper95_cm3_s, rel=1e-5)
    assert dl.flux_factors(source, (row,))[0][0] == pytest.approx(1.0)


def test_missing_data_invalid_units_and_dark_spectrum_are_refused(tmp_path):
    with pytest.raises(spectra.SpectrumUnavailable, match="Incomplete"):
        dl.load(tmp_path)
    with pytest.raises(ValueError, match="scan"):
        dwarf().model_copy().model_validate({**dwarf().model_dump(), "flux_per_gev": [[1.0, 2.0]]})
    with pytest.raises(ValueError, match="fraction"):
        dl.flux_factors(photons(), (dwarf(),), density_fraction=0.0)
    dark = photons().model_copy(update={"dnde_per_gev": [0.0] * 4})
    with pytest.raises(spectra.SpectrumUnavailable, match="No photons"):
        dl.upper_limit(dark, (dwarf(),))


def test_gate_precedes_all_external_reads_and_unknown_channels_stay_pending(monkeypatch, awaiting):
    awaiting("fermi-2311.04982-spectral")                                   # held unverified, whatever the owner has signed
    monkeypatch.setattr(spectra, "table", lambda *_: pytest.fail("unexpected source read"))
    assert "verification" in indirect.spectral_comparison({"b": 1.0, "c": 1.0}, 100.0, False).why
    assert "description" in indirect.spectral_comparison({"A'A'": 1.0}, 100.0, False, True).why


def test_recast_returns_the_actual_total_rate_and_typed_limit(monkeypatch):
    monkeypatch.setattr(spectra, "spectrum", lambda _: photons())
    limit = dl.SpectralLimit(
        upper95_cm3_s=4e-26,
        best_fit_cm3_s=0.0,
        dwarfs=42,
        self_conjugate=False,
        density_fraction=1.0,
    )
    monkeypatch.setattr(dl, "upper_limit", lambda _, **kwargs: limit)
    result = indirect.spectral_comparison({"b": 2e-26, "c": 1e-26}, 100.0, False, True)
    assert result.ratio == pytest.approx(0.75) and result.limit == limit


def test_installers_validate_downloads_before_extraction(tmp_path: Path):
    from scripts.install_spectral_data import install

    (tmp_path / "AtProduction_gammas.dat.zip").write_bytes(b"not the source")
    with pytest.raises(ValueError, match="validated"):
        install("pppc", tmp_path)
    (tmp_path / "42263853").write_bytes(b"not the source")
    with pytest.raises(ValueError, match="validated"):
        install("dwarfs", tmp_path)


def test_fits_loader_units_complete_benchmark_and_cache_identity(tmp_path: Path):
    from astropy.io import fits
    import csv

    folder = tmp_path / "dSphs" / "SEDs"
    folder.mkdir(parents=True)
    with (tmp_path / "dSphs.csv").open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(["name", "log10_J", "J_sigma"])
        writer.writerows((name, 18.0, 0.2) for name in dl.BENCHMARK)
    columns = [
        fits.Column(name="e_ref", format="D", unit="MeV", array=np.geomspace(579, 860000, 26)),
        fits.Column(
            name="ref_dnde", format="D", unit="cm-2 MeV-1 ph s-1", array=np.ones(26) * 1e-12
        ),
        fits.Column(name="norm_scan", format="20D", array=np.tile(np.arange(20), (26, 1))),
        fits.Column(
            name="dloglike_scan", format="20D", array=-(np.tile(np.arange(20), (26, 1)) ** 2)
        ),
    ]
    for name in dl.BENCHMARK:
        fits.BinTableHDU.from_columns(columns, name="SED").writeto(folder / f"{name}_sed.fits")
    data = dl.load(tmp_path)
    assert len(data) == 42
    assert data[0].energies_gev[0] == pytest.approx(0.579)
    assert data[0].flux_per_gev[0][1] == pytest.approx(1e-9)
    data[0].loglike[0][1] = 99.0
    assert dl.load(tmp_path)[0].loglike[0][1] == -1.0
    path = folder / f"{dl.BENCHMARK[0]}_sed.fits"
    with fits.open(path, mode="update") as source:
        source["SED"].data["ref_dnde"] *= 2
    assert dl.load(tmp_path)[0].flux_per_gev[0][1] == pytest.approx(2e-9)
    with fits.open(path, mode="update") as source:
        source["SED"].header["TUNIT1"] = "GeV"
    with pytest.raises(spectra.SpectrumUnavailable, match="schema"):
        dl.load(tmp_path)
