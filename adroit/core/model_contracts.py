"""Explicit narrow model contracts; missing physics is never a benchmark default."""

from __future__ import annotations

import math
from typing import Literal

from pydantic import Field, model_validator

from adroit.core.state import StrictModel

VECTOR_FLAVOURS = ("u", "d", "s", "c", "b", "t", "e", "mu", "tau")


class VectorCurrentContract(StrictModel):
    """Named full-Dirac vector currents and explicit zero flavours below EWSB.

    ``flavours`` maps engine flavour to the user's field name. Each coefficient
    comes from its ModelTerm in L; absent neutrino currents are part of this
    declared broken-phase simplified contract, not a gauge completion.
    """

    flavours: dict[str, str]
    zero_flavours: list[str]
    neutrinos: Literal["absent"]
    coefficient_convention: Literal["full coefficient in L"] = "full coefficient in L"

    @model_validator(mode="after")
    def _complete(self) -> VectorCurrentContract:
        keys = set(self.flavours)
        zeros = set(self.zero_flavours)
        if (
            keys & zeros
            or keys | zeros != set(VECTOR_FLAVOURS)
            or len(zeros) != len(self.zero_flavours)
        ):
            raise ValueError(
                "declare every named quark/charged-lepton current or list it explicitly as zero"
            )
        if len(set(self.flavours.values())) != len(self.flavours) or any(
            not v for v in self.flavours.values()
        ):
            raise ValueError("each flavour needs its own nonempty one-generation field mapping")
        return self


class ScalarVacuum(StrictModel):
    """Declared reference vacuum; zero singlet vev means no Higgs-singlet mixing."""

    v_gev: float = Field(gt=0, allow_inf_nan=False)
    singlet_vev_gev: float = Field(allow_inf_nan=False)

    @model_validator(mode="after")
    def _unbroken_dark_z2(self) -> ScalarVacuum:
        if self.singlet_vev_gev != 0:
            raise ValueError(
                "this Z2 DM contract requires a declared zero singlet vev; mixing needs another contract"
            )
        return self


class ResolvedScalarPotential(StrictModel):
    """Complete physical coefficients at a declared point, not a vacuum certificate."""

    scale_gev: float = Field(gt=0, allow_inf_nan=False)
    v_gev: float = Field(gt=0, allow_inf_nan=False)
    mu_h2_gev2: float = Field(allow_inf_nan=False)
    mu_s2_gev2: float = Field(allow_inf_nan=False)
    lambda_h: float = Field(allow_inf_nan=False)
    lambda_s: float = Field(allow_inf_nan=False)
    lambda_hs: float = Field(allow_inf_nan=False)
    higgs_mass_gev: float = Field(gt=0, allow_inf_nan=False)
    singlet_mass_gev: float = Field(gt=0, allow_inf_nan=False)
    higgs_field: str
    singlet_field: str
    convention: str = (
        "V=-mu_h2 H†H+lambda_h(H†H)^2+mu_s2 S^2/2+lambda_s S^4/4+lambda_hs H†H S^2/2; L=-V"
    )

    @model_validator(mode="after")
    def _physical_identity(self) -> ResolvedScalarPotential:
        squares = {
            "mu_h2": self.lambda_h * self.v_gev * self.v_gev,
            "higgs_mass2": 2 * self.lambda_h * self.v_gev * self.v_gev,
            "singlet_mass2": self.mu_s2_gev2 + self.lambda_hs * self.v_gev * self.v_gev / 2,
        }
        supplied = (
            self.mu_h2_gev2,
            self.higgs_mass_gev * self.higgs_mass_gev,
            self.singlet_mass_gev * self.singlet_mass_gev,
        )
        if not all(math.isfinite(v) for v in (*squares.values(), *supplied)) or any(
            not math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10)
            for a, b in zip(squares.values(), supplied)
        ):
            raise ValueError("resolved potential has inconsistent/nonfinite masses or stationarity")
        if not self.higgs_field or not self.singlet_field or self.higgs_field == self.singlet_field:
            raise ValueError("resolved potential requires distinct named fields")
        return self


class ScalarPotentialContract(StrictModel):
    """A complete Z2 potential in either potential or physical-mass coordinates."""

    basis: Literal["potential", "mass"]
    higgs_field: str
    singlet_field: str
    scale_gev: float = Field(gt=0, allow_inf_nan=False)
    vacuum: ScalarVacuum
    lambda_s: float = Field(allow_inf_nan=False)
    lambda_hs: float = Field(allow_inf_nan=False)
    mu_h2_gev2: float | None = Field(default=None, allow_inf_nan=False)
    mu_s2_gev2: float | None = Field(default=None, allow_inf_nan=False)
    lambda_h: float | None = Field(default=None, allow_inf_nan=False)
    higgs_mass_gev: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    singlet_mass_gev: float | None = Field(default=None, gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def _specified(self) -> ScalarPotentialContract:
        fields = (
            (self.mu_h2_gev2, self.mu_s2_gev2, self.lambda_h)
            if self.basis == "potential"
            else (self.higgs_mass_gev, self.singlet_mass_gev)
        )
        if (
            any(v is None for v in fields)
            or not self.higgs_field
            or not self.singlet_field
            or self.higgs_field == self.singlet_field
        ):
            raise ValueError(
                "complete scalar basis parameters and distinct field names are required"
            )
        self.resolve()
        return self

    def resolve(self) -> ResolvedScalarPotential:
        """Derive masses or quadratic/quartic coefficients and reject inconsistent redundancy."""
        v = self.vacuum.v_gev
        if self.basis == "potential":
            lh = self.lambda_h
            uh, us = self.mu_h2_gev2, self.mu_s2_gev2
            mh2, ms2 = 2 * lh * v * v, us + self.lambda_hs * v * v / 2
            if mh2 <= 0 or ms2 <= 0:
                raise ValueError(
                    "declared vacuum has nonpositive scalar mass squared; no physical engine map"
                )
            mh, ms = math.sqrt(mh2), math.sqrt(ms2)
        else:
            mh, ms = self.higgs_mass_gev, self.singlet_mass_gev
            if not math.isfinite(v * v) or v * v == 0:
                raise ValueError("electroweak scale outside finite numerical domain")
            lh = mh * mh / (2 * v * v)
            uh, us = lh * v * v, ms * ms - self.lambda_hs * v * v / 2
        derived = {
            "mu_h2_gev2": uh,
            "mu_s2_gev2": us,
            "lambda_h": lh,
            "higgs_mass_gev": mh,
            "singlet_mass_gev": ms,
        }
        if not all(math.isfinite(value) for value in derived.values()):
            raise ValueError(
                "derived scalar parameters overflow; finite physical coefficients required"
            )
        for name, value in derived.items():
            supplied = getattr(self, name)
            if supplied is not None and not math.isclose(
                supplied, value, rel_tol=1e-10, abs_tol=1e-10
            ):
                raise ValueError(
                    f"inconsistent redundant scalar input {name}: supplied {supplied}, derived {value}"
                )
        if not math.isclose(uh, lh * v * v, rel_tol=1e-10, abs_tol=1e-10):
            raise ValueError("declared electroweak vacuum is not stationary: mu_h2 != lambda_h v^2")
        return ResolvedScalarPotential(
            scale_gev=self.scale_gev,
            v_gev=v,
            mu_h2_gev2=uh,
            mu_s2_gev2=us,
            lambda_h=lh,
            lambda_s=self.lambda_s,
            lambda_hs=self.lambda_hs,
            higgs_mass_gev=mh,
            singlet_mass_gev=ms,
            higgs_field=self.higgs_field,
            singlet_field=self.singlet_field,
        )
