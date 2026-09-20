# Synthetic scenario corpus

Eight versioned, inert scenarios exercise the same normalization, detection and
correlation functions. They execute no attacks, network requests, or endpoint
commands. The original Atlas workload below remains the canonical database fixture;
browsing the additional scenarios does not seed or modify PostgreSQL.

| Scenario | Investigation purpose | Context worth inspecting |
|---|---|---|
| `atlas-compromise` | Unfamiliar access followed by privilege and resource activity | The original complete Atlas investigation |
| `auth-pressure` | Failed authentication followed by unfamiliar access and MFA acceptance | Acceptance does not establish MFA fatigue or who held the session |
| `service-access` | Service-principal requests outside a recorded job scope | Scope record, endpoint requests, sensitive read and volume |
| `sensitive-enumeration` | Endpoint exploration with limited corroboration | An alert sequence can remain below the incident threshold |
| `approved-admin` | Temporary administration with recorded approval | Legitimate security signals can have a benign explanation |
| `bulk-automation` | Scheduled reconciliation volume | A 1,200-record read against a recorded job limit of 1,500 |
| `isolated-anomaly` | One changed authentication source/device | An anomaly alone does not prove compromise |
| `mixed-context` | Unfamiliar activity alongside approval and device context | The recorded approval names a different session |

The [scenario module](../../apps/api/aegisgraph/scenarios.py) exposes fresh
canonical events and bounded analyst-visible metadata. `GET /api/scenarios` and
`GET /api/scenarios/{id}` return descriptions only. IDs come from a fixed catalog;
there is no upload, arbitrary generator, seed, or reset route. Cached telemetry is
serialized so a caller cannot mutate nested fields shared with another request.

The separate [ground-truth module](../../apps/api/aegisgraph/scenario_ground_truth.py)
contains independently authored expected/forbidden rule IDs, required signals,
correlation outcomes, relevant source IDs, benign context, non-established facts,
supported claim types, and question outcomes. These labels are for evaluation;
scenario generation and analyst context do not import them. See
[ADR-010](../../docs/adr/ADR-010.md).

Expected baseline alerts and required detections have different meanings. Approved
administration may legitimately fire role-change signals; benign bulk activity
currently fires the volume rule. Removing such an alert during tuning is not
automatically a missed malicious detection. Any later regression measurement must
state its rule, scenario labels, and denominator.

Detector output and provider claims also have separate contracts. For example,
the detector can count distinct endpoints, while the current analyst projection
does not pass endpoint strings or job/approval prose to a provider. Human reviewers
can inspect those observations, but an AI answer cannot claim to have weighed
fields omitted from its context. Fixture labels do not override this boundary.

## Original Atlas workload

`apps/api/aegisgraph/generator.py` creates 4,000 normal events plus 26 scenario/context events using seed 42 and fixed UTC timestamps on 2026-09-15. Twenty-four fictional engineers have recognized devices and sessions. The normal workload covers Identity Service, Trading API, Account Service, API Gateway, Endpoint telemetry, and subsequent scenario requests target Admin Service. All identities/resources are fictional; addresses are from documentation ranges.

The scenario begins with trusted login at 13:57, unfamiliar authentication at 14:02, accepted MFA at 14:03, role grant at 14:07, eighteen internal requests at 14:11, sensitive account access at 14:14, 2,400-record access at 14:17, a second unusual device/session at 14:21 and role reversion at 14:24. Those observations support a compromise hypothesis but do not prove malware execution, intent, real geography, or exfiltration.

For a reproducible disposable demo, run from the repository root with dependencies installed:

```sh
python -m aegisgraph.cli demo-reset
python -m aegisgraph.cli demo-api
# In another terminal:
python -m aegisgraph.cli demo-health
```

`demo-reset` deliberately destroys and recreates only the reserved repository database `.runtime/aegisgraph-demo.db`; it ignores `DATABASE_URL`. It applies migrations, generates telemetry, evaluates detections, correlates the case, and runs the deterministic evaluation suite. `demo-api` serves that same database on loopback and defaults to the deterministic provider even if local environment configuration selects OpenAI. Live calls require the explicit `--provider openai` option and valid local provider configuration. `demo-health` checks API/database reachability, expected fixture counts, primary evidence, fixture availability and an explicitly deterministic analyst invocation. It does not invoke an external model.

To use PostgreSQL, first provision the disposable database named exactly `aegisgraph_demo`, owned by the existing local `aegisgraph` demo role, on a loopback PostgreSQL server. Both `demo-reset --postgres-port PORT` and `demo-api --postgres-port PORT` use only that fixed database and the public local demo credentials in [`.env.example`](../../.env.example); see the [setup guide](../../docs/SETUP.md#postgresql). The command does not create PostgreSQL databases or accept an arbitrary database URL.

The legacy `alembic upgrade head` and `python -m aegisgraph.cli seed` commands still support configured, non-destructive setup. Seed is idempotent if events already exist. Destructive `seed --reset` is now guarded: only the two reserved SQLite files (`aegisgraph-demo.db` and browser-test `e2e.db` under `.runtime`) or the fixed local PostgreSQL `aegisgraph_demo` target are accepted. SQLite directory/file links and hard-linked database files are rejected. This protects against accidental target selection; it is not a security boundary against a hostile machine administrator or a filesystem race.

There is no destructive seed/reset HTTP endpoint. The root `.env` loads automatically without overriding explicit process settings; interpolation is disabled, and `AEGISGRAPH_LOAD_ENV=false` disables file loading. Tests disable workstation `.env` loading and default to deterministic mode. No command displays provider credentials.

Custom `normal_count` exists for tests and retains a minimum of 72 baseline logins so novelty rules have established history. The default produces exactly 4,026 events and is the documented demo workload.
