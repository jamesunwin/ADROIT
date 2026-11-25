"""Selected, integrity-checked evidence ZIPs. Verification executes no physics."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, NamedTuple
import zipfile

from adroit.core.durable import publish_new
from adroit.core.evidence import EvidenceEnvelope, content_hash
from adroit.evidence.archive_models import (
    ArchiveArtifact, ArchiveNode, BundleManifest, ReconstructedNode, VerificationResult, safe_member,
)
from adroit.evidence.bindings import report_path
from adroit.evidence.build import request_matches
from adroit.evidence.results import copies_match, result_type, summary_matches
from adroit.evidence.runtime import file_hash

MAX_MEMBERS = 4096
MAX_TOTAL = 512_000_000
# a provider key's shape, at a word's start or right after an underscore or a JSON escape (``\n``, ``\t``, ``\u2028``),
# where the raw bytes have no word boundary (AL2-17: a key after an escaped line break had passed)
_WORD_START = rb"(?:\b|(?<=_)|(?<=\\[nrtbf\"/])|(?<=\\u[0-9A-Fa-f]{4}))sk-(?:ant-|proj-)?[A-Za-z0-9_-]{16,}\b"
# shapes distinctive enough to be found anywhere, even right after a letter, a digit or ``%20``: a provider key with
# its prefix, a long run of letters and digits after ``sk-``, and other services' tokens (the security addendum's
# AL3-28, 2026-11-16); a hyphenated word ("risk-assessment-of-everything") holds none of them
TOKENS = re.compile(rb"sk-(?:ant-|proj-)[A-Za-z0-9][A-Za-z0-9_-]{15,}"
                    rb"|sk-(?=[A-Za-z0-9]*[0-9])(?=[A-Za-z0-9]*[A-Za-z])[A-Za-z0-9]{32,}"
                    rb"|hf_[A-Za-z0-9]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}"
                    rb"|AIza[0-9A-Za-z_-]{35}|xai-[A-Za-z0-9]{30,}")
SECRET = re.compile(_WORD_START + rb"|" + TOKENS.pattern)       # every shape; folds and %-escapes: ``credential_like``
PRIVATE_KEYS = {"prompt_text", "llm_prompt_text", "response_text", "llm_response_text"}
SECRET_KEYS = {"api_key", "apikey", "api-key", "x-api-key", "x_api_key", "anthropic_api_key", "openai_api_key",
               "authorization", "access_token", "refresh_token", "id_token", "token", "bearer", "password", "secret",
               "client_secret", "private_key"}


def credential_like(data: bytes) -> bool:
    """Whether ``data`` holds a credential's shape (``SECRET``, ``TOKENS``) as it is, with its line breaks removed (a
    token a terminal or a log folded over two lines, raw or JSON-escaped), or percent-decoded (AL3-28)."""
    from urllib.parse import unquote_to_bytes
    variants = {data, re.sub(rb"[\r\n]+[ \t]*", b"", data), re.sub(rb"(?:\\[rn])+", b"", data)}
    try:
        variants.add(unquote_to_bytes(data))
    except ValueError:
        pass
    return any(SECRET.search(v) for v in variants)


def refuse_credentials(path: str, data: bytes) -> None:
    """``ValueError`` where an exported file holds a credential: its shape anywhere (``credential_like``), or a
    credential-named field of a structured file (``SECRET_KEYS``)."""
    if credential_like(data):
        raise ValueError("credential-like content cannot be exported")
    if Path(path).suffix in (".json", ".yaml", ".yml"):
        _scrub(_structured(path, data))


def _bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=1).encode()


def _put(files: dict[str, bytes], path: str, data: bytes) -> None:
    safe_member(path)
    refuse_credentials(path, data)
    if len(data) > 100_000_000 or sum(map(len, files.values())) + len(data) > MAX_TOTAL:
        raise ValueError("evidence archive size cap exceeded")
    if len(files) >= MAX_MEMBERS - 1 or path in files:
        raise ValueError("duplicate member or evidence archive member cap exceeded")
    files[path] = data


def _structured(path: str, data: bytes) -> Any:
    """A structured attachment parsed strictly, or ValueError: it is scrubbed for credentials before it is exported, so
    a file that cannot be parsed, holds more than one YAML document or repeats a key is refused, never exported
    unchecked (the batch audit's B20-04: such files had been exported with their credential keys unread)."""
    import yaml

    def pairs(items):
        keys = [k for k, _ in items]
        if len(keys) != len(set(keys)):
            raise ValueError(f"{path}: a key is repeated, so its credential check cannot be trusted")
        return dict(items)
    try:
        if path.endswith(".json"):
            return json.loads(data, object_pairs_hook=pairs)
        documents = list(yaml.load_all(data, Loader=_StrictLoader))
    except yaml.YAMLError as error:
        raise ValueError(f"{path} cannot be exported: it is not valid YAML ({error.__class__.__name__})") from None
    except ValueError as error:
        raise ValueError(f"{path} cannot be exported: {error}") from None
    if len(documents) > 1:
        raise ValueError(f"{path} cannot be exported: it holds {len(documents)} YAML documents, not one")
    return documents[0] if documents else None


def _strict_loader():
    import yaml

    class Strict(getattr(yaml, "CSafeLoader", yaml.SafeLoader)):          # libyaml's safe loader: fast
        """The safe loader, refusing a repeated explicit key in a mapping. YAML's merge key (<<) is the safe loader's
        to resolve (``flatten_mapping``), as the input loader does, and an explicit key may override a merged one, as
        YAML allows (the recheck's RB20-03, 2026-10-20: the merge key had been built as a key and the legal merge
        refused); the credential scrub reads the resolved content."""
        def construct_mapping(self, node, deep=False):
            seen = set()
            for key_node, _ in node.value:
                if key_node.tag == "tag:yaml.org,2002:merge":
                    continue
                key = self.construct_object(key_node, deep=deep)
                marker = repr(key)
                if marker in seen:
                    raise ValueError(f"the key {key!r} is repeated, so its credential check cannot be trusted")
                seen.add(marker)
            return super().construct_mapping(node, deep=deep)
    return Strict


_StrictLoader = _strict_loader()


def _selected_file(path: Path, root: Path) -> bytes:
    _selectable(path, root)
    return path.read_bytes()


def _selectable(path: Path, root: Path) -> None:
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("selected artifact is missing, linked or outside the study")
    if path.name.startswith(".env"):
        raise ValueError("credential files cannot be exported")


def _scrub(value: Any, private: bool = False) -> Any:
    if isinstance(value, dict):
        if any(str(k).lower() in SECRET_KEYS and v for k, v in value.items()):
            raise ValueError("credentials cannot be exported")
        return {k: _scrub(v, private) for k, v in value.items() if private or k not in PRIVATE_KEYS}
    if isinstance(value, list):
        return [_scrub(v, private) for v in value]
    return value


def export_run(source, destination: Path, *, include_agents: bool = False,
               include_private_prompts: bool = False,
               agent_evidence: list[Path] | None = None) -> BundleManifest:
    """Export one result or study graph without running calculations.

    Args:
        source: the selected study's version (``evidence.version.Version``); a token naming the version its page showed
            (``Token``: another version's result, evidence, report or record is refused, naming it: the auditor's CX recheck,
            CY-03; its version-identity audit, VI-03); or a result file, or a folder holding ``result.json`` (the
            version saved now, read once).
        destination: new ZIP path; existing destinations are refused, when checked and again when the ZIP is put
            there (``durable.publish_new``): one another export wrote meanwhile is left as it is.
        include_agents: include allowlisted advisory outputs, not arbitrary logs.
        include_private_prompts: keep prompt/response text in explicitly included advisory evidence.
        agent_evidence: explicitly selected advisory JSON files from separate review folders.
    """
    from adroit.evidence.exports import held
    if destination.exists():
        raise ValueError("export destination already exists")
    if include_private_prompts and not (include_agents or agent_evidence):
        raise ValueError("private prompts require explicit agent-evidence inclusion")
    version = held(source, presentation=True)
    root = version.folder.resolve()
    files: dict[str, bytes] = {}
    manifest = BundleManifest(root="n0", nodes=[], artifacts=[])
    _node(version, root, files, manifest, {}, include_agents, include_private_prompts)
    for index, attachment in enumerate(agent_evidence or []):
        if attachment.suffix != ".json":
            raise ValueError("agent evidence must be an explicitly selected JSON file")
        payload = _scrub(json.loads(_selected_file(attachment, attachment.parent)), include_private_prompts)
        _put(files, f"advisory/{index}.json", _bytes(payload))
        manifest.warnings.append(f"advisory/{index}.json: {ADVISORY}")
    manifest.local_paths = local_paths(files)
    manifest.artifacts = [ArchiveArtifact(path=n, sha256=hashlib.sha256(data).hexdigest(),
        size=len(data), role="advisory" if n.startswith("advisory/") else "result/evidence" if n.startswith("studies/") else "input/citation")
        for n, data in sorted(files.items())]
    _put(files, "manifest.json", _bytes(manifest.model_dump(mode="json")))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".zip", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(files.items()):
                archive.writestr(name, data)
        try:                # only where no file is, when it is put there (the auditor's DK recheck, DL-05)
            publish_new(temporary, destination)
        except FileExistsError:
            raise ValueError(f"export destination already exists: {destination} was written by another export while "
                             "this one was prepared; that file is left as it is, and nothing of this export was "
                             "kept") from None
    finally:
        temporary.unlink(missing_ok=True)
    return manifest


def local_paths(files: dict[str, bytes]) -> str:
    """What absolute paths of the exporting machine the bundle's JSON files carry, as a note ("" for none): the runs'
    command lines and each input's and backend's location hold them, and in a home directory they name the user and
    the folder layout (the audit loop's AL3-22, 2026-11-15: a bundle had carried 198, unannounced). A path counts where
    its first folder exists here (``/Users``, ``/private``, ``/opt``…), so a page's address (``/files/…``) does not."""
    found: set[str] = set()
    for name, data in files.items():
        if not name.endswith(".json"):
            continue
        try:
            value = json.loads(data)
        except ValueError:
            continue
        for text in _texts(value):                  # a whole value, else the words of a command line
            found.update([text] if _machine_path(text) else [word for word in text.split() if _machine_path(word)])
    if not found:
        return ""
    home = str(Path.home())
    under = sum(1 for path in found if path == home or path.startswith(home.rstrip("/") + "/"))
    return (f"this bundle carries {len(found)} absolute paths of the machine it was exported on (in the runs' command "
            f"lines and each input's and backend's location), {under} of them under its home directory ({home}): they "
            "are descriptive and never followed, but they name the user's folders; share the bundle accordingly")


def _texts(value: object):
    """Every string in a JSON value, keys included."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _texts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _texts(item)


def _machine_path(text: str) -> bool:
    parts = Path(text).parts
    return text.startswith("/") and len(parts) > 2 and Path("/", parts[1]).is_dir()


class _Other(ValueError):
    """A result found as another version than the one its reader, or the edge to it, names (``found``: its digest)."""

    def __init__(self, found: str):
        super().__init__(found)
        self.found = found


def _node(version, root: Path, files: dict[str, bytes], manifest: BundleManifest,
          seen: dict[Path, tuple[str, str]], agents: bool, private: bool, expected: str = "") -> str:
    """The node of a saved result (``version``: its result, evidence, report, figures and study record read as one
    checked transaction, ``evidence.version``), added with its graph, and its id. With ``expected`` (the digest the
    edge to it names: a promotion's, for its parent and each child), a result reached before as another version
    (``seen``: each path's node and digest) raises ``_Other`` before anything is added. Its study record is attached
    as the node's only where it describes this result (``Version.record_state``), and its links followed only where it
    is attached (the auditor's version-identity audit, VI-01, 2026-11-03: B's record had been attached beside A's result, and
    the bundle had verified)."""
    path = version.path
    resolved = path.resolve()
    if resolved in seen:
        node_id, digest = seen[resolved]
        if expected and digest != expected:
            raise _Other(digest)
        return node_id
    _selectable(path, root)
    snapshot = version.saved()
    digest = version.result_sha256
    if expected and digest != expected:
        raise _Other(digest)
    data, kind, result, evidence = snapshot.content, snapshot.workflow, snapshot.result, snapshot.envelope
    _scrub(snapshot.data)
    node_id = f"n{len(manifest.nodes)}"
    seen[resolved] = (node_id, digest)
    prefix = f"studies/{node_id}"
    node = ArchiveNode(id=node_id, workflow=kind, result_path=f"{prefix}/result.json",
                       evidence_path=f"{prefix}/evidence.json")
    manifest.nodes.append(node)
    _put(files, node.result_path, data)
    _put(files, node.evidence_path, _bytes(_scrub(evidence.model_dump(mode="json"))))
    from adroit.constraints.review_queue import SelectedEvidence,build_queue,report
    queue=build_queue([SelectedEvidence(envelope=evidence,result=result.model_dump(mode="json"))])
    _put(files,f"{prefix}/review_queue.json",_bytes(queue.model_dump(mode="json")))
    _put(files,f"{prefix}/review_queue.md",report(queue).encode())
    manifest.warnings += _attachments(version, result, prefix, root, files, agents, private, kind)
    _inputs(evidence, files, manifest)
    if kind == "promotion":
        _promoted(version, node, prefix, (root, files, manifest, seen, agents, private))
    elif version.record_state in ATTACHED and (study := version.study()) is not None:
        from adroit.evidence.version import resolve
        for child in study.children:                 # the links of the record attached, as it was read (VI-01)
            node.children.append(_node(resolve(Path(child) / "result.json", presentation=True), root, files,
                                       manifest, seen, agents, private))
    return node_id


ATTACHED = ("bound", "unbound", "unread")           # a study record attached as its node's (``_attachments``)


class Edge(NamedTuple):
    """One edge of a promotion's record (``promotion_edges``): the result file it names, the digest the record keeps
    of the version it made or was promoted from ("" in a record made before ADROIT kept them), how a warning names it,
    and whether it is a child or the parent."""
    target: Path
    expected: str
    what: str
    role: str


def promotion_edges(path: Path, result: Any) -> list[Edge]:
    """The edges of the promotion record at ``path`` (``result``, typed), its children in order and then its parent:
    what every reader of a promotion's graph follows, each to the version the record names (the export, ``_promoted``,
    and the review queue, ``review_queue.load_selected``: the auditor's version-identity audit, VI-04, 2026-11-03, the review
    queue had followed the paths alone, and a replaced child had taken the place of the one the promotion made)."""
    edges = []
    for child in result.children:
        folder = Path(child.folder)
        folder = folder if folder.is_absolute() else path.parent / folder
        edges.append(Edge(folder / "result.json", child.result_sha256, f"the study of {child.model} for {child.label}",
                          "child"))
    parent = Path(result.parent)
    edges.append(Edge((parent if parent.is_absolute() else path.parent / parent) / "result.json",
                      result.parent_sha256, "the parent result", "parent"))
    return edges


def edge_notes(edges: list[Edge]) -> list[str]:
    """What a reader of a promotion's graph says of the edges its record keeps no digest for (made before ADROIT kept
    them), so that a review and an export qualify the same edges alike."""
    notes = []
    if any(e.role == "child" and not e.expected for e in edges):
        notes.append("records no digest of its children's results (made before ADROIT recorded them); they are "
                     "followed as found, not checked against it")
    if any(e.role == "parent" and not e.expected and e.target.exists() for e in edges):
        notes.append("records no digest of the result it was promoted from (made before ADROIT recorded one); its "
                     "parent is followed as found, not checked against it")
    return notes


def unavailable(edge: Edge, found: str = "") -> str:
    """Why an edge of a promotion's record is not followed: the version now saved there (``found``, its digest) is
    another than the record names, or nothing is saved there."""
    if found:
        return (f"{edge.what} now saved is another version (SHA-256 {found}) than the one this promotion records "
                f"({edge.expected})")
    return f"{edge.what} (SHA-256 {edge.expected or 'not recorded'}) is not saved"


def unfollowed(warning: str) -> bool:
    """Whether a bundle's manifest warning is one its export gave for an edge of a promotion's graph it did not follow
    (``unavailable``'s words): what a review of the bundle cannot show the tasks of (``review_queue.load_selected``;
    the auditor's DB/VI recheck, DC-02, 2026-11-03)."""
    return "than the one this promotion records (" in warning or ") is not saved; " in warning


def _promoted(version, node: ArchiveNode, prefix: str, graph: tuple) -> None:
    """A promotion's children and its parent (``node.parent``), each attached only as the version its record names
    (``evidence.version.follow``: ``Child.result_sha256``, ``Promotion.parent_sha256``): the auditor's CY recheck, CZ-01
    (2026-11-01), B, published at the parent's path since, had been attached as the parent of a promotion made from A,
    and the bundle had verified. Another version saved there now is left out, saying so, never attached in its place,
    and so is an edge to nothing saved (VI-04: a child, as a parent already was). A record made before ADROIT recorded
    these digests is followed as found, saying so. ``graph``: ``_node``'s remaining arguments."""
    from adroit.evidence.version import follow
    root, files, manifest, seen, agents, private = graph
    for followed in follow(version, presentation=True):
        edge = followed.edge
        if followed.version is None:
            manifest.warnings.append(f"{prefix}: {followed.note}; not exported"
                                     + (" as it" if "now saved is another version" in followed.note else ""))
            continue
        try:
            found = _node(followed.version, root, files, manifest, seen, agents, private, edge.expected)
        except _Other as other:
            manifest.warnings.append(f"{prefix}: {unavailable(edge, other.found)}; not exported as it")
            continue
        if edge.role == "parent":
            node.parent = found
        node.children.append(found)
    manifest.warnings += [f"{prefix}: {note}" for note in edge_notes(version.edges())]


def _attachments(version, result: Any, prefix: str, root: Path, files: dict[str, bytes],
                 agents: bool, private: bool, kind: str = "") -> list[str]:
    """Attach the study's report, study record, plots and (an idea's) model files, of its version (``version``: read
    with its result); the warnings for the manifest. The report and the plots are attached as the result's only where
    the report is bound to it, each plot with the bytes its binding names; a report of another version, and a plot not
    the one the report was written with, are left out, saying so; a report recording no binding (written before ADROIT
    recorded one) is attached as found, with the plots as read with it, saying so (``evidence.bindings``; the auditor's CX
    recheck, CY-03, 2026-11-01). The study record likewise: attached where it describes this result, as found where
    it names none, saying so, and left out, saying so, where it describes another version or is not a study record
    (the auditor's version-identity audit, VI-01, 2026-11-03)."""
    path = version.path
    report = version.report()
    warnings = []
    name = report_path(path).name
    if report.state in ("bound", "unbound"):
        _selectable(report_path(path), root)
        _put(files, f"{prefix}/{name}", report.data)            # its bytes as read with the result
        if report.state == "unbound":
            warnings.append(f"{prefix}/{name}: records no link to its result (written before ADROIT recorded one); "
                            "exported as found")
    elif report.state == "other":
        warnings.append(f"{prefix}/{name}: of another version of the result (replaced while it was read); not exported")
    elif report.state == "interrupted":                         # the auditor's portability audit, IC-01
        warnings.append(f"{prefix}/{name}: {STUDY_WARNINGS['interrupted']}")
    elif report.state == "unreadable":
        warnings.append(f"{prefix}/{name}: cannot be read; not exported")
    state = version.record_state
    if state not in ("absent", "unreadable"):
        _selectable(path.parent / "study.json", root)
    if state in ATTACHED:
        _put(files, f"{prefix}/study.json", version.record_bytes)   # its bytes as read with the result, and checked
    if state in STUDY_WARNINGS:
        warnings.append(f"{prefix}/study.json: {STUDY_WARNINGS[state]}")
    if kind == "idea" and (path.parent / "models").is_dir():        # the typed model files Track 1 reads
        for model in sorted((path.parent / "models").glob("*.yaml")):
            data = _selected_file(model, root)                      # read once: what is checked is what is exported
            if note := _model_file_note(model, result, data):
                warnings.append(note)
            _put(files, f"{prefix}/{model.relative_to(path.parent).as_posix()}", data)
    for plot in getattr(result, "plots", []):
        safe_member(plot)
        if Path(plot).suffix.lower() not in (".png", ".svg", ".pdf"):
            raise ValueError("unsupported plot attachment")
        item = path.parent / plot
        held = version.figure_as_found(plot)
        if held is None:
            continue
        if report.state == "bound":
            data = version.figure(plot)
            if data is None:
                warnings.append(f"{prefix}/{plot}: not the figure the report of this result was written with; "
                                "not exported")
                continue
            _selectable(item, root)
            _put(files, f"{prefix}/{item.relative_to(path.parent).as_posix()}", data)
        elif report.state in ("other", "unreadable", "interrupted"):
            warnings.append(f"{prefix}/{plot}: its report is not this result's (replaced while it was read); not "
                            "exported" if report.state != "interrupted" else
                            f"{prefix}/{plot}: {STUDY_WARNINGS['interrupted']}")
        else:
            _selectable(item, root)
            _put(files, f"{prefix}/{item.relative_to(path.parent).as_posix()}", held)
    if agents:
        for name in ("assistance.json", "agents.json"):
            item = path.parent / name
            if item.exists():
                payload = _scrub(json.loads(_selected_file(item, root)), private)
                _put(files, f"{prefix}/{name}", _bytes(payload))
                warnings.append(f"{prefix}/{name}: {ADVISORY}")
    return warnings


ADVISORY = ("advisory output, attached as found: not a version of this result, and not checked against it (the owner's "
            "decision on diagnostic outputs, 2026-11-03)")


STUDY_WARNINGS = {
    "unbound": "records no link to its result (written before ADROIT recorded one); exported as found",
    "unread": "names a version of its result this bundle does not hold to check it against; exported as found",
    "other": "describes another version of the result (one was replaced since the other was written); not exported",
    "interrupted": "may be an earlier publication's: the study's last publication was interrupted while it wrote its "
                   "parts; not exported",
    "damaged": "is not a study record that can be read; not exported",
    "unreadable": "cannot be read; not exported"}


def _model_file_note(path: Path, result: Any, data: bytes | None = None) -> str:
    """Whether an idea's model file (``data``: its bytes as exported, else read here) is one the run wrote (its spec one
    of the run's selected models), a completion written beside one (not part of the result), or neither: edited after
    the run (the batch audit's B20-03)."""
    if "_completion_" in path.stem:
        return f"models/{path.name}: a computable completion written beside a model, not part of the result"
    from adroit.orchestrator.model_approval import select_model
    try:
        spec = (_structured(path.name, data if data is not None else path.read_bytes()) or {}).get("spec")
    except (ValueError, AttributeError):
        spec = None
    built = []
    for model in getattr(result, "models", []):
        try:
            built.append(select_model(model)[0].model_dump(mode="json"))
        except ValueError:
            continue
    if spec is None or spec not in built:
        return f"models/{path.name}: not a model this run built (edited after the run?); exported as found"
    return ""


def _inputs(evidence: EvidenceEnvelope, files: dict[str, bytes], manifest: BundleManifest) -> None:
    """Each input the evidence captured, exported under its captured digest where its bytes, read once, have that
    digest (the auditor's CX recheck, 2026-11-01: hashed in one read and copied in another, a file replaced between them
    would have been exported as B under A's digest); else a reference, with a warning."""
    for artifact in evidence.context.inputs:
        if artifact.role in ("package_input", "user_input", "catalog_input") and artifact.redistribution != "reference_only":
            path = Path(artifact.location)
            name = f"inputs/{artifact.role}/{artifact.sha256}/{path.name}"
            if name in files:
                continue
            data = None
            if path.is_file() and not path.is_symlink():
                try:
                    data = _selected_file(path, path.parent)
                except OSError:                     # gone between the check and the read
                    data = None
            if data is None or hashlib.sha256(data).hexdigest() != artifact.sha256:
                manifest.references.append(artifact)
                manifest.warnings.append(f"input unavailable or changed since calculation: {artifact.name}")
                continue
            _put(files, name, data)
        elif artifact not in manifest.references:
            manifest.references.append(artifact)
    for backend in evidence.context.backends:
        from adroit.core.evidence import InputArtifact
        item = InputArtifact(name=backend.name, location=backend.location, sha256=backend.sha256,
                             role="software" if backend.role == "runtime/input" else "external")
        if item not in manifest.references:
            manifest.references.append(item)


def held_bundle(path: Path) -> bytes:
    """A bundle's bytes, read once: what its verification hashes, validates and reconstructs alike (the auditor's DB/VI
    recheck, DC-06, 2026-11-03: a ZIP replaced between its hash and its reading had verified as A's archive with B's
    decisions). A file larger than the size cap is refused before it is read."""
    if Path(path).stat().st_size > MAX_TOTAL:
        raise ValueError("archive size cap exceeded")
    return Path(path).read_bytes()


def read_bundle(path: Path | bytes) -> tuple[BundleManifest, dict[str, bytes]]:
    """Validate paths, size, content and version before returning any archive data. ``path``: the bundle's file, or its
    bytes as already held (``held_bundle``)."""
    with zipfile.ZipFile(io.BytesIO(path) if isinstance(path, bytes) else path) as archive:
        infos = archive.infolist()
        names = [safe_member(info.filename) for info in infos]
        if len(names) > MAX_MEMBERS or len(set(names)) != len(names):
            raise ValueError("duplicate archive member or member cap exceeded")
        if sum(info.file_size for info in infos) > MAX_TOTAL or any(info.file_size > 100_000_000 for info in infos):
            raise ValueError("archive size cap exceeded")
        if any(stat.S_ISLNK(info.external_attr >> 16) or info.is_dir() for info in infos):
            raise ValueError("archive links/directories are not permitted")
        if "manifest.json" not in names:
            raise ValueError("missing archive manifest")
        manifest = BundleManifest.model_validate_json(archive.read("manifest.json"))
        expected = {a.path for a in manifest.artifacts}
        if len(expected) != len(manifest.artifacts) or set(names) != expected | {"manifest.json"}:
            raise ValueError("missing, duplicate or unlisted artifact")
        files = {name: archive.read(name) for name in names}
    for item in manifest.artifacts:
        data = files[item.path]
        if len(data) != item.size or hashlib.sha256(data).hexdigest() != item.sha256:
            raise ValueError(f"artifact integrity mismatch: {item.path}")
    _validate_nodes(manifest, files)
    return manifest, files


def _validate_nodes(manifest: BundleManifest, files: dict[str, bytes]) -> None:
    nodes = {n.id: n for n in manifest.nodes}
    if len(nodes) != len(manifest.nodes) or manifest.root not in nodes:
        raise ValueError("invalid/duplicate study graph identity")
    for node in manifest.nodes:
        if any(child not in nodes for child in node.children):
            raise ValueError("missing child study")
        envelope = EvidenceEnvelope.model_validate_json(files[node.evidence_path])
        result = result_type(node.workflow).model_validate_json(files[node.result_path])
        if envelope.workflow != node.workflow or envelope.result_sha256 != hashlib.sha256(files[node.result_path]).hexdigest():
            raise ValueError("evidence/result identity mismatch")
        if not summary_matches(node.workflow, envelope.summary, result):
            raise ValueError("evidence/result conclusion mismatch")
        if not copies_match(node.workflow, envelope, result):
            raise ValueError("evidence/result copy mismatch: a certificate or the engine mapping differs from the result")
        if envelope.input_sha256 != content_hash(envelope.original_inputs):
            raise ValueError("evidence input digest mismatch")
        if hasattr(result, "request") and not request_matches(envelope.original_inputs, result.request):
            raise ValueError("evidence/result request mismatch")
        if (envelope.context.origin == "captured" and envelope.context.request_sha256
                and envelope.context.request_sha256 != envelope.input_sha256):
            raise ValueError("calculation-start request identity mismatch")
        _bound_attachments(node, files)
        _bound_study(node, files)
    _promotion_edges(manifest, files)
    _graph(manifest)


def _bound_attachments(node: ArchiveNode, files: dict[str, bytes]) -> None:
    """A node's report, where it records the result it describes, describes the node's result, and each figure it
    names that the node holds has the digest it names (``evidence.bindings``; the auditor's CX recheck, CY-03, 2026-11-01:
    a bundle had verified with A's result beside B's report). A report recording none (written before) is not
    checked."""
    from adroit.evidence.bindings import binding
    prefix = node.result_path.rsplit("/", 1)[0] + "/"
    digest = hashlib.sha256(files[node.result_path]).hexdigest()
    for name, data in files.items():
        if not name.startswith(prefix) or "/" in name[len(prefix):] or not name.endswith(".md") \
                or name.endswith("/review_queue.md"):
            continue
        found = binding(data.decode("utf-8", errors="replace"))
        if found is None:
            continue
        if found.result_sha256 != digest:
            raise ValueError(f"report/result mismatch: {name} describes another result")
        for figure, held in found.figures.items():
            member = prefix + figure
            if member in files and hashlib.sha256(files[member]).hexdigest() != held:
                raise ValueError(f"figure/report mismatch: {member} is not the figure {name} was written with")


def _bound_study(node: ArchiveNode, files: dict[str, bytes]) -> None:
    """A node's study record, where it names the result it describes, names the node's result (a promotion's: the
    result it was promoted from, whose record sits beside it), so that a bundle attaching another publication's title
    and cost to a result does not verify (the auditor's version-identity audit, VI-01, 2026-11-03). A record naming none
    (written before), or a promotion recording no parent digest, is not checked; nor is one that names nothing a
    record could (it was never checked before, and is attached as found)."""
    member = node.result_path.rsplit("/", 1)[0] + "/study.json"
    if member not in files:
        return
    try:
        named = json.loads(files[member]).get("result_sha256", "")
    except (ValueError, AttributeError):
        return
    if node.workflow == "promotion":
        expected = result_type("promotion").model_validate_json(files[node.result_path]).parent_sha256
    else:
        expected = hashlib.sha256(files[node.result_path]).hexdigest()
    if named and expected and named != expected:
        raise ValueError(f"study record/result mismatch: {member} describes another version of its result")


def _promotion_edges(manifest: BundleManifest, files: dict[str, bytes]) -> None:
    """A promotion node's parent and children are the versions its record names (the auditor's CY recheck, CZ-01,
    2026-11-01): its parent node has the digest ``parent_sha256`` names, and, in a record naming its children's digests,
    each other linked study has one of them. A bundle whose parent node was replaced, its manifest's hashes updated,
    does not verify. Each manifest is read as its export wrote it (the auditor's CZ recheck, DA-03, 2026-11-02, and its DA
    recheck, DB-01, 2026-11-03: valid version 1 bundles of each layout had been refused). A manifest naming the parent
    (``ArchiveNode.parent``: version 2, and version 1 from CZ-01's export, 2026-11-01) is checked by that name, and in
    version 2 a parent linked without its name is refused; a version 1 manifest naming none linked it after the
    record's children (``_legacy_parent``). A record made before ADROIT recorded these digests is not checked."""
    nodes = {n.id: n for n in manifest.nodes}

    def digest(key: str) -> str:
        return hashlib.sha256(files[nodes[key].result_path]).hexdigest()
    for node in manifest.nodes:
        if node.workflow != "promotion":
            if node.parent:
                raise ValueError(f"invalid study graph: {node.id} names a parent but is not a promotion")
            continue
        record = result_type("promotion").model_validate_json(files[node.result_path])
        parent = node.parent if node.parent or manifest.schema_version >= 2 else _legacy_parent(node, record)
        if parent and parent not in node.children:
            raise ValueError(f"invalid study graph: {node.id}'s parent is not one of its linked studies")
        if parent and record.parent_sha256 and digest(parent) != record.parent_sha256:
            raise ValueError(f"promotion/parent mismatch: {node.id}'s parent is another version than the result it was "
                             "promoted from")
        if not parent and record.parent_sha256 and any(digest(k) == record.parent_sha256 for k in node.children):
            raise ValueError(f"promotion/parent mismatch: {node.id} links the result it was promoted from without "
                             "naming it its parent")
        made = [c.result_sha256 for c in record.children]
        if record.parent_sha256 and all(made):
            for key in node.children:
                if key != parent and digest(key) not in made:
                    raise ValueError(f"promotion/child mismatch: {key} is not a study {node.id} made")


def _legacy_parent(node: ArchiveNode, record: Any) -> str:
    """The promotion parent of a version 1 manifest naming none: its export (before CZ-01, 2026-11-01) linked one study
    per child its record names, in order, then the parent where it was saved, unnamed; so the link after the
    children's, or "" where there is none (the parent was not saved). Such a manifest links no more studies than
    that."""
    if len(node.children) > len(record.children) + 1:
        raise ValueError(f"invalid study graph: {node.id} links more studies than its children and its parent")
    return node.children[-1] if len(node.children) == len(record.children) + 1 else ""


def _graph(manifest: BundleManifest) -> None:
    nodes = {n.id: n for n in manifest.nodes}
    active: set[str] = set()
    visited: set[str] = set()
    stack = [(manifest.root, False)]
    while stack:
        key, leaving = stack.pop()
        if leaving:
            active.remove(key)
            visited.add(key)
            continue
        if key in active:
            raise ValueError("cyclic study graph")
        if key in visited:
            continue
        active.add(key)
        stack.append((key, True))
        stack.extend((child, False) for child in nodes[key].children)
    if visited != nodes.keys():
        raise ValueError("unreachable study in evidence graph")


def readable(error: Exception) -> str:
    """One readable issue. A result that fails the installed schema names only its explicit refusals (for
    example a UFO parameter that is not arithmetic), not every alternative of a union."""
    from pydantic import ValidationError
    if not isinstance(error, ValidationError):
        return str(error)
    refusals = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors() if e["type"] == "value_error"]
    shown = refusals or [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors()[:3]]
    return ("a saved result does not validate under the installed schema: "
            + "; ".join(dict.fromkeys(shown)))[:2000]


def verify_bundle(path: Path, *, check_environment: bool = False) -> VerificationResult:
    """Reconstruct saved conclusions; optionally check installed reproduction inputs. The archive's digest, its checks
    and its reconstruction are of one read of its bytes (``held_bundle``; DC-06). ``OSError`` where it cannot be read."""
    try:
        data = held_bundle(path)
    except ValueError as error:
        return VerificationResult(valid=False, archive_sha256=file_hash(path), issues=[readable(error)],
                                  assurance="not internally consistent: see the issues")
    digest = hashlib.sha256(data).hexdigest()
    try:
        manifest, files = read_bundle(data)
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as error:
        return VerificationResult(valid=False, archive_sha256=digest, issues=[readable(error)],
                                  assurance="not internally consistent: see the issues")
    nodes = []
    reasons = list(manifest.warnings)
    for node in manifest.nodes:
        envelope = EvidenceEnvelope.model_validate_json(files[node.evidence_path])
        nodes.append(ReconstructedNode(id=node.id, workflow=node.workflow, evidence_identity=envelope.identity,
                     provenance=envelope.context.origin, summary=envelope.summary))
        if envelope.context.origin != "captured":
            reasons.append(f"{node.id}: {envelope.context.origin} calculation provenance")
    status = "not_checked"
    if check_environment:
        from adroit.orchestrator.track1_identity import dependencies
        from adroit.core.config import PROJECT_ROOT
        trusted = dependencies()["inputs"]
        for item in manifest.references:
            # Resolve installed dependencies by their known names, never by an
            # arbitrary filesystem path supplied inside an untrusted archive.
            if item.role in ("software", "external"):
                actual = trusted.get(item.name, {}).get("sha256", "missing")
            elif item.role == "package_input":
                target = PROJECT_ROOT / safe_member(item.name)
                actual = file_hash(target) if target.is_file() and target.resolve().is_relative_to(PROJECT_ROOT.resolve()) else "missing"
            else:
                actual = "missing"
            if not item.sha256 or item.sha256 == "missing" or actual != item.sha256:
                reasons.append(f"unavailable/incompatible reproduction input: {item.name}")
        status = "incomplete" if reasons else "available"
    return VerificationResult(valid=True, archive_sha256=digest, nodes=nodes,
                              reproduction_status=status, reproduction_reasons=list(dict.fromkeys(reasons)))
