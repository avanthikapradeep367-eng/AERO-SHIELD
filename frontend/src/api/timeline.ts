import { apiClient } from "./client";
import { normalizeDashboard } from "./envelopes";
import type { CustodyTimelineResponse, ThreatTimelineResponse, TimelineQuery, TimelineResponse } from "../types/dashboard";

export function getTimeline(query: TimelineQuery = {}) {
  // Trailing slash matches the route's actual registration (@router.get("/") under
  // the /timeline prefix); omitting it causes an extra 307-redirect round trip.
  return normalizeDashboard<TimelineResponse>(apiClient.get("/timeline/", { params: query }));
}

export function getCustodyTimeline(query: TimelineQuery = {}) {
  return normalizeDashboard<CustodyTimelineResponse>(apiClient.get("/timeline/custody", { params: query }));
}

export function getThreatsTimeline(query: TimelineQuery = {}) {
  return normalizeDashboard<ThreatTimelineResponse>(apiClient.get("/timeline/threats", { params: query }));
}
