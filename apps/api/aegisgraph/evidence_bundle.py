"""Bounded logical-file exports and exact UTF-8 SHA-256 verification.

No archives are extracted and no file paths are opened. A valid result establishes
agreement with the supplied unsigned manifest, not provenance or source truth.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import UTC, datetime

from pydantic import ValidationError

from .schema import CanonicalEvent

FORMAT_VERSION = "1"
MAX_BUNDLE_BYTES = 2 * 1024 * 1024
MAX_FILE_BYTES = 256 * 1024
MAX_FILES = 100
MAX_EVIDENCE = 80
MAX_DEPTH = 32
MAX_NODES = 100_000
LIMITATIONS = (
    "VALID means the supplied logical files match the supplied manifest's SHA-256 hashes and byte lengths.",
    "The manifest is unsigned and replaceable: replacing both content and its recorded hash cannot be detected here. Case, time, application, and projection metadata are not authenticated.",
    "Verification does not prove source telemetry truth, privileged-database integrity, authorship, or chain of custody.",
)
FIXED_PATHS = frozenset(
    {
        "incident.json",
        "timeline.json",
        "alerts.json",
        "findings.json",
        "hypotheses.json",
        "notes.json",
        "audit.json",
        "entities.json",
        "README.txt",
    }
)
_SNAPSHOT_FIELDS = {
    "incident",
    "scenario_id",
    "projection",
    "evidence",
    "alerts",
    "findings",
    "hypotheses",
    "notes",
    "audit",
    "entities",
}
_MANIFEST_FIELDS = {
    "format_version",
    "incident_id",
    "scenario_id",
    "projection",
    "generated_at",
    "evidence_ids",
    "files",
    "application",
    "limitations",
}
_ID = re.compile(r"^[A-Za-z][A-Za-z0-9-]{0,79}$")
_PATH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,119}$")
_HASH = re.compile(r"^[a-f0-9]{64}$")
_RESERVED = re.compile(r"^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", re.IGNORECASE)


class BundleInputError(ValueError):
    """Fixed safe diagnostics, without caller-controlled content or identifiers."""


def _fail(code):
    raise BundleInputError(code)


def _json_shape(value):
    """Bound nested objects before copying, encoding, or hashing them."""
    nodes = 0
    text_bytes = 0
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if depth > MAX_DEPTH or nodes > MAX_NODES:
            _fail("structure_limit_exceeded")
        if type(item) is dict:
            if len(item) * 2 + len(stack) + nodes > MAX_NODES:
                _fail("structure_limit_exceeded")
            for key, child in item.items():
                if type(key) is not str:
                    _fail("invalid_json_value")
                stack.append((key, depth + 1))
                stack.append((child, depth + 1))
        elif type(item) is list:
            if len(item) + len(stack) + nodes > MAX_NODES:
                _fail("structure_limit_exceeded")
            stack.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            if len(item) > MAX_BUNDLE_BYTES:
                _fail("bundle_bytes_exceeded")
            try:
                text_bytes += len(item.encode("utf-8"))
            except UnicodeError as exc:
                raise BundleInputError("invalid_utf8") from exc
            if text_bytes > MAX_BUNDLE_BYTES:
                _fail("bundle_bytes_exceeded")
        elif type(item) is float:
            if not math.isfinite(item):
                _fail("invalid_json_value")
        elif item is not None and type(item) not in (bool, int):
            _fail("invalid_json_value")


def _encode(value):
    _json_shape(value)
    try:
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
        raise BundleInputError("invalid_json_value") from exc
    if len(encoded) > MAX_BUNDLE_BYTES:
        _fail("bundle_bytes_exceeded")
    return encoded


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate_json_key")
        result[key] = value
    return result


def _constant(_value):
    _fail("invalid_json_value")


def _check_text_depth(text):
    """Reject deeply nested JSON before the recursive standard-library parser."""
    depth = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                _fail("structure_limit_exceeded")
        elif char in "]}":
            depth -= 1


def _load(value):
    if type(value) is dict:
        return json.loads(_encode(value), object_pairs_hook=_pairs)
    if type(value) is bytes:
        if len(value) > MAX_BUNDLE_BYTES:
            _fail("bundle_bytes_exceeded")
        try:
            value = value.decode("utf-8")
        except UnicodeError as exc:
            raise BundleInputError("invalid_utf8") from exc
    if type(value) is not str:
        _fail("invalid_container")
    try:
        if len(value.encode("utf-8")) > MAX_BUNDLE_BYTES:
            _fail("bundle_bytes_exceeded")
    except UnicodeError as exc:
        raise BundleInputError("invalid_utf8") from exc
    _check_text_depth(value)
    try:
        result = json.loads(value, object_pairs_hook=_pairs, parse_constant=_constant)
    except (ValueError, RecursionError) as exc:
        if isinstance(exc, BundleInputError):
            raise
        raise BundleInputError("invalid_json") from exc
    _json_shape(result)
    return result


def _identifier(value, prefix):
    if (
        type(value) is not str
        or not _ID.fullmatch(value)
        or not value.startswith(prefix + "-")
        or len(value) <= len(prefix) + 1
        or not value[len(prefix) + 1].isalnum()
    ):
        _fail("invalid_identifier")
    return value


def _timestamp(value):
    if type(value) is not str or len(value) > 40:
        _fail("invalid_timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timezone required")
        return parsed.astimezone(UTC)
    except (ValueError, OverflowError) as exc:
        raise BundleInputError("invalid_timestamp") from exc


def _list(value, maximum):
    if type(value) is not list or len(value) > maximum:
        _fail("collection_limit_exceeded")
    return value


def _references(value, allowed, maximum=MAX_EVIDENCE):
    rows = _list(value, maximum)
    if any(type(item) is not str for item in rows) or len(set(rows)) != len(rows):
        _fail("invalid_reference")
    if not set(rows) <= allowed:
        _fail("cross_scope_reference")


def _scoped_rows(value, incident_id, prefix, maximum):
    rows = _list(value, maximum)
    seen = set()
    for row in rows:
        if type(row) is not dict or row.get("incident_id") != incident_id:
            _fail("cross_scope_row")
        identifier = _identifier(row.get("id"), prefix)
        if identifier in seen:
            _fail("duplicate_identifier")
        seen.add(identifier)
    return seen


def _audit_references(rows, scope, evidence_ids, event_ids, finding_ids, note_ids, hypothesis_ids):
    """Check structured provenance references; never interpret arbitrary human prose."""
    references = {
        "evidence_ids": evidence_ids,
        "supporting_evidence_ids": evidence_ids,
        "contradicting_evidence_ids": evidence_ids,
        "event_ids": event_ids,
        "finding_ids": finding_ids,
        "related_finding_ids": finding_ids,
    }
    single_references = {
        "evidence_id": evidence_ids,
        "event_id": event_ids,
        "finding_id": finding_ids,
        "hypothesis_id": hypothesis_ids,
    }
    objects = {
        "incident_created": {scope},
        "status_changed": {scope},
        "severity_changed": {scope},
        "analyst_assigned": {scope},
        "ai_analysis_requested": {scope},
        "evidence_annotated": evidence_ids,
        "finding_created": finding_ids,
        "finding_reviewed": finding_ids,
        "note_created": note_ids,
    }
    for row in rows:
        action = row.get("action")
        if type(action) is not str:
            _fail("invalid_audit_action")
        if action in objects and (
            type(row.get("object_id")) is not str or row["object_id"] not in objects[action]
        ):
            _fail("cross_scope_audit_object")
        if action == "hypothesis_reviewed":
            # Revision membership is checked by the scoped database snapshot.
            # The audit preserves its real revision object, not a substituted HYP ID.
            _identifier(row.get("object_id"), "HPR")
            after = row.get("after")
            if type(after) is not dict:
                _fail("invalid_audit_revision")
            _references([after.get("hypothesis_id")], hypothesis_ids)
        stack = [row.get("before"), row.get("after")]
        while stack:
            value = stack.pop()
            if type(value) is dict:
                for key, child in value.items():
                    if key in references:
                        _references(child, references[key])
                    elif key in single_references:
                        _references([child], single_references[key])
                    elif key in ("incident_id", "scope_id") and child != scope:
                        _fail("cross_scope_audit_reference")
                    stack.append(child)
            elif type(value) is list:
                stack.extend(value)


def _validate_snapshot(snapshot):
    if type(snapshot) is not dict or set(snapshot) != _SNAPSHOT_FIELDS:
        _fail("invalid_snapshot")
    if snapshot["projection"] not in ("public_synthetic", "local_review"):
        _fail("invalid_projection")
    if snapshot["scenario_id"] not in (None, "atlas-compromise"):
        _fail("invalid_scenario")
    if type(snapshot["incident"]) is not dict:
        _fail("invalid_incident")
    scope = _identifier(snapshot["incident"].get("id"), "INC")
    evidence = snapshot["evidence"]
    evidence_ids = _scoped_rows(evidence, scope, "EVD", MAX_EVIDENCE)
    event_ids = set()
    for row in evidence:
        event_id = _identifier(row.get("event_id"), "EVT")
        if event_id in event_ids:
            _fail("duplicate_event")
        event_ids.add(event_id)
        event = row.get("event")
        if type(event) is not dict or event.get("event_id") != event_id:
            _fail("event_reference_mismatch")
        if _timestamp(row.get("timestamp")) != _timestamp(event.get("timestamp")):
            _fail("event_timestamp_mismatch")
        try:
            CanonicalEvent.model_validate(event)
        except (ValidationError, ValueError, TypeError) as exc:
            raise BundleInputError("invalid_canonical_event") from exc
    _scoped_rows(snapshot["alerts"], scope, "ALT", 80)
    for row in snapshot["alerts"]:
        _references(row.get("event_ids"), event_ids)
    finding_ids = _scoped_rows(snapshot["findings"], scope, "FND", 50)
    for row in snapshot["findings"]:
        _references(row.get("evidence_ids"), evidence_ids)
    note_ids = _scoped_rows(snapshot["notes"], scope, "NOTE", 100)
    _scoped_rows(snapshot["audit"], scope, "AUD", 1000)
    ledger = snapshot["hypotheses"]
    if type(ledger) is not dict or ledger.get("scope_id") != scope:
        _fail("cross_scope_hypothesis")
    seen_hypotheses = set()
    for row in _list(ledger.get("items"), 4):
        if type(row) is not dict:
            _fail("invalid_hypothesis")
        identifier = _identifier(row.get("id"), "HYP")
        if identifier in seen_hypotheses:
            _fail("duplicate_identifier")
        seen_hypotheses.add(identifier)
        provenance = row.get("provenance")
        if type(provenance) is not dict or provenance.get("scope_id") != scope:
            _fail("cross_scope_hypothesis")
        for field in ("supporting_evidence_ids", "contradicting_evidence_ids"):
            _references(row.get(field), evidence_ids)
        _references(row.get("related_finding_ids"), finding_ids, 50)
        if "review" in row:
            if type(row["review"]) is not dict:
                _fail("invalid_review")
            _references(row["review"].get("related_finding_ids"), finding_ids, 50)
    _audit_references(
        snapshot["audit"], scope, evidence_ids, event_ids, finding_ids, note_ids, seen_hypotheses
    )
    entities = snapshot["entities"]
    if type(entities) is not dict or set(entities) != {"nodes", "edges"}:
        _fail("invalid_entities")
    nodes = _list(entities["nodes"], 720)
    node_ids = set()
    for row in nodes:
        if type(row) is not dict:
            _fail("invalid_entities")
        identifier = _identifier(row.get("id"), "ENT")
        if identifier in node_ids:
            _fail("duplicate_identifier")
        node_ids.add(identifier)
    for row in _list(entities["edges"], 640):
        if (
            type(row) is not dict
            or type(row.get("source")) is not str
            or type(row.get("target")) is not str
            or row.get("source") not in node_ids
            or row.get("target") not in node_ids
        ):
            _fail("invalid_entity_reference")
        _references(row.get("evidence_ids"), evidence_ids)
    if snapshot["projection"] == "public_synthetic" and (
        snapshot["incident"].get("owner") is not None
        or any(row.get("note") not in (None, "") for row in evidence)
        or snapshot["findings"]
        or snapshot["notes"]
        or snapshot["audit"]
        or "context_digest" in ledger
        or any("review" in row for row in ledger["items"])
    ):
        _fail("private_public_projection")
    return scope, evidence_ids


def _readme(projection):
    return (
        "AegisGraph hash-verifiable synthetic investigation export\n\n"
        "This JSON container stores logical files as exact UTF-8 content strings. "
        "No paths need extraction. Hash the content string's UTF-8 bytes without "
        "normalizing Unicode or newlines. All telemetry is synthetic demo material.\n\n"
        f"Projection: {projection}. Public projections omit owner, evidence annotations, "
        "findings, notes, audit entries, and human hypothesis review state. Empty public "
        "collections describe that projection, not an assertion that no local actions exist. "
        "Local projections contain bounded committed case material; human actor labels "
        "are not authenticated identities.\n\n" + "\n".join(LIMITATIONS) + "\n"
    )


def build_bundle(snapshot: dict, *, generated_at: datetime) -> dict:
    """Build deterministic contents for one scoped snapshot and explicit export time."""
    snapshot = _load(snapshot)
    scope, evidence_ids = _validate_snapshot(snapshot)
    if not isinstance(generated_at, datetime) or generated_at.tzinfo is None:
        _fail("invalid_timestamp")
    try:
        timestamp = generated_at.astimezone(UTC).isoformat()
    except (ValueError, OverflowError) as exc:
        raise BundleInputError("invalid_timestamp") from exc
    evidence = sorted(
        snapshot["evidence"], key=lambda row: (_timestamp(row["timestamp"]), row["id"])
    )
    logical = {
        "incident.json": snapshot["incident"],
        "timeline.json": [
            {key: row[key] for key in ("id", "event_id", "timestamp")} for row in evidence
        ],
        "hypotheses.json": snapshot["hypotheses"],
        "entities.json": {
            "nodes": sorted(snapshot["entities"]["nodes"], key=lambda row: row["id"]),
            "edges": sorted(
                snapshot["entities"]["edges"],
                key=lambda row: (row["source"], row["target"], row.get("label", "")),
            ),
        },
    }
    for key in ("alerts", "findings", "notes", "audit"):
        logical[f"{key}.json"] = sorted(snapshot[key], key=lambda row: row["id"])
    for row in evidence:
        logical[f"evidence/{row['id']}.json"] = row
    contents = {path: _encode(value).decode("utf-8") + "\n" for path, value in logical.items()}
    contents["README.txt"] = _readme(snapshot["projection"])
    files, entries = [], []
    for path, content in sorted(contents.items()):
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_FILE_BYTES:
            _fail("file_bytes_exceeded")
        files.append({"path": path, "content": content})
        entries.append(
            {"path": path, "sha256": hashlib.sha256(encoded).hexdigest(), "bytes": len(encoded)}
        )
    result = {
        "format_version": FORMAT_VERSION,
        "manifest": {
            "format_version": FORMAT_VERSION,
            "incident_id": scope,
            "scenario_id": snapshot["scenario_id"],
            "projection": snapshot["projection"],
            "generated_at": timestamp,
            "evidence_ids": sorted(evidence_ids),
            "files": entries,
            "application": {"name": "AegisGraph", "version": "0.1.0"},
            "limitations": list(LIMITATIONS),
        },
        "files": files,
    }
    _encode(result)
    _validate_container(result)
    return result


def _path(value):
    if type(value) is not str or not _PATH.fullmatch(value):
        _fail("unsafe_path")
    if any(
        part in ("", ".", "..") or part.endswith(".") or _RESERVED.match(part)
        for part in value.split("/")
    ):
        _fail("unsafe_path")
    return value


def _file_index(value, manifest):
    result, folded = {}, set()
    for row in _list(value, MAX_FILES):
        fields = {"path", "sha256", "bytes"} if manifest else {"path", "content"}
        if type(row) is not dict or set(row) != fields:
            _fail("invalid_file_entry")
        path = _path(row["path"])
        if path.casefold() in folded:
            _fail("duplicate_path")
        folded.add(path.casefold())
        if manifest:
            if type(row["sha256"]) is not str or not _HASH.fullmatch(row["sha256"]):
                _fail("invalid_hash")
            if type(row["bytes"]) is not int or not 0 <= row["bytes"] <= MAX_FILE_BYTES:
                _fail("invalid_file_size")
        elif (
            type(row["content"]) is not str or len(row["content"].encode("utf-8")) > MAX_FILE_BYTES
        ):
            _fail("file_bytes_exceeded")
        result[path] = row
    return result


def _validate_container(value):
    if (
        type(value) is not dict
        or set(value) != {"format_version", "manifest", "files"}
        or value["format_version"] != FORMAT_VERSION
    ):
        _fail("invalid_container")
    manifest = value["manifest"]
    if (
        type(manifest) is not dict
        or set(manifest) != _MANIFEST_FIELDS
        or manifest["format_version"] != FORMAT_VERSION
    ):
        _fail("invalid_manifest")
    _identifier(manifest["incident_id"], "INC")
    if _timestamp(manifest["generated_at"]).isoformat() != manifest["generated_at"]:
        _fail("invalid_timestamp")
    if manifest["scenario_id"] not in (None, "atlas-compromise") or manifest["projection"] not in (
        "public_synthetic",
        "local_review",
    ):
        _fail("invalid_manifest")
    if manifest["application"] != {"name": "AegisGraph", "version": "0.1.0"} or manifest[
        "limitations"
    ] != list(LIMITATIONS):
        _fail("invalid_manifest")
    ids = [_identifier(item, "EVD") for item in _list(manifest["evidence_ids"], MAX_EVIDENCE)]
    if len(set(ids)) != len(ids):
        _fail("duplicate_identifier")
    expected = _file_index(manifest["files"], True)
    actual = _file_index(value["files"], False)
    if set(expected) != FIXED_PATHS | {f"evidence/{identifier}.json" for identifier in ids}:
        _fail("invalid_manifest_inventory")
    expected_folded = {path.casefold(): path for path in expected}
    if any(
        path.casefold() in expected_folded and path != expected_folded[path.casefold()]
        for path in actual
    ):
        _fail("duplicate_path")
    return expected, actual


def verify_bundle(value: dict | str | bytes) -> dict:
    """Verify supplied exact strings; return safe findings without rendering contents."""
    try:
        expected, actual = _validate_container(_load(value))
    except BundleInputError as exc:
        return {
            "status": "INVALID",
            "findings": [{"status": "INVALID", "code": str(exc)}],
            "checked_files": 0,
            "limitations": list(LIMITATIONS),
        }
    findings = []
    checked = 0
    for path, entry in sorted(expected.items()):
        if path not in actual:
            findings.append({"status": "MISSING FILE", "path": path, "code": "file_missing"})
            continue
        checked += 1
        encoded = actual[path]["content"].encode("utf-8")
        if len(encoded) != entry["bytes"] or hashlib.sha256(encoded).hexdigest() != entry["sha256"]:
            findings.append({"status": "MODIFIED", "path": path, "code": "content_mismatch"})
    findings.extend(
        {"status": "UNEXPECTED FILE", "path": path, "code": "file_unlisted"}
        for path in sorted(set(actual) - set(expected))
    )
    statuses = {row["status"] for row in findings}
    status = next(
        (item for item in ("MODIFIED", "MISSING FILE", "UNEXPECTED FILE") if item in statuses),
        "VALID",
    )
    return {
        "status": status,
        "findings": findings,
        "checked_files": checked,
        "limitations": list(LIMITATIONS),
    }
