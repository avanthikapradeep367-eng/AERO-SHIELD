import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Spinner } from "../../components/ui/Spinner";
import { getKpis, getOverview, getRecentTransactions } from "../../api/dashboard";
import { getBlockchainHealth, getSystemHealth } from "../../api/systemHealth";
import type { NormalizedError } from "../../api/envelopes";
import type { OverviewResponse, PlatformKpis, RecentTransaction, RecentTransactionsResponse } from "../../types/dashboard";
import type { BlockchainHealthSnapshot, ComponentHealth, HealthComponent, OverallHealth, SystemHealthResponse } from "../../types/health";
import { truncateHex } from "../../utils/truncateHex";
import { relativeTime } from "../../utils/relativeTime";

type Tone = "success" | "warning" | "danger" | "neutral";

const TONE_CLASSES: Record<Tone, string> = {
  success: "border-success/40 bg-success-muted text-success",
  warning: "border-warning/40 bg-warning-muted text-warning",
  danger: "border-danger/40 bg-danger-muted text-danger",
  neutral: "border-line-strong bg-surface-hover text-ink-faint",
};

const TONE_TEXT_CLASSES: Record<Tone, string> = {
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
  neutral: "text-ink",
};

const COMPONENT_TONE: Record<ComponentHealth, Tone> = {
  ONLINE: "success",
  DEGRADED: "warning",
  OFFLINE: "danger",
  UNKNOWN: "neutral",
};

const OVERALL_TONE: Record<OverallHealth, Tone> = {
  HEALTHY: "success",
  DEGRADED: "warning",
  CRITICAL: "danger",
};

const PLATFORM_HEALTH_TONE: Record<PlatformKpis["platform_health"], Tone> = {
  HEALTHY: "success",
  WARNING: "warning",
  CRITICAL: "danger",
};

const SEVERITY_TONE: Record<RecentTransaction["severity"], Tone> = {
  low: "success",
  medium: "warning",
  high: "danger",
  critical: "danger",
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

function Pill({ label, tone }: { label: string; tone: Tone }) {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONE_CLASSES[tone]}`}>
      {label}
    </span>
  );
}

function Card({ title, children, className = "" }: { title: string; children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border border-line bg-surface p-6 ${className}`}>
      <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">{title}</p>
      <div className="mt-4">{children}</div>
    </div>
  );
}

function SectionSpinner() {
  return (
    <div className="flex items-center gap-2 text-sm text-ink-muted">
      <Spinner size="sm" />
      Loading…
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

interface ResourceState<T> {
  status: "loading" | "success" | "error";
  data: T | null;
  error: NormalizedError | null;
}

function useResource<T>(fetcher: () => Promise<{ ok: boolean; data: T | null; error: NormalizedError | null }>) {
  const [state, setState] = useState<ResourceState<T>>({ status: "loading", data: null, error: null });
  const [tick, setTick] = useState(0);

  const load = useCallback(() => {
    let cancelled = false;
    setState({ status: "loading", data: null, error: null });

    fetcher().then((result) => {
      if (cancelled) return;
      if (result.ok && result.data !== null) {
        setState({ status: "success", data: result.data, error: null });
      } else {
        setState({ status: "error", data: null, error: result.error });
      }
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick]);

  useEffect(() => load(), [load]);

  const refetch = useCallback(() => setTick((t) => t + 1), []);
  return { ...state, refetch };
}

function statusLabel(status: ComponentHealth): string {
  return status.charAt(0) + status.slice(1).toLowerCase();
}

export default function OverviewPage() {
  const overview = useResource<OverviewResponse>(getOverview);
  const kpis = useResource<PlatformKpis>(async () => {
    const res = await getKpis();
    return { ok: res.ok, data: res.data?.kpis ?? null, error: res.error };
  });
  const systemHealth = useResource<SystemHealthResponse>(getSystemHealth);
  const blockchainHealth = useResource<BlockchainHealthSnapshot>(getBlockchainHealth);
  const recentActivity = useResource<RecentTransactionsResponse>(() => getRecentTransactions(8));

  const components: HealthComponent[] = systemHealth.data?.components ?? [];
  const aiComponent = components.find((c) => c.component === "ai_engine");

  return (
    <div className="space-y-6">
      <PageHeader
        title="Overview"
        description="Fleet-wide security posture, system health, and recent platform activity."
        actions={
          systemHealth.status === "success" && systemHealth.data ? (
            <Pill label={`System: ${systemHealth.data.overall_status}`} tone={OVERALL_TONE[systemHealth.data.overall_status]} />
          ) : undefined
        }
      />

      {/* System health */}
      <Card title="System Health">
        {systemHealth.status === "loading" ? (
          <SectionSpinner />
        ) : systemHealth.status === "error" && systemHealth.error ? (
          <SectionError error={systemHealth.error} onRetry={systemHealth.refetch} />
        ) : components.length === 0 ? (
          <p className="text-sm text-ink-faint">No component health data reported.</p>
        ) : (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {components.map((component) => (
              <div key={component.component} className="rounded-md border border-line bg-surface-raised p-4">
                <p className="text-xs text-ink-faint">{COMPONENT_LABELS[component.component] ?? component.component}</p>
                <div className="mt-2">
                  <Pill label={statusLabel(component.status)} tone={COMPONENT_TONE[component.status]} />
                </div>
                {component.detail ? <p className="mt-2 text-xs text-ink-muted">{component.detail}</p> : null}
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* AI + Blockchain status */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="AI Status">
          {systemHealth.status === "loading" ? (
            <SectionSpinner />
          ) : systemHealth.status === "error" && systemHealth.error ? (
            <SectionError error={systemHealth.error} onRetry={systemHealth.refetch} />
          ) : aiComponent ? (
            <div className="space-y-2">
              <Pill label={statusLabel(aiComponent.status)} tone={COMPONENT_TONE[aiComponent.status]} />
              <p className="text-sm text-ink-muted">{aiComponent.detail ?? "No further detail reported."}</p>
              <p className="text-xs text-ink-faint">Checked {relativeTime(aiComponent.checked_at)}</p>
            </div>
          ) : (
            <p className="text-sm text-ink-faint">AI engine status was not reported by the health check.</p>
          )}
        </Card>

        <Card title="Blockchain Status">
          {blockchainHealth.status === "loading" ? (
            <SectionSpinner />
          ) : blockchainHealth.status === "error" && blockchainHealth.error ? (
            <SectionError error={blockchainHealth.error} onRetry={blockchainHealth.refetch} />
          ) : blockchainHealth.data ? (
            <div className="space-y-3">
              <Pill
                label={blockchainHealth.data.connected ? "Connected" : "Unreachable"}
                tone={blockchainHealth.data.connected ? "success" : "danger"}
              />
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                <dt className="text-ink-faint">Network</dt>
                <dd className="text-ink">{blockchainHealth.data.network}</dd>
                <dt className="text-ink-faint">Latest block</dt>
                <dd className="tabular-nums text-ink">{blockchainHealth.data.currentBlock ?? "—"}</dd>
                <dt className="text-ink-faint">Wallet balance</dt>
                <dd className="tabular-nums text-ink">{blockchainHealth.data.walletBalance ?? "—"}</dd>
                <dt className="text-ink-faint">Gas price</dt>
                <dd className="tabular-nums text-ink">{blockchainHealth.data.gasPriceGwei ?? "—"}</dd>
                <dt className="text-ink-faint">Contract</dt>
                <dd className="font-mono text-ink" title={blockchainHealth.data.contractAddress ?? undefined}>
                  {blockchainHealth.data.contractAddress ? truncateHex(blockchainHealth.data.contractAddress) : "—"}
                </dd>
              </dl>
            </div>
          ) : (
            <p className="text-sm text-ink-faint">No blockchain health data available.</p>
          )}
        </Card>
      </div>

      {/* Device / platform statistics */}
      <Card title="Device & Platform Statistics">
        {overview.status === "loading" ? (
          <SectionSpinner />
        ) : overview.status === "error" && overview.error ? (
          <SectionError error={overview.error} onRetry={overview.refetch} />
        ) : overview.data ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <StatTile label="Registered Devices" value={overview.data.overview.registered_devices} />
              <StatTile label="Active Threats" value={overview.data.overview.active_threats} tone={overview.data.overview.active_threats > 0 ? "warning" : "success"} />
              <StatTile label="Evidence Records" value={overview.data.overview.evidence_count} />
              <StatTile label="Custody Records" value={overview.data.overview.custody_records} />
              <StatTile label="Verified Evidence" value={overview.data.overview.verified_evidence} tone="success" />
              <StatTile
                label="Tampered Evidence"
                value={overview.data.overview.tampered_evidence}
                tone={overview.data.overview.tampered_evidence > 0 ? "danger" : "success"}
              />
              <StatTile label="Authentications" value={overview.data.overview.authentication_count} />
              <StatTile label="Threat Profiles" value={overview.data.overview.threat_count} />
            </div>

            {kpis.status === "success" && kpis.data ? (
              <div className="flex flex-wrap items-center gap-3 border-t border-line pt-4">
                <Pill label={`Platform: ${kpis.data.platform_health}`} tone={PLATFORM_HEALTH_TONE[kpis.data.platform_health]} />
                <span className="text-sm text-ink-muted">
                  Integrity score: <span className="tabular-nums text-ink">{kpis.data.integrity_score}%</span>
                </span>
                <span className="text-sm text-ink-muted">
                  Avg. risk score: <span className="tabular-nums text-ink">{kpis.data.avg_risk_score}</span>
                </span>
              </div>
            ) : kpis.status === "loading" ? (
              <div className="border-t border-line pt-4">
                <SectionSpinner />
              </div>
            ) : null}
          </div>
        ) : (
          <p className="text-sm text-ink-faint">No platform statistics available.</p>
        )}
      </Card>

      {/* Recent activity */}
      <Card title="Recent Activity">
        {recentActivity.status === "loading" ? (
          <SectionSpinner />
        ) : recentActivity.status === "error" && recentActivity.error ? (
          <SectionError error={recentActivity.error} onRetry={recentActivity.refetch} />
        ) : recentActivity.data && recentActivity.data.transactions.length > 0 ? (
          <ul className="divide-y divide-line">
            {recentActivity.data.transactions.map((event, index) => (
              <li key={`${event.type}-${event.timestamp}-${index}`} className="flex items-center justify-between gap-4 py-3">
                <div>
                  <p className="text-sm text-ink">{event.title}</p>
                  <p className="text-xs text-ink-faint">{relativeTime(event.timestamp)}</p>
                </div>
                <Pill label={event.severity.toUpperCase()} tone={SEVERITY_TONE[event.severity]} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-ink-faint">No recent activity recorded yet.</p>
        )}
      </Card>
    </div>
  );
}

function StatTile({ label, value, tone }: { label: string; value: number; tone?: Tone }) {
  return (
    <div className="rounded-md border border-line bg-surface-raised p-4">
      <p className="text-xs uppercase tracking-wide text-ink-faint">{label}</p>
      <p className={`tabular-nums mt-2 text-2xl font-semibold ${tone ? TONE_TEXT_CLASSES[tone] : "text-ink"}`}>
        {value}
      </p>
    </div>
  );
}
