/**
 * Forensics — hashing/verification and chain of custody (/forensics/*).
 * Mirrors backend/app/schemas/forensics.py and app/forensics/*.
 *
 * This dialect is snake_case with its own envelope shape (distinct from
 * the blockchain layer's camelCase envelope). See api/envelopes.ts.
 */

import type { IncidentRecord } from "./blockchain";

export interface ForensicsEnvelope<T = unknown> {
  success: boolean;
  message: string;
  timestamp: string;
  verificationStatus: string | null;
  blockchainHash: string | null;
  currentHash: string | null;
  transactionHash: string | null;
  data: T;
}

export interface ForensicsErrorResponse {
  success: false;
  message: string;
  errorCode: string;
  details: Record<string, unknown> | null;
}

// ── Hashing (/forensics/hash) ────────────────────────────────────────

/** Matches schemas/forensics.py::HashRequest — exactly one of text/data/data_base64. */
export type HashRequest =
  | { type: "text"; text: string; label?: string | null }
  | { type: "json"; data: Record<string, unknown>; label?: string | null }
  | { type: "bytes"; data_base64: string; label?: string | null };

/** data payload of POST /forensics/hash — see app/forensics/hashing.py. */
export interface HashResult {
  hash: string;
  algorithm: string;
  input_type: "text" | "json" | "file" | "bytes";
  label: string | null;
  size_bytes: number;
  timestamp: string;
  canonical_representation?: string;
  elapsed_ms?: number;
}

// ── Verification (/forensics/verify) ─────────────────────────────────
// Not used by the Forensics page: verify_evidence_endpoint has a side
// effect (it writes a chain-of-custody event on every call), which is
// inappropriate to trigger from a passive lookup/display UI. Reporting
// uses /forensics/report instead, which reads the same data without
// mutating the custody trail. Left minimally typed since unused.

export interface VerifyEvidenceRequest {
  incident_id: string;
  current_hash?: string;
  current_text?: string;
  current_data?: Record<string, unknown>;
}

// ── Reporting (/forensics/report) ────────────────────────────────────

export type ForensicVerificationStatus =
  | "VERIFIED"
  | "TAMPERED"
  | "MISSING"
  | "CORRUPTED"
  | "ERROR"
  | "ON_CHAIN_ONLY";

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface GenerateReportRequest {
  incident_id: string;
  current_hash?: string;
  include_chain_of_custody?: boolean;
  include_incident_record?: boolean;
  analyst?: string;
}

/** data payload of POST /forensics/report — see app/forensics/evidence_utils.py::generate_forensic_report. */
export interface ForensicReport {
  report_id: string;
  evidence_id: string;
  report_type: string;
  analyst: string;
  blockchain_hash: string | null;
  current_hash: string | null;
  verification_status: ForensicVerificationStatus;
  hashes_match: boolean;
  transaction_hash: string | null;
  risk_level: RiskLevel;
  integrity_score: number;
  integrity_grade: "A" | "B" | "C" | "D" | "F";
  verification_result: string;
  timestamp: string;
  generated_at: string;
  incident_record?: IncidentRecord;
  chain_of_custody?: CustodyRecord | null;
  custody_history?: CustodyEvent[];
  custody_event_count?: number;
}

/** data payload of GET /forensics/history/{evidenceId} — unused by this page (superseded by /report). */
export interface EvidenceHistoryEntry {
  evidence_id: string;
  custody_record: CustodyRecord | null;
  history: CustodyEvent[];
  event_count: number;
}

// ── Chain of custody (/forensics/custody) ────────────────────────────

export type CustodyStatus =
  | "COLLECTED"
  | "VERIFIED"
  | "TAMPERED"
  | "INVESTIGATING"
  | "RESOLVED"
  | "CLOSED";

export type CustodyEvidenceType = "INCIDENT" | "FILE" | "LOG" | "REPORT" | "DEVICE";

/** Not used by this page (no create/update UI); left as request-only shapes matching the real schema. */
export interface CreateCustodyRequest {
  evidence_id: string;
  collected_by: string;
  evidence_type?: CustodyEvidenceType;
  description?: string | null;
  transaction_hash?: string | null;
  blockchain_block?: number | null;
}

export interface UpdateCustodyRequest {
  evidence_id: string;
  verified_by: string;
  status?: CustodyStatus;
  notes?: string | null;
  transaction_hash?: string | null;
  blockchain_block?: number | null;
}

/** One entry of CustodyRecord.verification_history — see app/forensics/chain_of_custody.py::CustodyEvent. */
export interface CustodyEvent {
  event_id: string;
  event_type: string;
  actor: string;
  status: CustodyStatus;
  notes: string | null;
  transaction_hash: string | null;
  blockchain_block: number | null;
  timestamp: string;
}

/** Matches CustodyRecord.to_dict() in app/forensics/chain_of_custody.py. */
export interface CustodyRecord {
  custody_id: string;
  evidence_id: string;
  evidence_type: CustodyEvidenceType;
  description: string | null;
  collected_by: string;
  collection_time: string;
  verified_by: string | null;
  verification_time: string | null;
  transaction_hash: string | null;
  blockchain_block: number | null;
  current_status: CustodyStatus;
  verification_history: CustodyEvent[];
  event_count: number;
  created_at: string;
  updated_at: string;
}

/** data payload of GET /forensics/custody/list */
export interface CustodyListResponse {
  records: CustodyRecord[];
  total: number;
}
