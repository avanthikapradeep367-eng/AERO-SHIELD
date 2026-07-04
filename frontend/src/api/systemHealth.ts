import { apiClient } from "./client";
import { normalizeBlockchain, normalizeDashboard } from "./envelopes";
import type { BlockchainHealthSnapshot, LivenessResponse, ReadinessResponse, SystemHealthResponse } from "../types/health";

export function getSystemHealth() {
  return normalizeDashboard<SystemHealthResponse>(apiClient.get("/system/health"));
}

export function getSystemHealthSummary() {
  return normalizeDashboard<SystemHealthResponse>(apiClient.get("/system/health/summary"));
}

export function getLiveness() {
  return normalizeDashboard<LivenessResponse>(apiClient.get("/system/health/live"));
}

export function getReadiness() {
  return normalizeDashboard<ReadinessResponse>(apiClient.get("/system/health/ready"));
}

export function getBlockchainHealth() {
  return normalizeBlockchain<BlockchainHealthSnapshot>(apiClient.get("/blockchain/health"));
}
