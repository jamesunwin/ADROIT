"""Reviewed multimodal transcription and model refinement; no physics calculator."""
from pydantic import Field
from typing import Literal
from adroit.core.state import StrictModel
from adroit.core.model_spec import ModelSpec
from adroit.agents.lagrangian import INTAKE_SYSTEM

class Interpretation(StrictModel):
    """A reviewed interpretation of a model: its transcription, the canonical model, the ambiguities, and whether the
    source gave a Lagrangian or a field content."""
    transcription: str
    spec: ModelSpec
    ambiguities: list[str] = Field(default_factory=list)
    explanation: str = ''
    representation: Literal['lagrangian','field_content'] = 'lagrangian'
    simplified: str = ''       # what a simplified model leaves out of the larger theory it is part of ('' if none)

SYSTEM=INTAKE_SYSTEM+'''
This is a researcher-reviewed interpretation/refinement. Return Interpretation JSON.
Distinguish a stated/implied Lagrangian from field content only using representation.
For field_content do not invent interactions; the deterministic generator constructs
the allowed Lagrangian afterward. Identify missing gauge information in ambiguities.
Transcribe the provided model faithfully into transcription (TeX where appropriate).
For an image identify unreadable symbols, signs, indices, charges and numeric values
in ambiguities; do not guess them as certain. Never invent numerical parameters.
Keep absent values null. If refining, retain all prior fields/terms/coefficients/
contracts unless the requested correction explicitly changes them. List every
interpretive assumption and omitted interaction. A valid JSON model does not imply
a calculable engine or a physically valid vacuum. The researcher reviews before use.
If the model keeps only part of a larger theory (for example the superpartners a
supersymmetric model needs here and not the others, or one mediator of a fuller
model), set simplified to what it leaves out, in a few words, and end its name with
"(simplified model)"; leave simplified empty for a model complete as given.
'''

def interpret(llm,text,*,previous=None,images=None,model='claude-opus-5-5'):
    """The LLM's interpretation of a model's text (and images); with ``previous``, a refinement that keeps the parts
    the correction does not change."""
    import json
    body='Source/correction:\n'+text
    if previous is not None:
        body+='\nPrevious canonical model (preserve unchanged parts):\n'+json.dumps(previous.model_dump(mode='json'))
    return llm.complete_structured(SYSTEM,[{'role':'user','content':body}],Interpretation,
                                   images=images,model=model,actor='model_intake_review')
