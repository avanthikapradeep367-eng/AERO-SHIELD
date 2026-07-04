/**
 * Health & readiness — core (/api/v1/health), system (/system/health),
 * and blockchain (/blockchain/health). The backend uses "HealthResponse"
 * for two different shapes (core vs. dashboard); renamed here to avoid
 * a naming collision.
 */

export type ComponentHealth = "ONLINE" | "DEGRADED" | "OFFLINE" | "UNKNOWN";
export type OverallHealth = "HEALTHY" | "DEGRADED" | "CRITICAL";

/** GET /api/v1/health */
export interface CoreHealthResponse {
  status: string;
  version: string;
  database: string;
  blockchain: string;
  ai_engine: string;
  timestamp: string;
}

/** One entry of the `components` array in SystemHealthResponse — see app/dashboard/health_monitor.py::_component. */
export interface HealthComponent {
  component: string;
  status: ComponentHealth;
  checked_at: string;
  detail?: string;
  [extra: string]: unknown;
}

export interface HealthSummaryCounts {
  online: number;
  degraded: number;
  offline: number;
  unknown: number;
}

/** GET /system/health, /system/health/summary */
export interface SystemHealthResponse {
  success: boolean;
  message?: string;
  overall_status: OverallHealth;
  components?: HealthComponent[];
  summary: HealthSummaryCounts;
  elapsed_ms?: number;
  timestamp: string;
}

/** GET /system/health/live */
export interface LivenessResponse {
  status: string;
  timestamp: string;
}

/** GET /system/health/ready */
export interface ReadinessResponse {
  status: "ready" | "not_ready";
  timestamp: string;
  reason?: string;
  blockchain?: string;
  contract?: string;
}

/** data payload of GET /blockchain/health (always wrapped in BlockchainApiResponse) */
export interface BlockchainHealthSnapshot {
  connected: boolean;
  nodeStatus: string;
  rpcUrl: string | null;
  chainId: number | null;
  network: string;
  currentBlock: number | null;
  walletAddress: string | null;
  walletBalance: string | null;
  contractAddress: string | null;
  gasPrice: string | null;
  gasPriceGwei: string | null;
  timestamp: string;
}
