"""The auditor's OL-02 (audit/uo06_offloop_audit.md, of a933a40): ``tree.Model.find`` had published its vertex index with its
final size before filling it, so a concurrent reader (the workbench's setup checks run in threads and share one cached
model) saw an empty index as complete and cached "no vertex", and a valid model was refused ("no annihilation channel").
The index is now built locally and published whole."""
from adroit.constraints import tree


class Reentrant(tree.Vertex):
    """A vertex whose legs, read while the index is being built, let another reader call ``find`` at that moment."""

    def __init__(self, model, probe, *args, **kwargs):
        super().__init__(*args, **kwargs)
        object.__setattr__(self, "_model", model)
        object.__setattr__(self, "_probe", probe)
        object.__setattr__(self, "_seen", [])

    def __getattribute__(self, name):
        value = object.__getattribute__(self, name)
        if name == "legs" and not object.__getattribute__(self, "_seen"):
            seen = object.__getattribute__(self, "_seen")
            seen.append(None)                                        # once: the nested reader reads these legs too
            seen[0] = object.__getattribute__(self, "_model").find(object.__getattribute__(self, "_probe"))
        return value


def test_a_reader_during_the_index_build_never_sees_an_empty_index_as_complete() -> None:
    model = tree.Model(particles={})
    target = tree.Vertex("FFS", ("chi~", "chi", "S"), c=1.0)
    model.vertices.append(target)
    model.find(["chi~", "chi", "S"])                                 # an index built for one vertex
    late = Reentrant(model, ["chi~", "chi", "S"], "SSS", ("S", "S", "S"), c=1.0)
    model.vertices.insert(0, late)                                   # a vertex added first: the index is rebuilt
    found = model.find(["S", "S", "S"])
    (during,) = object.__getattribute__(late, "_seen")
    assert [v for v, _ in during] == [target]                       # the concurrent reader found the real vertex
    assert [v for v, _ in model.find(["chi~", "chi", "S"])] == [target]   # and cached nothing false
    assert [v for v, _ in found] == [late]
