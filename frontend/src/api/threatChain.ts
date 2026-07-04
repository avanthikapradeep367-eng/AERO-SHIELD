import { apiClient } from "./client";
import { normalizeBlockchain } from "./envelopes";
import type { BlacklistDeviceRequest, ThreatProfile } from "../types/threat";

export function blacklistDevice(payload: BlacklistDeviceRequest) {
  return normalizeBlockchain<ThreatProfile>(apiClient.post("/blockchain/threat/blacklist", payload));
}

export function removeFromBlacklist(deviceId: string) {
  return normalizeBlockchain<null>(apiClient.delete(`/blockchain/threat/remove/${deviceId}`));
}

export function getBlacklistCount() {
  return normalizeBlockchain<number>(apiClient.get("/blockchain/threat/count"));
}

export function getThreatProfile(deviceId: string) {
  return normalizeBlockchain<ThreatProfile>(apiClient.get(`/blockchain/threat/${deviceId}`));
}
