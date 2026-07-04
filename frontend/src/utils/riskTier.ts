export type RiskTier = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

/** Maps a 0-100 risk score onto the platform's four-tier risk vocabulary. */
export function riskTier(score: number): RiskTier {
  if (score >= 80) return "CRITICAL";
  if (score >= 60) return "HIGH";
  if (score >= 30) return "MEDIUM";
  return "LOW";
}
