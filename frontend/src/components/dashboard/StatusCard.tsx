type Tone = "success" | "info" | "warning";

const DOT_CLASSES: Record<Tone, string> = {
  success: "bg-success shadow-[0_0_8px] shadow-success/60",
  info: "bg-accent shadow-[0_0_8px] shadow-accent/60",
  warning: "bg-orange shadow-[0_0_8px] shadow-orange/60",
};

interface StatusCardProps {
  label: string;
  value: string;
  tone?: Tone;
}

export function StatusCard({ label, value, tone = "info" }: StatusCardProps) {
  return (
    <div className="glass-panel rounded-2xl p-5">
      <div className="flex items-center gap-2">
        <span className={`h-2.5 w-2.5 rounded-full ${DOT_CLASSES[tone]}`} />
        <p className="text-xs font-medium text-ink-faint">{label}</p>
      </div>
      <p className="mt-2 text-xl font-semibold text-ink">{value}</p>
    </div>
  );
}
