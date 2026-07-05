import { useCallback, useEffect, useMemo, useState } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { StatCard } from "../../components/dashboard/StatCard";
import { ChartCard } from "../../components/dashboard/ChartCard";
import { StatusCard } from "../../components/dashboard/StatusCard";
import { ThreatTimelineChart, type ThreatTimelinePoint } from "../../components/dashboard/ThreatTimelineChart";
import { RiskDonutChart, type RiskSegment } from "../../components/dashboard/RiskDonutChart";
import { getIncidentGrowth, getRiskDistribution } from "../../api/analytics";
import { getOverview } from "../../api/dashboard";
import { getBlockchainHealth } from "../../api/systemHealth";
import type { NormalizedError } from "../../api/envelopes";
import type { IncidentGrowthChartResponse, OverviewResponse, RiskDistributionChartResponse } from "../../types/dashboard";
import type { BlockchainHealthSnapshot } from "../../types/health";

interface ResourceState<T> {
  status: "loading" | "success" | "error";
  data: T | null;
  error: NormalizedError | null;
}

function useResource<T>(fetcher: () => Promise<{ ok: boolean; data: T | null; error: NormalizedError | null }>) {
  const [state, setState] = useState<ResourceState<T>>({ status: "loading", data: null, error: null });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading", data: null, error: null });

    fetcher().then((result) => {
      if (cancelled) return;
      setState({
        status: result.ok && result.data !== null ? "success" : "error",
        data: result.data,
        error: result.error,
      });
    });

    return () => {
      cancelled = true;
    };
  }, [fetcher]);

  return state;
}

function AircraftIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
      <path
        d="M12 2 L13.5 9 L21 12 L13.5 13 L12 22 L10.5 13 L3 12 L10.5 9 Z"
        fill="currentColor"
      />
    </svg>
  );
}

function ThreatIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
      <path
        d="M12 3 L22 20 H2 Z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path d="M12 9v5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="12" cy="17" r="0.9" fill="currentColor" />
    </svg>
  );
}

function BlocksIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
      <rect x="3" y="3" width="7" height="7" rx="1.5" fill="currentColor" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.55" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.55" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" fill="currentColor" />
    </svg>
  );
}

function GaugeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
      <path
        d="M4 16a8 8 0 1 1 16 0"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <path d="M12 16 L16 10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function LegendDot({ color, label, value }: { color: string; label: string; value: number }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
      <span className="text-ink-muted">{label}</span>
      <span className="tabular-nums font-medium text-ink">{value}%</span>
    </div>
  );
}

export default function CommandCenterPage() {
  const overview = useResource<OverviewResponse>(useCallback(() => getOverview(), []));
  const blockchainHealth = useResource<BlockchainHealthSnapshot>(useCallback(() => getBlockchainHealth(), []));
  const incidentGrowth = useResource<IncidentGrowthChartResponse>(useCallback(() => getIncidentGrowth({ days: 7 }), []));
  const riskDistribution = useResource<RiskDistributionChartResponse>(useCallback(() => getRiskDistribution(), []));

  const timelineData = useMemo<ThreatTimelinePoint[]>(() => {
    if (!incidentGrowth.data?.labels || !incidentGrowth.data?.datasets?.[0]?.data) {
      return [];
    }

    return incidentGrowth.data.labels.map((label, index) => ({
      label,
      threats: Number(incidentGrowth.data?.datasets?.[0]?.data?.[index] ?? 0),
    }));
  }, [incidentGrowth.data]);

  const riskSegments = useMemo<RiskSegment[]>(() => {
    if (!riskDistribution.data?.labels || !riskDistribution.data?.datasets?.[0]?.data) {
      return [];
    }

    const palette = ["#2f6fed", "#22c3ee", "#f6923a", "#f24c3d"];
    return riskDistribution.data.labels.map((label, index) => ({
      name: label,
      value: Number(riskDistribution.data?.datasets?.[0]?.data?.[index] ?? 0),
      color: palette[index % palette.length],
    }));
  }, [riskDistribution.data]);

  const overviewCounters = overview.data?.overview;
  const blockchainNode = overview.data?.blockchain;
  const backendStatus = overview.status === "success" && overview.data?.success ? "Connected" : overview.status === "error" ? "Unavailable" : "Loading";
  const blockchainStatus = blockchainHealth.status === "success" && blockchainHealth.data?.connected ? "Connected" : "Offline";
  const centerLabel = riskSegments.length > 0 ? riskSegments[0]?.name ?? "—" : "—";

  return (
    <div className="space-y-4">
      <PageHeader
        title="Dashboard"
        description="Live fleet security posture, threat activity, and blockchain integrity."
      />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Registered Devices"
          value={overviewCounters?.registered_devices ?? "—"}
          icon={<AircraftIcon />}
          accent="accent"
        />
        <StatCard
          label="Active Threats"
          value={overviewCounters?.active_threats ?? "—"}
          icon={<ThreatIcon />}
          accent="orange"
        />
        <StatCard
          label="Evidence Blocks"
          value={overviewCounters?.evidence_count ?? "—"}
          icon={<BlocksIcon />}
          accent="cyan"
        />
        <StatCard
          label="Blockchain Node"
          value={blockchainNode?.network ?? "—"}
          icon={<GaugeIcon />}
          accent="success"
        />
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <ChartCard title="Threat Detection Timeline" className="lg:col-span-2">
          {incidentGrowth.status === "loading" ? (
            <p className="text-sm text-ink-faint">Loading threat timeline…</p>
          ) : incidentGrowth.status === "error" && incidentGrowth.error ? (
            <p className="text-sm text-danger">{incidentGrowth.error.message}</p>
          ) : (
            <ThreatTimelineChart data={timelineData} />
          )}
        </ChartCard>

        <ChartCard title="Risk Distribution">
          {riskDistribution.status === "loading" ? (
            <p className="text-sm text-ink-faint">Loading risk distribution…</p>
          ) : riskDistribution.status === "error" && riskDistribution.error ? (
            <p className="text-sm text-danger">{riskDistribution.error.message}</p>
          ) : (
            <>
              <RiskDonutChart data={riskSegments} centerLabel={centerLabel} />
              <div className="mt-3 flex flex-col gap-1.5">
                {riskSegments.map((segment) => (
                  <LegendDot key={segment.name} color={segment.color} label={segment.name} value={segment.value} />
                ))}
              </div>
            </>
          )}
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatusCard label="Backend API" value={backendStatus} tone={backendStatus === "Connected" ? "success" : "warning"} />
        <StatusCard label="Blockchain Status" value={blockchainStatus} tone={blockchainStatus === "Connected" ? "success" : "warning"} />
        <StatusCard
          label="Authentication Logs"
          value={overviewCounters?.authentication_count ? `${overviewCounters.authentication_count}` : "0"}
          tone="info"
        />
      </div>
    </div>
  );
}
