import {
  ArrowRight,
  Database,
  LockKeyhole,
  Network,
  ShieldCheck,
} from "lucide-react";
import { PageHeading, Panel } from "@/components/ui";
const stages = [
  [
    "01",
    "Synthetic telemetry",
    "Identity · API Gateway · Endpoint · Atlas application",
  ],
  [
    "02",
    "Normalize & store",
    "Validated canonical events. Immutable source records.",
  ],
  [
    "03",
    "Detection rules",
    "Typed, versioned parameters identify signals and temporal sequences.",
  ],
  [
    "04",
    "Alerts",
    "Individual signals with rule IDs and source-event references.",
  ],
  [
    "05",
    "Correlation",
    "Principal, time, and rule diversity form a case. Device and session links provide context.",
  ],
  [
    "06",
    "Incident & evidence",
    "Scoped evidence, entity relationships, and analyst decisions.",
  ],
];
const analysisStages = [
  [
    "01",
    "Bounded retrieval",
    "Explicit incident scope selects the allowed evidence set.",
  ],
  [
    "02",
    "Evidence projection",
    "Typed observations only. Telemetry text is untrusted data.",
  ],
  [
    "03",
    "AI provider",
    "Replaceable, read-only provider. No database session or tools.",
  ],
  [
    "04",
    "Schema validation",
    "Reject malformed output, unknown fields, and unsupported claims.",
  ],
  [
    "05",
    "Citation validation",
    "Every reference must belong to the case and the supplied context.",
  ],
  [
    "06",
    "Analyst review",
    "Inspect sources. Save drafts. Approve findings and reports explicitly.",
  ],
];
export default function ArchitecturePage() {
  return (
    <>
      <PageHeading
        eyebrow="ENGINEERING NOTES"
        title="Evidence is the system of record"
        description="A small, inspectable architecture with explicit trust boundaries."
      />
      <div className="architecture-pipelines">
        <Panel
          title="From telemetry to investigation"
          subtitle="One API, one relational database, and a replaceable model provider"
        >
          <div className="architecture-flow">
            {stages.map(([number, title, description]) => (
              <div className="architecture-step" key={number}>
                <span>{number}</span>
                <strong>{title}</strong>
                <p>{description}</p>
              </div>
            ))}
          </div>
          <div className="architecture-boundary-label">
            <Database size={15} />
            <span>
              <strong>System of record:</strong> PostgreSQL owns events, alerts,
              incidents, and analyst decisions. Correlation does not depend on
              AI.
            </span>
          </div>
        </Panel>
        <Panel
          title="From scoped evidence to a reviewable answer"
          subtitle="Model output crosses a validation boundary before an analyst sees it"
        >
          <div className="architecture-flow">
            {analysisStages.map(([number, title, description]) => (
              <div
                className={`architecture-step ${number === "04" || number === "05" ? "validation" : ""}`}
                key={number}
              >
                <span>{number}</span>
                <strong>{title}</strong>
                <p>{description}</p>
              </div>
            ))}
          </div>
          <div className="architecture-boundary-label">
            <LockKeyhole size={15} />
            <span>
              <strong>Human mutation boundary:</strong> AI cannot change
              incident state or evidence. Analyst write actions use separate API
              routes and create audit records.
            </span>
          </div>
        </Panel>
      </div>
      <div className="architecture-grid">
        <Panel
          title="Grounded analysis boundary"
          action={<LockKeyhole size={17} />}
        >
          <div className="panel-body architecture-copy">
            <h3>Retrieve before reasoning</h3>
            <p>
              The API selects a bounded evidence set for the requested incident.
              Only a small projection of that case enters the model context. Raw
              telemetry and annotations remain untrusted data.
            </p>
            <div className="trust-boundary">
              Question <ArrowRight size={12} style={{ display: "inline" }} />{" "}
              Incident scope{" "}
              <ArrowRight size={12} style={{ display: "inline" }} /> Evidence
              projection <ArrowRight size={12} style={{ display: "inline" }} />{" "}
              Provider <ArrowRight size={12} style={{ display: "inline" }} />{" "}
              Validation
            </div>
            <h3>Validate before display</h3>
            <p>
              Structured responses are validated for schema, citation
              membership, and supported claim types. Malformed or unsupported
              results fail closed. The deterministic local provider uses the
              same boundary as the configured external provider.
            </p>
            <h3>Human decisions</h3>
            <p>
              The model receives no database session or mutation tools. Incident
              edits, evidence annotations, approved findings, and report
              approval are separate analyst actions recorded in audit history.
            </p>
          </div>
        </Panel>
        <Panel title="Relational by design" action={<Database size={17} />}>
          <div className="panel-body architecture-copy">
            <h3>PostgreSQL as the authoritative store</h3>
            <p>
              Normalized events, alerts, incidents, evidence associations,
              entities, findings, and audit records live in one transactional
              database. Indexed queries and server-side pagination support this
              bounded dataset.
            </p>
            <h3>Detection and correlation are separate</h3>
            <p>
              A detection describes a signal. Correlation links related signals
              using explicit identity and temporal relationships. Neither
              component depends on a model response or opaque risk score.
            </p>
            <h3>Graph without a graph database</h3>
            <p>
              Entity edges are derived from event associations. The
              investigation UI exposes their supporting evidence so analysts can
              inspect how each relationship was established.
            </p>
          </div>
        </Panel>
        <Panel
          title="Implemented in this demo"
          action={<ShieldCheck size={17} />}
        >
          <div className="panel-body architecture-copy">
            <p>
              Deterministic synthetic data, four telemetry adapters, rules as
              code, temporal detections, deterministic correlation, evidence
              annotations, scoped AI analysis, structured-output validation,
              executed boundary evaluations, analyst findings, reports, and
              audit history.
            </p>
            <div className="trust-boundary">
              All identities, IP addresses, resources, and financial activity
              are synthetic. The default analyst provider requires no API
              credentials.
            </div>
          </div>
        </Panel>
        <Panel title="Production work remains" action={<Network size={17} />}>
          <div className="panel-body architecture-copy">
            <p>
              The hosted demonstration is anonymous and read-only; local mode
              supports a single-analyst workflow. Production identity and
              authorization, tenant isolation, durable tamper-resistant audit
              storage, retention controls, distributed ingestion, and
              workload-specific scaling require additional engineering.
            </p>
            <h3>Evaluation limits</h3>
            <p>
              Deterministic and adversarial fixtures test application
              boundaries. Passing those cases does not establish live-model
              prompt-injection resistance, enterprise readiness, or compliance
              certification.
            </p>
          </div>
        </Panel>
      </div>
      <Panel
        title="The inspection and improvement loop"
        className="mt-6"
        subtitle="Finite synthetic scenarios, explicit decisions, and reproducible comparisons"
      >
        <div className="panel-body architecture-copy">
          <p>
            Scenario → telemetry → detection → correlation → evidence →
            hypothesis → validated analysis → human review → typed rule proposal
            → replay and regression gate.
          </p>
          <h3>Replay without persistent public state</h3>
          <p>
            The API computes a bounded sequence of causal frames. The browser
            owns the playback cursor; starting, pausing, stepping, or resetting
            never edits the canonical database. A completed replay exposes its
            own scoped evidence. Stored Atlas records remain inspectable
            separately.
          </p>
          <h3>Review without an opaque score</h3>
          <p>
            Evidence-derived hypothesis status is separate from local human
            review. Fixed gap categories describe what further evidence could
            help. Proposed detection parameters are compared across independent,
            labeled synthetic fixtures. PASS, WARN, and BLOCK gates list their
            reasons. These measurements do not estimate production detection
            accuracy.
          </p>
          <h3>Verify exported bytes</h3>
          <p>
            Evidence exports contain fixed logical files and SHA-256 hashes.
            Local browser verification checks exact bytes and membership without
            uploading or extracting a file. The unsigned manifest does not prove
            authenticity, source telemetry truth, or privileged database
            integrity.
          </p>
          <div className="inline-meta">
            <a href="https://github.com/farhan-shafee/aegisgraph/blob/main/docs/architecture/SYSTEM.md">
              System design
            </a>
            <a href="https://github.com/farhan-shafee/aegisgraph/blob/main/docs/threat-model/THREAT_MODEL.md">
              Threat model
            </a>
            <a href="https://github.com/farhan-shafee/aegisgraph/tree/main/docs/adr">
              Architecture decisions
            </a>
          </div>
        </div>
      </Panel>
    </>
  );
}
