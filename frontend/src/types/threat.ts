/**
 * Threat intelligence — both on-chain (/blockchain/threat) and
 * in-memory (/threat) representations. Mirrors backend/app/schemas/threat.py.
 */

/** Matches THREAT_TYPES in app/forensics/threat_intelligence.py. */
export type ThreatType = "DEVICE" | "IOC" | "SIGNATURE" | "REPLAY_ATTACK" | "MALWARE" | "ANOMALY";

/** Matches the STATUS_* constants in app/forensics/threat_intelligence.py. */
export type ThreatStatus = "ACTIVE" | "INVESTIGATING" | "RESOLVED" | "REVOKED";

// ── On-chain (/blockchain/threat) ────────────────────────────────────

export interface BlacklistDeviceRequest {
  device_id: string;
  reason: string;
  risk_score: number;
}

export interface ThreatProfile {
  device_id: string;
  blacklisted: boolean;
  reason: string;
  risk_score: number;
  [extra: string]: unknown;
}

// ── In-memory (/threat) ──────────────────────────────────────────────

export interface PublishThreatRequest {
  device_id: string;
  threat_type: ThreatType;
  threat_level: number;
  risk_score: number;
  threat_category?: string;
  attack_signatures?: string[];
  ioc_patterns?: string[];
  description?: string | null;
  published_by?: string;
  publish_to_blockchain?: boolean;
  threat_id?: string | null;
}

export interface UpdateThreatRequest {
  threat_id: string;
  status?: ThreatStatus;
  risk_score?: number;
  description?: string | null;
}

/** Matches ThreatEntry.to_dict() in app/forensics/threat_intelligence.py. */
export interface ThreatEntry {
  threat_id: string;
  device_id: string;
  threat_type: ThreatType;
  threat_level: number;
  risk_score: number;
  threat_category: string;
  attack_signatures: string[];
  ioc_patterns: string[];
  description: string | null;
  status: ThreatStatus;
  on_chain: boolean;
  blockchain_tx: string | null;
  published_by: string;
  published_at: string;
  updated_at: string;
  attack_count: number;
  last_seen: string | null;
  feed_source: string;
}

export interface ThreatListQuery {
  status?: ThreatStatus;
  threat_type?: ThreatType;
  min_risk_score?: number;
  limit?: number;
}

export interface ThreatListFilters {
  status: string | null;
  threat_type: string | null;
  min_risk_score: number;
}

/** data payload of GET /threat/list */
export interface ThreatListResponse {
  threats: ThreatEntry[];
  total: number;
  filters: ThreatListFilters;
}

/** data payload of GET /threat/stats — see app/forensics/threat_intelligence.py::get_attack_statistics. */
export interface ThreatStats {
  total_threats: number;
  active_threats: number;
  on_chain_threats: number;
  avg_risk_score: number;
  avg_threat_level: number;
  by_type: Record<string, number>;
  by_category: Record<string, number>;
  by_status: Record<string, number>;
  high_risk_count: number;
}
