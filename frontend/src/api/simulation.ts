import { apiClient } from "./client";
import { normalizeCore } from "./envelopes";
import type { AttackRequest, AttackResponse } from "../types/attack";
import type { CoreHealthResponse } from "../types/health";

export function simulateAttack(payload: AttackRequest) {
  return normalizeCore<AttackResponse>(apiClient.post("/api/v1/simulate-attack", payload));
}

export function getCoreHealth() {
  return normalizeCore<CoreHealthResponse>(apiClient.get("/api/v1/health"));
}
