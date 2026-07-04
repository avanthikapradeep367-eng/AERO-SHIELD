/**
 * Postgres-backed device directory (Member 1).
 * Mirrors backend/app/schemas/device.py.
 */

export type DeviceStatus = "active" | "inactive" | "maintenance";

export interface DeviceRegisterRequest {
  device_id: string;
  device_name: string;
  status?: DeviceStatus;
}

export interface DeviceResponse {
  id: string;
  device_id: string;
  device_name: string;
  status: DeviceStatus;
  created_at: string;
}
