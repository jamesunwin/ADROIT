"""Researcher model selection, separate from statistical ranking."""
from __future__ import annotations
import re
from typing import Literal
from pydantic import Field, field_validator, model_validator
from adroit.core.state import StrictModel

def normalize_property(text: str) -> str:
    """Normalize an open vocabulary without inferring a theoretical property.

    Args:
        text: One researcher-defined property, not a conjunction to be evaluated.
    """
    value=' '.join(text.strip().lower().split())
    if not value or len(value)>200 or any(ord(c)<32 for c in value):
        raise ValueError('model properties need one nonempty phrase of at most 200 characters')
    # Preserve established spellings without restricting the vocabulary.
    return {'supersymmetric':'susy','supersymmetry':'susy',
            'inelastic dark matter':'inelastic','inelastic models':'inelastic'}.get(value,value)

class StyleDeclaration(StrictModel):
    """A reviewed yes/no declaration of a model property, with its source, scope and reviewer."""
    property: str = Field(min_length=1,max_length=200)
    state: Literal['yes','no']
    source: str = Field(min_length=1, max_length=2000)
    scope: str = Field(min_length=1, max_length=2000)
    reviewed_by: str = Field(min_length=1, max_length=200)

    _property = field_validator('property')(normalize_property)

    @model_validator(mode='after')
    def nonblank(self):
        """Refuse a declaration whose source, scope or reviewer is blank."""
        if any(not x.strip() for x in (self.source,self.scope,self.reviewed_by)):
            raise ValueError('style declarations need a source, scope and reviewer')
        return self

class ModelPreference(StrictModel):
    """A model property (normalised) and whether the researcher requires or prefers it."""
    property: str = Field(min_length=1,max_length=200)
    mode: Literal['required','preferred'] = 'required'
    _property = field_validator('property')(normalize_property)

def parse_preference(text: str, mode: str | None=None) -> ModelPreference:
    """Retain a general property phrase and its explicit required/preferred mode.

    Args:
        text: One property statement; compound statements remain opaque phrases.
        mode: Explicit policy, overriding a leading preference/requirement verb.
    """
    value=text.strip().lower()
    inferred='preferred' if re.match(r'^(prefer|preferred|ideally)\b',value) else 'required'
    value=re.sub(r'^(?:should\s+(?:be|have)|must\s+(?:be|have)|require|prefer|preferred|ideally|with|only)\s+', '',value)
    return ModelPreference(property=normalize_property(value),mode=mode or inferred)

def properties(candidate) -> dict[str,str]:
    """Resolve numerical inelasticity and arbitrary reviewed model declarations."""
    result={'inelastic':'yes' if candidate.splitting_kev!=0 else 'no'}
    for declaration in candidate.style_declarations:
        key=declaration.property
        if key in result and result[key]!=declaration.state:
            raise ValueError('contradictory model property: '+key)
        result[key]=declaration.state
    return result

def select(candidates, preferences: list[ModelPreference]):
    """Filter requirements; preferences only annotate the surviving ranking."""
    if not preferences:
        return candidates,{},{}
    if len({p.property for p in preferences})!=len(preferences):
        raise ValueError('choose one required/preferred policy per model property')
    kept=[]
    excluded={}
    matches={}
    for c in candidates:
        values=properties(c)
        failed=[p.property+': '+values.get(p.property,'unknown') for p in preferences
                if p.mode=='required' and values.get(p.property,'unknown')!='yes']
        if failed:
            excluded[c.label]='; '.join(failed)
            continue
        kept.append(c)
        matches[c.label]={p.property:values.get(p.property,'unknown') for p in preferences}
    if preferences and not kept:
        raise ValueError('no candidates establish the required model properties; add a compatible reviewed personal model or relax the requirement')
    return kept,excluded,matches
