"""Declared active scan coordinates and model-aware defaults; no numerical probing."""
from __future__ import annotations

import ast
import math

from pydantic import Field

from adroit.core.state import StrictModel
from adroit.parameter_space.classes import Point,Spin1Class,ScalarClass
from adroit.parameter_space.flavour_vector import FlavourVectorClass
from adroit.parameter_space.portals.base import Portal
from adroit.parameter_space.portals.scalar_potential import CompleteScalarPortal
from adroit.parameter_space.portals.ufo import UFOPortal

SLOTS=("m_chi","m_med","g_chi","g_q","g_l")


def active_coordinates(cls) -> list[str]:
    """The ``Point`` slots this engine's scan can vary: all five for DM13's classes; m_χ, m_med and g_χ for a flavour
    vector; those a UFO portal's parameter expressions name; or a portal's labelled slots."""
    if isinstance(cls,FlavourVectorClass):
        return ["m_chi","m_med","g_chi"]
    if isinstance(cls,(Spin1Class,ScalarClass)):
        return list(SLOTS)
    if isinstance(cls,UFOPortal):
        used={node.id for expression in cls.parameters.values()
              for node in ast.walk(ast.parse(expression,mode='eval')) if isinstance(node,ast.Name)}
        return [p for p in SLOTS if p in used]
    from adroit.parameter_space.portals.generic import GenericModel
    if isinstance(cls,GenericModel):            # m_med moves something only where it is tied (G12, G3/G4-3)
        return ["m_chi"]+(["m_med"] if cls.tied else [])
    if isinstance(cls,Portal) and cls.LABELS:
        return [p for p in SLOTS if p in cls.LABELS]
    raise ValueError("the numerical engine has no declared scan coordinates")


def validate_axes(cls, x, y, mediator_ratio=None, coupling_relations=()) -> None:
    """Raise ValueError unless the two axes are distinct active coordinates with finite bounds (positive for masses,
    one sign branch on a log axis), consistent with the mass ratio and the coupling relations."""
    active=active_coordinates(cls)
    if x.parameter == y.parameter:
        raise ValueError("the two scan axes must be different")
    for axis in (x,y):
        if axis.parameter not in active:
            raise ValueError(f"{axis.parameter} is fixed or unused by this model; active coordinates: {', '.join(active)}")
        if not all(math.isfinite(v) for v in (axis.low,axis.high)) or axis.low >= axis.high:
            raise ValueError("scan bounds must be finite with low < high")
        if axis.log and (axis.low==0 or axis.high==0 or axis.low*axis.high<0):
            raise ValueError("logarithmic axes must occupy one nonzero sign branch")
        if axis.parameter.startswith('m_') and axis.low <= 0:
            raise ValueError("mass scan bounds must be positive")
    if mediator_ratio is not None:
        if 'm_med' not in active:
            raise ValueError("this model's mediator mass is fixed; a mass ratio cannot vary it")
        if 'm_med' in (x.parameter,y.parameter):
            raise ValueError("m_med is derived from mediator_ratio and cannot be an independent axis")
    for r in coupling_relations:
        if r.derived not in active or r.source not in active:
            raise ValueError(f"the relation {r.text()} names a coupling this model does not use")
    from adroit.parameter_space import relations
    relations.check(list(coupling_relations),(x.parameter,y.parameter))


def default_axes(cls, point: Point, mediator_ratio=None, n=24, coupling_relations=()):
    """The validated (x, y) of the default plane: (g_χ, m_χ) for the complete scalar portal, a library entry's plane
    for the same engine, else (m_med, m_χ), else (m_χ, a coupling); a coupling negative at ``point`` takes the
    negative branch."""
    from adroit.parameter_space.scan import Axis
    from adroit.parameter_space import library
    active=active_coordinates(cls)
    tied={r.derived for r in coupling_relations}
    independent=[p for p in active if (p!='m_med' or mediator_ratio is None) and p not in tied]
    if isinstance(cls,CompleteScalarPortal):
        x,y=Axis(parameter='g_chi',low=1e-5,high=1.,n=n),Axis(parameter='m_chi',low=1.,high=2000.,n=n)
    else:
        def shape(model):return model.model_dump(mode='json',exclude={'name'})
        match=next((e for e in library.ENTRIES if shape(e.model_class)==shape(cls)
                    and all(a.parameter in independent for a in (e.x,e.y))),None)
        if match:
            x,y=match.x.model_copy(update={'n':n}),match.y.model_copy(update={'n':n})
        elif 'm_med' in independent and 'm_chi' in independent:
            x,y=Axis(parameter='m_med',low=10.,high=1e4,n=n),Axis(parameter='m_chi',low=1.,high=2000.,n=n)
        else:
            coupling=next((p for p in ('g_chi','g_q','g_l') if p in independent),None)
            if 'm_chi' not in independent or coupling is None:
                raise ValueError("no supported default two-parameter plane; select active axes explicitly")
            x,y=Axis(parameter='m_chi',low=1.,high=2000.,n=n),Axis(parameter=coupling,low=1e-5,high=1.,n=n)
    # Retain a supplied negative coupling branch when the template is positive.
    for axis in (x,y):
        if axis.parameter.startswith('g_') and getattr(point,axis.parameter)<0 and axis.low>0:
            low,high=axis.low,axis.high
            axis.low,axis.high=-high,-low
    validate_axes(cls,x,y,mediator_ratio,coupling_relations)
    return x,y


class ScanSetup(StrictModel):
    """A scan's declared coordinates: active, inactive, fixed and derived slots, the engine's contract, the labels
    and the two axes."""
    active: list[str]
    inactive: list[str]
    reference_engine_contract: dict
    fixed: dict[str,float]
    derived: dict[str,str] = Field(default_factory=dict)
    mediator_ratio: float | None = None
    labels: dict[str,str]
    x: dict
    y: dict
    mapping_notes: list[str] = Field(default_factory=list)


def preview(cls, point: Point, x=None, y=None, mediator_ratio=None, *, notes=None, n=24,
            coupling_relations=()) -> ScanSetup:
    """The ``ScanSetup`` a scan would run (default axes where none are given), without evaluating any point."""
    defaults=default_axes(cls,point,mediator_ratio,n,coupling_relations) if x is None or y is None else (x,y)
    x,y=x or defaults[0],y or defaults[1]
    validate_axes(cls,x,y,mediator_ratio,coupling_relations)
    free={x.parameter,y.parameter}
    derived={'m_med':f'{mediator_ratio:.17g} * m_chi'} if mediator_ratio is not None else {}
    derived|={r.derived:f'{r.factor:.17g} * {r.source}' for r in coupling_relations}   # the model's tied couplings (M9)
    labels=getattr(cls,'labels',None) or getattr(cls,'LABELS',{})
    return ScanSetup(active=[p for p in active_coordinates(cls) if p not in derived],
        inactive=[p for p in SLOTS if p not in active_coordinates(cls)],
        reference_engine_contract=cls.model_dump(mode='json',exclude={'name'}),
        fixed={p:getattr(point,p) for p in SLOTS if p not in free and p not in derived},
        derived=derived,mediator_ratio=mediator_ratio,labels={p:labels.get(p,p) for p in active_coordinates(cls)},
        x=x.model_dump(mode='json'),y=y.model_dump(mode='json'),mapping_notes=notes or [])


def model_relations(spec=None, portal: str = "", x=None, y=None) -> list:
    """The coupling relations a scan must keep (audit M9): the library entry's for a portal run, else those the
    typed model's shared symbols give (``classify.coupling_relations``), oriented so that a scanned coupling is
    its group's source. Raises Unsupported (non-linear sharing) or ValueError (both axes tied)."""
    from adroit.parameter_space import relations
    if portal:
        from adroit.parameter_space import library
        ties = list(library.entry(portal).coupling_relations)
    else:
        from adroit.parameter_space.classify import Unsupported, coupling_relations, flavour_tie
        ties = coupling_relations(spec) if spec is not None else []
        shared = flavour_tie(spec) if spec is not None else set()
        if shared and "g_chi" in (a.parameter for a in (x, y) if a is not None):
            raise Unsupported(f"the dark current shares {', '.join(sorted(shared))} with the flavour currents, which "
                              "this class keeps fixed: scanning g_chi would break the tie; scan the masses instead")
    return relations.orient(ties, tuple(a.parameter for a in (x, y) if a is not None))


def setup_identity(spec, cls, point: Point, setup: ScanSetup) -> str:
    """Content hash of the typed model, the engine, the reference point and the scan setup."""
    from adroit.core.evidence import content_hash
    return content_hash({'model':spec.model_dump(mode='json'),'engine':cls.model_dump(mode='json'),
                         'reference_point':point.model_dump(mode='json'),'setup':setup.model_dump(mode='json')})
