# Canonical telemetry contract

The executable Pydantic schema is `apps/api/aegisgraph/schema.py`; `security-event.schema.json` is its generated JSON Schema. Four source adapters map source-specific type keys into this shared contract. Events carry timezone-aware timestamps, identity, target, network, device, session, bounded extensible attributes, and an allowlisted sanitized synthetic source reference. IP fields accept valid IPv4/IPv6; the generator uses documentation-safe ranges only.

`event_id` is stable and unique. Events are append-only after ingestion: API endpoints never expose event updates/deletes, the ORM rejects edits, and migrations install PostgreSQL/SQLite triggers against UPDATE/DELETE. The guarded `python -m aegisgraph.cli demo-reset` command intentionally drops/recreates tables and reinstalls triggers only in a reserved disposable demo target; it never infers a reset target from `DATABASE_URL`. Legacy `seed --reset` also rejects arbitrary database targets. A database owner can remove triggers; this is not cryptographic evidence preservation. Analyst annotations and relevance live in `incident_evidence`, leaving source events unchanged. Audit records also have database immutability triggers.

The metadata maps are JSON snapshots. Pydantic models are frozen at their top-level field boundary, but nested Python dictionaries are not recursively frozen. The persisted database record is the immutable system of record, not an in-memory model instance. Each metadata field is limited to 16 KiB serialized UTF-8 and eight nesting levels. Telemetry strings remain untrusted data, including instruction-like text.

Incident responses also expose derived `correlation` metadata: observed principals, linked alert count, distinct rule IDs/families, first/last alert times, measured span, and the configured minimum rule/family and time-window requirements. Its explicit grouping keys are principal and event time; device/session/IP links are labeled context only. This metadata describes deterministic grouping and is not model-generated reasoning or another source event.

Generate the schema from the root:

```sh
python -c "import json; from pathlib import Path; from aegisgraph.schema import CanonicalEvent; Path('packages/schemas/security-event.schema.json').write_text(json.dumps(CanonicalEvent.model_json_schema(), indent=2) + '\n', encoding='utf-8')"
```
