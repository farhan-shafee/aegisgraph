import Link from "next/link";
import type { Alert, Incident, SecurityEvent } from "@/lib/types";
import { Badge, Empty } from "./ui";
import { dateTime, eventLabel, humanize, time } from "@/lib/format";
export function IncidentTable({ items }: { items: Incident[] }) {
  if (!items.length)
    return (
      <Empty title="No incidents in this view">
        Run the deterministic seed to ingest telemetry, evaluate detections, and
        correlate incidents.
      </Empty>
    );
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Incident</th>
            <th>Severity</th>
            <th>Status</th>
            <th>Owner</th>
            <th>Updated (UTC)</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <Link
                  className="table-primary-link"
                  href={`/incidents/${encodeURIComponent(item.id)}`}
                >
                  <strong>{item.title}</strong>
                  <small className="mono">{item.id}</small>
                </Link>
              </td>
              <td>
                <Badge value={item.severity} />
              </td>
              <td>
                <Badge value={item.status} />
              </td>
              <td>{item.owner || <span className="muted">Unassigned</span>}</td>
              <td className="mono">{dateTime(item.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function AlertTable({
  items,
  compact = false,
}: {
  items: Alert[];
  compact?: boolean;
}) {
  if (!items.length)
    return (
      <Empty title="No alerts found">
        Alerts appear when normalized events satisfy a detection rule.
      </Empty>
    );
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Detection signal</th>
            <th>Severity</th>
            <th>Time (UTC)</th>
            {!compact && <th>Incident</th>}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <strong>{item.title || item.rule_name}</strong>
                <small>
                  {item.rule_id}
                  {!compact && ` · ${item.description}`}
                </small>
              </td>
              <td>
                <Badge value={item.severity} />
              </td>
              <td className="mono">{time(item.timestamp)}</td>
              {!compact && (
                <td>
                  {item.incident_id ? (
                    <Link
                      className="text-link"
                      href={`/incidents/${encodeURIComponent(item.incident_id)}`}
                    >
                      {item.incident_id}
                    </Link>
                  ) : (
                    "Uncorrelated"
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function EventTable({ items }: { items: SecurityEvent[] }) {
  if (!items.length)
    return (
      <Empty title="No matching events">
        Change your search or source filter to broaden this view.
      </Empty>
    );
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Time (UTC)</th>
            <th>Event</th>
            <th>Source</th>
            <th>Actor</th>
            <th>Resource / endpoint</th>
            <th>Outcome</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.event_id}>
              <td className="mono">
                {time(item.timestamp)}
                <small>{item.timestamp.slice(0, 10)}</small>
              </td>
              <td>
                <strong>{eventLabel(item)}</strong>
                <details className="source-details">
                  <summary className="mono">{item.event_id}</summary>
                  <pre>{JSON.stringify(item, null, 2)}</pre>
                </details>
              </td>
              <td>{humanize(item.source)}</td>
              <td>
                {item.actor?.username || item.actor?.user_id || "—"}
                <small className="mono">{item.network?.source_ip}</small>
              </td>
              <td className="mono">
                {item.target?.endpoint || item.target?.service || "—"}
              </td>
              <td>
                <Badge value={item.outcome === "success" ? "low" : "medium"}>
                  {humanize(item.outcome)}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
