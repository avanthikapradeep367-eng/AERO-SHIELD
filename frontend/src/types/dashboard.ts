/**
 * Dashboard, analytics, and timeline (/dashboard, /analytics, /timeline).
 * Mirrors backend/app/schemas/dashboard.py.
 *
 * Dialect D: each endpoint returns a typed body with fields at the top
 * level — no single uniform "data" wrapper like the other three dialects.
 */

import type { BlockchainDeviceRecord } from "./blockchain";
import type { ThreatStats } from "./threat";

// ── Dashboard ─────────────────────────────────────────────────────────

/** overview.overview — platform counters, see app/dashboard/dashboard_service.py::get_overview */
export interface OverviewCounters {
  registered_devices: number;
  authentication_count: number;
  evidence_count: number;
  threat_count: number;
  verified_evidence: number;
  tampered_evidence: number;
  active_threats: number;
  custody_records: number;
}

/** overview.blockchain — node/wallet/contract snapshot embedded in the overview response */
export interface OverviewBlockchainNode {
  connected: boolean;
  node_status: string;
  latest_block: number | null;
  chain_id: number | null;
  network: string;
  wallet_address: string | null;
  wallet_balance: string;
  contract_address: string | null;
  gas_price: string | null;
  rpc_url: string | null;
}

/** GET /dashboard/overview */
export interface OverviewResponse {
  success: boolean;
  message: string;
  timestamp: string;
  overview: OverviewCounters;
  blockchain: OverviewBlockchainNode;
  elapsed_ms: number;
}

export interface DashboardResponse {
  data: unknown[];
  [extra: string]: unknown;
}

/** GET /dashboard/kpis — kpis, see app/dashboard/statistics.py::compute_platform_kpis */
export interface PlatformKpis {
  registered_devices: number;
  total_incidents: number;
  total_threats: number;
  total_authentications: number;
  active_threats: number;
  on_chain_threats: number;
  high_risk_threats: number;
  avg_risk_score: number;
  avg_threat_level: number;
  verified_evidence: number;
  tampered_evidence: number;
  integrity_score: number;
  custody_records: number;
  platform_health: "HEALTHY" | "WARNING" | "CRITICAL";
  computed_at: string;
}

export interface KPIResponse {
  success: boolean;
  message: string;
  timestamp: string;
  kpis: PlatformKpis;
}

/** One entry of GET /dashboard/recent-transactions' `transactions` array — shape varies by `type`. */
export interface RecentTransaction {
  type: "EVIDENCE_RECORDED" | "AUTHENTICATION" | "CUSTODY_EVENT";
  title: string;
  timestamp: string;
  icon: string;
  severity: "low" | "medium" | "high" | "critical";
  [extra: string]: unknown;
}

/** GET /dashboard/recent-transactions */
export interface RecentTransactionsResponse {
  success: boolean;
  message: string;
  timestamp: string;
  transactions: RecentTransaction[];
  count: number;
}

/** One entry of GET /dashboard/device-status' `devices` array — see dashboard_service.py::get_device_status */
export interface DeviceStatusEntry extends BlockchainDeviceRecord {
  blacklisted: boolean;
  status_label: "ACTIVE" | "INACTIVE";
  threat_badge: "BLACKLISTED" | "CLEAN";
}

/** GET /dashboard/device-status */
export interface DeviceStatusResponse {
  success: boolean;
  message: string;
  timestamp: string;
  devices: DeviceStatusEntry[];
  count: number;
}

// ── Analytics ─────────────────────────────────────────────────────────
// See app/api/dashboard/analytics.py and app/dashboard/analytics.py — every
// chart endpoint shares the `_chart()` envelope below except activity-heatmap,
// which has its own x_labels/y_labels/data matrix shape.

/** One entry of a chart response's `datasets` array — fields vary per chart, all Chart.js-style hints. */
export interface ChartDataset {
  label?: string;
  type?: "bar" | "line";
  data: number[];
  backgroundColor?: string | string[];
  borderColor?: string;
  borderWidth?: number;
  borderRadius?: number;
  fill?: boolean;
  tension?: number;
  yAxisID?: string;
  [extra: string]: unknown;
}

/** Common envelope shared by every /analytics/* chart endpoint except activity-heatmap. */
export interface ChartResponse<TSummary = Record<string, unknown>> {
  success: boolean;
  message: string;
  timestamp: string;
  chart_type: "bar" | "area" | "doughnut" | "pie";
  title: string;
  labels: string[];
  datasets: ChartDataset[];
  summary: TSummary;
}

/** GET /analytics/device-growth summary — see dashboard/analytics.py::device_growth_chart */
export interface DeviceGrowthSummary {
  total_devices: number;
  new_this_week: number;
  growth_percent: number;
}
export type DeviceGrowthChartResponse = ChartResponse<DeviceGrowthSummary>;

/** GET /analytics/incident-growth summary */
export interface IncidentGrowthSummary {
  total_incidents: number;
  this_week: number;
}
export type IncidentGrowthChartResponse = ChartResponse<IncidentGrowthSummary>;

/** GET /analytics/threat-distribution summary */
export interface ThreatDistributionSummary {
  total: number;
  categories: number;
  most_common: string;
}
export type ThreatDistributionChartResponse = ChartResponse<ThreatDistributionSummary>;

/** GET /analytics/authentication-success summary */
export interface AuthSuccessSummary {
  total: number;
  success: number;
  failed: number;
  success_rate: string;
}
export type AuthSuccessChartResponse = ChartResponse<AuthSuccessSummary>;

/** GET /analytics/risk-distribution summary (the summary IS the bucket counts) */
export interface RiskDistributionSummary {
  CRITICAL: number;
  HIGH: number;
  MEDIUM: number;
  LOW: number;
}
export type RiskDistributionChartResponse = ChartResponse<RiskDistributionSummary>;

/** GET /analytics/activity-heatmap — distinct shape, not a ChartResponse. */
export interface ActivityHeatmapResponse {
  success: boolean;
  message: string;
  timestamp: string;
  chart_type: "heatmap";
  title: string;
  x_labels: string[];
  y_labels: string[];
  data: number[][];
  summary: { total_events: number };
}

/** statistics.device_stats — see app/dashboard/statistics.py::compute_device_stats */
export interface DeviceStats {
  total: number;
  active: number;
  inactive: number;
  type_distribution: Record<string, number>;
}

/** GET /analytics/statistics */
export interface StatisticsResponse {
  success: boolean;
  message: string;
  timestamp: string;
  platform_kpis: PlatformKpis;
  threat_stats: ThreatStats;
  device_stats: DeviceStats;
}

export interface DeviceGrowthQuery {
  days?: number;
}

// ── Timeline ──────────────────────────────────────────────────────────

export interface TimelineEvent {
  id: string;
  type: string;
  timestamp: string;
  summary: string;
  [extra: string]: unknown;
}

export interface TimelineResponse {
  events: TimelineEvent[];
  [extra: string]: unknown;
}

export interface TimelineQuery {
  limit?: number;
}
