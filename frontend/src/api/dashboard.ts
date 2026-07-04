import { apiClient } from "./client";
import { normalizeDashboard } from "./envelopes";
import type { AuthRecord, IncidentRecord } from "../types/blockchain";
import type { DeviceStatusResponse, KPIResponse, OverviewResponse, RecentTransactionsResponse } from "../types/dashboard";
import type { ThreatEntry } from "../types/threat";

export function getOverview() {
  return normalizeDashboard<OverviewResponse>(apiClient.get("/dashboard/overview"));
}

export function getRecentTransactions(limit?: number) {
  return normalizeDashboard<RecentTransactionsResponse>(
    apiClient.get("/dashboard/recent-transactions", { params: { limit } }),
  );
}

export function getRecentIncidents() {
  return normalizeDashboard<IncidentRecord[]>(apiClient.get("/dashboard/recent-incidents"));
}

export function getRecentAuthentication() {
  return normalizeDashboard<AuthRecord[]>(apiClient.get("/dashboard/recent-authentication"));
}

export function getThreatFeed() {
  return normalizeDashboard<ThreatEntry[]>(apiClient.get("/dashboard/threat-feed"));
}

export function getDeviceStatus(limit?: number) {
  return normalizeDashboard<DeviceStatusResponse>(apiClient.get("/dashboard/device-status", { params: { limit } }));
}

export function getKpis() {
  return normalizeDashboard<KPIResponse>(apiClient.get("/dashboard/kpis"));
}
