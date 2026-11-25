"""Explicit bounded Point coordinates; no expression evaluation or inferred relations."""
from __future__ import annotations

import math
from typing import Literal

from pydantic import Field, model_validator

from adroit.core.state import StrictModel

Parameter = Literal["m_chi", "m_med", "g_chi", "g_q", "g_l"]


class FitCoordinate(StrictModel):
    """One free slot of the Point: a range [low, high] on a linear or log scale, or a list of discrete values."""
    parameter: Parameter
    low: float | None = Field(default=None, allow_inf_nan=False)
    high: float | None = Field(default=None, allow_inf_nan=False)
    values: list[float] | None = None
    scale: Literal["linear", "log"] = "linear"

    @model_validator(mode="after")
    def valid_coordinate(self):
        """Refuse discrete values with bounds or a transform, empty or repeated values, low ≥ high, a log range
        reaching zero, non-finite numbers, and non-positive masses."""
        if self.values is not None:
            if self.low is not None or self.high is not None or self.scale != "linear":
                raise ValueError("discrete values cannot also have bounds or a transform")
            if not self.values or len(set(self.values)) != len(self.values):
                raise ValueError("nonempty distinct discrete values required")
            numbers = self.values
        else:
            if self.low is None or self.high is None or self.low >= self.high:
                raise ValueError("continuous coordinate requires low < high")
            if self.scale == "log" and self.low <= 0:
                raise ValueError("log coordinates require positive bounds")
            numbers = [self.low, self.high]
        if not all(math.isfinite(v) for v in numbers):
            raise ValueError("finite physical coordinates required")
        if self.parameter.startswith("m_") and min(numbers) <= 0:
            raise ValueError("physical masses must be positive")
        return self

    def value(self, unit: float) -> float:
        """The coordinate at the fraction ``unit`` of its range, linearly or logarithmically; the endpoints exactly."""
        if self.values is not None:
            raise ValueError("discrete coordinates have no continuous transform")
        if unit == 0:
            return self.low
        if unit == 1:
            return self.high
        return (math.exp(math.log(self.low) + unit * math.log(self.high / self.low))
                if self.scale == "log" else self.low + unit * (self.high - self.low))


class FitRelation(StrictModel):
    """target = scale * source + offset, in the Point slot's declared units."""
    target: Parameter
    source: Parameter
    scale: float = Field(default=1, allow_inf_nan=False)
    offset: float = Field(default=0, allow_inf_nan=False)


class FitBranch(StrictModel):
    """A labelled branch of the domain, with the further slots it fixes."""
    label: str = Field(min_length=1)
    fixed: dict[Parameter, float] = Field(default_factory=dict)


class PhysicalDomain(StrictModel):
    """Unspecified slots retain the recorded reference Point, never a fitted default."""
    coordinates: list[FitCoordinate] = Field(min_length=1, max_length=5)
    fixed: dict[Parameter, float] = Field(default_factory=dict)
    relations: list[FitRelation] = Field(default_factory=list)
    branches: list[FitBranch] = Field(default_factory=lambda: [FitBranch(label="default")],
                                     min_length=1, max_length=16)

    @model_validator(mode="after")
    def valid_domain(self):
        """Refuse repeated coordinates or relation targets, a slot both free and fixed or related, chained relations,
        repeated branch labels, a branch setting a free or related slot, non-finite fixed values or non-positive
        masses, and more than three continuous coordinates."""
        names = [c.parameter for c in self.coordinates]
        targets = [r.target for r in self.relations]
        if len(set(names)) != len(names) or len(set(targets)) != len(targets):
            raise ValueError("coordinates and relation targets must be unique")
        if set(names) & (set(self.fixed) | set(targets)) or set(targets) & set(self.fixed):
            raise ValueError("a slot cannot be both free, fixed or related")
        # Relations are intentionally independent, avoiding order-dependent expressions.
        if any(r.source in targets for r in self.relations):
            raise ValueError("chained/cyclic relations are unsupported; declare direct relations")
        if len({b.label for b in self.branches}) != len(self.branches):
            raise ValueError("branch labels must be distinct")
        for values in [self.fixed, *(b.fixed for b in self.branches)]:
            if values is not self.fixed and set(values) & (set(names) | set(targets)):
                raise ValueError("branches can only set non-free, non-related slots")
            if any(not math.isfinite(v) or (k.startswith("m_") and v <= 0)
                   for k, v in values.items()):
                raise ValueError("fixed slots require finite values and positive masses")
        if sum(c.values is None for c in self.coordinates) > 3:
            raise ValueError("at most three continuous fit coordinates are supported")
        return self


class DomainFitSettings(StrictModel):
    """The numerics of a domain fit: grid sizes, the evaluation and mode budgets, and the tolerances in the
    coordinates and in log L."""
    grid: int = Field(default=5, ge=3, le=17)
    profile_grid: int = Field(default=5, ge=3, le=17)
    max_evaluations: int = Field(default=12000, ge=5, le=100000)
    max_modes: int = Field(default=128, ge=1, le=1024)
    coordinate_tolerance: float = Field(default=1e-7, gt=0, le=1e-3)
    log_l_tolerance: float = Field(default=1e-4, gt=0, le=0.01)
