import { NavLink } from "react-router-dom";

interface NavItem {
  to: string;
  label: string;
  end?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/command-center", label: "Dashboard" },
  { to: "/", label: "Overview", end: true },
  { to: "/simulate", label: "Attack Simulation" },
  { to: "/devices", label: "Devices" },
  { to: "/authentication", label: "Authentication" },
  { to: "/evidence", label: "Evidence" },
  { to: "/forensics", label: "Forensics" },
  { to: "/threat-intelligence", label: "Threat Intelligence" },
  { to: "/analytics", label: "Analytics" },
  { to: "/timeline", label: "Timeline" },
  { to: "/system-health", label: "System Health" },
];

function LogoMark() {
  return (
    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-cyan shadow-lg shadow-accent/30">
      <svg viewBox="0 0 24 24" fill="none" className="h-4.5 w-4.5" aria-hidden="true">
        <path d="M12 3 L20 19 L12 15.5 L4 19 Z" fill="white" />
      </svg>
    </span>
  );
}

export function Sidebar() {
  return (
    <aside className="glass-panel relative z-10 flex h-screen w-64 shrink-0 flex-col border-r border-line">
      <div className="flex h-16 items-center gap-3 border-b border-line px-5">
        <LogoMark />
        <div className="leading-tight">
          <p className="text-sm font-semibold tracking-wide text-ink">AERO-SHIELD</p>
          <p className="text-[11px] text-ink-faint">Command Center</p>
        </div>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end ?? item.to === "/"}
            className={({ isActive }) =>
              `block rounded-xl px-3.5 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-accent-muted text-accent-strong shadow-sm"
                  : "text-ink-muted hover:bg-surface-hover hover:text-ink"
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
