# Security policy

AegisGraph is an investigation demonstration with entirely synthetic data, not a
production security service. Publishing its source does not make the writable
local mode safe to expose to the public internet. Its fixed analyst is not
production authentication or authorization.

The explicit `APP_MODE=public_demo` configuration provides a separate read-only
deployment surface: persistent API writes are denied and only the curated,
deterministic analyst is available. Follow the [deployment guide](docs/DEPLOYMENT.md)
for the required PostgreSQL, host, origin, and environment configuration. Shared
in-process request budgets are limited protection, not a distributed abuse defense.
Do not load customer data or real credentials into fixtures, screenshots, issues,
or evaluation records.

Use **Security → Advisories → Report a vulnerability** to report a suspected issue
privately when GitHub private vulnerability reporting is enabled. Include the
affected commit, expected and observed behavior, and a minimal synthetic example.
Do not include API keys, authorization headers, private data, or exploit payloads.

If the private-report button is unavailable, open an issue requesting a private
contact channel **without disclosing vulnerability details**, then wait for the
maintainer to provide one. This policy does not claim that private reporting is
already enabled. The maintainer should enable it when publishing the repository
and verify that the button is available. No response-time commitment or bounty
program is offered.

See [the threat model](docs/threat-model/THREAT_MODEL.md) for implemented controls,
residual risks, and the prerequisites for production deployment.
