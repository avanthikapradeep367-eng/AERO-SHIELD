import { apiClient } from "./client";
import { normalizeBlockchain } from "./envelopes";
import type { AuthenticationHistory, AuthRecord, RecordAuthenticationRequest } from "../types/blockchain";

export function recordAuthentication(payload: RecordAuthenticationRequest) {
  // Trailing slash matches the route's actual registration (@router.post("/")
  // under the /blockchain/authentication prefix); omitting it causes an
  // extra 307-redirect round trip — see api/timeline.ts's getTimeline() for
  // the same fix.
  return normalizeBlockchain<AuthRecord>(apiClient.post("/blockchain/authentication/", payload));
}

export function getAuthenticationCount() {
  return normalizeBlockchain<{ count: number }>(apiClient.get("/blockchain/authentication/count"));
}

export function getLatestAuthentication() {
  return normalizeBlockchain<AuthRecord | null>(apiClient.get("/blockchain/authentication/latest"));
}

export function getAuthenticationHistory(deviceId: string) {
  return normalizeBlockchain<AuthenticationHistory>(apiClient.get(`/blockchain/authentication/history/${deviceId}`));
}

export function getAuthenticationRecord(authenticationId: string) {
  return normalizeBlockchain<AuthRecord>(apiClient.get(`/blockchain/authentication/${authenticationId}`));
}
