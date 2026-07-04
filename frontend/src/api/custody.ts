import { apiClient } from "./client";
import { normalizeForensics } from "./envelopes";
import type { CreateCustodyRequest, CustodyListResponse, CustodyRecord, UpdateCustodyRequest } from "../types/forensics";

export function createCustodyRecord(payload: CreateCustodyRequest) {
  return normalizeForensics<CustodyRecord>(apiClient.post("/forensics/custody/create", payload));
}

export function updateCustodyRecord(payload: UpdateCustodyRequest) {
  return normalizeForensics<CustodyRecord>(apiClient.put("/forensics/custody/update", payload));
}

export function listCustodyRecords() {
  return normalizeForensics<CustodyListResponse>(apiClient.get("/forensics/custody/list"));
}
