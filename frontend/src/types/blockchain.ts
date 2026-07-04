/**
 * On-chain blockchain layer (Member 2): device registry, authentication
 * ledger, evidence vault, and the shared response envelope every
 * /blockchain/* endpoint uses.
 *
 * Mirrors backend/app/schemas/common.py, schemas/authentication.py,
 * schemas/evidence.py, and app/api/blockchain/device.py's inline models.
 *
 * Note the camelCase fields below — this dialect differs from the core
 * and forensics layers, which use snake_case. See api/envelopes.ts.
 */

/** Uniform success envelope returned by every /blockchain/* endpoint. */
export interface BlockchainApiResponse<T = unknown> {
  success: true;
  message: string;
  timestamp: string;
  transactionHash: string | null;
  gasUsed: string | null;
  data: T;
}

/** Uniform error envelope returned by every /blockchain/* endpoint. */
export interface BlockchainErrorResponse {
  success: false;
  message: string;
  errorCode: string;
  details: Record<string, unknown> | null;
}

// ── Device registry ──────────────────────────────────────────────────

export type BlockchainDeviceType =
  | "UAV"
  | "AIRCRAFT"
  | "GROUND_STATION"
  | "SATELLITE_GW"
  | "IOT_NODE";

export interface RegisterBlockchainDeviceRequest {
  device_id: string;
  device_type: BlockchainDeviceType;
  public_key: string;
}

export interface UpdateDeviceStatusRequest {
  device_id: string;
  active: boolean;
}

/** Matches DeviceRecord.to_dict() in app/blockchain/services/device_service.py. */
export interface BlockchainDeviceRecord {
  device_id: string;
  device_type: string;
  public_key: string;
  owner: string;
  active: boolean;
  registered_at: number;
  updated_at: number;
  registered_at_iso: string;
  updated_at_iso: string;
  [extra: string]: unknown;
}

// ── Authentication ledger ────────────────────────────────────────────

export interface RecordAuthenticationRequest {
  auth_id: string;
  device_id: string;
  key_version: number;
  success: boolean;
  session_id: string;
}

/**
 * Matches AuthRecord.to_dict() in app/blockchain/services/authentication_service.py.
 * Note device_id_bytes is keccak256(device_id), not the human-readable device ID.
 */
export interface AuthRecord {
  authentication_id: string;
  device_id_bytes: string;
  session_id: string;
  timestamp: number;
  timestamp_iso: string;
  rolling_key_version: number;
  auth_status: number;
  success: boolean;
}

/** data payload of GET /blockchain/authentication/history/{deviceId} */
export interface AuthenticationHistory {
  device_id: string;
  auth_ids: string[];
  count: number;
}

// ── Evidence vault ───────────────────────────────────────────────────

export interface RecordEvidenceRequest {
  incident_id: string;
  attack_type: string;
  source_device: string;
  target_device: string;
  risk_score: number;
  ai_confidence: number;
  action_taken: string;
  evidence_hash: string;
}

export type IncidentStatusLabel = "OPEN" | "INVESTIGATING" | "RESOLVED" | "CLOSED";

/**
 * Matches IncidentRecord.to_dict() in app/blockchain/services/evidence_service.py.
 * Note source_device/target_device are keccak256(device_id) hashes, not the
 * human-readable device ID — the on-chain record does not store the original string.
 * There is no on-chain transaction hash field: view calls always return
 * transactionHash: null in the envelope (only write calls populate it).
 */
export interface IncidentRecord {
  incident_id: string;
  source_device: string;
  target_device: string;
  evidence_hash: string;
  timestamp: number;
  timestamp_iso: string;
  attack_type: string;
  action_taken: string;
  risk_score: number;
  ai_confidence: number;
  status: number;
  status_label: IncidentStatusLabel;
}
