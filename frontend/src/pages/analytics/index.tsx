import { Fragment, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Spinner } from "../../components/ui/Spinner";
import { LoadingView } from "../../components/ui/LoadingView";
import {
  getActivityHeatmap,
  getAuthenticationSuccess,
  getDeviceGrowth,
  getIncidentGrowth,
  getRiskDistribution,
  getStatistics,
  getThreatDistribution,
} from "../../api/analytics";
import type { NormalizedError } from "../../api/envelopes";
import type {
  ActivityHeatmapResponse,
  AuthSuccessChartResponse,
  DeviceGrowthChartResponse,
  IncidentGrowthChartResponse,
  RiskDistributionChartResponse,
  StatisticsResponse,
  ThreatDistributionChartResponse,
} from "../../types/dashboard";

type Tone = "success" | "warning" | "danger" | "neutral";

const TONE_CLASSES: Record<Tone, string> = {
  success: "border-success/40 bg-success-muted text-success",
  warning: "border-warning/40 bg-warning-muted text-warning",
  danger: "border-danger/40 bg-danger-muted text-danger",
  neutral: "border-line-strong bg-surface-hover text-ink-faint",
};

const PLATFORM_HEALTH_TONE: Record<StatisticsResponse["platform_kpis"]["platform_health"], Tone> = {
  HEALTHY: "success",
  WARNING: "warning",
  CRITICAL: "danger",
};

const CHART_PALETTE = [
  "var(--color-accent)",
  "var(--color-success)",
  "var(--color-warning)",
  "var(--color-danger)",
  "var(--color-accent-strong)",
  "var(--color-ink-muted)",
];

function Pill({ label, tone }: { label: string; tone: Tone }) {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONE_CLASSES[tone]}`}>
      {label}
    </span>
  );
}

function Card({ title, description, actions, children }: { title: string; description?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">{title}</p>
          {description ? <p className="mt-1 text-xs text-ink-faint">{description}</p> : null}
        </div>
        {actions}
      </div>
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

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-line bg-surface-raised p-4">
      <p className="text-xs uppercase tracking-wide text-ink-faint">{label}</p>
      <p className="tabular-nums mt-2 text-2xl font-semibold text-ink">{value}</p>
    </div>
  );
}

interface ResourceState<T> {
  status: "loading" | "success" | "error";
  data: T | null;
  error: NormalizedError | null;
}

function useResource<T>(
  fetcher: () => Promise<{ ok: boolean; data: T | null; error: NormalizedError | null }>,
  deps: unknown[],
) {
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

/** Vertical bar chart for a single series. */
function BarChart({ labels, values, colorVar = "var(--color-accent)", height = 140 }: { labels: string[]; values: number[]; colorVar?: string; height?: number }) {
  const max = Math.max(1, ...values);
  const barAreaHeight = height - 34;
  return (
    <div className="flex items-end gap-2" style={{ height }}>
      {values.map((v, i) => {
        const h = Math.max(Math.round((v / max) * barAreaHeight), v > 0 ? 3 : 0);
        return (
          <div key={i} className="flex h-full flex-1 flex-col items-center justify-end gap-1">
            <span className="tabular-nums text-[10px] text-ink-muted">{v}</span>
            <div className="w-full rounded-t-sm" style={{ height: h, backgroundColor: colorVar }} />
            <span className="w-full truncate text-center text-[10px] text-ink-faint" title={labels[i]}>
              {labels[i]}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/** Filled area/line chart for a single series, drawn with SVG. */
function AreaChart({ labels, values, colorVar = "var(--color-danger)", fillVar = "var(--color-danger-muted)", height = 140 }: { labels: string[]; values: number[]; colorVar?: string; fillVar?: string; height?: number }) {
  const max = Math.max(1, ...values);
  const width = 100;
  const top = 8;
  const usable = height - top;
  const stepX = values.length > 1 ? width / (values.length - 1) : 0;
  const points = values.map((v, i) => {
    const x = values.length > 1 ? i * stepX : width / 2;
    const y = top + usable - (v / max) * usable;
    return [x, y] as const;
  });
  const linePath = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x},${y}`).join(" ");
  const areaPath = `${linePath} L${points[points.length - 1][0]},${height} L${points[0][0]},${height} Z`;

  return (
    <div>
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="w-full" style={{ height }}>
        <path d={areaPath} fill={fillVar} stroke="none" />
        <path d={linePath} fill="none" stroke={colorVar} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="mt-1 flex justify-between text-[10px] text-ink-faint">
        {labels.map((l, i) => (
          <span key={i} className={i !== 0 && i !== labels.length - 1 ? "hidden sm:inline" : undefined}>
            {l}
          </span>
        ))}
      </div>
    </div>
  );
}

/** Ring chart (pie when hole=0, doughnut when hole>0) via conic-gradient. */
function RingChart({ labels, values, hole = 0.6 }: { labels: string[]; values: number[]; hole?: number }) {
  const total = values.reduce((a, b) => a + b, 0) || 1;
  let cumulative = 0;
  const stops = values
    .map((v, i) => {
      const start = (cumulative / total) * 360;
      cumulative += v;
      const end = (cumulative / total) * 360;
      return `${CHART_PALETTE[i % CHART_PALETTE.length]} ${start}deg ${end}deg`;
    })
    .join(", ");

  return (
    <div className="flex flex-wrap items-center gap-6">
      <div
        className="h-32 w-32 shrink-0 rounded-full"
        style={{
          background: `conic-gradient(${stops})`,
          WebkitMask: `radial-gradient(circle, transparent ${hole * 100}%, black ${hole * 100}%)`,
          mask: `radial-gradient(circle, transparent ${hole * 100}%, black ${hole * 100}%)`,
        }}
      />
      <ul className="space-y-1.5 text-sm">
        {labels.map((l, i) => (
          <li key={l} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: CHART_PALETTE[i % CHART_PALETTE.length] }} />
            <span className="text-ink-muted">{l}</span>
            <span className="tabular-nums text-ink">{values[i]}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Heatmap({ xLabels, yLabels, data }: { xLabels: string[]; yLabels: string[]; data: number[][] }) {
  const max = Math.max(1, ...data.flat());
  return (
    <div className="overflow-x-auto">
      <div className="inline-grid gap-0.5" style={{ gridTemplateColumns: `3rem repeat(${xLabels.length}, minmax(10px, 1fr))` }}>
        <div />
        {xLabels.map((x, i) => (
          <span key={x} className="pb-1 text-center text-[8px] text-ink-faint">
            {i % 3 === 0 ? x.slice(0, 2) : ""}
          </span>
        ))}
        {yLabels.map((y, rowIdx) => (
          <Fragment key={y}>
            <span className="pr-2 text-right text-[10px] text-ink-faint">{y}</span>
            {data[rowIdx].map((v, colIdx) => {
              const intensity = v / max;
              return (
                <div
                  key={colIdx}
                  className="aspect-square rounded-[2px]"
                  style={{
                    backgroundColor:
                      intensity === 0
                        ? "var(--color-surface-hover)"
                        : `color-mix(in srgb, var(--color-accent) ${Math.round(intensity * 100)}%, var(--color-surface-hover))`,
                  }}
                  title={`${y} ${xLabels[colIdx]}: ${v} event(s)`}
                />
              );
            })}
          </Fragment>
        ))}
      </div>
    </div>
  );
}

const DAY_RANGES = [7, 14, 30];

export default function AnalyticsPage() {
  const [statsTick, setStatsTick] = useState(0);
  const stats = useResource<StatisticsResponse>(getStatistics, [statsTick]);

  const [days, setDays] = useState(7);
  const [growthTick, setGrowthTick] = useState(0);
  const deviceGrowth = useResource<DeviceGrowthChartResponse>(() => getDeviceGrowth({ days }), [days, growthTick]);
  const incidentGrowth = useResource<IncidentGrowthChartResponse>(() => getIncidentGrowth({ days }), [days, growthTick]);

  const [distTick, setDistTick] = useState(0);
  const threatDistribution = useResource<ThreatDistributionChartResponse>(getThreatDistribution, [distTick]);
  const authSuccess = useResource<AuthSuccessChartResponse>(getAuthenticationSuccess, [distTick]);

  const [riskTick, setRiskTick] = useState(0);
  const riskDistribution = useResource<RiskDistributionChartResponse>(getRiskDistribution, [riskTick]);

  const [heatmapTick, setHeatmapTick] = useState(0);
  const heatmap = useResource<ActivityHeatmapResponse>(getActivityHeatmap, [heatmapTick]);

  const threatDistIsEmpty = threatDistribution.data?.labels.length === 1 && threatDistribution.data.labels[0] === "NO_DATA";
  const riskDistIsEmpty =
    riskDistribution.data && Object.values(riskDistribution.data.summary).every((v) => v === 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Analytics"
        description="Platform statistics, trends, and distributions across devices, incidents, threats, and authentication."
      />

      {/* Platform statistics */}
      <Card title="Platform Statistics" description="Aggregated KPIs computed across all platform data.">
        {stats.status === "loading" ? (
          <SectionSpinner />
        ) : stats.status === "error" && stats.error ? (
          <SectionError error={stats.error} onRetry={() => setStatsTick((t) => t + 1)} />
        ) : stats.data ? (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center gap-3">
              <Pill
                label={`Platform: ${stats.data.platform_kpis.platform_health}`}
                tone={PLATFORM_HEALTH_TONE[stats.data.platform_kpis.platform_health]}
              />
              <span className="text-sm text-ink-muted">
                Integrity score: <span className="tabular-nums text-ink">{stats.data.platform_kpis.integrity_score}%</span>
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
              <StatTile label="Devices" value={stats.data.platform_kpis.registered_devices} />
              <StatTile label="Incidents" value={stats.data.platform_kpis.total_incidents} />
              <StatTile label="Threats" value={stats.data.platform_kpis.total_threats} />
              <StatTile label="Authentications" value={stats.data.platform_kpis.total_authentications} />
              <StatTile label="Active Threats" value={stats.data.platform_kpis.active_threats} />
              <StatTile label="High-Risk Threats" value={stats.data.platform_kpis.high_risk_threats} />
              <StatTile label="On-Chain Threats" value={stats.data.platform_kpis.on_chain_threats} />
              <StatTile label="Avg Risk Score" value={stats.data.platform_kpis.avg_risk_score} />
              <StatTile label="Avg Threat Level" value={stats.data.platform_kpis.avg_threat_level} />
              <StatTile label="Verified Evidence" value={stats.data.platform_kpis.verified_evidence} />
              <StatTile label="Tampered Evidence" value={stats.data.platform_kpis.tampered_evidence} />
              <StatTile label="Custody Records" value={stats.data.platform_kpis.custody_records} />
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="rounded-md border border-line bg-surface-raised p-4">
                <p className="text-xs uppercase tracking-wide text-ink-faint">Device Registry</p>
                <div className="mt-2 flex items-center gap-4 text-sm">
                  <span className="text-ink-muted">
                    Total: <span className="tabular-nums text-ink">{stats.data.device_stats.total}</span>
                  </span>
                  <span className="text-ink-muted">
                    Active: <span className="tabular-nums text-success">{stats.data.device_stats.active}</span>
                  </span>
                  <span className="text-ink-muted">
                    Inactive: <span className="tabular-nums text-ink-faint">{stats.data.device_stats.inactive}</span>
                  </span>
                </div>
                {Object.keys(stats.data.device_stats.type_distribution).length > 0 ? (
                  <ul className="mt-3 space-y-1">
                    {Object.entries(stats.data.device_stats.type_distribution).map(([type, count]) => (
                      <li key={type} className="flex items-center justify-between text-xs text-ink-muted">
                        <span>{type}</span>
                        <span className="tabular-nums text-ink">{count}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-3 text-xs text-ink-faint">No devices registered yet.</p>
                )}
              </div>

              <div className="rounded-md border border-line bg-surface-raised p-4">
                <p className="text-xs uppercase tracking-wide text-ink-faint">Threats by Status</p>
                {Object.keys(stats.data.threat_stats.by_status).length > 0 ? (
                  <ul className="mt-2 space-y-1">
                    {Object.entries(stats.data.threat_stats.by_status).map(([status, count]) => (
                      <li key={status} className="flex items-center justify-between text-xs text-ink-muted">
                        <span>{status}</span>
                        <span className="tabular-nums text-ink">{count}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-xs text-ink-faint">No threats published yet.</p>
                )}
              </div>
            </div>
          </div>
        ) : null}
      </Card>

      {/* Trends over time */}
      <Card
        title="Growth Trends"
        description="Device registrations and security incidents over time."
        actions={
          <div className="flex gap-1">
            {DAY_RANGES.map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setDays(d)}
                className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                  days === d ? "border-accent text-accent" : "border-line text-ink-muted hover:border-accent hover:text-accent"
                }`}
              >
                {d}d
              </button>
            ))}
          </div>
        }
      >
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div>
            <p className="mb-2 text-sm text-ink">Device Registrations</p>
            {deviceGrowth.status === "loading" ? (
              <SectionSpinner />
            ) : deviceGrowth.status === "error" && deviceGrowth.error ? (
              <SectionError error={deviceGrowth.error} onRetry={() => setGrowthTick((t) => t + 1)} />
            ) : deviceGrowth.data && deviceGrowth.data.summary.total_devices > 0 ? (
              <>
                <BarChart labels={deviceGrowth.data.labels} values={deviceGrowth.data.datasets[0]?.data ?? []} colorVar="var(--color-accent)" />
                <p className="mt-2 text-xs text-ink-faint">
                  {deviceGrowth.data.summary.total_devices} total devices · {deviceGrowth.data.summary.growth_percent}% growth
                </p>
              </>
            ) : (
              <p className="text-sm text-ink-faint">No device registrations recorded yet.</p>
            )}
          </div>

          <div>
            <p className="mb-2 text-sm text-ink">Security Incidents</p>
            {incidentGrowth.status === "loading" ? (
              <SectionSpinner />
            ) : incidentGrowth.status === "error" && incidentGrowth.error ? (
              <SectionError error={incidentGrowth.error} onRetry={() => setGrowthTick((t) => t + 1)} />
            ) : incidentGrowth.data && incidentGrowth.data.summary.total_incidents > 0 ? (
              <>
                <AreaChart labels={incidentGrowth.data.labels} values={incidentGrowth.data.datasets[0]?.data ?? []} />
                <p className="mt-2 text-xs text-ink-faint">{incidentGrowth.data.summary.total_incidents} total incidents</p>
              </>
            ) : (
              <p className="text-sm text-ink-faint">No security incidents recorded yet.</p>
            )}
          </div>
        </div>
      </Card>

      {/* Distributions */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="Threat Distribution" description="Threats broken down by attack category.">
          {threatDistribution.status === "loading" ? (
            <SectionSpinner />
          ) : threatDistribution.status === "error" && threatDistribution.error ? (
            <SectionError error={threatDistribution.error} onRetry={() => setDistTick((t) => t + 1)} />
          ) : threatDistribution.data && !threatDistIsEmpty ? (
            <>
              <RingChart labels={threatDistribution.data.labels} values={threatDistribution.data.datasets[0]?.data ?? []} hole={0.6} />
              <p className="mt-3 text-xs text-ink-faint">
                {threatDistribution.data.summary.categories} categories · most common: {threatDistribution.data.summary.most_common}
              </p>
            </>
          ) : (
            <p className="text-sm text-ink-faint">No threat category data recorded yet.</p>
          )}
        </Card>

        <Card title="Authentication Success Rate" description="Successful vs. failed authentication events.">
          {authSuccess.status === "loading" ? (
            <SectionSpinner />
          ) : authSuccess.status === "error" && authSuccess.error ? (
            <SectionError error={authSuccess.error} onRetry={() => setDistTick((t) => t + 1)} />
          ) : authSuccess.data && authSuccess.data.summary.total > 0 ? (
            <>
              <RingChart labels={authSuccess.data.labels} values={authSuccess.data.datasets[0]?.data ?? []} hole={0} />
              <p className="mt-3 text-xs text-ink-faint">
                {authSuccess.data.summary.total} total events · {authSuccess.data.summary.success_rate} success rate
              </p>
            </>
          ) : (
            <p className="text-sm text-ink-faint">No authentication events recorded yet.</p>
          )}
        </Card>
      </div>

      {/* Risk distribution */}
      <Card title="Risk Score Distribution" description="Threats and incidents grouped by risk tier.">
        {riskDistribution.status === "loading" ? (
          <SectionSpinner />
        ) : riskDistribution.status === "error" && riskDistribution.error ? (
          <SectionError error={riskDistribution.error} onRetry={() => setRiskTick((t) => t + 1)} />
        ) : riskDistribution.data && !riskDistIsEmpty ? (
          <BarChart
            labels={["CRITICAL", "HIGH", "MEDIUM", "LOW"]}
            values={[
              riskDistribution.data.summary.CRITICAL,
              riskDistribution.data.summary.HIGH,
              riskDistribution.data.summary.MEDIUM,
              riskDistribution.data.summary.LOW,
            ]}
            colorVar="var(--color-danger)"
          />
        ) : (
          <p className="text-sm text-ink-faint">No risk-scored threats or incidents recorded yet.</p>
        )}
      </Card>

      {/* Activity heatmap */}
      <Card title="Activity Heatmap" description="Chain-of-custody event intensity by day of week and hour of day.">
        {heatmap.status === "loading" ? (
          <LoadingView label="Loading activity heatmap…" />
        ) : heatmap.status === "error" && heatmap.error ? (
          <SectionError error={heatmap.error} onRetry={() => setHeatmapTick((t) => t + 1)} />
        ) : heatmap.data && heatmap.data.summary.total_events > 0 ? (
          <>
            <Heatmap xLabels={heatmap.data.x_labels} yLabels={heatmap.data.y_labels} data={heatmap.data.data} />
            <p className="mt-3 text-xs text-ink-faint">{heatmap.data.summary.total_events} total custody events</p>
          </>
        ) : (
          <p className="text-sm text-ink-faint">No custody activity recorded yet.</p>
        )}
      </Card>
    </div>
  );
}
