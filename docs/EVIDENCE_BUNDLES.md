# Hash-verifiable evidence bundles

An investigation export is one bounded JSON document containing a manifest and
logical files. It contains synthetic case material, not an executable archive.
The export endpoint is a read in both modes; it creates no database record or audit
entry and does not invoke an analyst provider.

`GET /api/incidents/{incident_id}/export` exports a persisted case. An ephemeral
scenario observation scope is not a persisted incident and cannot use this route.
The canonical Atlas case identifies its scenario as `atlas-compromise`; other
persisted cases use a null scenario ID rather than guessing provenance.

## Contents and projections

The format includes `incident.json`, `timeline.json`, `alerts.json`, `findings.json`,
`hypotheses.json`, `notes.json`, `audit.json`, `entities.json`, `README.txt`, and one
`evidence/{id}.json` file per included evidence item. Contents are strings inside
JSON; neither generation nor verification writes these logical paths to disk.

The manifest declares the case, scenario, evidence IDs, format/application version,
generation time, projection, and each file's UTF-8 byte length and SHA-256 digest.

| Projection | Included material |
|---|---|
| `public_synthetic` | Scoped synthetic observations, alerts, relationships, case metadata, and derived hypotheses; owner labels, evidence notes, findings, notes, audit records, and saved hypothesis reviews are omitted |
| `local_review` | Bounded committed case material, including annotations, findings, notes, audit records, and hypothesis review metadata |

Empty public files reflect the declared projection; they do not establish that no
human records exist. Local actor labels are not authenticated identities. Local
annotations are exported as supplied; the application does not detect or redact
personal information that a local user writes into them.

## Verification

Save the API response as a JSON file, then run:

```sh
python -m aegisgraph.cli verify-bundle bundle.json
```

Verification requires no database, credentials, network, or filesystem extraction.
The command exits zero only for `VALID`. It checks exact decoded content strings
as UTF-8 bytes; editing whitespace inside a logical file changes its hash. Reordering
the outer JSON object's keys does not change the logical file contents.

| Result | Meaning |
|---|---|
| VALID | File membership, lengths, and hashes match the supplied manifest |
| MODIFIED | A listed file's content or length differs |
| MISSING FILE | A file listed in the manifest is absent |
| UNEXPECTED FILE | The container includes an extra file |
| INVALID | The container or manifest violates the bounded format |

The verifier reports all discovered discrepancies. Multiple discrepancy classes
use the priority MODIFIED, MISSING FILE, UNEXPECTED FILE for the overall status.
Malformed containers receive INVALID. No raw file contents are echoed in errors.

## Exact boundary

This is a **hash-verifiable export**, not proof of authenticity. It can detect a
changed file against its supplied manifest. Someone who changes both a file and
the unsigned manifest can produce a matching bundle. The manifest metadata is
also unsigned. Verification does not prove telemetry truth, privileged-database
integrity, authenticated analyst identity, legal chain of custody, or that a
previously displayed bundle is the same one a reviewer received.

The exporter captures `generated_at` once at export time. Serialization is
deterministic for the same committed snapshot and that timestamp; a later export
has a new generation time. It does not relabel an old event timestamp as the time
the export was generated.

## Bounds and inspection

The container is limited to 2 MiB, 100 logical files, and 256 KiB per file. Database
reads request at most the supported row limit plus one and reject excess instead
of silently truncating evidence: 80 evidence rows, 80 alerts, 50 findings, 100 notes,
and 1,000 audit rows. The byte bound may be reached before a row bound.

The snapshot uses a dedicated read transaction: PostgreSQL repeatable-read,
read-only isolation, or an explicit SQLite read transaction. It includes committed
state only. SQLite exports require a file-backed database with independent
connections; shared in-memory pools are rejected to preserve other sessions' work.
Duplicate JSON keys, nonfinite numbers, unsafe logical paths, duplicate
file entries, unknown versions, malformed text, and oversized input are rejected.

- [Bundle format and verifier](../apps/api/aegisgraph/evidence_bundle.py)
- [Bounded snapshot reader](../apps/api/aegisgraph/evidence_export.py)
- [API](../apps/api/aegisgraph/export_api.py)
- [Format and boundary tests](../tests/backend/test_evidence_bundle.py)
- [Snapshot tests](../tests/backend/test_evidence_export.py)
- [ADR-014](adr/ADR-014.md)
