import { apiClient } from "./client";
import { normalizeForensics } from "./envelopes";
import type {
  PublishThreatRequest,
  ThreatEntry,
  ThreatListQuery,
  ThreatListResponse,
  ThreatStats,
  UpdateThreatRequest,
} from "../types/threat";

export function publishThreat(payload: PublishThreatRequest) {
  return normalizeForensics<ThreatEntry>(apiClient.post("/threat/publish", payload));
}

export function updateThreat(payload: UpdateThreatRequest) {
  return normalizeForensics<ThreatEntry>(apiClient.put("/threat/update", payload));
}

export function listThreats(query: ThreatListQuery = {}) {
  return normalizeForensics<ThreatListResponse>(apiClient.get("/threat/list", { params: query }));
}

export function getThreatStats() {
  return normalizeForensics<ThreatStats>(apiClient.get("/threat/stats"));
}

export function removeThreat(threatId: string, removeFromBlockchain = false) {
  return normalizeForensics<null>(
    apiClient.delete(`/threat/remove/${threatId}`, { params: { remove_from_blockchain: removeFromBlockchain } }),
  );
}

export function getThreat(threatId: string) {
  return normalizeForensics<ThreatEntry>(apiClient.get(`/threat/${threatId}`));
}
