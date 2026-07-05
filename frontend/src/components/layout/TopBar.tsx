export function TopBar() {
  return (
    <header className="glass-panel relative z-10 flex h-16 shrink-0 items-center justify-between border-b border-line px-6">
      <p className="text-sm text-ink-muted">Aerospace device security console</p>
      <div className="flex items-center gap-4">
        <div className="relative hidden sm:block">
          <svg
            viewBox="0 0 20 20"
            fill="none"
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint"
            aria-hidden="true"
          >
            <circle cx="9" cy="9" r="6" stroke="currentColor" strokeWidth="1.5" />
            <path d="m17 17-3.5-3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <input
            type="search"
            placeholder="Search incidents, devices, evidence…"
            className="w-72 rounded-full border border-line bg-surface-raised py-2 pl-9 pr-4 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
          />
        </div>
        <div className="flex items-center gap-2 text-xs text-ink-faint">
          <span className="h-2 w-2 rounded-full bg-ink-faint" />
          <span>System status unavailable</span>
        </div>
      </div>
    </header>
  );
}
