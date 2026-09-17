import Link from "next/link";
import { Search } from "lucide-react";
import { serverApi } from "@/lib/server-api";
import type { PageResult, SecurityEvent } from "@/lib/types";
import { PageHeading, Panel, Unavailable } from "@/components/ui";
import { EventTable } from "@/components/data-tables";
import { count } from "@/lib/format";
export const dynamic = "force-dynamic";
export default async function EventsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const val = (key: string) =>
    typeof params[key] === "string" ? (params[key] as string) : "";
  const q = val("q").slice(0, 200),
    source = val("source"),
    eventType = val("event_type");
  const offset = Math.max(0, Number.parseInt(val("offset"), 10) || 0),
    limit = 25;
  const query = new URLSearchParams({
    q,
    source,
    event_type: eventType,
    limit: String(limit),
    offset: String(offset),
  });
  let data: PageResult<SecurityEvent>;
  try {
    data = await serverApi(`/events?${query}`);
  } catch {
    return <Unavailable />;
  }
  function href(newOffset: number) {
    const next = new URLSearchParams(query);
    next.set("offset", String(newOffset));
    return `/events?${next}`;
  }
  return (
    <>
      <PageHeading
        eyebrow="TELEMETRY EXPLORER"
        title="Security events"
        description="Canonical, immutable events from four simulated sources."
      />
      <Panel>
        <form action="/events" method="get" className="toolbar">
          <div className="form-field search-field">
            <label htmlFor="q">Search events</label>
            <input
              id="q"
              name="q"
              defaultValue={q}
              maxLength={200}
              placeholder="User, event, IP, or resource…"
            />
          </div>
          <div className="form-field filter-field">
            <label htmlFor="source">Source</label>
            <select id="source" name="source" defaultValue={source}>
              <option value="">All sources</option>
              <option value="identity">Identity</option>
              <option value="api_gateway">API Gateway</option>
              <option value="endpoint">Endpoint</option>
              <option value="atlas">Atlas application</option>
            </select>
          </div>
          <div className="form-field filter-field">
            <label htmlFor="event_type">Event type</label>
            <input
              id="event_type"
              name="event_type"
              defaultValue={eventType}
              placeholder="All event types"
            />
          </div>
          <button className="button secondary" type="submit">
            <Search size={14} />
            Filter
          </button>
          {(q || source || eventType) && (
            <Link className="button ghost" href="/events">
              Clear
            </Link>
          )}
        </form>
        <EventTable items={data.items} />
        <div className="pagination">
          <span>
            {data.total
              ? `${count(offset + 1)}–${count(Math.min(offset + limit, data.total))}`
              : "0"}{" "}
            of {count(data.total)} events
          </span>
          <div className="pagination-actions">
            {offset > 0 ? (
              <Link
                className="button small secondary"
                href={href(Math.max(0, offset - limit))}
              >
                Previous
              </Link>
            ) : (
              <span>First page</span>
            )}
            {offset + limit < data.total && (
              <Link
                className="button small secondary"
                href={href(offset + limit)}
              >
                Next page
              </Link>
            )}
          </div>
        </div>
      </Panel>
      <p className="page-note">
        Server-side search and pagination. Source payloads are displayed as
        inert text.
      </p>
    </>
  );
}
