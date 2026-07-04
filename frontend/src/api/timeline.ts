import { apiClient } from "./client";
import { normalizeDashboard } from "./envelopes";
import type { TimelineQuery, TimelineResponse } from "../types/dashboard";

export function getTimeline(query: TimelineQuery = {}) {
  return normalizeDashboard<TimelineResponse>(apiClient.get("/timeline", { params: query }));
}

export function getCustodyTimeline() {
  return normalizeDashboard<TimelineResponse>(apiClient.get("/timeline/custody"));
}

export function getThreatsTimeline() {
  return normalizeDashboard<TimelineResponse>(apiClient.get("/timeline/threats"));
}
