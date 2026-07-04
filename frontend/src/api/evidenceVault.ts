import { apiClient } from "./client";
import { normalizeBlockchain } from "./envelopes";
import type { IncidentRecord, RecordEvidenceRequest } from "../types/blockchain";

export function recordEvidence(payload: RecordEvidenceRequest) {
  return normalizeBlockchain<IncidentRecord>(apiClient.post("/blockchain/evidence", payload));
}

export function getEvidenceCount() {
  return normalizeBlockchain<{ count: number }>(apiClient.get("/blockchain/evidence/count"));
}

export function getLatestEvidence() {
  return normalizeBlockchain<IncidentRecord | null>(apiClient.get("/blockchain/evidence/latest"));
}

export function getEvidence(incidentId: string) {
  return normalizeBlockchain<IncidentRecord>(apiClient.get(`/blockchain/evidence/${incidentId}`));
}
