import type { ReactNode } from "react";

type Accent = "accent" | "cyan" | "orange" | "success";

const ACCENT_ICON_CLASSES: Record<Accent, string> = {
  accent: "bg-accent-muted text-accent-strong",
  cyan: "bg-cyan-muted text-cyan",
  orange: "bg-orange-muted text-orange",
  success: "bg-success-muted text-success",
};

const ACCENT_VALUE_CLASSES: Record<Accent, string> = {
  accent: "text-accent-strong",
  cyan: "text-cyan",
  orange: "text-orange",
  success: "text-success",
};

interface StatCardProps {
  label: string;
  value: ReactNode;
  icon: ReactNode;
  accent?: Accent;
}

export function StatCard({ label, value, icon, accent = "accent" }: StatCardProps) {
  return (
    <div className="glass-panel flex items-center gap-3 rounded-2xl p-3.5">
      <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${ACCENT_ICON_CLASSES[accent]}`}>
        {icon}
      </span>
      <div className="min-w-0">
        <p className="text-[11px] font-medium text-ink-faint">{label}</p>
        <p className={`tabular-nums mt-0.5 text-lg font-semibold ${ACCENT_VALUE_CLASSES[accent]}`}>{value}</p>
      </div>
    </div>
  );
}
