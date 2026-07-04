export function TopBar() {
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-line bg-surface px-6">
      <p className="text-sm text-ink-muted">Aerospace device security console</p>
      <div className="flex items-center gap-2 text-xs text-ink-faint">
        <span className="h-2 w-2 rounded-full bg-ink-faint" />
        <span>System status unavailable</span>
      </div>
    </header>
  );
}
