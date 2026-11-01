# Dependency audit repair

Goal: clear the Python and npm audit failures in PR #1 without removing security
checks, changing application behavior or deploying production.

The Python audit identifies msgpack 1.2.2, fixed in 1.2.3. The npm findings all
originate in minimatch below 11.0.1. ESLint's legacy plugins still call the v3
default-function interface, while patched minimatch exports named APIs.

## Constraints

- Keep all existing lint rules and security audits enabled.
- Use the real patched minimatch implementation; never relabel vulnerable code.
- A compatibility adapter, if required, must be private, limited to lint tooling,
  transparent in the dependency graph and tested through actual consumer rules.
- Preserve runtime/public-mode checks, source routing fixes and dependency ranges
  outside the necessary security corrections.
- No production deployments, configuration changes or database writes.

## Tasks

- [x] Pin msgpack 1.2.3 and verify Python audit, dependency consistency and tests.
- [x] Validate a compatible minimatch replacement in an isolated npm fixture.
- [x] Add regression coverage for legacy/default and named module consumers,
  actual ESLint rule behavior and clean lockfile installation.
- [x] Replace affected npm implementations and verify zero audit findings.
- [x] Run full frontend and routing checks; obtain fresh independent review.
- [ ] Update the existing PR and verify remote CI before reporting completion.

Review focus: ESM/CJS resolution, all transitive consumers, no stale vulnerable
package copies, unchanged lint enforcement, reproducible npm ci and audit checks.
