"""Contents of the numerical runtimes used by cached statistical calculations."""
from __future__ import annotations

from functools import lru_cache
import importlib.util
from pathlib import Path
import platform
import os
import re
import subprocess
import sys

from adroit.orchestrator.track1_identity import tree_identity
from adroit.core import calculation_cache


def _expand(name: str, binary: str, executable_dir: str) -> str:
    return name.replace("@loader_path", str(Path(binary).parent)).replace("@executable_path", executable_dir)


@lru_cache(maxsize=64)
def _libraries(binary: str, size: int, mtime: int, ctime: int, executable_dir: str = "") -> tuple[Path, ...]:
    """Discover linked runtimes; unsupported discovery bypasses persistent reuse."""
    if sys.platform == "darwin":
        output = subprocess.check_output(["otool", "-L", binary], text=True)
        names = [line.strip().split(" (", 1)[0] for line in output.splitlines()[1:]]
        commands = subprocess.check_output(["otool", "-l", binary], text=True) if any("@rpath" in n for n in names) else ""
        rpaths = re.findall(r"cmd LC_RPATH\s+cmdsize \d+\s+path (.*?) \(offset", commands)
        expanded = []
        for name in names:
            if name.startswith("@rpath/"):
                choices = [Path(_expand(root, binary, executable_dir))/name.removeprefix("@rpath/") for root in rpaths]
                name = str(next((path for path in choices if path.is_file()), name))
            expanded.append(_expand(name, binary, executable_dir))
        names = expanded
    elif sys.platform.startswith("linux"):
        output = subprocess.check_output(["ldd", binary], text=True)
        names = [word for word in output.split() if word.startswith("/")]
    else:
        raise RuntimeError("Native library contents cannot be tracked on this platform")
    paths = []
    for name in names:
        if Path(name).is_file():
            paths.append(Path(name))
        elif not (sys.platform == "darwin" and name.startswith(("/usr/lib/", "/System/Library/"))):
            raise RuntimeError(f"Native library contents cannot be tracked: {name}")
    return tuple(paths)


def native(binary: Path) -> dict:
    """Fingerprint the actual executable, tables/source and linked native libraries."""
    stat = binary.stat()
    if any(os.environ.get(name) for name in ("DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES",
                                            "LD_LIBRARY_PATH", "LD_PRELOAD")):
        raise RuntimeError("Overridden native library loading requires a fresh calculation")
    executable_dir = str(binary.parent.resolve())
    libraries = list(_libraries(str(binary.resolve()), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, executable_dir))
    if sys.platform == "darwin":
        for path in libraries:
            metadata = path.stat()
            for child in _libraries(str(path.resolve()), metadata.st_size, metadata.st_mtime_ns, metadata.st_ctime_ns, executable_dir):
                if child not in libraries:
                    libraries.append(child)
    return {"system": platform.platform(), "folder": str(binary.parent.resolve()),
            "backend": tree_identity(binary.parent),
            "libraries": {str(path): tree_identity(path) for path in libraries},
            "adapter": tree_identity(Path(__file__).with_name("optimum_interval.py")),
            "cache_code": tree_identity(Path(__file__)),
            "persistence": tree_identity(Path(calculation_cache.__file__))}


def python_statistics() -> dict:
    """Fingerprint NumPy/SciPy contents and the statistic implementation."""
    roots = {"statistic": Path(__file__).with_name("poisson.py"), "cache_code": Path(__file__),
             "persistence": Path(calculation_cache.__file__)}
    for name in ("numpy", "scipy"):
        spec = importlib.util.find_spec(name)
        if spec and spec.origin:
            roots[name] = Path(spec.origin).parent
            for sibling in (f"{name}.libs", f"{name}.dylibs"):
                path = Path(spec.origin).parent.parent / sibling
                if path.exists():
                    roots[sibling] = path
    return {"python": sys.version, "system": platform.platform(),
            "contents": {name: tree_identity(path) for name, path in roots.items()}}
