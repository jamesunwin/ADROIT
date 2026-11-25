"""A model's fields as a form (the UI clarity plan §4, item 2): one row per field, with the YAML kept as an
export and an "Edit as YAML" switch.

The form writes the YAML the command reads (``adroit idea --fields``: a ``ModelSpec`` with a name and fields), so
both ways in give the same model. Each choice is a menu of the allowed values (spin 0, ½ or 1; colour 1, 3, 3̄ or 8;
the SU(2) multiplet), a hypercharge may be a fraction (1/6), and a mistake is reported on its row, or on its line in
the YAML, before anything runs. Keys the form does not show (a field's mass_justification, the model's stability or
assumptions) are carried through unchanged.

The YAML is validated as a ``ModelSpec`` before it becomes the form, and the form is built from the typed model, so a
valid model survives the round trip unchanged and an invalid one is reported, never rewritten (the external audit's
A04, 2026-10-16: a quoted "false" had become true, 2.9 had become 2 and a malformed field had vanished).
"""

from __future__ import annotations

from fractions import Fraction

import yaml
from pydantic import ValidationError

from adroit.core.model_spec import ModelField, ModelSpec

ROLES = {"dark_matter": "dark matter", "mediator": "mediator", "other": "other new field",
         "standard_model": "Standard Model field"}
SPINS = {0.0: "0 (scalar)", 0.5: "½ (fermion)", 1.0: "1 (vector)"}
CHIRALITY = {"": "both (Dirac or Majorana)", "L": "left-handed (Weyl)", "R": "right-handed (Weyl)"}
COLOUR = {"1": "1 (no colour)", "3": "3", "3bar": "3̄", "8": "8"}
ISOSPIN = {1: "singlet", 2: "doublet", 3: "triplet", 4: "quadruplet", 5: "quintuplet", 6: "sextet",
           7: "septuplet"}
PARITY = {-1: "odd (dark sector)", 1: "even", 0: "not stated"}
EXAMPLE = """name: singlet_fermion_with_scalar
fields:
- {name: chi, role: dark_matter, spin: 0.5, dark_parity: -1}
- {name: S, role: mediator, spin: 0, self_conjugate: true}
"""


FIELD_KEYS = {"name", "role", "spin", "self_conjugate", "chirality", "generations", "charges", "dark_parity",
              "mass_gev", "vev_gev"}
CHARGE_KEYS = {"su3", "su2", "hypercharge", "extra"}


def blank_row() -> dict:
    """A new field's row: a neutral scalar mediator."""
    return {"name": "", "role": "mediator", "spin": 0.0, "self_conjugate": False, "chirality": "", "generations": 1,
            "su3": "1", "su2": 1, "hypercharge": "0", "extra": "", "dark_parity": 1, "mass_gev": None, "vev_gev": None}


def number(text: str | float | int) -> float:
    """A charge as typed: "1/6", "-1/2", "0.5" or a number. Raises ValueError."""
    try:
        return float(Fraction(str(text).strip().replace("−", "-") or "0"))
    except (ValueError, ZeroDivisionError):
        raise ValueError(f"{text!r} is not a number or a fraction") from None


def fraction_text(value: float) -> str:
    """A charge for the form: 1/6 rather than 0.16666666666666666."""
    near = Fraction(value).limit_denominator(12)
    return str(near) if abs(float(near) - value) < 1e-9 else repr(value)


def extra_charges(text: str) -> dict[str, float]:
    """New U(1) charges typed "D=1, BL=-1/3". Raises ValueError."""
    out = {}
    for part in filter(None, (p.strip() for p in text.split(","))):
        name, sep, value = part.partition("=")
        if not sep or not name.strip():
            raise ValueError(f"{part!r}: write a new U(1)'s charge as name=charge, e.g. D=1")
        out[name.strip()] = number(value)
    return out


def _field(row: dict) -> dict:
    """One row as the YAML's field, leaving out what is at its default."""
    spin = float(row["spin"])
    field = {"name": row["name"].strip(), "role": row["role"], "spin": int(spin) if spin.is_integer() else spin}
    if row.get("self_conjugate"):
        field["self_conjugate"] = True
    if spin == 0.5 and row.get("chirality"):
        field["chirality"] = row["chirality"]
    generations = float(row.get("generations") or 1)
    if not generations.is_integer():
        raise ValueError(f"generations must be a whole number, not {row['generations']}")
    if generations != 1:
        field["generations"] = int(generations)
    charges = {}
    if row.get("su3", "1") != "1":
        charges["su3"] = row["su3"]
    if int(row.get("su2") or 1) != 1:
        charges["su2"] = int(row["su2"])
    if number(row.get("hypercharge", "0")):
        charges["hypercharge"] = number(row["hypercharge"])
    if extra_charges(row.get("extra", "")):
        charges["extra"] = extra_charges(row["extra"])
    if charges:
        field["charges"] = charges
    if row.get("dark_parity"):
        field["dark_parity"] = int(row["dark_parity"])
    for key in ("mass_gev", "vev_gev"):
        if row.get(key) not in (None, ""):
            field[key] = float(row[key])
    if row.get("more_charges"):
        field.setdefault("charges", {}).update(row["more_charges"])
    return {**field, **{k: v for k, v in (row.get("more") or {}).items() if k not in field}}


def spec_data(name: str, rows: list[dict], extra: dict | None = None) -> dict:
    """The model as the command reads it: its name, the keys the form does not show (``extra``) and its fields.
    Raises ValueError for a row that cannot be read."""
    fields = []
    for i, row in enumerate(rows, 1):
        try:
            fields.append(_field(row))
        except ValueError as error:
            raise ValueError(f"field {i} ({row.get('name') or 'unnamed'}): {error}") from None
    return {"name": name.strip(), **(extra or {}), "fields": fields}


def to_yaml(name: str, rows: list[dict], extra: dict | None = None) -> str:
    """The form as YAML, one field per line, with the model's other keys (``extra``) after its name."""
    data = spec_data(name, rows, extra)
    head = yaml.safe_dump({k: v for k, v in data.items() if k != "fields"}, allow_unicode=True, sort_keys=False)
    lines = [f"- {yaml.safe_dump(f, default_flow_style=True, allow_unicode=True, width=1000, sort_keys=False).strip()}"
             for f in data["fields"]]
    return head + "fields:\n" + "".join(line + "\n" for line in lines)


def _row(field: ModelField, raw: dict) -> dict:
    """A validated field as its row; ``raw`` (the field as written) says which keys the form does not show."""
    c = field.charges
    shown = (field.spin in SPINS, field.chirality in CHIRALITY, c.su2 in ISOSPIN, (field.dark_parity or 0) in PARITY,
             field.generations <= 3)
    if not all(shown):
        raise ValueError(f"field {field.name}: the form cannot show it (spin {field.spin:g}, SU(2) {c.su2}, "
                         f"{field.generations} generations); edit it as YAML")
    dumped, charges = field.model_dump(mode="json"), c.model_dump(mode="json")
    row = blank_row()
    row.update(name=field.name, role=field.role.value, spin=float(field.spin), self_conjugate=field.self_conjugate,
               chirality=field.chirality, generations=field.generations, su3=c.su3, su2=c.su2,
               hypercharge=fraction_text(c.hypercharge),
               extra=", ".join(f"{k}={fraction_text(v)}" for k, v in c.extra.items()),
               dark_parity=field.dark_parity or 0, mass_gev=field.mass_gev, vev_gev=field.vev_gev,
               more={k: dumped[k] for k in raw if k not in FIELD_KEYS and k in dumped},
               more_charges={k: charges[k] for k in (raw.get("charges") or {}) if k not in CHARGE_KEYS and k in charges})
    return row


def from_yaml(text: str) -> tuple[str, list[dict]]:
    """The YAML as the form: the model's name and one row per field. Raises ValueError, naming the line of a YAML
    error."""
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        where = f"line {mark.line + 1}: " if mark is not None else ""
        raise ValueError(f"{where}{getattr(error, 'problem', None) or error}") from None
    if not isinstance(data, dict) or not isinstance(data.get("fields", []), list):
        raise ValueError("the YAML is a model: a name, and fields as a list")
    found = _schema_errors(data)
    if found:
        raise ValueError("\n".join(found))
    spec = ModelSpec.model_validate({**data, "name": data.get("name") or "unnamed"})
    return str(data.get("name") or ""), [_row(f, raw) for f, raw in zip(spec.fields, data.get("fields", []))]


def extras(text: str) -> dict:
    """The model's keys other than its name and fields (stability, assumptions, couplings, …), as the YAML has them;
    {} if the YAML cannot be read."""
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return {}
    return {k: v for k, v in data.items() if k not in ("name", "fields")} if isinstance(data, dict) else {}


def _schema_errors(data: dict) -> list[str]:
    """``ModelSpec``'s objections to a model (its name aside), each on its field: "field 1 (X), charges.su2: …"."""
    names = [f.get("name") if isinstance(f, dict) else None for f in data.get("fields", [])]
    try:
        ModelSpec.model_validate({**data, "name": data.get("name") or "unnamed"})
    except ValidationError as error:
        out = []
        for e in error.errors():
            loc = e["loc"]
            if len(loc) >= 2 and loc[0] == "fields" and isinstance(loc[1], int):
                name = names[loc[1]] if loc[1] < len(names) else ""
                where = ".".join(map(str, loc[2:])) or "the entry"
                out.append(f"field {loc[1] + 1} ({name or 'unnamed'}), {where}: {e['msg']}")
            else:
                out.append(f"{'.'.join(map(str, loc)) or 'the model'}: {e['msg']}")
        return list(dict.fromkeys(out))
    return []


def problems(data: dict) -> list[str]:
    """What the command would refuse, each on its field: "field 2 (S): spin must be 0, ½ or 1"."""
    fields = [f for f in data.get("fields", []) if isinstance(f, dict)]
    out = [] if data.get("name") else ["the model needs a name"]
    names = [f.get("name") for f in fields]
    out += [f"field {i}: give it a name" for i, n in enumerate(names, 1) if not n]
    out += [f"two fields are named {n}" for n in sorted({n for n in names if n and names.count(n) > 1})]
    if not any(f.get("role") == "dark_matter" for f in fields):
        out.append("one field must be the dark matter")
    return list(dict.fromkeys(out + _schema_errors(data)))
