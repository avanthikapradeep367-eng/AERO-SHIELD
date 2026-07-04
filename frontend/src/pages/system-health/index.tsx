import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Spinner } from "../../components/ui/Spinner";
import { LoadingView } from "../../components/ui/LoadingView";
import { getLiveness, getReadiness, getSystemHealth } from "../../api/systemHealth";
import { getCoreHealth } from "../../api/simulation";
import type { NormalizedError } from "../../api/envelopes";
import type {
  ComponentHealth,
  CoreHealthResponse,
  HealthComponent,
  LivenessResponse,
  OverallHealth,
  ReadinessResponse,
  SystemHealthResponse,
} from "../../types/health";
import { relativeTime } from "../../utils/relativeTime";
import { truncateHex } from "../../utils/truncateHex";

type Tone = "success" | "warning" | "danger" | "neutral";

const TONE_CLASSES: Record<Tone, string> = {
  success: "border-success/40 bg-success-muted text-success",
  warning: "border-warning/40 bg-warning-muted text-warning",
  danger: "border-danger/40 bg-danger-muted text-danger",
  neutral: "border-line-strong bg-surface-hover text-ink-faint",
};

const OVERALL_TONE: Record<OverallHealth, Tone> = {
  HEALTHY: "success",
  DEGRADED: "warning",
  CRITICAL: "danger",
};

const COMPONENT_TONE: Record<ComponentHealth, Tone> = {
  ONLINE: "success",
  DEGRADED: "warning",
  OFFLINE: "danger",
  UNKNOWN: "neutral",
};

const COMPONENT_LABELS: Record<string, string> = {
  fastapi: "API Server",
  blockchain: "Blockchain Node",
  contract: "Smart Contract",
  wallet: "Wallet",
  ai_engine: "AI Engine (SentinelX)",
  memory: "Memory",
  cpu: "CPU Load",
  disk: "Disk",
};

/** Auto-refresh cadence: /system/health caches results server-side for 10s
 * (see app/dashboard/health_monitor.py), so polling faster would just re-read
 * the same cached report — 15s keeps every refresh meaningful. */
const AUTO_REFRESH_MS = 15_000;

function Pill({ label, tone }: { label: string; tone: Tone }) {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONE_CLASSES[tone]}`}>
      {label}
    </span>
  );
}

function Card({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-6">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">{title}</p>
      {description ? <p className="mt-1 text-xs text-ink-faint">{description}</p> : null}
      <div className="mt-4">{children}</div>
    </div>
  );
}

function SectionError({ error, onRetry }: { error: NormalizedError; onRetry: () => void }) {
  return (
    <div className="space-y-2">
      <p className="text-sm text-danger">{error.message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="rounded-md border border-line px-3 py-1 text-xs font-medium text-ink-muted transition-colors hover:border-accent hover:text-accent"
      >
        Retry
      </button>
    </div>
  );
}

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-line bg-surface-raised p-4">
      <p className="text-xs uppercase tracking-wide text-ink-faint">{label}</p>
      <p className="tabular-nums mt-2 text-2xl font-semibold text-ink">{value}</p>
    </div>
  );
}

function isNotReadyBody(details: Record<string, unknown> | null | undefined): details is Record<string, unknown> {
  return !!details && (details.status === "ready" || details.status === "not_ready");
}

function ReadinessView({
  status,
  reason,
  blockchain,
  contract,
}: {
  status: "ready" | "not_ready";
  reason?: string;
  blockchain?: string;
  contract?: string;
}) {
  return (
    <div className="space-y-2">
      <Pill label={status} tone={status === "ready" ? "success" : "danger"} />
      {reason ? <p className="text-sm text-ink-muted">{reason}</p> : null}
      {blockchain || contract ? (
        <p className="text-xs text-ink-faint">
          blockchain: {blockchain ?? "—"} · contract: {contract ?? "—"}
        </p>
      ) : null}
    </div>
  );
}

interface ResourceState<T> {
  status: "loading" | "success" | "error";
  data: T | null;
  error: NormalizedError | null;
  updatedAt: string | null;
}

function useResource<T>(fetcher: () => Promise<{ ok: boolean; data: T | null; error: NormalizedError | null }>, tick: number) {
  const [state, setState] = useState<ResourceState<T>>({ status: "loading", data: null, error: null, updatedAt: null });

  useEffect(() => {
    let cancelled = false;
    setState((prev) => ({ status: "loading", data: prev.data, error: null, updatedAt: prev.updatedAt }));

    fetcher().then((result) => {
      if (cancelled) return;
      if (result.ok) {
        setState({ status: "success", data: result.data, error: null, updatedAt: new Date().toISOString() });
      } else {
        setState({ status: "error", data: null, error: result.error, updatedAt: null });
      }
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick]);

  return state;
}

function componentExtraDetails(component: HealthComponent): { label: string; value: string }[] {
  const details: { label: string; value: string }[] = [];
  const known: Record<string, (v: unknown) => string> = {
    used_percent: (v) => `${v}% used`,
    available_gb: (v) => `${v} GB free`,
    total_gb: (v) => `${v} GB total`,
    cpu_count: (v) => `${v} cores`,
    cpu_percent: (v) => `${v}% load`,
    free_gb: (v) => `${v} GB free`,
    balance_eth: (v) => `${v} ETH`,
    address: (v) => truncateHex(String(v)),
    block_number: (v) => `Block #${v}`,
    chain_id: (v) => `Chain ${v}`,
    rpc_url: (v) => String(v),
    network: (v) => String(v),
    contract_address: (v) => truncateHex(String(v)),
  };

  for (const [key, formatter] of Object.entries(known)) {
    if (component[key] !== undefined && component[key] !== null) {
      details.push({ label: key.replace(/_/g, " "), value: formatter(component[key]) });
    }
  }
  return details;
}

export default function SystemHealthPage() {
  const [tick, setTick] = useState(0);

  const systemHealth = useResource<SystemHealthResponse>(getSystemHealth, tick);
  const coreHealth = useResource<CoreHealthResponse>(getCoreHealth, tick);
  const liveness = useResource<LivenessResponse>(getLiveness, tick);
  const readiness = useResource<ReadinessResponse>(getReadiness, tick);

  useEffect(() => {
    const interval = setInterval(() => setTick((t) => t + 1), AUTO_REFRESH_MS);
    return () => clearInterval(interval);
  }, []);

  const components = systemHealth.data?.components ?? [];
  const anyLoading =
    systemHealth.status === "loading" || coreHealth.status === "loading" || liveness.status === "loading" || readiness.status === "loading";

  return (
    <div className="space-y-6">
      <PageHeader
        title="System Health"
        description="Live status for every backend subsystem — API, database, blockchain, AI engine, and host resources."
        actions={
          <div className="flex items-center gap-3">
            {systemHealth.updatedAt ? (
              <span className="text-xs text-ink-faint" title={systemHealth.updatedAt}>
                Updated {relativeTime(systemHealth.updatedAt)} · auto-refreshes every {AUTO_REFRESH_MS / 1000}s
              </span>
            ) : null}
            <button
              type="button"
              onClick={() => setTick((t) => t + 1)}
              disabled={anyLoading}
              className="flex items-center gap-2 rounded-md border border-line bg-surface-raised px-3 py-1.5 text-sm font-medium text-ink transition-colors hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-60"
            >
              {anyLoading ? <Spinner size="sm" /> : null}
              Refresh
            </button>
          </div>
        }
      />

      {/* Overall system health */}
      <Card title="Overall System Health">
        {systemHealth.status === "loading" && !systemHealth.data ? (
          <LoadingView label="Loading system health…" />
        ) : systemHealth.status === "error" && systemHealth.error ? (
          <SectionError error={systemHealth.error} onRetry={() => setTick((t) => t + 1)} />
        ) : systemHealth.data ? (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <Pill label={systemHealth.data.overall_status} tone={OVERALL_TONE[systemHealth.data.overall_status]} />
              {systemHealth.data.elapsed_ms !== undefined ? (
                <span className="text-sm text-ink-muted">
                  Checked in <span className="tabular-nums text-ink">{systemHealth.data.elapsed_ms}ms</span>
                </span>
              ) : null}
            </div>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <StatTile label="Online" value={systemHealth.data.summary.online} />
              <StatTile label="Degraded" value={systemHealth.data.summary.degraded} />
              <StatTile label="Offline" value={systemHealth.data.summary.offline} />
              <StatTile label="Unknown" value={systemHealth.data.summary.unknown} />
            </div>
          </div>
        ) : null}
      </Card>

      {/* Core API health */}
      <Card title="API Status" description="GET /api/v1/health — database probe, version, and mocked-layer summaries.">
        {coreHealth.status === "loading" && !coreHealth.data ? (
          <div className="flex items-center gap-2 text-sm text-ink-muted">
            <Spinner size="sm" />
            Loading…
          </div>
        ) : coreHealth.status === "error" && coreHealth.error ? (
          <SectionError error={coreHealth.error} onRetry={() => setTick((t) => t + 1)} />
        ) : coreHealth.data ? (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            <div className="rounded-md border border-line bg-surface-raised p-4">
              <p className="text-xs uppercase tracking-wide text-ink-faint">Status</p>
              <div className="mt-2">
                <Pill
                  label={coreHealth.data.status}
                  tone={coreHealth.data.status === "operational" ? "success" : "warning"}
                />
              </div>
            </div>
            <div className="rounded-md border border-line bg-surface-raised p-4">
              <p className="text-xs uppercase tracking-wide text-ink-faint">Version</p>
              <p className="mt-2 text-sm text-ink">{coreHealth.data.version}</p>
            </div>
            <div className="rounded-md border border-line bg-surface-raised p-4">
              <p className="text-xs uppercase tracking-wide text-ink-faint">Database</p>
              <div className="mt-2">
                <Pill label={coreHealth.data.database} tone={coreHealth.data.database === "connected" ? "success" : "danger"} />
              </div>
            </div>
            <div className="rounded-md border border-line bg-surface-raised p-4">
              <p className="text-xs uppercase tracking-wide text-ink-faint">Blockchain</p>
              <p className="mt-2 text-sm text-ink-muted">{coreHealth.data.blockchain}</p>
            </div>
            <div className="rounded-md border border-line bg-surface-raised p-4">
              <p className="text-xs uppercase tracking-wide text-ink-faint">AI Engine</p>
              <p className="mt-2 text-sm text-ink-muted">{coreHealth.data.ai_engine}</p>
            </div>
          </div>
        ) : null}
      </Card>

      {/* Liveness & readiness */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <Card title="Liveness Probe" description="GET /system/health/live">
          {liveness.status === "loading" && !liveness.data ? (
            <div className="flex items-center gap-2 text-sm text-ink-muted">
              <Spinner size="sm" />
              Loading…
            </div>
          ) : liveness.status === "error" && liveness.error ? (
            <SectionError error={liveness.error} onRetry={() => setTick((t) => t + 1)} />
          ) : liveness.data ? (
            <Pill label={liveness.data.status} tone={liveness.data.status === "alive" ? "success" : "danger"} />
          ) : null}
        </Card>

        <Card title="Readiness Probe" description="GET /system/health/ready">
          {readiness.status === "loading" && !readiness.data ? (
            <div className="flex items-center gap-2 text-sm text-ink-muted">
              <Spinner size="sm" />
              Loading…
            </div>
          ) : readiness.status === "success" && readiness.data ? (
            <ReadinessView
              status={readiness.data.status}
              reason={readiness.data.reason}
              blockchain={readiness.data.blockchain}
              contract={readiness.data.contract}
            />
          ) : readiness.status === "error" && isNotReadyBody(readiness.error?.details) ? (
            // GET /system/health/ready responds 503 (not 200) when not ready, so
            // this genuinely arrives via the error path — but the body itself is
            // still meaningful readiness data, not a fetch failure, so render it
            // the same way as the success case rather than a generic error banner.
            <ReadinessView
              status={readiness.error!.details!.status as "ready" | "not_ready"}
              reason={readiness.error!.details!.reason as string | undefined}
              blockchain={readiness.error!.details!.blockchain as string | undefined}
              contract={readiness.error!.details!.contract as string | undefined}
            />
          ) : readiness.status === "error" && readiness.error ? (
            <SectionError error={readiness.error} onRetry={() => setTick((t) => t + 1)} />
          ) : null}
        </Card>
      </div>

      {/* Individual component health */}
      <Card title="Component Health" description="Every subsystem checked concurrently by the health monitor.">
        {systemHealth.status === "loading" && !systemHealth.data ? (
          <LoadingView label="Loading component health…" />
        ) : systemHealth.status === "error" && systemHealth.error ? (
          <SectionError error={systemHealth.error} onRetry={() => setTick((t) => t + 1)} />
        ) : components.length === 0 ? (
          <p className="text-sm text-ink-faint">No component health data reported.</p>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {components.map((component) => {
              const extras = componentExtraDetails(component);
              return (
                <div key={component.component} className="rounded-md border border-line bg-surface-raised p-4">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm text-ink">{COMPONENT_LABELS[component.component] ?? component.component}</p>
                    <Pill label={component.status} tone={COMPONENT_TONE[component.status]} />
                  </div>
                  {component.detail ? <p className="mt-2 text-xs text-ink-muted">{component.detail}</p> : null}
                  {extras.length > 0 ? (
                    <ul className="mt-2 space-y-0.5">
                      {extras.map((e) => (
                        <li key={e.label} className="text-xs text-ink-faint">
                          <span className="capitalize">{e.label}</span>: <span className="text-ink-muted">{e.value}</span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  <p className="mt-2 text-xs text-ink-faint">Checked {relativeTime(component.checked_at)}</p>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
