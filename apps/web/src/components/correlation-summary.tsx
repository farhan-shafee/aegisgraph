import { GitMerge, Info } from "lucide-react";
import type { Incident } from "@/lib/types";
import { time } from "@/lib/format";
export function CorrelationSummary({
  correlation,
}: {
  correlation: Incident["correlation"];
}) {
  if (!correlation) return null;
  return (
    <section
      className="correlation-summary"
      aria-labelledby="correlation-title"
    >
      <div className="correlation-title">
        <GitMerge size={17} />
        <h2 id="correlation-title">Why these alerts form one incident</h2>
        <span>DETERMINISTIC CORRELATION</span>
      </div>
      <dl className="correlation-facts">
        <div>
          <dt>Principal</dt>
          <dd>{correlation.principal_ids.join(", ")}</dd>
        </div>
        <div>
          <dt>Alert window · UTC</dt>
          <dd>
            {time(correlation.first_alert_at).slice(0, 5)}–
            {time(correlation.last_alert_at).slice(0, 5)}
            <small>
              {correlation.span_minutes} min within a{" "}
              {correlation.window_minutes}-minute window
            </small>
          </dd>
        </div>
        <div>
          <dt>Distinct rules</dt>
          <dd>
            {correlation.distinct_rule_count}
            <small>
              {correlation.alert_count} alerts · minimum{" "}
              {correlation.minimum_rules} distinct rules
            </small>
          </dd>
        </div>
        <div>
          <dt>Rule families</dt>
          <dd>
            {correlation.rule_families.join(" · ")}
            <small>
              {correlation.rule_families.length} families · minimum{" "}
              {correlation.minimum_families}
            </small>
          </dd>
        </div>
      </dl>
      <div className="correlation-context">
        <Info size={13} />
        <span>
          Grouped by principal and event time. Device, session, and IP
          relationships provide investigation context.
        </span>
        <details>
          <summary>Inspect correlation rationale</summary>
          <ul>
            {correlation.explanation.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </details>
      </div>
    </section>
  );
}
