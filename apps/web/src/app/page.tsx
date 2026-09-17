import Link from "next/link";
import {
  Activity,
  ArrowRight,
  Bell,
  CalendarDays,
  Clock3,
  FileSearch,
  Layers3,
  ShieldAlert,
  UserRound,
} from "lucide-react";
import { serverApi } from "@/lib/server-api";
import type { Overview } from "@/lib/types";
import {
  Badge,
  Empty,
  PageHeading,
  Panel,
  TextLink,
  Unavailable,
} from "@/components/ui";
import { AlertTable } from "@/components/data-tables";
import { count, eventLabel, humanize, time } from "@/lib/format";
export const dynamic = "force-dynamic";
export default async function OverviewPage() {
  let data: Overview;
  try {
    data = await serverApi<Overview>("/overview");
  } catch {
    return <Unavailable />;
  }
  const featured =
    data.incidents.find(
      (i) => i.severity === "high" || i.severity === "critical",
    ) || data.incidents[0];
  const metrics = [
    {
      title: "Active incidents",
      value: data.counts.active_incidents,
      note: "New and investigating",
      icon: FileSearch,
    },
    {
      title: "High severity",
      value: data.counts.high_incidents,
      note: "High or critical incidents",
      icon: ShieldAlert,
      accent: true,
    },
    {
      title: "Detection signals",
      value: data.counts.alerts,
      note: "Alerts from normalized telemetry",
      icon: Bell,
    },
    {
      title: "Events ingested",
      value: data.counts.events,
      note: "Immutable synthetic source events",
      icon: Activity,
    },
  ];
  return (
    <>
      <PageHeading
        eyebrow="SECURITY OPERATIONS"
        title="Operations overview"
        description="Investigate connected signals. Follow the evidence."
        action={
          data.recent_events[0] && (
            <div className="date-chip">
              <CalendarDays size={13} />
              {data.recent_events[0].timestamp.slice(0, 10)}
              <span>UTC</span>
            </div>
          )
        }
      />
      <div className="metrics">
        {metrics.map(({ title, value, note, icon: Icon, accent }) => (
          <div
            className={`metric ${accent ? "metric-accent" : ""}`}
            key={title}
          >
            <div className="metric-top">
              <span>{title}</span>
              <Icon size={17} strokeWidth={1.6} />
            </div>
            <div className="metric-value">{count(value)}</div>
            <small>{note}</small>
          </div>
        ))}
      </div>
      <Panel
        title="Investigation focus"
        subtitle="Correlated activity that deserves a closer look"
        action={<TextLink href="/incidents">View all incidents</TextLink>}
      >
        {featured ? (
          <div className="featured-incident">
            <div className="featured-copy">
              <div className="inline-meta">
                <span className="mono">{featured.id}</span>
                <Badge value={featured.severity} />
                <Badge value={featured.status} />
              </div>
              <h2>{featured.title}</h2>
              <p>{featured.summary}</p>
              <div className="featured-stats">
                <span>
                  <Layers3 size={13} />
                  {(featured.alert_count ?? featured.alerts?.length) !==
                  undefined
                    ? `${featured.alert_count ?? featured.alerts?.length} linked alerts`
                    : "Related detection signals"}
                </span>
                <span>
                  <UserRound size={13} />
                  {featured.owner || "Unassigned"}
                </span>
              </div>
              <Link
                href={`/incidents/${encodeURIComponent(featured.id)}`}
                className="button primary"
              >
                Open investigation
                <ArrowRight size={14} />
              </Link>
            </div>
            <div className="featured-sequence">
              <div className="micro-label">Connected detection signals</div>
              <div className="sequence">
                {data.recent_alerts
                  .filter((a) => a.incident_id === featured.id)
                  .slice()
                  .sort((a, b) => a.timestamp.localeCompare(b.timestamp))
                  .slice(0, 5)
                  .map((alert) => (
                    <div className="sequence-row" key={alert.id}>
                      <time>{time(alert.timestamp).slice(0, 5)}</time>
                      <span className="sequence-dot" />
                      <div>
                        <strong>{alert.title || alert.rule_name}</strong>
                        <small>
                          {alert.rule_id} · {humanize(alert.severity)}
                        </small>
                      </div>
                    </div>
                  ))}
              </div>
              <p className="page-note">
                Principal + time window + rule diversity
              </p>
            </div>
          </div>
        ) : (
          <Empty title="No investigation yet">
            Seed the simulated environment to begin.
          </Empty>
        )}
      </Panel>
      <div className="overview-grid">
        <Panel
          title="Recent alerts"
          subtitle="Evidence-driven detections"
          action={<TextLink href="/alerts">All alerts</TextLink>}
        >
          <AlertTable items={data.recent_alerts.slice(0, 5)} compact />
        </Panel>
        <Panel
          title="Recent telemetry"
          subtitle="Across the Atlas environment"
          action={<TextLink href="/events">Explore events</TextLink>}
        >
          {data.recent_events.length ? (
            <ul className="activity-list">
              {data.recent_events.slice(0, 5).map((event) => (
                <li key={event.event_id}>
                  <span className="activity-icon">
                    <Activity size={15} />
                  </span>
                  <div className="activity-copy">
                    <strong>{eventLabel(event)}</strong>
                    <p>
                      {event.actor?.username || "System"} ·{" "}
                      {humanize(event.source)}
                    </p>
                  </div>
                  <time>{time(event.timestamp)}</time>
                </li>
              ))}
            </ul>
          ) : (
            <Empty title="No telemetry ingested" />
          )}
        </Panel>
      </div>
      <p className="page-note inline-meta">
        <Clock3 size={12} />
        {count(data.counts.review_required)} cases require analyst review.
        Counts reflect stored application data.
      </p>
    </>
  );
}
