"""The frame a speed table is given in.

A table in the detector's frame is ADROIT's ordinary tabulated halo (``HaloModel`` of kind ``tabulated``), which the
rate code reads. A table in the Sun's frame is a ``SunFrameTable``, which only capture in the Sun reads
(``constraints.capture.sun_frame``). An anisotropic distribution's speeds depend on the direction of the boost, so a
detector's table is not the Sun's, and neither is ever turned into the other.

The Sun's frame is marked by this subclass, not by a field of ``HaloModel``: ``adroit/core/dm_state.py`` is an input
of the native PICO-60 validation certificate (``experiments/data/native_pico_si_validation.yaml``, which byte-hashes
it), and is kept byte for byte.
"""
from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from adroit.core.dm_state import HaloKind, HaloModel


class SunFrameTable(HaloModel):
    """A tabulated speed distribution in the Sun's frame (its record says so: ``frame: sun``)."""
    frame: Literal["sun"] = "sun"

    @model_validator(mode="after")
    def _a_table(self) -> "SunFrameTable":
        if self.kind is not HaloKind.tabulated:
            raise ValueError("only a table is given in the Sun's frame; a standard halo is boosted to it")
        return self


def frame_of(halo: HaloModel) -> Literal["detector", "sun"]:
    """The frame a halo's table is in: the Sun's for a ``SunFrameTable``, else the detector's."""
    return "sun" if isinstance(halo, SunFrameTable) else "detector"
