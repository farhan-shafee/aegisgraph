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
    "Detect",
    "Versioned rules identify individual signals and temporal sequences.",
  ],
  [
    "04",
    "Correlate",
    "Principal, time, and rule diversity form a case. Device and session links provide context.",
  ],
  [
    "05",
    "Investigate",
    "Scoped evidence, entity relationships, and analyst decisions.",
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
      </Panel>
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
              This is a local single-analyst application. Production identity
              and authorization, tenant isolation, durable tamper-resistant
              audit storage, retention controls, distributed ingestion, and
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
    </>
  );
}
