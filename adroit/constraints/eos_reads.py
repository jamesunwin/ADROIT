"""The equation-of-state tables a calculation reads, each in the version it read (the auditor's CT recheck, CU-02,
2026-10-28): a thermal claim is bound to the tables as its calculation read them, and the files as they are now are
read only to judge whether it is stale. The certificate had hashed the files when it was made, after the calculation,
so a table changed in between was bound as if it had been used.

A producer runs inside ``reading`` (``producer``). Within it, ``relic`` notes each table it reads: the prerequisite's
check of every table (``relic.eos_unavailable``: the sha256 of the bytes read, "" where missing or unreadable), and
each table used (``relic.eos_table``: read once, its hash checked and its values parsed from the same bytes, so the
published hash). A table used keeps that hash for the rest of the block: the process holds the published table it
validated, whatever a later check finds on the disk. A table only checked keeps its first reading in the block, which
every claim decided in the block came after: a later reading never binds a claim decided before it. ``held`` gives
what a certificate made inside the block binds.
"""
from __future__ import annotations

import functools
from contextlib import contextmanager
from contextvars import ContextVar

_BLOCKS: ContextVar[tuple[tuple[dict[str, str], set[str]], ...]] = ContextVar("adroit_eos_reads", default=())


@contextmanager
def reading():
    """The tables read inside the block, each with the sha256 read (``noted``). Blocks nest: a read is noted in each
    block in force."""
    found: dict[str, str] = {}
    token = _BLOCKS.set((*_BLOCKS.get(), (found, set())))
    try:
        yield found
    finally:
        _BLOCKS.reset(token)


def producer(function):
    """``function`` run inside ``reading``: a producer whose claims rest on the tables."""
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        with reading():
            return function(*args, **kwargs)
    return wrapped


def noted(name: str, sha256: str, used: bool = False) -> None:
    """A read of the table ``name`` in the version ``sha256``, in every block in force: its first reading there, or,
    ``used``, the table the calculation holds, kept for the rest of the block."""
    for found, kept in _BLOCKS.get():
        if name in kept:
            continue
        if used:
            found[name] = sha256
            kept.add(name)
        else:
            found.setdefault(name, sha256)


def held() -> dict[str, str] | None:
    """The tables read in the blocks in force (an inner block's reading first), or None outside every block."""
    blocks = _BLOCKS.get()
    if not blocks:
        return None
    out: dict[str, str] = {}
    for found, _ in blocks:
        out.update(found)
    return out
