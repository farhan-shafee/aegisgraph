"use client";
import { useState } from "react";
import {
  ArrowUpRight,
  FilePenLine,
  LockKeyhole,
  Send,
  Sparkles,
} from "lucide-react";
import type { Analysis } from "@/lib/types";
import { api, errorMessage } from "@/lib/api";
import { humanize } from "@/lib/format";
import { Badge, ErrorNotice, Panel } from "./ui";
export interface FindingDraft {
  title: string;
  narrative: string;
  evidence_ids: string[];
  ai_assisted: boolean;
}
export function CitedText({
  text,
  allowedIds,
  onEvidence,
}: {
  text: string;
  allowedIds: Set<string>;
  onEvidence: (id: string) => void;
}) {
  return (
    <>
      {text.split(/(EVD-[a-zA-Z0-9-]+)/g).map((part, index) =>
        allowedIds.has(part) ? (
          <button
            key={index}
            className="evidence-citation"
            aria-label={`Inspect evidence ${part}`}
            onClick={() => onEvidence(part)}
          >
            {part}
          </button>
        ) : (
          <span key={index}>{part}</span>
        ),
      )}
    </>
  );
}
export function EvidenceAnalyst({
  incidentId,
  evidenceCount,
  onEvidence,
  onDraft,
  onComplete,
}: {
  incidentId: string;
  evidenceCount: number;
  onEvidence: (id: string) => void;
  onDraft: (draft: FindingDraft) => void;
  onComplete: () => Promise<void>;
}) {
  const [question, setQuestion] = useState(""),
    [answer, setAnswer] = useState<Analysis | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<string | null>(null),
    [asked, setAsked] = useState("");
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    setBusy(true);
    setError(null);
    setAnswer(null);
    setAsked(question);
    try {
      const result = await api<Analysis>(
        `/incidents/${encodeURIComponent(incidentId)}/analysis`,
        { method: "POST", body: JSON.stringify({ question: question.trim() }) },
      );
      setAnswer(result);
      await onComplete();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  const allowedIds = new Set(
    answer?.findings.flatMap((finding) => finding.evidence_ids) || [],
  );
  return (
    <Panel className="analyst-panel">
      <div className="panel-heading">
        <div className="analyst-heading">
          <span className="analyst-icon">
            <Sparkles size={17} />
          </span>
          <div>
            <h2>Evidence Analyst</h2>
            <p>Grounded in this investigation</p>
          </div>
        </div>
        <span className="badge">READ ONLY</span>
      </div>
      <div className="analyst-intro">
        <strong>Ask a question. Inspect the evidence.</strong>Answers are
        limited to this incident’s evidence. Every factual finding must cite a
        source.
      </div>
      <div className="suggested-questions">
        {["What most likely happened?", "What malware family was used?"].map(
          (text) => (
            <button key={text} type="button" onClick={() => setQuestion(text)}>
              {text}
              <ArrowUpRight size={12} />
            </button>
          ),
        )}
      </div>
      <form onSubmit={submit} className="analyst-form">
        <label htmlFor="analyst-question" className="field-label">
          Investigation question
        </label>
        <textarea
          id="analyst-question"
          value={question}
          maxLength={2000}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about the sequence, supported findings, or gaps…"
          required
        />
        <div className="analyst-form-footer">
          <small>{evidenceCount} evidence items in this case</small>
          <button
            className="button primary"
            type="submit"
            disabled={busy || !question.trim()}
          >
            <Send size={13} />
            {busy ? "Analyzing…" : "Ask analyst"}
          </button>
        </div>
        <ErrorNotice message={error} />
      </form>
      {busy && (
        <div className="notice" role="status" style={{ margin: "0 20px 18px" }}>
          Retrieving scoped evidence and validating the response…
        </div>
      )}
      {answer && (
        <section
          className={`analysis-answer answer-${answer.status}`}
          aria-live="polite"
          aria-label="Analyst response"
        >
          <div className="inline-meta">
            <Badge value={answer.status} />
            <span className="source-chip">{answer.confidence} confidence</span>
          </div>
          <p className="answer-question">{asked}</p>
          <div className="answer-context">
            <span>Provider: {answer.provider}</span>
            <span>
              {answer.context_evidence_count} evidence items retrieved
            </span>
          </div>
          <h3>
            {answer.status === "insufficient_evidence"
              ? "What the evidence cannot establish"
              : "Summary"}
          </h3>
          <p>
            <CitedText
              text={answer.summary}
              allowedIds={allowedIds}
              onEvidence={onEvidence}
            />
          </p>
          {answer.context_notice && (
            <div className="notice warning" style={{ marginTop: 12 }}>
              {answer.context_notice}
            </div>
          )}
          {answer.findings.length > 0 && (
            <>
              <h3 className="answer-section-title">
                Findings <span>{answer.findings.length}</span>
              </h3>
              <ul className="analysis-findings">
                {answer.findings.map((finding, index) => (
                  <li key={index}>
                    <div className="finding-number">
                      Finding {String(index + 1).padStart(2, "0")}
                      {finding.claim_type && (
                        <span>{humanize(finding.claim_type)}</span>
                      )}
                    </div>
                    <p>{finding.statement}</p>
                    <div className="citation-group">
                      {finding.evidence_ids.map((id) => (
                        <button
                          className="evidence-citation"
                          key={id}
                          onClick={() => onEvidence(id)}
                          aria-label={`Inspect evidence ${id}`}
                        >
                          {id}
                        </button>
                      ))}
                    </div>
                    <button
                      className="button ghost small"
                      style={{ marginTop: 11 }}
                      onClick={() =>
                        onDraft({
                          title: finding.statement.slice(0, 150),
                          narrative: finding.statement,
                          evidence_ids: finding.evidence_ids,
                          ai_assisted: true,
                        })
                      }
                    >
                      <FilePenLine size={12} />
                      Review as finding
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
          {answer.missing_evidence.length > 0 && (
            <>
              <h3>Missing evidence</h3>
              <ul className="compact-list">
                {answer.missing_evidence.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </>
          )}
          {answer.recommended_next_steps.length > 0 && (
            <>
              <h3>Recommended next steps</h3>
              <ul className="compact-list">
                {answer.recommended_next_steps.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </>
          )}
          {answer.validation_errors.length > 0 && (
            <ErrorNotice message={answer.validation_errors.join(" ")} />
          )}
          <div className="answer-meta">
            Provider: {answer.provider} · {answer.context_evidence_count}{" "}
            retrieved evidence items
            <br />
            Analyst review required. Confidence is a qualitative assessment.
          </div>
        </section>
      )}
      <div className="analyst-boundary">
        <LockKeyhole size={12} />
        <span>
          No tools, state changes, or cross-incident access. Human approval is
          required for findings and reports.
        </span>
      </div>
    </Panel>
  );
}
