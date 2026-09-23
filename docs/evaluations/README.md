# Evidence Analyst evaluation

Evaluation separates the current [V2 analyst benchmark](BENCHMARK.md), the historical
28-case deterministic boundary suite, and an explicitly invoked live OpenAI runner.
Their results are never combined into one accuracy score. [Live validation](LIVE_VALIDATION.md)
records the executed live scenarios, earlier HTTP 429 failures, and separately local
scope/citation checks. The rest of this page describes the original boundary suite
and the shared analyst validation contract.

The deterministic suite executes synthetic, isolated fixtures through the same projection, structured-output parser, citation validator, support predicates, and renderer used by Evidence Analyst. It never reads or changes incidents in the application database. Results include an execution ID, timestamps, the fixture version, each case's outcome, and totals calculated from those outcomes.

```bash
# From the repository, after installing the API dependencies
python -m aegisgraph.evaluations
python -m pytest tests/backend/test_ai_analyst.py -q
```

The CLI exits nonzero when any case fails. The application evaluation endpoint calls the same `run_evaluations()` function. This function explicitly constructs deterministic and adversarial fixture providers, regardless of `AI_PROVIDER` or whether an API key exists. Running the evaluation UI does not cause external model calls or change production case state; the API may store the returned evaluation result for display and audit.

## What is measured

The checked-in suite contains 28 cases in `tests/fixtures/ai_cases.json`. The UI computes pass counts and category rates from the results of an actual invocation. Repository tests separately exercise the HTTP provider contract, failure handling, projection types, and output boundaries.

| Category | Checks |
| --- | --- |
| Grounding | Current-context citations; nonexistent citations; arbitrary prose with a valid citation; unsupported claim types; uncited summaries; account/time sequence support |
| False premises | Malware family, SSNs and exfiltration, attacker country, and attacker identity |
| Prompt injection | Instructions in raw telemetry, metadata, annotations, and a poisoned boolean field |
| Data isolation | A foreign incident in input, a foreign-case citation, and an existing citation omitted from bounded context |
| Structured output | Malformed JSON, extra properties, and response size limits |
| Authorization boundary | An unallowed incident, mutation output, a mutation request, and attempted in-memory context tampering |
| Context bounds | Too many evidence rows and an empty evidence context |

**These are application boundary results, not measured live-model prompt-injection robustness.** The injection cases demonstrate that specified free-text channels are excluded and cannot alter deterministic output. The malicious-provider cases demonstrate the validator rejects specified unsafe outputs. The suite does not establish how frequently a live model would attempt those outputs or miss relevant evidence. The returned `live_model_tested` field is `false` and the provider is `deterministic`.

No fixed pass rate is a product capability or performance claim. A passing run covers the named fixtures, with no statistical claim about unseen prompts, languages, model versions, or attack distributions.

## Why a valid citation is insufficient

A model can cite a real login event while claiming it proves malware execution. Checking only that an ID exists would accept that unsupported claim. AegisGraph uses a small typed claim language instead:

1. The API resolves the current incident before retrieving case-scoped evidence. The local demo analyst can access every case; this is not production user or tenant authorization.
2. Evidence must explicitly belong to that incident and fit the context limit.
3. Allowlisted fields are projected into typed observations. Free-form raw data, annotations, user agents, endpoint strings, and metadata text are omitted.
   Analyst-marked benign rows are excluded from the provider context and claim candidates; the answer discloses the exclusion count. Their original immutable telemetry remains in the investigation timeline.
4. Server predicates derive candidate observations and their exact evidence ID sets.
5. The provider selects `claim_type` and `evidence_ids`, with enumerated missing-evidence and next-step values. It cannot return a free-form statement or summary.
6. The validator independently checks the original context, exact support sets, schema, limits, and disposition. A single failure rejects the entire answer.
7. Fixed server templates render accepted claims. The summary repeats at most two accepted findings and includes their citations.

The temporal hypothesis requires anomalous authentication, privileged-role assignment, and sensitive-resource access for the same account, in chronological order within 30 minutes. The output calls possible account misuse a hypothesis. It does not claim a named attacker, malware, confirmed compromise, exfiltration, or particular personal-data fields.

The common false-premise guard conservatively recognizes relevant question phrases and provides a fixed insufficient-evidence response with the evidence needed to investigate. It is not a general natural-language entailment classifier. Novel wording can bypass that question classifier, but cannot add a new factual claim type or arbitrary model prose to the rendered answer.

## Optional real provider

The default `AI_PROVIDER=deterministic` supports the full local investigation flow without credentials. To opt into the model provider, configure all three values in the API process:

```dotenv
AI_PROVIDER=openai
OPENAI_API_KEY=your-local-key
OPENAI_MODEL=your-supported-model-id
```

Use a model available to your account that supports Responses structured output. No model ID or API key is embedded in provider code. Missing or invalid configuration fails safely as `unavailable`; it does not silently impersonate a live model with mock output.

The OpenAI adapter uses a single REST `POST /v1/responses` request. Its `text.format` is `json_schema` with `strict: true`, `store: false`, disabled context truncation, and a 2,000-token output limit. There are no tools, conversation IDs, or previous response IDs. Only the case-scoped projected context is sent; this demo does not implement production user authorization. These request and response conventions were checked against the [official structured-output guide](https://developers.openai.com/api/docs/guides/structured-outputs) during implementation. The adapter handles refusals, incomplete output, HTTP errors, malformed envelopes, unexpected tool output, and excessive response size before application validation.

The HTTP adapter's integration tests use `httpx.MockTransport` and do not contact a model. Actual credentialed validation was also executed on 2026-09-17 UTC: three named live scenarios ultimately passed over six harness requests, with three earlier HTTP 429 failures preserved in the attempt history. Five local application-boundary checks passed separately. Two additional grounded/false-premise calls succeeded through the production-built browser application. See [the detailed record](LIVE_VALIDATION.md) for exact outcomes and limitations.

The ignored root `.env` loads without overriding explicit process values. Its values are not copied into evaluation records. Workstation `.env` loading is disabled in tests, and the deterministic suite explicitly chooses fixture providers even when live configuration exists.

## Opt-in live runner

With dependencies installed, the database migrated/seeded, and provider variables configured locally:

```sh
# External calls require explicit opt-in and may incur charges.
python -m aegisgraph.live_evaluations --run-live --incident-id INC-fe8fa4b9508c --persist
```

The default scenario ID is shown above; use the current case ID if the dataset changes. The runner sends at most three bounded scenario requests, has no automatic retry, and stops further live calls when a provider request is unavailable. It separately runs local scope/citation checks with test doubles. `--persist` stores only the sanitized result for display; it does not mutate incident state or evidence. A later explicit run replaces the checked-in result/attempt files, so preserve an earlier run if its history matters.

Recorded output allowlists fields and values: fixed case labels, enumerated safe statuses/errors, counts, booleans and timestamps. It excludes keys, headers, configured model values, raw provider prose and exception text. The configured model was checked against official provider documentation before execution and intentionally omitted from records.

`GET /api/evaluations` reads deterministic results; `GET /api/evaluations/live` reads recorded live results without calling the provider. The evaluation page's run action remains deterministic. Case totals describe the latest recorded outcome for each scenario; request totals retain earlier failed attempts. Neither is a general model-accuracy or injection-resistance rate.

## Bounds and error behavior

- The analyst boundary accepts at most 80 evidence rows, while application retrieval can apply a smaller limit. It rejects excess input instead of silently taking a subset.
- Question length is at most 2,000 characters; the serialized projected context is at most 64,000 UTF-8 bytes.
- Drafts contain at most 12 claims, each with 1–8 citations, and at most 24,000 UTF-8 bytes.
- The HTTP response is streamed into a bounded 128,000-byte buffer. Requests use a 30-second timeout and a 5-second connection timeout, without redirects.
- Invalid input scope is rejected before provider execution. Invalid output returns no findings. Unavailable providers do not yield partial answers.
- Logs contain provider/status/count/error metadata, not questions, prompts, raw model output, or keys. The backend records the safe analysis result and audit metadata according to its persistence policy.

## Limits and future measurement

Grounding here means consistency with typed synthetic telemetry, not proof that a telemetry source is truthful. A compromised producer can forge correctly typed events. Human investigation, source integrity, provenance verification, and corroborating records remain necessary. The fixed templates are subject to engineering review: a defective predicate or misleading template can still overstate evidence.

The restricted claim vocabulary intentionally gives up open-ended model-written factual narratives. This removes the need to trust a general semantic entailment judge for displayed findings. It does not solve relevance, completeness, or causal inference. A model may omit important observations, select supported but unhelpful observations, or return insufficient evidence unnecessarily. An accepted temporal pattern supports investigation, not proof of account takeover.

Adding arbitrary prose later would reintroduce natural-language entailment risk; valid citations and schema validation would not be enough. Such a change requires separately reviewed claim support mechanisms and live-model evaluation.

The implemented live runner is a small deployment check, not a statistically designed benchmark. Future measurement should add approved provenance for model/version and fixture revision, repeated trials, omissions, false refusals and confidence intervals where justified, without retaining secrets or unnecessary raw responses. Keep those results separate from deterministic boundary tests, and do not extrapolate a small test set into a universal prompt-injection-resistance percentage.
