"""Field contents used across the model-building tests."""

from adroit.core.model_spec import Charges, FieldRole, ModelField, ModelSpec


def field(name: str, spin: float, role: FieldRole = FieldRole.dark_matter, **kw) -> ModelField:
    charges = kw.pop("charges", {})
    return ModelField(name=name, role=role, spin=spin, charges=Charges(**charges), **kw)


def model(*fields: ModelField, name: str = "m") -> ModelSpec:
    return ModelSpec(name=name, phase="unbroken", fields=list(fields))
