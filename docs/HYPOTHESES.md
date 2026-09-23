# Hypotheses and investigation gaps

The ledger separates **what the evidence supports** from **what a human reviewed**.
It uses fixed propositions and validated evidence references. It does not assign
probabilities, infer an attacker's identity, or let a model change case state.

| Proposition | Evidence-derived interpretation |
|---|---|
| Account activity reflects unauthorized control | Unfamiliar authentication can provide partial support; it cannot confirm the operator or intent |
| Unfamiliar authentication preceded privilege assignment and sensitive access | Supported only by the existing ordered, same-principal, 30-minute observation predicate |
| Privileged-role assignment was outside its recorded change approval | Contradicted only when every observed grant matches a recorded principal/session/role/time approval; missing approval is insufficient evidence |
| Bulk access exceeded its recorded automation allowance | Compare scoped job records and cumulative account-query volume; incomplete or conflicting context remains insufficient |

Every row exposes supporting and contradicting evidence IDs, typed missing-evidence
categories, source-time bounds, and derivation provenance. The four propositions
remain visible when evidence is insufficient, preserving a place to inspect stale
reviews. Raw text, notes, fixture classifications and evaluation answer keys do not
become factual claims. Recorded approvals and allowances are observations whose
authenticity is outside this demo's guarantees.

“What would confirm or reject this?” provides conditional guidance: verify account
control, collect session history, check scoped change approvals, reconcile job
allowances, or collect endpoint forensic evidence. The malware guidance does not
assert that a process executed or identify a malware family.

## Local human review

A local analyst can record an open, accepted or rejected review with a reason and
up to ten case-scoped finding references. The server derives the proposition and
citations again. It rejects obsolete versions or context digests. Acceptance does
not promote `PARTIALLY_SUPPORTED` to `SUPPORTED`.

Reviews are immutable revisions. Changes to observations, annotations, derived
semantics or current finding content/approval/citations make previous reviews
stale. Reads detect staleness without writing. Local case mutations share an
incident lock with hypothesis review. Report generation includes only current
accepted reviews, explicitly labeled as hypotheses; review changes invalidate an
existing report's approval.

There is no authenticated analyst identity. The fixed local actor label is
provenance for the demo workflow. Review capacity is 20 revisions per proposition.

## Public and replay inspection

Public case views derive an ephemeral ledger and omit saved local history and
findings. All persistent review actions remain denied. A completed scenario can
also be inspected through its bounded replay evidence, even when it produced only
an observation scope. These views do not create a canonical incident.

Two scenario analyst examples use an explicit deterministic provider in both
public and local mode. They accept fixed example identifiers, not arbitrary
questions, and share the public analyst rate/concurrency budget. Optional OpenAI
remains available only through the existing local case-analysis workflow.

Scenario hypotheses and analyst results describe the **completed scenario**.
Playback must not render their final citations as if they existed at an earlier
cursor. The evaluation labels remain separate from runtime analyst evidence.

## Inspection points

- [Pure hypothesis derivation](../apps/api/aegisgraph/hypotheses.py)
- [Local review and stale-context validation](../apps/api/aegisgraph/hypothesis_workflow.py)
- [API boundaries](../apps/api/aegisgraph/hypothesis_api.py)
- [Report integration](../apps/api/aegisgraph/services.py)
- [ADR-013](adr/ADR-013.md)

API reads include `/api/incidents/{id}/hypotheses`,
`/api/scenarios/{id}/hypotheses`, `/api/hypotheses/{kind}/gaps`, and
`/api/scenarios/{id}/analysis/{summary|malware}`. Local review and history routes
are documented by the local OpenAPI page. Public API documentation stays disabled.
