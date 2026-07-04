import { apiClient } from "./client";
import { normalizeBlockchain } from "./envelopes";
import type {
  BlockchainDeviceRecord,
  RegisterBlockchainDeviceRequest,
  UpdateDeviceStatusRequest,
} from "../types/blockchain";

export function registerBlockchainDevice(payload: RegisterBlockchainDeviceRequest) {
  return normalizeBlockchain<BlockchainDeviceRecord>(apiClient.post("/blockchain/device/register", payload));
}

export function getBlockchainDeviceCount() {
  return normalizeBlockchain<number>(apiClient.get("/blockchain/device/count"));
}

export function getAllBlockchainDevices() {
  return normalizeBlockchain<BlockchainDeviceRecord[]>(apiClient.get("/blockchain/device/all"));
}

export function updateBlockchainDeviceStatus(payload: UpdateDeviceStatusRequest) {
  return normalizeBlockchain<BlockchainDeviceRecord>(apiClient.put("/blockchain/device/status", payload));
}

export function getBlockchainDevice(deviceId: string) {
  return normalizeBlockchain<BlockchainDeviceRecord>(apiClient.get(`/blockchain/device/${deviceId}`));
}
