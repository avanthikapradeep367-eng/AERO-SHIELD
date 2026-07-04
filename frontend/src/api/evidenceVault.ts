import { apiClient } from "./client";
import { normalizeBlockchain } from "./envelopes";
import type { IncidentRecord, RecordEvidenceRequest } from "../types/blockchain";

export function recordEvidence(payload: RecordEvidenceRequest) {
  // Trailing slash matches the route's actual registration (@router.post("/")
  // under the /blockchain/evidence prefix); omitting it causes an extra
  // 307-redirect round trip — see api/timeline.ts's getTimeline() for the
  // same fix.
  return normalizeBlockchain<IncidentRecord>(apiClient.post("/blockchain/evidence/", payload));
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
