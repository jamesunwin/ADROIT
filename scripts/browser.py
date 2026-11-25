"""The release acceptance layer's browser: the installed Chrome, driven through its own DevTools protocol over a
WebSocket written here with the standard library alone (the consolidation plan's M4 and the owner's direction D-5,
2026-10-25): no driver to download, no new dependency. Only 127.0.0.1 is contacted: every local request here bypasses any proxy
setting, and Chrome itself is fenced (``Chrome.start``: a proxy on a closed local port for everything but 127.0.0.1,
and every host name but 127.0.0.1 resolved to nothing).

A slow machine is waited for, never mistaken for a failure (the auditor's consolidation audit, 2026-10-25, saw three
journeys time out where every journey took eight times as long as here): each DevTools call has its own deadline
(``CALL_TIMEOUT``) instead of a 30-second socket timeout that ended the journey, a page counts as loaded only once its
NiceGUI client has connected to the server (``Page.ready``: before that, a click or a typed value can be lost, and a
server that does not answer within NiceGUI's 20 seconds makes the client reload the page), a choice in a select is
checked to have taken, and each journey has a tab of its own.

    with Chrome.start() as browser:
        page = browser.page()
        page.goto("http://127.0.0.1:18790/studies")
        page.wait_text("Studies")
"""
from __future__ import annotations

import base64
import json
import math
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request
from collections import deque
from pathlib import Path
from urllib.parse import urlparse

MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CALL_TIMEOUT = 180.0        # one DevTools call (a navigation on a slow first render included)
WAIT_TIMEOUT = 120.0        # a condition on a page
SEND_TIMEOUT = 60.0         # one frame sent whole (a read polls each second; a send never stops part way)
REATTACH_LIMIT = 3          # the attempts to make a connection to one tab again while it is waited on (``Page.reattach``)
LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # this machine, never through a proxy
# Each page's NiceGUI connection, said in its console as it happens: why a page reloads is in the console NiceGUI
# writes ("reloading because …"), and why its connection dropped is here (the auditor's CR recheck, 2026-10-27: a form found
# reloaded and a click that launched nothing were not diagnosed). It only logs.
SOCKET_WATCH = """(() => { const began = Date.now();
  const watch = () => {
    if (!window.socket) { if (Date.now() - began < 300000) setTimeout(watch, 200); return; }
    window.socket.on('connect', () => console.log('harness: connected'));
    window.socket.on('disconnect', why => console.log('harness: disconnected: ' + why));
    window.socket.io.on('reconnect_attempt', n => console.log('harness: reconnecting, attempt ' + n)); };
  watch(); })()"""


def local_get(url: str, timeout: float = 30.0, method: str = "GET") -> bytes:
    """A request to this machine (127.0.0.1 only), bypassing any proxy setting."""
    if urlparse(url).hostname not in ("127.0.0.1", "localhost"):
        raise ValueError("the browser layer contacts this machine only")
    with LOCAL.open(urllib.request.Request(url, method=method), timeout=timeout) as response:
        return response.read()


def closed_port() -> int:
    """A port of this machine where nothing listens (Chrome's proxy: a request to it fails at once)."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# what headless Chrome logs on macOS at every display it cannot link, whatever happens: left out of the ends of its log
# shown (the log keeps it)
CHROME_NOISE = ("CVDisplayLinkCreateWithCGDisplay failed",)


def chrome_tail(log: Path | None, lines: int) -> list[str]:
    """The last ``lines`` lines of Chrome's own log (``Chrome.start``) but its noise (``CHROME_NOISE``); none where it
    has none."""
    try:
        found = log.read_text(errors="replace").splitlines() if log else []
    except OSError:
        return []
    return [line for line in found if line.strip() and not any(n in line for n in CHROME_NOISE)][-lines:]


def chrome_said(log: Path | None, lines: int = 8) -> str:
    """The end of Chrome's own log, as a clause: "" where there is none."""
    tail = chrome_tail(log, lines)
    return f"; Chrome's log ended: {' | '.join(tail)[:1200]}" if tail else ""


def find_chrome() -> str:
    """The Chrome to drive: ``ADROIT_CHROME``, this Mac's installed Chrome, or one on the PATH; "" if none."""
    for candidate in (os.environ.get("ADROIT_CHROME", ""), MAC_CHROME):
        if candidate and Path(candidate).is_file():
            return candidate
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if found := shutil.which(name):
            return found
    return ""


def chrome_version(path: str) -> str:
    try:
        return subprocess.run([path, "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


class WebSocket:
    """A minimal RFC 6455 client: text frames, masked as a client must, ping answered, close honoured."""

    def __init__(self, url: str, timeout: float = 30.0) -> None:
        parts = urlparse(url)
        if parts.hostname not in ("127.0.0.1", "localhost"):
            raise ValueError("the browser layer contacts this machine only")
        self.sock = socket.create_connection((parts.hostname, parts.port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        path = parts.path + (f"?{parts.query}" if parts.query else "")
        self.sock.sendall((f"GET {path} HTTP/1.1\r\nHost: {parts.hostname}:{parts.port}\r\nUpgrade: websocket\r\n"
                           f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
                          .encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("the browser closed the connection during the handshake")
            head += chunk
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise ConnectionError(f"no WebSocket upgrade: {head[:120]!r}")
        self.buffer = head.split(b"\r\n\r\n", 1)[1]
        self.sock.settimeout(1.0)                 # reads poll; each caller's own deadline decides (``receive``)
        self.deadline = math.inf

    def send(self, text: str) -> None:
        self._frame(0x1, text.encode())

    def _frame(self, opcode: int, payload: bytes) -> None:
        """One frame, sent whole: under its own timeout, not the reads' one-second poll, which could have stopped
        a send part way through a frame, and Chrome then reads the rest of the stream as nonsense (the auditor's DP recheck,
        2026-11-09: a connection Chrome closed was not diagnosed; this was one way it could close)."""
        mask = os.urandom(4)
        n = len(payload)
        header = bytes([0x80 | opcode])
        header += (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack(">H", n) if n < 65536
                   else bytes([0x80 | 127]) + struct.pack(">Q", n))
        self.sock.settimeout(SEND_TIMEOUT)
        try:
            self.sock.sendall(header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))
        finally:
            self.sock.settimeout(1.0)

    def _read(self, n: int) -> bytes:
        while len(self.buffer) < n:
            try:
                chunk = self.sock.recv(65536)
            except socket.timeout:
                if time.monotonic() > self.deadline:
                    raise TimeoutError("no message from Chrome before the deadline") from None
                continue
            if not chunk:
                raise ConnectionError("the browser closed the connection")
            self.buffer += chunk
        out, self.buffer = self.buffer[:n], self.buffer[n:]
        return out

    def receive(self, deadline: float = math.inf) -> str:
        """The next text message (fragments joined; pings answered), waiting until ``deadline`` (monotonic). A
        deadline reached part way through a message keeps what was read of it, to be read whole next time, so that the
        stream is never read from the middle of a frame."""
        self.deadline = deadline
        taken: list[bytes] = []
        try:
            return self._message(taken)
        except TimeoutError:
            self.buffer = b"".join(taken) + self.buffer
            raise

    def _message(self, taken: list[bytes]) -> str:
        def read(n: int) -> bytes:
            taken.append(self._read(n))
            return taken[-1]
        message = b""
        while True:
            first, second = read(2)
            opcode, n = first & 0x0F, second & 0x7F
            if n == 126:
                n = struct.unpack(">H", read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", read(8))[0]
            mask = read(4) if second & 0x80 else b""
            payload = read(n)
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if opcode == 0x9:
                self._frame(0xA, payload)
                continue
            if opcode == 0x8:
                raise ConnectionError("the browser closed the page")
            message += payload
            if first & 0x80:
                return message.decode()

    def close(self) -> None:
        try:
            self._frame(0x8, b"")
        except OSError:
            pass
        self.sock.close()


class Page:
    """One browser tab: navigate, evaluate script, read its text, click, type, wait."""

    def __init__(self, ws: WebSocket, target: str = "", port: int = 0, log: Path | None = None) -> None:
        self.ws, self.next_id, self.target, self.port, self.log = ws, 0, target, port, log
        self.console: deque[str] = deque(maxlen=300)      # the page's console messages, as they arrived
        self.reattached: list[str] = []                   # each attempt to make its connection again, said (``reattach``)
        self.made_again: list[str] = []                   # those of them that made it again

    def call(self, method: str, timeout: float = CALL_TIMEOUT, **params) -> dict:
        """One DevTools call and its answer, waited for until ``timeout`` (events in between are passed over, the
        page's console messages kept: ``console``)."""
        self.next_id += 1
        mine = self.next_id
        self.ws.send(json.dumps({"id": mine, "method": method, "params": params}))
        deadline = time.monotonic() + timeout
        while True:
            try:
                message = json.loads(self.ws.receive(deadline))
            except TimeoutError:
                raise TimeoutError(f"Chrome did not answer {method} within {timeout:.0f} s (on a slow machine a page "
                                   "may still be rendering; nothing else is known)") from None
            if message.get("method") == "Runtime.consoleAPICalled":
                self._console(message.get("params", {}))
            if message.get("id") == mine:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get("result", {})

    def _console(self, params: dict) -> None:
        words = " ".join(str(a.get("value", a.get("description", ""))) for a in params.get("args", []))
        self.console.append(f"{time.strftime('%H:%M:%S')} {params.get('type', 'log')}: {words[:400]}")

    def evaluate(self, script: str):
        found = self.call("Runtime.evaluate", expression=script, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in found:
            raise RuntimeError(f"script failed: {found['exceptionDetails'].get('text')}: {script[:120]}")
        return found.get("result", {}).get("value")

    def goto(self, url: str, ready: bool = True, error_ok: bool = False, attempts: int = 3) -> dict:
        """Navigate and wait for the page: loaded at ``url``'s path and, for the workbench's pages, its client
        connected (``ready``). A navigation aborted or overtaken (a page whose server restarted reloads itself when
        its client reconnects) is tried again. A failed one raises, unless ``error_ok`` (then its result, with
        "errorText", is returned)."""
        want = urlparse(url).path or "/"
        for attempt in range(attempts):
            result = self.call("Page.navigate", url=url)
            if result.get("errorText"):
                if error_ok:
                    return result
                if "ERR_ABORTED" in result["errorText"] and attempt < attempts - 1:
                    time.sleep(1)
                    continue
                raise RuntimeError(f"Chrome could not open {url}: {result['errorText']}")
            self.wait(lambda: self.evaluate("document.readyState") == "complete", "the page to load")
            if url.startswith("about:") or (urlparse(self.url()).path or "/") == want:
                if ready:
                    self.ready()
                return result
            time.sleep(1)
        raise RuntimeError(f"Chrome did not stay on {url} (it shows {self.url()})")

    def ready(self, timeout: float = WAIT_TIMEOUT) -> str:
        """Wait until the page's NiceGUI client has connected and finished its handshake with the server; its
        document id (a reload makes a new one)."""
        return self.wait(lambda: self.evaluate("window.did_handshake === true && !!window.socket && "
                                               "window.socket.connected ? window.documentId : ''"),
                         "the page's connection to the workbench", timeout)

    def document(self) -> str:
        """The page's NiceGUI document id ("" before its client starts): it changes when the page reloads."""
        try:
            return self.evaluate("window.documentId || ''") or ""
        except (RuntimeError, OSError):
            return ""

    def text(self) -> str:
        return self.evaluate("document.body ? document.body.innerText : ''") or ""

    def url(self) -> str:
        return self.evaluate("location.href") or ""

    def wait(self, condition, what: str, timeout: float = WAIT_TIMEOUT, every: float = 0.25):
        """Poll ``condition`` until it is truthy (its value returned) or ``timeout``; a call that fails or is slow
        meanwhile is retried, its error kept for the message (the first such error too, with when). A connection Chrome
        closed is made again to the same tab (``reattach``), which only observes: nothing is reloaded or done again."""
        deadline = time.monotonic() + timeout
        last, error, first = None, "", ""
        while time.monotonic() < deadline:
            try:
                last = condition()
                if last:
                    return last
            except (RuntimeError, OSError, json.JSONDecodeError) as problem:     # OSError: timeouts, connections
                error = f"{type(problem).__name__}: {problem}"
                first = first or f"{time.strftime('%H:%M:%S')} {error}"
                if isinstance(problem, ConnectionError):
                    self.reattach(problem)
            time.sleep(every)
        try:
            shown = f"{self.url()}: {self.text()[:600]!r}"
        except (RuntimeError, OSError) as problem:
            shown = f"(the page could not be read: {type(problem).__name__}: {problem})"
        raise TimeoutError(f"waited {timeout:.0f} s for {what}" + (f"; first error at {first}" if first else "")
                           + (f"; last error {error}" if error else "") + f"; the page at {shown}")

    def reattach(self, problem: Exception) -> None:
        """A new DevTools connection to this same tab, its last one closed by Chrome (``problem``): its domains enabled
        again and the console watch added again for its next documents; nothing is reloaded, clicked or typed again.
        Said in ``reattached``, with the end of Chrome's own log (the auditor's DP recheck, 2026-11-09: the connection to a
        promotion's tab broke, BrokenPipeError, while the tab lived on and showed its run complete, and the wait polled
        the dead connection until its deadline; why Chrome closed it was not known), whether it was made again or
        could not be; one made again is also kept in ``made_again``, so that an attempt that failed is never counted
        as a connection made (the auditor's DR recheck, DS-02, 2026-11-09: the gate's summary had counted three attempts to
        reach a tab no longer there as three connections made again). At most ``REATTACH_LIMIT`` attempts, each counted
        as it begins and said as what it came to once its connection is usable, its domains enabled and the watch
        added, or not: one that fails anywhere in that, its new connection then closed and the last one kept, is said as
        one that could not be made again, and none is said as made again before it is usable (the auditor's DS recheck,
        DT-02, 2026-11-10: a connection made again whose domains could not be enabled had been said nowhere, counted
        nowhere and not counted against the limit)."""
        if len(self.reattached) >= REATTACH_LIMIT or not (self.port and self.target):
            return
        lost = f"{time.strftime('%H:%M:%S')}: its DevTools connection was closed ({type(problem).__name__}: {problem})"
        said = chrome_said(self.log)
        self.reattached.append(f"{lost}, and an attempt to make it again was begun and did not end{said}")
        last, fresh = self.ws, None
        try:
            targets = json.loads(local_get(f"http://127.0.0.1:{self.port}/json/list", timeout=30))
            found = next(t for t in targets if t.get("id") == self.target)
            fresh = self.ws = WebSocket(found["webSocketDebuggerUrl"])
            self.call("Page.enable")
            self.call("Runtime.enable")
            self.call("Page.addScriptToEvaluateOnNewDocument", source=SOCKET_WATCH)
        except (OSError, ValueError, KeyError, StopIteration, RuntimeError) as failed:
            self.ws = last
            if fresh is not None:
                fresh.close()
            self.reattached[-1] = f"{lost}, and could not be made again ({type(failed).__name__}: {failed}){said}"
            return
        try:
            last.sock.close()
        except OSError:
            pass
        self.reattached[-1] = f"{lost}, and made again to the same tab: nothing reloaded or done again{said}"
        self.made_again.append(self.reattached[-1])

    def wait_text(self, words: str, timeout: float = WAIT_TIMEOUT) -> None:
        self.wait(lambda: words in self.text(), f"the words {words!r}", timeout)

    def screenshot(self, path: Path) -> None:
        """The page as a PNG at ``path`` (for a failed journey's evidence)."""
        path.write_bytes(base64.b64decode(self.call("Page.captureScreenshot", timeout=60, format="png")["data"]))

    def close(self) -> None:
        """Close the connection and the tab."""
        self.ws.close()
        if self.target and self.port:
            try:
                local_get(f"http://127.0.0.1:{self.port}/json/close/{self.target}", timeout=10)
            except OSError:
                pass

    def mouse_click(self, x: float, y: float, hold: float = 0.0) -> None:
        """A real click at (x, y) of the viewport: the browser's own input events, which every widget trusts; the
        button held down ``hold`` seconds (a person's slow click, or one delayed under load)."""
        for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
            if kind == "mouseReleased" and hold:
                time.sleep(hold)
            self.call("Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left", clickCount=1)

    def _click_found(self, finder: str, what: str, hold: float = 0.0) -> None:
        """Scroll to the element ``finder`` (a script returning it or null) and click its centre with the mouse, once
        its place has settled: measured again 0.15 s later and unmoved (cycle 5's checks, 2026-11-16: an expansion
        still opening moves what follows it, and a click measured mid-transition lands on a neighbour; Track 1's
        "1. Review scan setup", clicked just after "Advanced: axis strings" opened, ticked the coverage box above it)."""
        script = f"""(() => {{ const e = ({finder})(); if (!e) return null; e.scrollIntoView({{block: 'center'}});
                     const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }})()"""
        x, y = self.wait(lambda: self.evaluate(script), what)
        for _ in range(40):                                  # at most 6 s for a transition to end
            time.sleep(0.15)
            again = self.wait(lambda: self.evaluate(script), what)
            if abs(again[0] - x) < 0.5 and abs(again[1] - y) < 0.5:
                break
            x, y = again
        self.mouse_click(x, y, hold)

    def click_text(self, words: str, selector: str = "button, a, .q-item, [role=button], .q-tab, .q-checkbox",
                   hold: float = 0.0) -> None:
        """Click the innermost element of ``selector`` whose visible text is (or starts with) ``words`` (held down
        ``hold`` seconds)."""
        finder = f"""() => {{
            const want = {json.dumps(words)}.toLowerCase();      // innerText follows CSS: Quasar's buttons are capitals
            const all = [...document.querySelectorAll({json.dumps(selector)})].filter(e => e.offsetParent !== null);
            const text = e => e.innerText.trim().toLowerCase();
            return all.find(e => text(e) === want) || all.find(e => text(e).startsWith(want)) || null; }}"""
        self._click_found(finder, f"something to click reading {words!r}", hold)

    def type_into(self, label: str, value: str) -> None:
        """Set the input or textarea labelled ``label`` (its label, aria-label or placeholder) and tell Vue."""
        script = f"""(() => {{
            const want = {json.dumps(label)};
            const fields = [...document.querySelectorAll('.q-field')].filter(f => f.offsetParent !== null);
            let el = null;
            for (const f of fields) {{
                const l = f.querySelector('.q-field__label');
                const input = f.querySelector('input, textarea');
                if (input && ((l && l.innerText.trim() === want) || input.getAttribute('aria-label') === want
                              || input.getAttribute('placeholder') === want)) {{ el = input; break; }} }}
            if (!el) return false;
            const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
            Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, {json.dumps(value)});
            el.dispatchEvent(new Event('input', {{bubbles: true}}));
            el.dispatchEvent(new Event('change', {{bubbles: true}}));
            el.dispatchEvent(new Event('blur', {{bubbles: true}}));
            return true; }})()"""
        self.wait(lambda: self.evaluate(script), f"a field labelled {label!r}")

    def tick(self, words: str) -> None:
        """Tick the checkbox reading ``words`` (clicked only if not ticked yet; checked to have taken)."""
        state = f"""(() => {{
            const want = {json.dumps(words)}.toLowerCase();
            const box = [...document.querySelectorAll('.q-checkbox')].find(e => e.offsetParent !== null &&
                         e.innerText.trim().toLowerCase().startsWith(want));
            return box ? box.getAttribute('aria-checked') : null; }})()"""
        if self.wait(lambda: self.evaluate(state), f"a checkbox reading {words!r}") != "true":
            self.click_text(words, ".q-checkbox")
        self.wait(lambda: self.evaluate(state) == "true", f"the checkbox {words!r} to be ticked", timeout=10)

    def value_of(self, label: str) -> str:
        """What the field or select labelled ``label`` shows (a select's chosen option, a field's value)."""
        return self.evaluate(f"""(() => {{
            const want = {json.dumps(label)};
            const f = [...document.querySelectorAll('.q-field')].find(f => f.offsetParent !== null &&
                       f.querySelector('.q-field__label') && f.querySelector('.q-field__label').innerText.trim() === want);
            if (!f) return null;
            const input = f.querySelector('input, textarea');
            if (f.classList.contains('q-select')) {{
                const shown = f.querySelector('.q-field__native');
                return shown ? shown.innerText.trim() : ''; }}
            return input ? input.value : ''; }})()""") or ""

    def choose(self, label: str, option: str, attempts: int = 3) -> None:
        """Choose ``option`` in the Quasar select labelled ``label``: open it with the mouse, click the option, and
        check that the select then shows it (a click during the menu's animation can miss), trying again if not."""
        finder = f"""() => {{
            const want = {json.dumps(label)};
            const f = [...document.querySelectorAll('.q-select')].find(s => s.offsetParent !== null &&
                       s.querySelector('.q-field__label') && s.querySelector('.q-field__label').innerText.trim() === want);
            return f ? f.querySelector('.q-field__control') : null; }}"""
        for attempt in range(attempts):
            self._click_found(finder, f"the select labelled {label!r}")
            time.sleep(0.4)                                   # the menu's opening transition
            self.click_text(option, ".q-menu .q-item")
            try:
                self.wait(lambda: self.value_of(label).lower().startswith(option.lower()[:20]),
                          f"the select {label!r} to show {option!r}", timeout=10)
                return
            except TimeoutError:
                if attempt == attempts - 1:
                    raise


class Chrome:
    """A headless Chrome of its own profile in a temporary folder, its DevTools port read from the profile."""

    def __init__(self, path: str, log: Path | None = None) -> None:
        self.path, self.log = path, log
        self.profile = Path(tempfile.mkdtemp(prefix="adroit-chrome-"))
        self.proxy_port = closed_port()
        self.process: subprocess.Popen | None = None
        self.port = 0
        self.pages: list[Page] = []

    def fence(self) -> list[str]:
        """Chrome's network fence: every request but one to 127.0.0.1 goes to a proxy on a closed local port, and
        every host name but 127.0.0.1 resolves to nothing, so nothing leaves this machine."""
        return [f"--proxy-server=http://127.0.0.1:{self.proxy_port}", "--proxy-bypass-list=127.0.0.1",
                "--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE 127.0.0.1"]

    @classmethod
    def start(cls, path: str = "", env: dict | None = None, log: Path | None = None) -> "Chrome":
        """A headless Chrome; its own log (its errors) appended to ``log`` where one is named, else nowhere (the auditor's DP
        recheck, 2026-11-09: why it closed a DevTools connection had not been kept)."""
        found = path or find_chrome()
        if not found:
            raise FileNotFoundError("no Chrome on this machine (set ADROIT_CHROME to its executable)")
        browser = cls(found, log)
        if log is not None:
            log.parent.mkdir(parents=True, exist_ok=True)
        said = log.open("ab") if log is not None else subprocess.DEVNULL
        try:
            browser.process = subprocess.Popen(
                [found, "--headless=new", "--remote-debugging-port=0", "--remote-debugging-address=127.0.0.1",
                 f"--user-data-dir={browser.profile}", "--no-first-run", "--no-default-browser-check",
                 "--disable-extensions", "--disable-background-networking", "--disable-sync",
                 "--disable-component-update", "--disable-breakpad", "--window-size=1400,1000", *browser.fence(),
                 *(["--enable-logging=stderr", "--log-level=2"] if log is not None else []), "about:blank"],
                stdout=subprocess.DEVNULL, stderr=said, env=env)
        finally:
            if log is not None:
                said.close()
        marker = browser.profile / "DevToolsActivePort"
        deadline = time.monotonic() + 60
        while not (marker.exists() and marker.read_text().strip()):
            if time.monotonic() > deadline or browser.process.poll() is not None:
                browser.stop()
                raise RuntimeError("Chrome did not open its DevTools port")
            time.sleep(0.2)
        browser.port = int(marker.read_text().split()[0])
        return browser

    def page(self) -> Page:
        """A new tab of its own (a journey's: no other connection is left attached to it)."""
        target = json.loads(local_get(f"http://127.0.0.1:{self.port}/json/new?about:blank", timeout=60,
                                      method="PUT"))
        page = Page(WebSocket(target["webSocketDebuggerUrl"]), target.get("id", ""), self.port, self.log)
        page.call("Page.enable")
        page.call("Runtime.enable")
        page.call("Page.addScriptToEvaluateOnNewDocument", source=SOCKET_WATCH)
        self.pages.append(page)
        return page

    def stop(self) -> None:
        for page in self.pages:
            page.close()
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.process.kill()
        shutil.rmtree(self.profile, ignore_errors=True)

    def __enter__(self) -> "Chrome":
        return self

    def __exit__(self, *exc) -> None:
        self.stop()
