import { NavLink } from "react-router-dom";

interface NavItem {
  to: string;
  label: string;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Overview" },
  { to: "/devices", label: "Devices" },
  { to: "/simulate", label: "Attack Simulation" },
  { to: "/authentication", label: "Authentication" },
  { to: "/evidence", label: "Evidence" },
  { to: "/forensics", label: "Forensics" },
  { to: "/threat-intelligence", label: "Threat Intelligence" },
  { to: "/analytics", label: "Analytics" },
  { to: "/timeline", label: "Timeline" },
  { to: "/system-health", label: "System Health" },
];

export function Sidebar() {
  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r border-line bg-surface">
      <div className="flex h-16 items-center gap-2 border-b border-line px-5">
        <span className="h-2.5 w-2.5 rounded-full bg-accent shadow-[0_0_8px] shadow-accent" />
        <span className="text-sm font-semibold tracking-wide text-ink">AERO-SHIELD</span>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              `block rounded-md px-3 py-2 text-sm transition-colors ${
                isActive
                  ? "bg-accent-muted text-accent-strong"
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
