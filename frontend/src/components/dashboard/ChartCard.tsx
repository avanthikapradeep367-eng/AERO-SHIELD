import type { ReactNode } from "react";

interface ChartCardProps {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function ChartCard({ title, actions, children, className = "" }: ChartCardProps) {
  return (
    <div className={`glass-panel rounded-2xl p-4 ${className}`}>
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-ink">{title}</p>
        {actions}
      </div>
      <div className="mt-3">{children}</div>
    </div>
  );
}
