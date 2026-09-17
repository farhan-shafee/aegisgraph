import Link from "next/link";
import { AlertTriangle, ArrowUpRight, Inbox } from "lucide-react";
import type { ReactNode } from "react";
import { humanize } from "@/lib/format";

export function Badge({
  value,
  children,
}: {
  value: string;
  children?: ReactNode;
}) {
  return (
    <span className={`badge badge-${value}`}>
      {children || humanize(value)}
    </span>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
export function Panel({
  title,
  subtitle,
  action,
  children,
  className = "",
}: {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {title && (
        <div className="panel-heading">
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <Inbox size={25} aria-hidden="true" />
      <h3>{title}</h3>
      {children && <p>{children}</p>}
    </div>
  );
}
export function Unavailable({ incident = false }: { incident?: boolean }) {
  return (
    <div className="unavailable" role="alert">
      <AlertTriangle size={24} />
      <h1>
        {incident ? "Incident unavailable" : "Unable to load workspace data"}
      </h1>
      <p>
        The API could not return this page. Confirm the API and database are
        running, then try again.
      </p>
      <Link href={incident ? "/incidents" : "/"} className="button secondary">
        {incident ? "Return to incidents" : "Retry overview"}
      </Link>
    </div>
  );
}
export function TextLink({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  return (
    <Link className="text-link" href={href}>
      {children}
      <ArrowUpRight size={14} aria-hidden="true" />
    </Link>
  );
}
export function ErrorNotice({ message }: { message: string | null }) {
  return message ? (
    <div className="notice error" role="alert">
      <AlertTriangle size={16} aria-hidden="true" />
      <span>{message}</span>
    </div>
  ) : null;
}
