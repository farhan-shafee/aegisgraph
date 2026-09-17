# Synthetic Atlas workload

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
