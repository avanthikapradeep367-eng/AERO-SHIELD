import { Spinner } from "./Spinner";

interface LoadingViewProps {
  label?: string;
}

/** Full-panel loading placeholder for pages waiting on their first fetch. */
export function LoadingView({ label = "Loading…" }: LoadingViewProps) {
  return (
    <div className="flex min-h-[240px] flex-col items-center justify-center gap-3 text-ink-muted">
      <Spinner size="lg" />
      <p className="text-sm">{label}</p>
    </div>
  );
}
