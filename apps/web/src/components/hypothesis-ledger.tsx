"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, errorMessage } from "@/lib/api";
import { dateTime, humanize } from "@/lib/format";
import type { Finding } from "@/lib/types";
import type {
  Hypothesis,
  HypothesisData,
  ReplayProvenance,
} from "@/lib/hypothesis-types";
import { usePublicDemo } from "./demo-mode";
import { Badge, ErrorNotice } from "./ui";

interface Props {
  endpoint: string;
  readOnly?: boolean;
  incidentId?: string;
  findings?: Finding[];
  onEvidence: (id: string) => void;
  onChanged?: () => Promise<void>;
  expectedScopeId?: string;
  expectedProvenance?: ReplayProvenance;
}

export function HypothesisLedger(props: Props) {
  return (
    <LedgerContent
      key={`${props.endpoint}:${props.expectedScopeId}:${props.expectedProvenance?.scenario_id}:${props.expectedProvenance?.scenario_version}:${props.expectedProvenance?.ruleset_digest}`}
      {...props}
    />
  );
}

function LedgerContent({
  endpoint,
  readOnly = false,
  incidentId,
  findings = [],
  onEvidence,
  onChanged,
  expectedScopeId,
  expectedProvenance,
}: Props) {
  const publicDemo = usePublicDemo();
  const [ledger, setLedger] = useState<HypothesisData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  const [saved, setSaved] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const { scenario_id, scenario_version, ruleset_digest } =
    expectedProvenance || {};
  const load = useCallback(() => {
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    const operation = ++generation.current;
    return api<HypothesisData>(endpoint, {
      signal: request.signal,
    })
      .then((result) => {
        if (operation !== generation.current || request.signal.aborted) return;
        const scope = expectedScopeId || incidentId;
        if (
          (scope && result.scope_id !== scope) ||
          (scenario_id &&
            (result.provenance?.scenario_id !== scenario_id ||
              result.provenance?.scenario_version !== scenario_version ||
              result.provenance?.ruleset_digest !== ruleset_digest))
        )
          throw new Error(
            "Rules or scope changed; reset and reload replay before inspecting hypotheses.",
          );
        setError(null);
        setLedger(result);
      })
      .catch((err: unknown) => {
        if (operation === generation.current && !request.signal.aborted) {
          setLedger(null);
          setError(errorMessage(err));
        }
      })
      .finally(() => {
        if (operation === generation.current && !request.signal.aborted)
          setBusy(false);
      });
  }, [
    endpoint,
    expectedScopeId,
    incidentId,
    scenario_id,
    scenario_version,
    ruleset_digest,
  ]);
  useEffect(() => {
    void load();
    return () => {
      controller.current?.abort();
    };
  }, [load]);
  const canReview =
    !publicDemo &&
    !readOnly &&
    ledger?.read_only === false &&
    !!incidentId &&
    !!ledger.context_digest;

  async function review(
    row: Hypothesis,
    decision: string,
    reason: string,
    related: string[],
  ) {
    if (!canReview || !ledger || !reason.trim() || busy) return;
    const operation = ++generation.current;
    const request = new AbortController();
    controller.current = request;
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await api(
        `/incidents/${encodeURIComponent(incidentId!)}/hypotheses/${encodeURIComponent(row.kind)}/review`,
        {
          method: "POST",
          signal: request.signal,
          body: JSON.stringify({
            expected_version: row.review.version,
            context_digest: ledger.context_digest,
            review_status: decision,
            related_finding_ids: related,
            reason: reason.trim(),
          }),
        },
      );
      if (operation !== generation.current || request.signal.aborted) return;
      setSaved(true);
      await load();
      await onChanged?.();
    } catch (err) {
      if (operation === generation.current && !request.signal.aborted) {
        // A failed write response can be ambiguous. Require fresh context before retrying.
        setLedger(null);
        setError(
          err instanceof ApiError && err.status === 409
            ? "Case context or review version changed. Reload hypotheses before reviewing again."
            : `${errorMessage(err)} Reload hypotheses to check the current review before retrying.`,
        );
      }
    } finally {
      if (operation === generation.current && !request.signal.aborted)
        setBusy(false);
    }
  }
  return (
    <section
      className="panel-body hypothesis-ledger"
      aria-label="Hypothesis ledger"
    >
      <h2>Hypothesis ledger</h2>
      <p className="page-note">
        Evidence-derived status and human review are separate. Accepting a
        working hypothesis does not confirm it. No probabilities are assigned.
      </p>
      <ErrorNotice message={error} />
      {busy && <p role="status">Loading current hypothesis context…</p>}
      {saved && (
        <p role="status" className="notice success">
          Human review saved. Evidence-derived status is unchanged.
        </p>
      )}
      {!busy && (
        <button
          className="button secondary"
          onClick={() => {
            setSaved(false);
            setBusy(true);
            setError(null);
            setLedger(null);
            void load();
          }}
        >
          Reload hypotheses
        </button>
      )}
      {ledger && (
        <>
          {!canReview && (
            <p className="read-only-note">
              Read-only evidence assessment. Human review is available on stored
              incidents in local mode.
            </p>
          )}
          {ledger.items.map((row) => (
            <article
              className="hypothesis-card"
              key={`${row.id}:${row.review.version}:${ledger.context_digest || ledger.evidence_digest}`}
            >
              <div className="inline-meta">
                <span className="mono">{row.id}</span>
                <Badge value={row.epistemic_status.toLowerCase()} />
              </div>
              <h3>{row.title}</h3>
              <div className="hypothesis-evidence">
                <Citations
                  title="Supporting evidence"
                  ids={row.supporting_evidence_ids}
                  onEvidence={onEvidence}
                />
                <Citations
                  title="Contradicting evidence"
                  ids={row.contradicting_evidence_ids}
                  onEvidence={onEvidence}
                />
              </div>
              <details className="hypothesis-gaps">
                <summary>What would confirm or reject this?</summary>
                <p className="page-note">
                  These are investigation gaps, not observed facts.
                </p>
                <ul>
                  {row.missing_evidence.map((gap) => (
                    <li key={gap.category}>
                      <strong>{humanize(gap.category)}</strong>
                      <p>{gap.guidance}</p>
                    </li>
                  ))}
                </ul>
              </details>
              <dl className="detail-grid">
                <div>
                  <dt>Human review</dt>
                  <dd>
                    {humanize(row.review.status)} · revision{" "}
                    {row.review.version}
                  </dd>
                </div>
                <div>
                  <dt>Evidence as of</dt>
                  <dd>
                    {row.as_of ? dateTime(row.as_of) : "No scoped observations"}
                  </dd>
                </div>
              </dl>
              {row.review.status === "stale" && (
                <p className="notice">
                  The recorded {row.review.recorded_status} review applies to
                  older evidence or findings. Review the current context again.
                </p>
              )}
              {row.review.reason && (
                <blockquote>
                  {row.review.reason}
                  <p className="page-note">
                    {row.review.actor_label || "Local analyst"} ·{" "}
                    {row.review.created_at
                      ? dateTime(row.review.created_at)
                      : "Time unavailable"}{" "}
                    · unauthenticated actor label
                  </p>
                </blockquote>
              )}
              {row.review.related_finding_ids.length > 0 && (
                <p className="page-note">
                  Related findings: {row.review.related_finding_ids.join(", ")}
                </p>
              )}
              <details className="source-details">
                <summary>Inspect hypothesis provenance</summary>
                <pre>{JSON.stringify(row.provenance, null, 2)}</pre>
              </details>
              {canReview && (
                <ReviewForm
                  row={row}
                  findings={findings}
                  busy={busy}
                  onReview={review}
                />
              )}
            </article>
          ))}
        </>
      )}
    </section>
  );
}

function Citations({
  title,
  ids,
  onEvidence,
}: {
  title: string;
  ids: string[];
  onEvidence: (id: string) => void;
}) {
  return (
    <div>
      <h4>{title}</h4>
      {ids.length ? (
        <div className="citation-list">
          {ids.map((id) => (
            <button
              className="evidence-citation"
              key={id}
              onClick={() => onEvidence(id)}
            >
              {id}
            </button>
          ))}
        </div>
      ) : (
        <p className="page-note">None established in this evidence set.</p>
      )}
    </div>
  );
}

function ReviewForm({
  row,
  findings,
  busy,
  onReview,
}: {
  row: Hypothesis;
  findings: Finding[];
  busy: boolean;
  onReview: (
    row: Hypothesis,
    decision: string,
    reason: string,
    related: string[],
  ) => Promise<void>;
}) {
  const [decision, setDecision] = useState("open");
  const [reason, setReason] = useState("");
  const [related, setRelated] = useState<string[]>(
    row.review.related_finding_ids,
  );
  return (
    <form
      className="hypothesis-review"
      onSubmit={(event) => {
        event.preventDefault();
        void onReview(row, decision, reason, related);
      }}
    >
      <div className="form-field">
        <label htmlFor={`${row.id}-decision`}>Human decision</label>
        <select
          id={`${row.id}-decision`}
          value={decision}
          onChange={(e) => setDecision(e.target.value)}
          disabled={busy}
        >
          <option value="open">Keep open</option>
          <option value="accepted">Accept as working hypothesis</option>
          <option value="rejected">Reject working hypothesis</option>
        </select>
      </div>
      <div className="form-field">
        <label htmlFor={`${row.id}-reason`}>Review reason</label>
        <textarea
          id={`${row.id}-reason`}
          required
          maxLength={1000}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          disabled={busy}
        />
      </div>
      {findings.length > 0 && (
        <fieldset>
          <legend>Related case findings (up to 10)</legend>
          {findings.map((finding) => (
            <label className="finding-choice" key={finding.id}>
              <input
                type="checkbox"
                checked={related.includes(finding.id)}
                disabled={
                  busy ||
                  (!related.includes(finding.id) && related.length >= 10)
                }
                onChange={(e) =>
                  setRelated(
                    e.target.checked
                      ? [...related, finding.id]
                      : related.filter((id) => id !== finding.id),
                  )
                }
              />
              {finding.title} · {finding.id}
            </label>
          ))}
        </fieldset>
      )}
      <button
        className="button primary"
        disabled={busy || !reason.trim() || row.review.version >= 20}
      >
        Save human review
      </button>
      {row.review.version >= 20 && (
        <p className="page-note">
          This hypothesis has reached its bounded review history capacity.
        </p>
      )}
    </form>
  );
}
