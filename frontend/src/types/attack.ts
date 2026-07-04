/**
 * Attack simulation pipeline (Member 1 route -> Member 3 AI -> Member 2 chain).
 * Mirrors backend/app/schemas/attack.py.
 */

export type AttackType =
  | "DDOS"
  | "INJECTION"
  | "REPLAY"
  | "MAN_IN_THE_MIDDLE"
  | "BRUTE_FORCE"
  | "SPOOFING"
  | "JAMMING"
  | "UNKNOWN";

export interface AttackRequest {
  device_id: string;
  attack_type: AttackType;
  source_ip?: string | null;
  payload_sample?: string | null;
}

export interface AttackResponse {
  device_id: string;
  attack_type: string;
  analysis_id: string;
  risk_score: number;
  ai_confidence: number;
  threat_detected: boolean;
  key_rotated: boolean;
  blockchain_logged: boolean;
  blockchain_tx: string | null;
  action_taken: string;
  timestamp: string;
}
