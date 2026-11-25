"""Finding and fetching external items, with the network replaced by a stub."""

from __future__ import annotations

import pytest

from adroit.external import fetch
from adroit.external.manifest import ExternalItem, Manifest, Obtain


class _Response:
    def __init__(self, status: int, content: bytes = b"") -> None:
        self.status_code, self.content = status, content

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _manifest() -> Manifest:
    item = ExternalItem(name="release", purpose="p", obtain=Obtain.download, source="s",
                        folder="release",
                        files=["https://arxiv.org/src/1/anc/data/a.txt", "https://x.org/b.txt"])
    return Manifest(data=[item])


def test_where_items_live(tmp_path, monkeypatch) -> None:
    """With the default data folder, whatever the environment says (the combined audit's V1-05, 2026-10-24: run with
    ``ADROIT_DATA_DIR`` set, this test expected the checkout's manual folder, which the override rightly moves;
    ``test_manual_items_follow_the_data_folder`` checks the override)."""
    from adroit.core import config
    settings = config.get_settings().model_copy(update={"data_dir": fetch.PROJECT_ROOT / "data"})
    monkeypatch.setattr(fetch, "get_settings", lambda: settings)
    item = _manifest().data[0]
    assert fetch.folder_of(item, tmp_path) == tmp_path / "release"
    manual = ExternalItem(name="m", purpose="p", obtain=Obtain.manual, source="s",
                          manual_steps="download it", folder="m")
    assert fetch.folder_of(manual, tmp_path) == fetch.MANUAL_DIR / "m"
    assert fetch.local_name("https://arxiv.org/src/1/anc/data/a.txt") == "data/a.txt"
    assert fetch.local_name("https://x.org/b.txt") == "b.txt"


def test_a_download_is_fetched_once_and_retried_politely(tmp_path, monkeypatch) -> None:
    calls = []
    answers = iter([_Response(406), _Response(200, b"A"), _Response(200, b"B")])

    def fake_get(url, headers, timeout):
        calls.append(url)
        return next(answers)

    monkeypatch.setattr(fetch, "_session", lambda: type("S", (), {"get": staticmethod(fake_get)})())
    monkeypatch.setattr(fetch, "PAUSE_S", 0.0)
    manifest = _manifest()
    assert fetch.locate("release", manifest, tmp_path) is None
    folder = fetch.fetch("release", manifest, tmp_path)
    assert (folder / "data" / "a.txt").read_bytes() == b"A" and (folder / "b.txt").read_bytes() == b"B"
    assert len(calls) == 3                                   # one refusal, then two files
    assert fetch.locate("release", manifest, tmp_path) == folder
    fetch.fetch("release", manifest, tmp_path)               # present: nothing more fetched
    assert len(calls) == 3


def test_a_named_fragment_and_an_items_own_user_agent(tmp_path, monkeypatch) -> None:
    """HEPData's tables all end in /csv: a fragment names each file; its front end needs its own agent."""
    seen = []

    def fake_get(url, headers, timeout):
        seen.append((url, headers["User-Agent"]))
        return _Response(200, url.encode())
    monkeypatch.setattr(fetch, "_session", lambda: type("S", (), {"get": staticmethod(fake_get)})())
    monkeypatch.setattr(fetch, "PAUSE_S", 0.0)
    item = ExternalItem(name="h", purpose="p", obtain=Obtain.download, source="s", folder="h", user_agent="curl/8.7.1",
                        files=["https://x.org/table/A%20b/2/csv#a.csv", "https://x.org/table/C/2/csv#c.csv"])
    folder = fetch.fetch("h", Manifest(data=[item]), tmp_path)
    assert sorted(p.name for p in folder.iterdir()) == ["a.csv", "c.csv"]
    assert [u for u, _ in seen] == ["https://x.org/table/A%20b/2/csv", "https://x.org/table/C/2/csv"]
    assert {a for _, a in seen} == {"curl/8.7.1"}
    assert fetch.local_name("https://x.org/t/csv#name.csv") == "name.csv"


def test_items_the_system_cannot_fetch_say_so(tmp_path) -> None:
    manifest = Manifest(tools=[
        ExternalItem(name="p", purpose="p", obtain=Obtain.pip, source="nestpy"),
        ExternalItem(name="m", purpose="p", obtain=Obtain.manual, source="s",
                     manual_steps="open the page and download")])
    with pytest.raises(ValueError, match="install nestpy"):
        fetch.fetch("p", manifest, tmp_path)
    with pytest.raises(ValueError, match="open the page"):
        fetch.fetch("m", manifest, tmp_path)


def test_downloads_verify_against_the_systems_trust_store() -> None:
    """A server that omits its intermediate certificate verifies where the operating system can complete the chain
    (Harvard's f_eff host failed with certifi's bundle in the clean-machine install test, 2026-10-12)."""
    import truststore
    adapter = fetch._session().get_adapter("https://example.org")
    assert isinstance(adapter, fetch._SystemTrust)
    assert isinstance(adapter.poolmanager.connection_pool_kw["ssl_context"], truststore.SSLContext)


def test_manual_items_follow_the_data_folder(tmp_path, monkeypatch) -> None:
    """The release audit's PR23-01 (2026-10-23): ``ADROIT_DATA_DIR`` moved every data folder but the manual external
    inputs, which stayed in the checkout's data/external/manual, so a manual release put in the configured folder was
    reported missing. They follow it, setup names the folder, and an item still only in the checkout's folder is found
    there."""
    from adroit.core import config
    settings = config.get_settings().model_copy(update={"data_dir": tmp_path / "data"})
    monkeypatch.setattr(fetch, "get_settings", lambda: settings)
    monkeypatch.setattr(fetch, "MANUAL_DIR", tmp_path / "checkout" / "manual")
    manual = ExternalItem(name="m", purpose="p", obtain=Obtain.manual, source="s", manual_steps="download it",
                          folder="m")
    old = ExternalItem(name="old", purpose="p", obtain=Obtain.manual, source="s", manual_steps="download it",
                       folder="old")
    manifest = Manifest(data=[manual, old])
    configured = tmp_path / "data" / "external" / "manual" / "m"
    assert fetch.folder_of(manual) == configured and fetch.locate("m", manifest) is None
    configured.mkdir(parents=True)
    (configured / "release.txt").write_text("x")
    assert fetch.locate("m", manifest) == configured
    assert str(configured) in fetch.how_to_get("m", manifest)
    (tmp_path / "checkout" / "manual" / "old").mkdir(parents=True)
    (tmp_path / "checkout" / "manual" / "old" / "release.txt").write_text("x")
    assert fetch.locate("old", manifest) == tmp_path / "checkout" / "manual" / "old"
