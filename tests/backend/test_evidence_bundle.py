"""A bundle verifies bytes against an unsigned manifest, never source truth."""

import copy
import hashlib
import json
from datetime import UTC, datetime

import pytest
from aegisgraph.evidence_bundle import (
    MAX_BUNDLE_BYTES,
    MAX_FILE_BYTES,
    BundleInputError,
    build_bundle,
    verify_bundle,
)
from aegisgraph.hypotheses import build_ledger
from aegisgraph.replay import replay_projection

GENERATED_AT = datetime(2026, 9, 23, 12, tzinfo=UTC)


@pytest.fixture
def snapshot():
    investigation = copy.deepcopy(
        replay_projection("atlas-compromise")["final_state"]["investigation"]
    )
    scope = investigation["id"]
    rows = investigation["evidence"]
    return {
        "incident": {"id": scope, "title": "Synthetic Atlas investigation"},
        "scenario_id": "atlas-compromise",
        "projection": "local_review",
        "evidence": rows,
        "alerts": [],
        "findings": [],
        "hypotheses": build_ledger(scope, rows, allowed_scope_ids={scope}),
        "notes": [],
        "audit": [],
        "entities": {"nodes": [], "edges": []},
    }


@pytest.fixture
def bundle(snapshot):
    return build_bundle(snapshot, generated_at=GENERATED_AT)


def test_valid_bundle_has_exact_utf8_hashes_and_roundtrips(bundle, snapshot):
    assert verify_bundle(bundle)["status"] == "VALID"
    assert verify_bundle(json.dumps(bundle))["status"] == "VALID"
    assert verify_bundle(json.dumps(bundle).encode())["status"] == "VALID"
    manifest = bundle["manifest"]
    assert manifest["incident_id"] == snapshot["incident"]["id"]
    assert manifest["evidence_ids"] == sorted(row["id"] for row in snapshot["evidence"])
    assert manifest["generated_at"] == GENERATED_AT.isoformat()
    assert manifest["application"] == {"name": "AegisGraph", "version": "0.1.0"}
    assert len(bundle["files"]) == len(snapshot["evidence"]) + 9
    for entry, file in zip(manifest["files"], bundle["files"], strict=True):
        data = file["content"].encode("utf-8")
        assert entry == {
            "path": file["path"],
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        }


def test_builder_is_deterministic_without_changing_input(snapshot):
    prior = copy.deepcopy(snapshot)
    one = build_bundle(snapshot, generated_at=GENERATED_AT)
    snapshot["evidence"].reverse()
    two = build_bundle(snapshot, generated_at=GENERATED_AT)
    assert one == two
    snapshot["evidence"].reverse()
    assert snapshot == prior
    timeline = json.loads(
        next(row["content"] for row in one["files"] if row["path"] == "timeline.json")
    )
    assert [row["timestamp"] for row in timeline] == sorted(row["timestamp"] for row in timeline)


def test_unicode_is_hashed_as_exact_utf8_without_normalization(snapshot):
    snapshot["incident"]["title"] = "Synthetic café / cafe\u0301 / 東京 / 🔎"
    result = build_bundle(snapshot, generated_at=GENERATED_AT)
    assert (
        verify_bundle(json.dumps(result, ensure_ascii=False).encode("utf-8"))["status"] == "VALID"
    )
    file = next(item for item in result["files"] if item["path"] == "incident.json")
    file["content"] = file["content"].replace("cafe\u0301", "café")
    assert verify_bundle(result)["status"] == "MODIFIED"


def test_newline_change_is_modification(bundle):
    bundle["files"][0]["content"] += "\r\n"
    result = verify_bundle(bundle)
    assert result["status"] == "MODIFIED"
    assert result["findings"] == [
        {"status": "MODIFIED", "path": bundle["files"][0]["path"], "code": "content_mismatch"}
    ]


def test_missing_and_unexpected_files_remain_visible_together(bundle):
    missing = bundle["files"].pop(0)["path"]
    bundle["files"].append({"path": "extra.txt", "content": "untrusted <script>text</script>"})
    result = verify_bundle(bundle)
    assert result["status"] == "MISSING FILE"
    assert result["findings"] == [
        {"status": "MISSING FILE", "path": missing, "code": "file_missing"},
        {"status": "UNEXPECTED FILE", "path": "extra.txt", "code": "file_unlisted"},
    ]
    assert "<script>" not in json.dumps(result)


def test_unexpected_safe_file(bundle):
    bundle["files"].append({"path": "extra.txt", "content": "additional material"})
    assert verify_bundle(bundle)["status"] == "UNEXPECTED FILE"


def test_file_and_manifest_order_does_not_affect_verification(bundle):
    bundle["files"].reverse()
    bundle["manifest"]["files"].reverse()
    assert verify_bundle(bundle)["status"] == "VALID"


def test_unsigned_manifest_replacement_cannot_be_detected(bundle):
    file = bundle["files"][0]
    file["content"] = "replacement content, not necessarily JSON"
    entry = next(item for item in bundle["manifest"]["files"] if item["path"] == file["path"])
    entry["sha256"] = hashlib.sha256(file["content"].encode()).hexdigest()
    entry["bytes"] = len(file["content"].encode())
    result = verify_bundle(bundle)
    assert result["status"] == "VALID"
    assert any("unsigned" in item and "replace" in item for item in result["limitations"])
    assert any("source telemetry" in item for item in result["limitations"])


@pytest.mark.parametrize(
    "path",
    [
        "../secret",
        "/incident.json",
        "C:/incident.json",
        "evidence\\EVD-x.json",
        "evidence/../x",
        "./incident.json",
        "evidence//x",
        "incident.json\x00",
        "<script>.json",
        "evidence/%2e%2e/x",
    ],
)
def test_unsafe_paths_are_invalid_without_echoing_them(bundle, path):
    bundle["files"].append({"path": path, "content": "secret-canary"})
    result = verify_bundle(bundle)
    assert result["status"] == "INVALID"
    assert path not in json.dumps(result)
    assert "secret-canary" not in json.dumps(result)


@pytest.mark.parametrize("duplicate", ["exact", "case"])
def test_duplicate_and_case_colliding_paths_are_invalid(bundle, duplicate):
    row = copy.deepcopy(bundle["files"][0])
    if duplicate == "case":
        row["path"] = row["path"].upper()
    bundle["files"].append(row)
    assert verify_bundle(bundle)["status"] == "INVALID"


@pytest.mark.parametrize(
    "change",
    [
        "version",
        "unknown",
        "hash",
        "bytes_bool",
        "manifest_path",
        "evidence_id",
        "timestamp",
        "limit_removed",
    ],
)
def test_malformed_manifest_fails_closed(bundle, change):
    if change == "version":
        bundle["format_version"] = "2"
    elif change == "unknown":
        bundle["manifest"]["extra"] = True
    elif change == "hash":
        bundle["manifest"]["files"][0]["sha256"] = "MD5-not-supported"
    elif change == "bytes_bool":
        bundle["manifest"]["files"][0]["bytes"] = True
    elif change == "manifest_path":
        bundle["manifest"]["files"][0]["path"] = "other.txt"
    elif change == "evidence_id":
        bundle["manifest"]["evidence_ids"].append("EVD-not-exported")
    elif change == "timestamp":
        bundle["manifest"]["generated_at"] = "2026-09-23"
    else:
        bundle["manifest"]["limitations"] = []
    assert verify_bundle(bundle)["status"] == "INVALID"


@pytest.mark.parametrize(
    "value",
    [
        b"\xff",
        '{"a":1,"a":2}',
        '{"a":{"b":1,"b":2}}',
        '{"a":NaN}',
        '{"a":Infinity}',
        '{"a":"\\ud800"}',
        "[" * 100 + "]" * 100,
        "x" * (MAX_BUNDLE_BYTES + 1),
    ],
    ids=[
        "invalid-utf8",
        "duplicate-key",
        "nested-duplicate-key",
        "nan",
        "infinity",
        "surrogate",
        "depth",
        "bytes",
    ],
)
def test_malformed_or_excessive_serialized_input_is_invalid(value):
    assert verify_bundle(value)["status"] == "INVALID"


def test_bounds_apply_to_in_memory_input_and_files(bundle):
    bundle["files"][0]["content"] = "x" * (MAX_FILE_BYTES + 1)
    assert verify_bundle(bundle)["status"] == "INVALID"
    cycle = {}
    cycle["cycle"] = cycle
    assert verify_bundle(cycle)["status"] == "INVALID"


@pytest.mark.parametrize(
    "change",
    [
        "case",
        "event",
        "timestamp",
        "duplicate",
        "finding",
        "hypothesis",
        "hypothesis_scope",
        "hypothesis_finding",
        "alert",
        "note",
        "audit",
        "entity",
    ],
)
def test_builder_rejects_cross_scope_or_dangling_references(snapshot, change):
    case = snapshot["incident"]["id"]
    if change == "case":
        snapshot["evidence"][0]["incident_id"] = "INC-other"
    elif change == "event":
        snapshot["evidence"][0]["event"]["event_id"] = "EVT-other"
    elif change == "timestamp":
        snapshot["evidence"][0]["timestamp"] = "2026-01-01T00:00:00+00:00"
    elif change == "duplicate":
        snapshot["evidence"].append(copy.deepcopy(snapshot["evidence"][0]))
    elif change == "finding":
        snapshot["findings"] = [{"id": "FND-a", "incident_id": case, "evidence_ids": ["EVD-other"]}]
    elif change == "hypothesis":
        snapshot["hypotheses"]["items"][0]["supporting_evidence_ids"] = ["EVD-other"]
    elif change == "hypothesis_scope":
        snapshot["hypotheses"]["items"][0]["provenance"]["scope_id"] = "INC-other"
    elif change == "hypothesis_finding":
        snapshot["hypotheses"]["items"][0]["related_finding_ids"] = ["FND-other"]
    elif change == "alert":
        snapshot["alerts"] = [{"id": "ALT-a", "incident_id": case, "event_ids": ["EVT-other"]}]
    elif change in {"note", "audit"}:
        snapshot["notes" if change == "note" else "audit"] = [
            {"id": "NOTE-a" if change == "note" else "AUD-a", "incident_id": "INC-other"}
        ]
    else:
        snapshot["entities"]["edges"] = [
            {"source": "ENT-a", "target": "ENT-b", "evidence_ids": ["EVD-other"]}
        ]
    with pytest.raises(BundleInputError):
        build_bundle(snapshot, generated_at=GENERATED_AT)


def test_builder_rejects_naive_time_unknown_snapshot_fields_and_excesses(snapshot):
    with pytest.raises(BundleInputError):
        build_bundle(snapshot, generated_at=datetime(2026, 9, 23))
    snapshot["secret"] = "not-an-export-field"
    with pytest.raises(BundleInputError):
        build_bundle(snapshot, generated_at=GENERATED_AT)
    del snapshot["secret"]
    snapshot["incident"]["title"] = "x" * MAX_FILE_BYTES
    with pytest.raises(BundleInputError):
        build_bundle(snapshot, generated_at=GENERATED_AT)


@pytest.mark.parametrize("encoding", ["utf-16", "utf-32", "utf-8-sig"])
def test_verifier_rejects_alternative_encodings_and_bom(bundle, encoding):
    assert verify_bundle(json.dumps(bundle).encode(encoding))["status"] == "INVALID"


def test_duplicate_escaped_equivalent_keys_fail_before_schema_validation(bundle):
    text = json.dumps(bundle)
    duplicated = text.replace(
        '"format_version": "1"', '"format_version": "1", "format_\\u0076ersion": "1"', 1
    )
    result = verify_bundle(duplicated)
    assert result["status"] == "INVALID"
    assert result["findings"][0]["code"] == "duplicate_json_key"


def test_numeric_overflow_is_invalid():
    assert verify_bundle('{"x":1e309}')["status"] == "INVALID"


def test_manifest_duplicate_paths_and_actual_file_count_are_bounded(bundle):
    duplicate = copy.deepcopy(bundle)
    duplicate["manifest"]["files"].append(copy.deepcopy(duplicate["manifest"]["files"][0]))
    assert verify_bundle(duplicate)["status"] == "INVALID"
    bundle["files"].extend({"path": f"extra-{index}.txt", "content": ""} for index in range(101))
    assert verify_bundle(bundle)["status"] == "INVALID"


@pytest.mark.parametrize(
    "field", ["owner", "annotation", "findings", "notes", "audit", "review", "context_digest"]
)
def test_public_projection_cannot_include_private_workflow_material(snapshot, field):
    snapshot["projection"] = "public_synthetic"
    for row in snapshot["evidence"]:
        row["note"] = ""
    assert verify_bundle(build_bundle(snapshot, generated_at=GENERATED_AT))["status"] == "VALID"
    if field == "owner":
        snapshot["incident"]["owner"] = "private actor"
    elif field == "annotation":
        snapshot["evidence"][0]["note"] = "private note"
    elif field == "review":
        snapshot["hypotheses"]["items"][0]["review"] = {"related_finding_ids": []}
    elif field == "context_digest":
        snapshot["hypotheses"]["context_digest"] = "local review digest"
    else:
        prefix = {"findings": "FND", "notes": "NOTE", "audit": "AUD"}[field]
        snapshot[field] = [
            {"id": f"{prefix}-local", "incident_id": snapshot["incident"]["id"], "evidence_ids": []}
        ]
    with pytest.raises(BundleInputError):
        build_bundle(snapshot, generated_at=GENERATED_AT)


def test_builder_rejects_malformed_entity_reference_with_safe_error(snapshot):
    snapshot["entities"]["edges"] = [{"source": {}, "target": "ENT-x", "evidence_ids": []}]
    with pytest.raises(BundleInputError):
        build_bundle(snapshot, generated_at=GENERATED_AT)


@pytest.mark.parametrize(
    "field,value",
    [
        ("evidence_ids", ["EVD-other"]),
        ("supporting_evidence_ids", ["EVD-other"]),
        ("event_ids", ["EVT-other"]),
        ("related_finding_ids", ["FND-other"]),
        ("scope_id", "INC-other"),
        ("incident_id", "INC-other"),
    ],
)
def test_audit_nested_structured_references_are_scoped(snapshot, field, value):
    snapshot["audit"] = [
        {
            "id": "AUD-test",
            "incident_id": snapshot["incident"]["id"],
            "action": "test_review",
            "object_id": "OBJ-test",
            "before": None,
            "after": {"nested": [{field: value}]},
        }
    ]
    with pytest.raises(BundleInputError):
        build_bundle(snapshot, generated_at=GENERATED_AT)


def test_audit_human_prose_is_inert_and_report_objects_need_not_be_exported(snapshot):
    snapshot["audit"] = [
        {
            "id": "AUD-test",
            "incident_id": snapshot["incident"]["id"],
            "action": "report_generated",
            "object_id": "RPT-test",
            "before": None,
            "after": {"reason": '{"evidence_ids":["EVD-other"]}'},
        }
    ]
    assert verify_bundle(build_bundle(snapshot, generated_at=GENERATED_AT))["status"] == "VALID"


@pytest.mark.parametrize(
    "action,prefix",
    [
        ("incident_created", "INC"),
        ("evidence_annotated", "EVD"),
        ("finding_created", "FND"),
        ("finding_reviewed", "FND"),
        ("note_created", "NOTE"),
        ("hypothesis_reviewed", "HYP"),
    ],
)
def test_audit_known_object_types_cannot_reference_foreign_objects(snapshot, action, prefix):
    snapshot["audit"] = [
        {
            "id": "AUD-test",
            "incident_id": snapshot["incident"]["id"],
            "action": action,
            "object_id": f"{prefix}-other",
            "before": None,
            "after": None,
        }
    ]
    with pytest.raises(BundleInputError):
        build_bundle(snapshot, generated_at=GENERATED_AT)


def test_manifest_timestamp_requires_canonical_utc_iso_form(bundle):
    bundle["manifest"]["generated_at"] = "2026-W39-3T12:00:00Z"
    assert verify_bundle(bundle)["status"] == "INVALID"


def test_hypothesis_audit_preserves_revision_object_and_validates_related_hypothesis(snapshot):
    audit = {
        "id": "AUD-review",
        "incident_id": snapshot["incident"]["id"],
        "action": "hypothesis_reviewed",
        "object_id": "HPR-revision",
        "before": None,
        "after": {"hypothesis_id": snapshot["hypotheses"]["items"][0]["id"]},
    }
    snapshot["audit"] = [audit]
    result = build_bundle(snapshot, generated_at=GENERATED_AT)
    exported_audit = json.loads(
        next(row["content"] for row in result["files"] if row["path"] == "audit.json")
    )
    assert exported_audit[0]["object_id"] == "HPR-revision"
    audit["after"]["hypothesis_id"] = "HYP-other"
    with pytest.raises(BundleInputError):
        build_bundle(snapshot, generated_at=GENERATED_AT)


def test_manifest_case_labels_are_not_authenticated_by_content_hashes(bundle):
    bundle["manifest"]["incident_id"] = "INC-replaced-label"
    bundle["manifest"]["scenario_id"] = None
    assert verify_bundle(bundle)["status"] == "VALID"


def test_small_serialized_input_can_still_exceed_structural_work_budget():
    value = '{"items":[' + ",".join("0" for _ in range(100_001)) + "]}"
    assert len(value.encode()) < MAX_BUNDLE_BYTES
    result = verify_bundle(value)
    assert result["status"] == "INVALID"
    assert result["findings"][0]["code"] == "structure_limit_exceeded"
