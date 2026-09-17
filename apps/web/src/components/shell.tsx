"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Bell,
  Blocks,
  ChevronRight,
  CircleDot,
  FileSearch,
  GitBranch,
  LayoutDashboard,
  PanelLeftClose,
  PanelLeftOpen,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import { useState } from "react";
import { ThemeToggle } from "./theme-toggle";
import { usePublicDemo } from "./demo-mode";
const navigation = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/incidents", label: "Incidents", icon: FileSearch },
  { href: "/alerts", label: "Alerts", icon: Bell },
  { href: "/events", label: "Security events", icon: Activity },
  { href: "/detections", label: "Detections", icon: GitBranch },
  { href: "/evaluations", label: "AI evaluations", icon: ShieldCheck },
  { href: "/architecture", label: "Architecture", icon: Blocks },
];
export function Shell({ children }: { children: React.ReactNode }) {
  const publicDemo = usePublicDemo();
  const pathname = usePathname();
  const [expanded, setExpanded] = useState(false);
  const active = navigation.find((item) =>
    item.href === "/" ? pathname === "/" : pathname.startsWith(item.href),
  );
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <aside className={`sidebar ${expanded ? "is-open" : ""}`}>
        <Link href="/" className="brand" aria-label="AegisGraph home">
          <span className="brand-mark">
            <Workflow size={24} strokeWidth={1.7} />
          </span>
          <span>
            AEGIS<span className="brand-light">GRAPH</span>
            <small>INVESTIGATION PLATFORM</small>
          </span>
        </Link>
        <div className="workspace-label">
          <span className="workspace-avatar">AT</span>
          <div>
            Atlas Trading Platform<small>Synthetic environment</small>
          </div>
          <CircleDot size={13} />
        </div>
        <nav aria-label="Main navigation">
          <p className="nav-group">WORKSPACE</p>
          {navigation.map(({ href, label, icon: Icon }, i) => (
            <div key={href}>
              {i === 5 && (
                <p className="nav-group secondary-group">SYSTEM ASSURANCE</p>
              )}
              <Link
                href={href}
                className={`nav-link ${active?.href === href ? "active" : ""}`}
                aria-current={active?.href === href ? "page" : undefined}
                onClick={() => setExpanded(false)}
              >
                <Icon size={18} strokeWidth={1.7} />
                <span>{label}</span>
                {active?.href === href && <span className="nav-dot" />}
              </Link>
            </div>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="boundary-icon">
            <ShieldCheck size={18} />
          </div>
          <strong>Evidence before inference</strong>
          <p>
            Bounded context. Validated citations.
            <br />
            Human decisions.
          </p>
          <span className="version-label">
            {publicDemo ? "PUBLIC DEMO · READ ONLY" : "LOCAL DEMO · V0.1"}
          </span>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button menu-toggle"
              aria-label={expanded ? "Close navigation" : "Open navigation"}
              aria-expanded={expanded}
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? (
                <PanelLeftClose size={19} />
              ) : (
                <PanelLeftOpen size={19} />
              )}
            </button>
            <span>Workspace</span>
            <ChevronRight size={13} />
            <strong>{active?.label || "Investigation"}</strong>
          </div>
          <div className="topbar-actions">
            <ThemeToggle />
            <div className="environment-badge">
              <span className="status-dot" />
              SIMULATED TELEMETRY
            </div>
          </div>
        </header>
        <main id="main-content" tabIndex={-1}>
          {publicDemo && (
            <aside
              className="public-demo-notice"
              aria-label="Public demonstration"
            >
              <strong>Read-only public demo</strong>
              <span>
                AegisGraph uses synthetic fintech telemetry and is an
                engineering demonstration, not a production SOC system.
              </span>
            </aside>
          )}
          {children}
        </main>
        <footer className="main-footer">
          <span>AegisGraph · Atlas Trading Platform</span>
          <span>
            All identities and telemetry are synthetic. Timestamps in UTC.
          </span>
        </footer>
      </div>
    </div>
  );
}
