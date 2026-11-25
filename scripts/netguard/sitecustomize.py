"""The release browser layer's network boundary for every Python process it starts (``scripts/browser_acceptance.py``
puts this folder first on ``PYTHONPATH``, so the workbench and each run it launches import it at start-up).

A connection to any address but this machine's loopback is refused before a packet is sent: a TCP connect, a UDP
datagram (``sendto``, ``sendmsg``), resolving any name but ``localhost``, and a reverse lookup (``gethostbyaddr``,
``getnameinfo`` but for a numeric answer) of any address but the loopback's. This holds for clients that ignore the proxy variables too, since
it sits beneath them, in the socket module. A refusal raises with the words "ADROIT network guard" and, where
``ADROIT_NETWORK_GUARD_LOG`` names a file, is logged there (one JSON line each). The auditor's consolidation audit fenced its
own run this way (its ``harness/sitecustomize.py``); this is the gate's own (the owner's acceptance criteria for the
release layer, 2026-10-25).

A ``sitecustomize`` further along the path, which this one would otherwise hide (Python imports only the first),
is run before it: an outer guard of the caller's stays in force in the processes the tests start (the audit loop's
AL3-17, 2026-11-15).

Where ``ADROIT_PROCESS_LOG`` names a file, each process also appends a line there as it starts (its pid, its
parent's and its whole command line): the evidence of how many times a run's child was actually started, which the
batch journey counts (a job file alone would not show a second launch).
"""
import ipaddress
import json
import os
import socket
import time

MARK = "ADROIT network guard"
LOCAL_NAMES = {None, "", "localhost", "0.0.0.0", "::"}      # resolving these never leaves the machine


def _outer() -> None:
    """Run the first ``sitecustomize`` after this one's folder on the path, the one Python would have imported, before
    this guard takes the socket's functions: its checks are then inside this guard's, whose refusals reach this guard's
    journal first."""
    import importlib.util
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    folders = [os.path.abspath(entry or os.getcwd()) for entry in sys.path]
    for folder in folders[folders.index(here) + 1:] if here in folders else []:
        candidate = os.path.join(folder, "sitecustomize.py")
        if folder != here and os.path.isfile(candidate):
            spec = importlib.util.spec_from_file_location("adroit_outer_sitecustomize", candidate)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            return


_outer()


class NetworkGuardRefused(PermissionError):
    """A connection or a resolution outside this machine, refused."""


def _log(kind: str, target) -> None:
    path = os.environ.get("ADROIT_NETWORK_GUARD_LOG")
    if path:
        try:
            with open(path, "a") as stream:
                stream.write(json.dumps({"kind": kind, "target": str(target), "pid": os.getpid(),
                                         "time": time.time()}) + "\n")
        except OSError:
            pass


def _loopback(host) -> bool:
    if isinstance(host, bytes):
        host = host.decode()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(str(host).split("%")[0]).is_loopback
    except ValueError:
        return False


def _check(sock, address, kind: str) -> None:
    if sock.family in (socket.AF_INET, socket.AF_INET6) and isinstance(address, tuple) and not _loopback(address[0]):
        _log(kind, address[0])
        raise NetworkGuardRefused(f"{MARK}: refused a {kind} to {address[0]} (only this machine's loopback is "
                                  "permitted in the release browser layer)")


_connect, _connect_ex = socket.socket.connect, socket.socket.connect_ex
_sendto, _sendmsg = socket.socket.sendto, socket.socket.sendmsg
_getaddrinfo, _gethostbyname, _gethostbyname_ex = socket.getaddrinfo, socket.gethostbyname, socket.gethostbyname_ex
_gethostbyaddr, _getnameinfo = socket.gethostbyaddr, socket.getnameinfo


def connect(self, address):
    _check(self, address, "connection")
    return _connect(self, address)


def connect_ex(self, address):
    _check(self, address, "connection")
    return _connect_ex(self, address)


def sendto(self, data, *args):
    _check(self, args[-1], "datagram")
    return _sendto(self, data, *args)


def sendmsg(self, buffers, *args):
    if len(args) >= 3:                                   # (ancillary data, flags, address)
        _check(self, args[2], "datagram")
    return _sendmsg(self, buffers, *args)


def _resolvable(host) -> None:
    name = host.decode() if isinstance(host, bytes) else host
    if name not in LOCAL_NAMES and not _loopback(name):
        _log("resolution", name)
        raise socket.gaierror(socket.EAI_NONAME, f"{MARK}: refused to resolve {name} (only this machine is "
                                                 "permitted in the release browser layer)")


def getaddrinfo(host, *args, **kwargs):
    _resolvable(host)
    return _getaddrinfo(host, *args, **kwargs)


def gethostbyname(host):
    _resolvable(host)
    return _gethostbyname(host)


def gethostbyname_ex(host):
    _resolvable(host)
    return _gethostbyname_ex(host)


def gethostbyaddr(host):
    _resolvable(host)
    return _gethostbyaddr(host)


def getnameinfo(sockaddr, flags):
    host = sockaddr[0] if isinstance(sockaddr, tuple) and sockaddr else None
    if not flags & socket.NI_NUMERICHOST and not _loopback(host):
        _log("reverse lookup", host)
        raise socket.gaierror(socket.EAI_NONAME, f"{MARK}: refused to look up {host}'s name (only this machine is "
                                                 "permitted in the release browser layer)")
    return _getnameinfo(sockaddr, flags)


socket.socket.connect, socket.socket.connect_ex = connect, connect_ex
socket.socket.sendto, socket.socket.sendmsg = sendto, sendmsg
socket.getaddrinfo, socket.gethostbyname, socket.gethostbyname_ex = getaddrinfo, gethostbyname, gethostbyname_ex
socket.gethostbyaddr, socket.getnameinfo = gethostbyaddr, getnameinfo
socket.ADROIT_NETWORK_GUARD = MARK


def _started() -> None:
    import sys
    path = os.environ.get("ADROIT_PROCESS_LOG")
    if path:
        try:
            with open(path, "a") as stream:
                stream.write(json.dumps({"pid": os.getpid(), "ppid": os.getppid(), "time": time.time(),
                                         "argv": list(getattr(sys, "orig_argv", sys.argv))}) + "\n")
        except OSError:
            pass


_started()

if os.environ.get("ADROIT_ACCEPTANCE_MUTATION"):     # the release layer's mutation controls only
    import acceptance_mutations
    acceptance_mutations.install(os.environ["ADROIT_ACCEPTANCE_MUTATION"])
