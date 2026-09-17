"use client";
import { useEffect, useState } from "react";
import { Check, Download, FileText, Plus, RotateCcw, Save } from "lucide-react";
import type { Evidence, Finding, Incident, IncidentReport } from "@/lib/types";
import { api, ApiError, errorMessage } from "@/lib/api";
import { dateTime, eventLabel, humanize, time } from "@/lib/format";
import { CitedText, type FindingDraft } from "./evidence-analyst";
import { Badge, Empty, ErrorNotice } from "./ui";

export function Findings({
  incident,
  draft,
  onEvidence,
  refresh,
}: {
  incident: Incident;
  draft: FindingDraft | null;
  onEvidence: (id: string) => void;
  refresh: () => Promise<void>;
}) {
  const [title, setTitle] = useState(draft?.title || ""),
    [narrative, setNarrative] = useState(draft?.narrative || ""),
    [evidenceIds, setEvidenceIds] = useState<string[]>(
      draft?.evidence_ids || [],
    ),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<string | null>(null);
  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api(`/incidents/${encodeURIComponent(incident.id)}/findings`, {
        method: "POST",
        body: JSON.stringify({
          title,
          narrative,
          evidence_ids: evidenceIds,
          ai_assisted: draft?.ai_assisted || false,
          approved: false,
        }),
      });
      await refresh();
      setTitle("");
      setNarrative("");
      setEvidenceIds([]);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  async function approve(finding: Finding) {
    setBusy(true);
    setError(null);
    try {
      await api(
        `/incidents/${encodeURIComponent(incident.id)}/findings/${encodeURIComponent(finding.id)}`,
        { method: "PATCH", body: JSON.stringify({ approved: true }) },
      );
      await refresh();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="timeline-heading">
        <div>
          <h2>Analyst findings</h2>
          <p>Cited conclusions require explicit human approval.</p>
        </div>
      </div>
      {incident.findings.length ? (
        incident.findings.map((finding) => (
          <article className="finding-card" key={finding.id}>
            <div className="inline-meta">
              <Badge value={finding.approved ? "approved" : "draft"} />
              <span className="source-chip">
                {finding.ai_assisted
                  ? "AI-assisted · analyst saved"
                  : "Analyst authored"}
              </span>
            </div>
            <h3 style={{ marginTop: 12 }}>{finding.title}</h3>
            <p>{finding.narrative}</p>
            <div className="citation-group">
              {finding.evidence_ids.map((id) => (
                <button
                  key={id}
                  className="evidence-citation"
                  onClick={() => onEvidence(id)}
                >
                  {id}
                </button>
              ))}
            </div>
            <footer>
              <span>
                {finding.author || "Local analyst"} ·{" "}
                {dateTime(finding.created_at)}
              </span>
              {!finding.approved && (
                <button
                  className="button secondary small"
                  disabled={busy}
                  onClick={() => approve(finding)}
                >
                  <Check size={13} />
                  Approve finding
                </button>
              )}
            </footer>
          </article>
        ))
      ) : (
        <Empty title="No findings recorded">
          Turn evidence into a supported conclusion, then approve it after
          review.
        </Empty>
      )}
      <hr className="section-divider" />
      <form className="finding-form" onSubmit={save}>
        <h3>{draft ? "Review AI-assisted draft" : "Create a finding"}</h3>
        {draft && (
          <div className="notice warning">
            Review the narrative and every cited source before saving. Saving
            creates an unapproved draft.
          </div>
        )}
        <div className="form-field">
          <label htmlFor="finding-title">Finding title</label>
          <input
            id="finding-title"
            required
            maxLength={200}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="State the supported conclusion"
          />
        </div>
        <div className="form-field">
          <label htmlFor="finding-narrative">Narrative</label>
          <textarea
            id="finding-narrative"
            required
            maxLength={5000}
            value={narrative}
            onChange={(e) => setNarrative(e.target.value)}
            placeholder="Explain what the evidence supports and where uncertainty remains…"
          />
        </div>
        <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
          <legend className="field-label" style={{ marginBottom: 8 }}>
            Supporting evidence ({evidenceIds.length} selected)
          </legend>
          <div className="evidence-select-list">
            {incident.evidence.map((item) => (
              <label className="checkbox-row" key={item.id}>
                <input
                  type="checkbox"
                  checked={evidenceIds.includes(item.id)}
                  onChange={(e) =>
                    setEvidenceIds(
                      e.target.checked
                        ? [...evidenceIds, item.id]
                        : evidenceIds.filter((id) => id !== item.id),
                    )
                  }
                />
                <span>
                  <span className="mono">{item.id}</span> ·{" "}
                  {time(item.timestamp)} · {eventLabel(item.event)}
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        <ErrorNotice message={error} />
        <button
          className="button primary"
          disabled={
            busy || !evidenceIds.length || !title.trim() || !narrative.trim()
          }
          type="submit"
        >
          <Plus size={14} />
          {busy ? "Saving…" : "Save finding draft"}
        </button>
      </form>
    </>
  );
}

export function NotesAndAudit({
  incident,
  refresh,
}: {
  incident: Incident;
  refresh: () => Promise<void>;
}) {
  const [text, setText] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<string | null>(null);
  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api(`/incidents/${encodeURIComponent(incident.id)}/notes`, {
        method: "POST",
        body: JSON.stringify({ text }),
      });
      await refresh();
      setText("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="timeline-heading">
        <div>
          <h2>Analyst notes</h2>
          <p>Record questions, decisions, and follow-up context.</p>
        </div>
      </div>
      {incident.notes.length ? (
        <ul className="notes-list">
          {incident.notes.map((note) => (
            <li key={note.id}>
              <p>{note.text}</p>
              <small>
                {note.author || note.actor || "Local analyst"} ·{" "}
                {dateTime(note.created_at)}
              </small>
            </li>
          ))}
        </ul>
      ) : (
        <Empty title="No notes yet" />
      )}
      <form className="finding-form" onSubmit={save}>
        <div className="form-field">
          <label htmlFor="analyst-note">Add a note</label>
          <textarea
            id="analyst-note"
            required
            maxLength={5000}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Add investigation context…"
          />
        </div>
        <ErrorNotice message={error} />
        <button
          type="submit"
          className="button secondary"
          disabled={busy || !text.trim()}
        >
          <Save size={14} />
          {busy ? "Saving…" : "Save note"}
        </button>
      </form>
      <hr className="section-divider" />
      <div className="timeline-heading">
        <div>
          <h2>Audit history</h2>
          <p>
            Recorded actors distinguish system processing from analyst actions.
            AI-assisted findings retain their analyst author.
          </p>
        </div>
      </div>
      <ul className="audit-list">
        {incident.audit
          .slice()
          .reverse()
          .map((entry) => (
            <li key={entry.id}>
              <div>
                <strong>{humanize(entry.action)}</strong> · {entry.actor}
                <span className="audit-actor-type">
                  {entry.actor_type === "system"
                    ? "System"
                    : entry.actor_type === "human"
                      ? "Analyst"
                      : entry.actor_type === "model"
                        ? "Model"
                        : "Unspecified"}
                </span>
                {entry.action === "finding_created" &&
                  entry.after !== null &&
                  typeof entry.after === "object" &&
                  "ai_assisted" in entry.after &&
                  entry.after.ai_assisted === true && (
                    <span className="audit-actor-type">
                      AI-assisted finding
                    </span>
                  )}
              </div>
              <time>{dateTime(entry.timestamp)}</time>
              {entry.before || entry.after ? (
                <details>
                  <summary>Change details</summary>
                  <pre>
                    {JSON.stringify(
                      { before: entry.before, after: entry.after },
                      null,
                      2,
                    )}
                  </pre>
                </details>
              ) : null}
            </li>
          ))}
      </ul>
    </>
  );
}

function downloadReport(report: IncidentReport) {
  const url = URL.createObjectURL(
    new Blob([report.content], { type: "text/markdown;charset=utf-8" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = `aegisgraph-${report.incident_id}-${report.status}.md`;
  link.click();
  URL.revokeObjectURL(url);
}

export function ReportPanel({
  incidentId,
  refresh,
  evidence,
  onEvidence,
}: {
  incidentId: string;
  refresh: () => Promise<void>;
  evidence: Evidence[];
  onEvidence: (id: string) => void;
}) {
  const [report, setReport] = useState<IncidentReport | null>(null),
    [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [reviewed, setReviewed] = useState(false),
    [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    api<IncidentReport>(`/incidents/${encodeURIComponent(incidentId)}/report`)
      .then((data) => {
        if (!cancelled) setReport(data);
      })
      .catch((err) => {
        if (!cancelled && !(err instanceof ApiError && err.status === 404))
          setError(errorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [incidentId]);
  async function generate() {
    setBusy(true);
    setError(null);
    setReviewed(false);
    try {
      setReport(
        await api<IncidentReport>(
          `/incidents/${encodeURIComponent(incidentId)}/report`,
          { method: "POST" },
        ),
      );
      await refresh();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  async function approve() {
    setBusy(true);
    setError(null);
    try {
      setReport(
        await api<IncidentReport>(
          `/incidents/${encodeURIComponent(incidentId)}/report/approve`,
          { method: "POST" },
        ),
      );
      await refresh();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  if (loading)
    return (
      <div className="loading-state" role="status">
        Loading report…
      </div>
    );
  return (
    <>
      <div className="timeline-heading">
        <div>
          <h2>Incident report</h2>
          <p>Evidence-grounded summary for analyst review.</p>
        </div>
        {report && <Badge value={report.status} />}
      </div>
      <div style={{ padding: "0 20px" }}>
        <ErrorNotice message={error} />
      </div>
      {report ? (
        <>
          {report.status === "stale" && (
            <div className="notice warning" style={{ margin: "0 20px" }}>
              This incident changed after the report was generated. Regenerate
              the report and review the current evidence before approving.
            </div>
          )}
          <div className="report-content">
            <CitedText
              text={report.content}
              allowedIds={new Set(evidence.map((item) => item.id))}
              onEvidence={onEvidence}
            />
          </div>
          {report.status === "draft" && (
            <label className="checkbox-row" style={{ padding: "0 20px 20px" }}>
              <input
                type="checkbox"
                checked={reviewed}
                onChange={(e) => setReviewed(e.target.checked)}
              />
              <span>
                I have reviewed this report and its supporting evidence.
              </span>
            </label>
          )}
          <div className="report-controls">
            {report.status === "draft" && (
              <button
                className="button primary"
                disabled={busy || !reviewed}
                onClick={approve}
              >
                <Check size={14} />
                Approve report
              </button>
            )}
            <button
              className="button secondary"
              disabled={busy}
              onClick={generate}
            >
              <RotateCcw size={14} />
              {busy ? "Working…" : "Regenerate draft"}
            </button>
            <button
              className="button ghost"
              onClick={() => downloadReport(report)}
            >
              <Download size={14} />
              Download Markdown
            </button>
          </div>
          {report.approved_at && (
            <p className="page-note" style={{ padding: "0 20px 20px" }}>
              Approved by {report.approved_by} · {dateTime(report.approved_at)}
            </p>
          )}
        </>
      ) : (
        <>
          <Empty title="Ready for a reviewable report">
            Generate a draft from this incident’s scoped evidence, findings, and
            analyst decisions.
          </Empty>
          <div className="report-controls">
            <button
              className="button primary"
              onClick={generate}
              disabled={busy}
            >
              <FileText size={14} />
              {busy ? "Generating…" : "Generate report draft"}
            </button>
          </div>
        </>
      )}
    </>
  );
}
