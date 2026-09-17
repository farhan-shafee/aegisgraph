# Synthetic Atlas workload

`apps/api/aegisgraph/generator.py` creates 4,000 normal events plus 26 scenario/context events using seed 42 and fixed UTC timestamps on 2026-09-15. Twenty-four fictional engineers have recognized devices and sessions. The normal workload covers Identity Service, Trading API, Account Service, API Gateway, Endpoint telemetry, and subsequent scenario requests target Admin Service. All identities/resources are fictional; addresses are from documentation ranges.

The scenario begins with trusted login at 13:57, unfamiliar authentication at 14:02, accepted MFA at 14:03, role grant at 14:07, eighteen internal requests at 14:11, sensitive account access at 14:14, 2,400-record access at 14:17, a second unusual device/session at 14:21 and role reversion at 14:24. Those observations support a compromise hypothesis but do not prove malware execution, intent, real geography, or exfiltration.

From the repository root with dependencies installed and `DATABASE_URL` configured:

```sh
alembic upgrade head
python -m aegisgraph.cli seed
python -m aegisgraph.cli seed --reset
python -m aegisgraph.cli evaluate
```

Seed is idempotent if events already exist. `--reset` is deliberately a local CLI action that drops and recreates application tables; use only a disposable demo database. There is no destructive seed/reset HTTP endpoint. Custom `normal_count` exists for tests and retains a minimum of 72 baseline logins so novelty rules have established history. The default produces exactly 4,026 events and is the documented demo workload.
