import { apiClient } from "./client";
import { normalizeForensics } from "./envelopes";
import type {
  EvidenceHistoryEntry,
  ForensicReport,
  GenerateReportRequest,
  HashRequest,
  HashResult,
  VerifyEvidenceRequest,
} from "../types/forensics";

export function hashEvidence(payload: HashRequest) {
  return normalizeForensics<HashResult>(apiClient.post("/forensics/hash", payload));
}

/**
 * Not called by the Forensics page: this endpoint writes a chain-of-custody
 * event as a side effect on every call, which is inappropriate to trigger
 * from a passive lookup UI. Use generateForensicsReport for read-only lookups.
 */
export function verifyEvidence(payload: VerifyEvidenceRequest) {
  return normalizeForensics<{ status: string }>(apiClient.post("/forensics/verify", payload));
}

export function generateForensicsReport(payload: GenerateReportRequest) {
  return normalizeForensics<ForensicReport>(apiClient.post("/forensics/report", payload));
}

/** Not called by the Forensics page — superseded by generateForensicsReport, which includes the same history plus more. */
export function getEvidenceHistory(evidenceId: string) {
  return normalizeForensics<EvidenceHistoryEntry>(apiClient.get(`/forensics/history/${evidenceId}`));
}
