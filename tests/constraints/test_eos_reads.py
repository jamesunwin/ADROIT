"""``constraints.eos_reads`` (the auditor's CT recheck, CU-02, 2026-10-28): the equation-of-state tables a calculation read,
each in the version it read, which a certificate made inside it binds."""
from __future__ import annotations

from adroit.constraints import eos_reads


def test_a_table_used_keeps_its_hash_one_checked_its_first_reading_and_blocks_nest():
    """Outside every block nothing is kept. Inside, a table used keeps the hash it was validated with, whatever a later
    check reads; a table only checked keeps its first reading; a read is noted in each block in force."""
    eos_reads.noted("upper", "outside")
    assert eos_reads.held() is None
    with eos_reads.reading() as outer:
        eos_reads.noted("central", "first")
        eos_reads.noted("upper", "published", used=True)
        eos_reads.noted("upper", "changed on the disk")
        eos_reads.noted("central", "changed on the disk")
        with eos_reads.reading() as inner:
            eos_reads.noted("lower", "lower")
            eos_reads.noted("central", "changed on the disk")
            assert eos_reads.held() == {"central": "changed on the disk", "upper": "published", "lower": "lower"}
        assert inner == {"lower": "lower", "central": "changed on the disk"}
        assert outer == {"central": "first", "upper": "published", "lower": "lower"} == eos_reads.held()
    assert eos_reads.held() is None


def test_a_producer_runs_inside_its_own_block():
    @eos_reads.producer
    def produce():
        """A producer's own docstring."""
        eos_reads.noted("upper", "published", used=True)
        return eos_reads.held()
    assert produce() == {"upper": "published"} and eos_reads.held() is None
    assert produce.__name__ == "produce" and produce.__doc__ == "A producer's own docstring."
