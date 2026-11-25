"""Resolve installed native runtime aliases without guessing library locations."""
from adroit.statistics import cache_identity as identity


def test_macos_loader_path_rpath_resolution_and_content_change(tmp_path,monkeypatch):
    binary=tmp_path/'libparent.dylib'
    child=tmp_path/'libchild.dylib'
    binary.write_text('parent')
    child.write_text('child')
    monkeypatch.setattr(identity.sys,'platform','darwin')
    def output(command,**kwargs):
        if command[1]=='-L':
            return f'{binary}:\n\t@rpath/libchild.dylib (compatibility version 1)\n\t/usr/lib/libSystem.B.dylib (version 1)\n'
        return 'Load command 1\n cmd LC_RPATH\n cmdsize 32\n path @loader_path (offset 12)\n'
    monkeypatch.setattr(identity.subprocess,'check_output',output)
    metadata=binary.stat()
    paths=identity._libraries(str(binary),metadata.st_size,metadata.st_mtime_ns,metadata.st_ctime_ns,str(tmp_path))
    assert paths==(child,)
    before=identity.tree_identity(child)
    child.write_text('updated')
    assert identity.tree_identity(child)!=before
