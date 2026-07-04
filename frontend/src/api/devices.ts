import { apiClient } from "./client";
import { normalizeCore } from "./envelopes";
import type { DeviceRegisterRequest, DeviceResponse } from "../types/device";

export function registerDevice(payload: DeviceRegisterRequest) {
  return normalizeCore<DeviceResponse>(apiClient.post("/api/v1/register-device", payload));
}

export function getDevice(deviceId: string) {
  return normalizeCore<DeviceResponse>(apiClient.get(`/api/v1/device/${deviceId}`));
}
