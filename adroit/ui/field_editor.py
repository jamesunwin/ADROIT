"""The fields form on the page (``field_form`` holds its rules): one row per field, "Add a field", and "Edit as
YAML", which shows the same model as text and reads it back."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from adroit.ui import field_form as ff
from adroit.ui.style import FIELD

LEGEND = ("Hypercharge Y with Q = T₃ + Y (the Higgs doublet's is ½); fractions such as 1/6 are fine. Dark parity is "
          "−1 for the stabilised dark sector. Standard Model fields are added by ADROIT where a term needs them; list "
          "one only to name a flavour of your own. New U(1) charges: name=charge, e.g. D=1.")


def _compact(element, width: str):
    """An input sized for a row of the table, not the page's default field width."""
    return element.classes(remove=FIELD).classes(width).props("dense")


def _row(row: dict, remove: Callable[[], None]) -> None:
    fermion, scalar = (lambda s: s == 0.5), (lambda s: s == 0.0)
    with ui.card().classes("w-full p-2"):
        with ui.row().classes("items-end gap-2 w-full flex-wrap"):
            _compact(ui.input("name"), "w-28").bind_value(row, "name")
            _compact(ui.select(ff.ROLES, label="role"), "w-44").bind_value(row, "role")
            _compact(ui.select(ff.SPINS, label="spin"), "w-32").bind_value(row, "spin")
            ui.checkbox("real or Majorana").bind_value(row, "self_conjugate") \
                .tooltip("a real scalar or vector, or a Majorana fermion: its own antiparticle")
            _compact(ui.select(ff.CHIRALITY, label="chirality"), "w-48").bind_value(row, "chirality") \
                .bind_visibility_from(row, "spin", backward=fermion)
            _compact(ui.number("generations", min=1, max=3, step=1, format="%d"), "w-24") \
                .bind_value(row, "generations")
            _compact(ui.select(ff.COLOUR, label="colour SU(3)"), "w-32").bind_value(row, "su3")
            _compact(ui.select(ff.ISOSPIN, label="SU(2)"), "w-32").bind_value(row, "su2")
            _compact(ui.input("hypercharge Y"), "w-28").bind_value(row, "hypercharge")
            _compact(ui.select(ff.PARITY, label="dark parity"), "w-40").bind_value(row, "dark_parity")
            _compact(ui.number("mass (GeV)"), "w-28").bind_value(row, "mass_gev")
            _compact(ui.number("vev (GeV)"), "w-28").bind_value(row, "vev_gev") \
                .bind_visibility_from(row, "spin", backward=scalar)
            _compact(ui.input("new U(1) charges"), "w-36").bind_value(row, "extra")
            ui.button(icon="delete", on_click=remove).props("flat dense").tooltip("remove this field")


def editor(initial: str = ff.EXAMPLE) -> Callable[[], str | None]:
    """The form, filled from ``initial`` (YAML). Returns a function giving the model's YAML, or None (with the
    problems shown) when it is not ready."""
    name, rows = ff.from_yaml(initial)
    state = {"name": name, "rows": rows, "extra": ff.extras(initial)}
    with ui.row().classes("items-end gap-4"):
        ui.input("model name").bind_value(state, "name")
        switch = ui.switch("Edit as YAML").mark("yaml_switch")
    ui.label(LEGEND).classes("text-sm text-gray-600 max-w-4xl")
    message = ui.label().classes("text-sm text-red-700 whitespace-pre-line")
    text = ui.textarea().classes("w-full font-mono").props("rows=12")
    text.set_visibility(False)

    @ui.refreshable
    def table() -> None:
        for row in state["rows"]:
            _row(row, lambda row=row: (state.update(rows=[r for r in state["rows"] if r is not row]),
                                       table.refresh()))
        ui.button("Add a field", icon="add", on_click=lambda: (state["rows"].append(ff.blank_row()),
                                                                table.refresh())).props("flat no-caps")

    with ui.column().classes("w-full gap-2") as form:
        table()

    def toggle(event) -> None:
        if state.get("reverting"):
            return
        message.text = ""
        try:
            if event.value:
                text.value = ff.to_yaml(state["name"], state["rows"], state["extra"])
            else:
                state["name"], state["rows"] = ff.from_yaml(text.value)
                state["extra"] = ff.extras(text.value)
                table.refresh()
        except ValueError as error:
            message.text = str(error)
            state["reverting"] = True                      # stay where the mistake can be corrected, text kept
            switch.value = not event.value
            state["reverting"] = False
            return
        form.set_visibility(not event.value)
        text.set_visibility(event.value)

    switch.on_value_change(toggle)

    def current() -> str | None:
        try:
            source = text.value if switch.value else ff.to_yaml(state["name"], state["rows"], state["extra"])
            found = ff.problems(ff.spec_data(*ff.from_yaml(source), ff.extras(source)))
        except ValueError as error:
            found = [str(error)]
        message.text = "\n".join(found)
        if found:
            ui.notify("The model is not ready: see the list above the fields")
            return None
        return source

    return current
