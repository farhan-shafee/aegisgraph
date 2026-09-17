# Security policy

AegisGraph is a local investigation demonstration with entirely synthetic data,
not a production security service. Publishing its source does not make its API
safe to expose to the public internet. The fixed local analyst is not production
authentication or authorization. Do not load customer data or real credentials
into fixtures, screenshots, issues, or evaluation records.

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
