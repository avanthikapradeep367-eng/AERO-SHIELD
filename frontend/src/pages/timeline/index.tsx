import { useEffect, useMemo, useState } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Spinner } from "../../components/ui/Spinner";
import { LoadingView } from "../../components/ui/LoadingView";
import { getCustodyTimeline, getThreatsTimeline, getTimeline } from "../../api/timeline";
import type { NormalizedError } from "../../api/envelopes";
import type { CustodyTimelineEvent, ThreatTimelineEvent, TimelineEvent } from "../../types/dashboard";
import { relativeTime } from "../../utils/relativeTime";
import { truncateHex } from "../../utils/truncateHex";

type Tone = "success" | "warning" | "danger" | "neutral";

const TONE_CLASSES: Record<Tone, string> = {
  success: "border-success/40 bg-success-muted text-success",
  warning: "border-warning/40 bg-warning-muted text-warning",
  danger: "border-danger/40 bg-danger-muted text-danger",
  neutral: "border-line-strong bg-surface-hover text-ink-faint",
};

const DOT_CLASSES: Record<Tone, string> = {
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  neutral: "bg-ink-faint",
};

function Pill({ label, tone }: { label: string; tone: Tone }) {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONE_CLASSES[tone]}`}>
      {label}
    </span>
  );
}

function severityTone(severity?: string): Tone {
  switch (severity) {
    case "critical":
    case "high":
      return "danger";
    case "medium":
      return "warning";
    case "low":
      return "success";
    default:
      return "neutral";
  }
}

function statusTone(status: string): Tone {
  const s = status.toUpperCase();
  if (s.includes("TAMPER") || s.includes("FAIL") || s.includes("BLOCK")) return "danger";
  if (s.includes("INVESTIGAT") || s.includes("DETECT")) return "warning";
  if (s.includes("VERIF") || s.includes("RESOLV") || s.includes("REGISTER") || s.includes("CLOS")) return "success";
  return "neutral";
}

type Source = "all" | "custody" | "threats";

interface DisplayEvent {
  key: string;
  time: string;
  title: string;
  description: string;
  status: string;
  type: string;
  severity?: string;
  metadata: Record<string, unknown>;
}

function fromUnified(events: TimelineEvent[]): DisplayEvent[] {
  return events.map((e, i) => ({
    key: `${e.time}-${i}`,
    time: e.time,
    title: e.title,
    description: e.description,
    status: e.status,
    type: e.type,
    severity: e.severity,
    metadata: e.data ?? {},
  }));
}

function fromCustody(events: CustodyTimelineEvent[]): DisplayEvent[] {
  return events.map((e, i) => ({
    key: `${e.time}-${i}`,
    time: e.time,
    title: e.title,
    description: e.description,
    status: e.status,
    type: e.type,
    metadata: { evidence_id: e.evidence_id, actor: e.actor },
  }));
}

function fromThreats(events: ThreatTimelineEvent[]): DisplayEvent[] {
  return events.map((e, i) => ({
    key: `${e.time}-${i}`,
    time: e.time,
    title: e.title,
    description: e.description,
    status: e.status,
    type: e.type,
    metadata: { threat_id: e.threat_id, device_id: e.device_id, risk_score: e.risk_score, on_chain: e.on_chain },
  }));
}

async function fetchDisplayEvents(
  source: Source,
  limit: number,
): Promise<{ ok: boolean; data: DisplayEvent[] | null; error: NormalizedError | null }> {
  if (source === "custody") {
    const res = await getCustodyTimeline({ limit });
    if (!res.ok || !res.data) return { ok: false, data: null, error: res.error };
    return { ok: true, data: fromCustody(res.data.events), error: null };
  }
  if (source === "threats") {
    const res = await getThreatsTimeline({ limit });
    if (!res.ok || !res.data) return { ok: false, data: null, error: res.error };
    return { ok: true, data: fromThreats(res.data.events), error: null };
  }
  const res = await getTimeline({ limit });
  if (!res.ok || !res.data) return { ok: false, data: null, error: res.error };
  return { ok: true, data: fromUnified(res.data.events), error: null };
}

function dayLabel(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Unknown date";
  return d.toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" });
}

function metadataLabel(key: string): string {
  return key
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function metadataValue(key: string, value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string" && (key.toLowerCase().includes("hash") || key.toLowerCase().includes("_id")) && value.length > 20) {
    return truncateHex(value, 10, 6);
  }
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

interface ResourceState<T> {
  status: "loading" | "success" | "error";
  data: T | null;
  error: NormalizedError | null;
}

function useResource<T>(fetcher: () => Promise<{ ok: boolean; data: T | null; error: NormalizedError | null }>, deps: unknown[]) {
  const [state, setState] = useState<ResourceState<T>>({ status: "loading", data: null, error: null });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading", data: null, error: null });

    fetcher().then((result) => {
      if (cancelled) return;
      if (result.ok) {
        setState({ status: "success", data: result.data, error: null });
      } else {
        setState({ status: "error", data: null, error: result.error });
      }
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}

const SOURCE_OPTIONS: { value: Source; label: string }[] = [
  { value: "all", label: "All Sources" },
  { value: "custody", label: "Chain of Custody" },
  { value: "threats", label: "Threat Intelligence" },
];

const LIMIT_OPTIONS = [25, 50, 100, 200];

export default function TimelinePage() {
  const [source, setSource] = useState<Source>("all");
  const [limit, setLimit] = useState(50);
  const [tick, setTick] = useState(0);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const timeline = useResource<DisplayEvent[]>(() => fetchDisplayEvents(source, limit), [source, limit, tick]);
  const events = timeline.data ?? [];
  const selected = events.find((e) => e.key === selectedKey) ?? events[0] ?? null;

  const groups = useMemo(() => {
    const map = new Map<string, DisplayEvent[]>();
    for (const e of events) {
      const label = dayLabel(e.time);
      const list = map.get(label);
      if (list) {
        list.push(e);
      } else {
        map.set(label, [e]);
      }
    }
    return Array.from(map.entries());
  }, [events]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Timeline"
        description="Unified chronological feed of security events, custody actions, and published threats."
      />

      <div className="flex flex-wrap items-end gap-4 rounded-lg border border-line bg-surface p-4">
        <div>
          <label htmlFor="source_select" className="text-xs font-medium uppercase tracking-wide text-ink-muted">
            Source
          </label>
          <select
            id="source_select"
            value={source}
            onChange={(e) => {
              setSource(e.target.value as Source);
              setSelectedKey(null);
            }}
            className="mt-1.5 rounded-md border border-line bg-surface-raised px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none"
          >
            {SOURCE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="limit_select" className="text-xs font-medium uppercase tracking-wide text-ink-muted">
            Show
          </label>
          <select
            id="limit_select"
            value={limit}
            onChange={(e) => {
              setLimit(Number(e.target.value));
              setSelectedKey(null);
            }}
            className="mt-1.5 rounded-md border border-line bg-surface-raised px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none"
          >
            {LIMIT_OPTIONS.map((l) => (
              <option key={l} value={l}>
                {l} events
              </option>
            ))}
          </select>
        </div>

        <button
          type="button"
          onClick={() => setTick((t) => t + 1)}
          className="rounded-md border border-line px-3 py-2 text-sm font-medium text-ink-muted transition-colors hover:border-accent hover:text-accent"
        >
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_380px]">
        <div className="rounded-lg border border-line bg-surface p-6">
          {timeline.status === "loading" ? (
            <LoadingView label="Loading timeline events…" />
          ) : timeline.status === "error" && timeline.error ? (
            <div className="space-y-2">
              <p className="text-sm text-danger">{timeline.error.message}</p>
              <button
                type="button"
                onClick={() => setTick((t) => t + 1)}
                className="rounded-md border border-line px-3 py-1 text-xs font-medium text-ink-muted transition-colors hover:border-accent hover:text-accent"
              >
                Retry
              </button>
            </div>
          ) : events.length === 0 ? (
            <p className="text-sm text-ink-faint">No events recorded yet for this source.</p>
          ) : (
            <div className="space-y-8">
              {groups.map(([label, groupEvents]) => (
                <div key={label}>
                  <p className="mb-4 text-xs font-medium uppercase tracking-wide text-ink-faint">{label}</p>
                  <ul className="space-y-0">
                    {groupEvents.map((event) => {
                      const tone = event.severity ? severityTone(event.severity) : statusTone(event.status);
                      const isSelected = selected?.key === event.key;
                      return (
                        <li key={event.key} className="relative flex gap-3 pb-6 last:pb-0">
                          <div className="flex flex-col items-center">
                            <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${DOT_CLASSES[tone]}`} />
                            <span className="mt-1 w-px flex-1 bg-line" />
                          </div>
                          <button
                            type="button"
                            onClick={() => setSelectedKey(event.key)}
                            className={`flex-1 rounded-md border p-3 text-left transition-colors ${
                              isSelected ? "border-accent bg-surface-raised" : "border-transparent hover:bg-surface-hover"
                            }`}
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-sm text-ink">{event.title}</p>
                              <span className="text-xs text-ink-faint" title={event.time}>
                                {relativeTime(event.time)}
                              </span>
                            </div>
                            {event.description ? <p className="mt-1 text-xs text-ink-muted">{event.description}</p> : null}
                            <div className="mt-2 flex flex-wrap items-center gap-2">
                              <Pill label={event.status || "UNKNOWN"} tone={statusTone(event.status)} />
                              {event.severity ? (
                                <Pill label={event.severity.toUpperCase()} tone={severityTone(event.severity)} />
                              ) : null}
                              <span className="text-xs text-ink-faint">{event.type}</span>
                            </div>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-lg border border-line bg-surface p-6">
          <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">Event Details</p>
          {timeline.status === "loading" ? (
            <div className="mt-4 flex items-center gap-2 text-sm text-ink-muted">
              <Spinner size="sm" />
              Loading…
            </div>
          ) : !selected ? (
            <p className="mt-4 text-sm text-ink-faint">Select an event from the timeline to view its details.</p>
          ) : (
            <div className="mt-4 space-y-4">
              <div>
                <p className="text-sm font-medium text-ink">{selected.title}</p>
                <p className="mt-1 text-xs text-ink-faint" title={selected.time}>
                  {new Date(selected.time).toLocaleString()} · {relativeTime(selected.time)}
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Pill label={selected.status || "UNKNOWN"} tone={statusTone(selected.status)} />
                {selected.severity ? <Pill label={selected.severity.toUpperCase()} tone={severityTone(selected.severity)} /> : null}
                <Pill label={selected.type} tone="neutral" />
              </div>

              {selected.description ? (
                <div>
                  <p className="text-xs uppercase tracking-wide text-ink-faint">Description</p>
                  <p className="mt-1 text-sm text-ink">{selected.description}</p>
                </div>
              ) : null}

              {Object.keys(selected.metadata).length > 0 ? (
                <div>
                  <p className="text-xs uppercase tracking-wide text-ink-faint">Related Metadata</p>
                  <dl className="mt-2 space-y-1.5">
                    {Object.entries(selected.metadata).map(([key, value]) => (
                      <div key={key} className="flex items-center justify-between gap-3 text-sm">
                        <dt className="text-ink-faint">{metadataLabel(key)}</dt>
                        <dd className="truncate font-mono text-xs text-ink" title={String(value)}>
                          {metadataValue(key, value)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </div>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
