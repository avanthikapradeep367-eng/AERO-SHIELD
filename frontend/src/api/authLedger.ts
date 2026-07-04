import { apiClient } from "./client";
import { normalizeBlockchain } from "./envelopes";
import type { AuthenticationHistory, AuthRecord, RecordAuthenticationRequest } from "../types/blockchain";

export function recordAuthentication(payload: RecordAuthenticationRequest) {
  return normalizeBlockchain<AuthRecord>(apiClient.post("/blockchain/authentication", payload));
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
