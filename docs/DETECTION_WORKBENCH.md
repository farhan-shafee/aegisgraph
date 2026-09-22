# Detection tuning and regression

The local workbench compares an immutable proposed rule revision with the current
ruleset across all eight [synthetic scenarios](../packages/synthetic-data/README.md).
Public mode exposes the shipped rules and three fixed comparisons. It cannot save
rule proposals, run arbitrary parameter comparisons, or approve revisions.

## Local review cycle

1. Inspect a rule's effective parameters and version. Only parameters used by that
   detector are offered; values are bounded integers, with no expressions or code.
2. Propose a change with a reason. The proposal records the complete baseline
   ruleset digest, its generation and the selected rule's parent version.
3. Run the corpus comparison. Inspect individual scenarios, changed signals,
   correlation outcomes and gate reasons.
4. Approve or reject with a human reason. Approval recomputes the result and
   rejects an obsolete baseline or a blocking result. A WARN result requires
   deliberate review; it is not evidence that the change improved detection.
5. Replay a scenario. Approved local rules affect subsequent projections without
   rewriting historical events, alerts or the canonical Atlas investigation.

The analyst label is a local attribution label, not an authenticated identity.
Revision snapshots, regression results and reviews are append-only. A generation
check makes simultaneous approvals compete against the same complete ruleset,
including when the proposals change different rules.

Local storage is bounded to 100 proposals, 20 recent revisions per workbench view,
and 10 runs per proposal (including the reserved approval recomputation). A local
revision-detail read exposes saved results and review provenance after refresh.
Approval also requires the reviewed run to match the current corpus and rule
digests; a changed corpus requires a new comparison and review.

## What the measurements mean

Every comparison evaluates the complete ruleset before and after the change.
This matters because authentication novelty also influences MFA and privilege
sequence signals. Results identify the corpus and both rulesets by SHA-256 digest.

The selected-rule confusion matrix has explicit populations:

- TP/FN count scenarios that independently require the selected rule, according to
  whether it fired.
- FP/TN count scenarios labeled benign, according to whether it fired.
- Other scenarios remain in the full regression and correlation checks but are
  excluded from that selected-rule matrix. The response reports every denominator.

These are **synthetic fixture measurements**, not measured real-world precision,
recall, production accuracy or a security guarantee. An expected baseline firing
on a benign fixture is an observation to inspect, not a required detection that
must be preserved.

| Gate | Interpretation |
|---|---|
| BLOCK | Required detection missing, forbidden detection present, or labeled correlation outcome violated |
| WARN | No measured improvement, or increased permitted alert burden on benign fixtures |
| PASS | Measured improvement without a blocking policy violation |

## Reproducible volume examples

The shipped APP-002 threshold is 1,000 records. The original description's normal
query baseline refers to Atlas background queries (at most 90), not every benign
workflow. The corpus also contains approved reconciliation reading 1,200 records,
a service-principal sequence reading 1,800, and Atlas access reading 2,400.

| Proposed threshold | Observed tradeoff | Gate |
|---|---|---|
| 1,500 | Removes the benign reconciliation signal while retaining both required volume signals | PASS |
| 1,100 | Leaves those fixture outcomes unchanged | WARN |
| 2,200 | Loses the required service-principal volume signal and its correlated incident | BLOCK |

These outcomes are computed from telemetry and independent labels by the same
comparison function used for local review; they are not saved flattering scores.
Passing them says nothing about unmodeled traffic or a different threat model.

## Inspection points

- [Typed rule definitions](../apps/api/aegisgraph/rule_specs.py)
- [Corpus comparison and gate policy](../apps/api/aegisgraph/regressions.py)
- [Local revision and review service](../apps/api/aegisgraph/rule_workflow.py)
- [Independent scenario labels](../apps/api/aegisgraph/scenario_ground_truth.py)
- [Replay architecture](REPLAY.md)
- [ADR-012](adr/ADR-012.md)

The API exposes `GET /api/detections/{rule_id}/workbench` and fixed examples at
`GET /api/regressions/examples/{example_id}`. Local proposal, regression and review
routes are documented by the local OpenAPI page. Public OpenAPI remains disabled.
Stored detection-catalog alert counts describe canonical historical alerts; they
are not silently recomputed after approval.
