# Deterministic analyst benchmark

The V2 benchmark measures named application obligations on synthetic fixtures. It
executes the same evidence projection, support predicates, structured-output
validation, citation checks, and fixed renderer as the analyst. It uses only
deterministic and adversarial fixture providers. It makes no external model calls,
requires no key, and opens no database session.

```sh
python -m aegisgraph.cli evaluate-benchmark
```

A failed obligation makes the command exit nonzero. Public CI runs this command.
`GET /api/evaluations/benchmark` executes and caches the versioned benchmark in
process, returning a fresh copy of the bounded result. It accepts no query
parameters, provider selection, uploaded fixtures, or arbitrary questions. A
single lock prevents duplicate cold runs. There is no persisted evaluation write.

## Inspection and measurement

- [Named fixture obligations](../../tests/fixtures/analyst_benchmark.json)
- [Runner and metric definitions](../../apps/api/aegisgraph/analyst_benchmark.py)
- [Independent scenario expectations](../../apps/api/aegisgraph/scenario_ground_truth.py)
- [Runner tests](../../tests/backend/test_analyst_benchmark.py)

Each result contains an ID, category, expected observation, actual observation, and
pass/fail outcome. Totals are calculated from execution, including failures.
Metrics report their own explicit denominator and definition. A case may test
more than one boundary, so metric totals are not an independent sample population.

The version 1 manifest contains 145 named obligations. Inspect the executed result
for its current counts; this is a fixture count, not a model-performance claim.
The eight metric groups cover citation validity, claim support, unsupported-claim
rejection, insufficient-evidence behavior, case isolation, context containment,
schema validity, and narrow counterevidence. Pure schema errors are excluded from
the unsupported-claim denominator. Hypothesis counterevidence is reported separately
from the analyst's factual claim support.

Coverage includes the eight scenarios, supported questions, common false premises,
missing evidence, benign and mixed context, typed signal boundaries, prompt-like
telemetry, malformed drafts, nonexistent/foreign/omitted citations, unsupported
claims with real citations, context limits, and attempted model mutation.
Question variations cover named phrases; they do not establish general language
understanding. Contradictory approval/job context belongs in the hypothesis ledger;
the analyst's narrower projection does not receive evaluator labels as an answer key.

Result provenance identifies the fixture, corpus, and baseline ruleset with
SHA-256 digests. Timing goes to operational metadata, not the deterministic result.
Local rule proposals do not alter this baseline analyst benchmark; the separate
[detection workbench](../DETECTION_WORKBENCH.md) measures those proposals.

## Three separate records

| Record | Meaning |
|---|---|
| V2 benchmark | Current, code-backed deterministic application obligations, read without persistence |
| Original 28 cases | Version 1 suite and stored evaluation/audit record, preserved for deployment compatibility |
| [Live validation](LIVE_VALIDATION.md) | Historical, explicitly credentialed OpenAI execution with its own limitations |

The hosted dataset readiness check still validates the original stored 28-case
record. The new benchmark does not rewrite that record or manufacture a new
historical timestamp. Its deterministic bytes remain the same for the same code
and fixtures. Restarting the process recomputes its cache.

These results are not model accuracy, statistical precision/recall, production
detection effectiveness, or universal prompt-injection resistance. They establish
only whether the named fixtures satisfy their application obligations. Correctly
typed but forged source telemetry, predicate defects, omissions, and novel
question wording remain limitations; see [evaluation methodology](README.md).
