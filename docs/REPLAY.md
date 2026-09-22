# Deterministic scenario replay

Replay follows inert synthetic observations through the existing detector and
correlator. It is a computed history, not live collection or execution of an attack.
See the [corpus](../packages/synthetic-data/README.md) and
[replay decision](adr/ADR-011.md).

`GET /api/replays/{scenario_id}` selects one repository-owned scenario. It accepts
no query parameters, uploaded events, arbitrary rules or executable code. The
response contains version/digest provenance, disclosed event counts, ordered
frames, and a separately named completed result. All public activity is ephemeral;
neither fetching a replay nor changing its eventual browser cursor changes the
canonical PostgreSQL fixture.

Public replay always uses the shipped rules. Local replay uses the current
human-approved ruleset from the [detection workbench](DETECTION_WORKBENCH.md),
identified by its digest in the projection. Approval changes subsequent local
projections; it does not rewrite historical canonical incidents or alerts.

Frames describe actual stages: context initialization, telemetry arrival,
normalization, rule match, alert, correlation decision and incident creation or
update. The detector is causal: it uses prior observations and the current event.
Correlation receives only the available prefix. For Atlas, the first incident is
created at 14:03 UTC after three rules across two families; later resource access
changes the case's evidence and severity. The completed investigation must not be
rendered as though it existed at the first frame.

Atlas preserves all 4,026 events. Its 4,000 normal background records are explicitly
initialized before playback; the 26 investigation observations play from 13:57 UTC.
Smaller scenarios play every event. A scenario that never reaches the correlation
threshold retains an **observation scope**, with no invented incident ID.

The API bounds replay to 5,000 source events, 80 playback observations, 600 frames
and a 1 MiB serialized projection. A finite cache stores shipped-rule projections
as serialized values and returns fresh objects; changed local rules are evaluated
against the requested scenario. Existing public request/concurrency budgets still apply.
These are demonstration-scale controls, not flood resistance or a scale benchmark.

Required execution calls neither OpenAI nor another external provider. Evaluation
answer keys are separate from runtime frames and evidence. Frame timestamps are
source event times; processing duration is operational metadata and is not used
to manufacture event timing or quality scores.

Reproduce the engine and API checks locally with:

```sh
python -m pytest -q tests/backend/test_replay.py tests/backend/test_replay_api.py
```

The runtime capability `replay: 1` identifies this API contract. Frontends should
treat missing capabilities as unavailable features while retaining the existing
investigation workflow. Public authorization remains enforced by the server.
