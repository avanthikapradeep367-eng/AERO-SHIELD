import { apiClient } from "./client";
import { normalizeDashboard } from "./envelopes";
import type {
  ActivityHeatmapResponse,
  AuthSuccessChartResponse,
  DeviceGrowthChartResponse,
  DeviceGrowthQuery,
  IncidentGrowthChartResponse,
  RiskDistributionChartResponse,
  StatisticsResponse,
  ThreatDistributionChartResponse,
} from "../types/dashboard";

export function getDeviceGrowth(query: DeviceGrowthQuery = {}) {
  return normalizeDashboard<DeviceGrowthChartResponse>(apiClient.get("/analytics/device-growth", { params: query }));
}

export function getIncidentGrowth(query: DeviceGrowthQuery = {}) {
  return normalizeDashboard<IncidentGrowthChartResponse>(apiClient.get("/analytics/incident-growth", { params: query }));
}

export function getThreatDistribution() {
  return normalizeDashboard<ThreatDistributionChartResponse>(apiClient.get("/analytics/threat-distribution"));
}

export function getAuthenticationSuccess() {
  return normalizeDashboard<AuthSuccessChartResponse>(apiClient.get("/analytics/authentication-success"));
}

export function getRiskDistribution() {
  return normalizeDashboard<RiskDistributionChartResponse>(apiClient.get("/analytics/risk-distribution"));
}

export function getActivityHeatmap() {
  return normalizeDashboard<ActivityHeatmapResponse>(apiClient.get("/analytics/activity-heatmap"));
}

export function getStatistics() {
  return normalizeDashboard<StatisticsResponse>(apiClient.get("/analytics/statistics"));
}
