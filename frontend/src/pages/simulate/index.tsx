import { useState } from "react";
import type { FormEvent } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Spinner } from "../../components/ui/Spinner";
import { simulateAttack } from "../../api/simulation";
import type { NormalizedError } from "../../api/envelopes";
import type { AttackRequest, AttackResponse, AttackType } from "../../types/attack";
import { riskTier } from "../../utils/riskTier";
import { truncateHex } from "../../utils/truncateHex";
import { relativeTime } from "../../utils/relativeTime";

const ATTACK_TYPE_OPTIONS: { value: AttackType; label: string }[] = [
  { value: "DDOS", label: "DDoS" },
  { value: "INJECTION", label: "Injection" },
  { value: "REPLAY", label: "Replay" },
  { value: "MAN_IN_THE_MIDDLE", label: "Man in the Middle" },
  { value: "BRUTE_FORCE", label: "Brute Force" },
  { value: "SPOOFING", label: "Spoofing" },
  { value: "JAMMING", label: "Jamming" },
  { value: "UNKNOWN", label: "Unknown" },
];

interface FormState {
  device_id: string;
  attack_type: AttackType | "";
  source_ip: string;
  payload_sample: string;
}

interface FormErrors {
  device_id?: string;
  attack_type?: string;
  source_ip?: string;
  payload_sample?: string;
}

const INITIAL_FORM: FormState = {
  device_id: "",
  attack_type: "",
  source_ip: "",
  payload_sample: "",
};

const IPV4_RE = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/;
const IPV6_RE = /^[0-9a-fA-F:]+$/;

function isValidIp(value: string): boolean {
  const ipv4Match = value.match(IPV4_RE);
  if (ipv4Match) {
    return ipv4Match.slice(1).every((octet) => Number(octet) <= 255);
  }
  return IPV6_RE.test(value) && value.includes(":");
}

function validate(form: FormState): FormErrors {
  const errors: FormErrors = {};

  const deviceId = form.device_id.trim();
  if (!deviceId) {
    errors.device_id = "Device ID is required.";
  } else if (deviceId.length < 3 || deviceId.length > 100) {
    errors.device_id = "Device ID must be between 3 and 100 characters.";
  }

  if (!form.attack_type) {
    errors.attack_type = "Select an attack type.";
  }

  if (form.source_ip.trim() && !isValidIp(form.source_ip.trim())) {
    errors.source_ip = "Enter a valid IPv4 or IPv6 address.";
  }

  if (form.payload_sample.length > 1000) {
    errors.payload_sample = "Payload sample must be 1000 characters or fewer.";
  }

  return errors;
}

interface ErrorPresentation {
  title: string;
  tone: "warning" | "danger";
}

function classifyError(error: NormalizedError): ErrorPresentation {
  if (error.status === 503) {
    return { title: "AI engine unavailable", tone: "warning" };
  }
  if (error.status === 422) {
    return { title: "Validation error", tone: "danger" };
  }
  if (error.status === undefined) {
    return { title: "Network error", tone: "danger" };
  }
  if (error.status === 404) {
    return { title: "Device not found", tone: "danger" };
  }
  return { title: "Request failed", tone: "danger" };
}

const TONE_CLASSES: Record<ErrorPresentation["tone"], string> = {
  warning: "border-warning/40 bg-warning-muted text-warning",
  danger: "border-danger/40 bg-danger-muted text-danger",
};

interface StatPillProps {
  label: string;
  value: string;
  tone: "success" | "warning" | "danger" | "neutral";
}

const PILL_TONE_CLASSES: Record<StatPillProps["tone"], string> = {
  success: "border-success/40 bg-success-muted text-success",
  warning: "border-warning/40 bg-warning-muted text-warning",
  danger: "border-danger/40 bg-danger-muted text-danger",
  neutral: "border-line-strong bg-surface-hover text-ink-faint",
};

function StatTile({ label, value, tone }: StatPillProps) {
  return (
    <div className="rounded-md border border-line bg-surface-raised p-4">
      <p className="text-xs uppercase tracking-wide text-ink-faint">{label}</p>
      <span
        className={`mt-2 inline-flex rounded-full border px-2.5 py-0.5 text-sm font-medium ${PILL_TONE_CLASSES[tone]}`}
      >
        {value}
      </span>
    </div>
  );
}

function RiskTierBadge({ score }: { score: number }) {
  const tier = riskTier(score);
  const toneByTier: Record<string, StatPillProps["tone"]> = {
    CRITICAL: "danger",
    HIGH: "danger",
    MEDIUM: "warning",
    LOW: "success",
  };
  return (
    <div className="rounded-md border border-line bg-surface-raised p-4">
      <p className="text-xs uppercase tracking-wide text-ink-faint">Risk Score</p>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="tabular-nums text-2xl font-semibold text-ink">{score.toFixed(1)}</span>
        <span
          className={`rounded-full border px-2 py-0.5 text-xs font-medium ${PILL_TONE_CLASSES[toneByTier[tier]]}`}
        >
          {tier}
        </span>
      </div>
    </div>
  );
}

export default function SimulateAttackPage() {
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [errors, setErrors] = useState<FormErrors>({});
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AttackResponse | null>(null);
  const [requestError, setRequestError] = useState<NormalizedError | null>(null);

  const updateField = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const validationErrors = validate(form);
    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) {
      return;
    }

    const payload: AttackRequest = {
      device_id: form.device_id.trim(),
      attack_type: form.attack_type as AttackType,
      source_ip: form.source_ip.trim() || null,
      payload_sample: form.payload_sample.trim() || null,
    };

    setLoading(true);
    setRequestError(null);
    setResult(null);

    const response = await simulateAttack(payload);

    setLoading(false);
    if (response.ok && response.data) {
      setResult(response.data);
    } else if (response.error) {
      setRequestError(response.error);
    }
  };

  const errorPresentation = requestError ? classifyError(requestError) : null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Attack Simulation"
        description="Submit a simulated attack to SentinelX and review the AI risk analysis."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[420px_1fr]">
        <form
          onSubmit={handleSubmit}
          noValidate
          className="space-y-5 rounded-lg border border-line bg-surface p-6"
        >
          <div>
            <label htmlFor="device_id" className="text-xs font-medium uppercase tracking-wide text-ink-muted">
              Device ID
            </label>
            <input
              id="device_id"
              type="text"
              value={form.device_id}
              onChange={(e) => updateField("device_id", e.target.value)}
              placeholder="SHIELD-001"
              disabled={loading}
              className="mt-1.5 w-full rounded-md border border-line bg-surface-raised px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none disabled:opacity-50"
            />
            {errors.device_id ? <p className="mt-1.5 text-xs text-danger">{errors.device_id}</p> : null}
          </div>

          <div>
            <label htmlFor="attack_type" className="text-xs font-medium uppercase tracking-wide text-ink-muted">
              Attack Type
            </label>
            <select
              id="attack_type"
              value={form.attack_type}
              onChange={(e) => updateField("attack_type", e.target.value as AttackType)}
              disabled={loading}
              className="mt-1.5 w-full rounded-md border border-line bg-surface-raised px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none disabled:opacity-50"
            >
              <option value="" disabled>
                Select attack type
              </option>
              {ATTACK_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            {errors.attack_type ? <p className="mt-1.5 text-xs text-danger">{errors.attack_type}</p> : null}
          </div>

          <div>
            <label htmlFor="source_ip" className="text-xs font-medium uppercase tracking-wide text-ink-muted">
              Source IP <span className="normal-case text-ink-faint">(optional)</span>
            </label>
            <input
              id="source_ip"
              type="text"
              value={form.source_ip}
              onChange={(e) => updateField("source_ip", e.target.value)}
              placeholder="192.168.1.100"
              disabled={loading}
              className="mt-1.5 w-full rounded-md border border-line bg-surface-raised px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none disabled:opacity-50"
            />
            {errors.source_ip ? <p className="mt-1.5 text-xs text-danger">{errors.source_ip}</p> : null}
          </div>

          <div>
            <label htmlFor="payload_sample" className="text-xs font-medium uppercase tracking-wide text-ink-muted">
              Payload Sample <span className="normal-case text-ink-faint">(optional)</span>
            </label>
            <textarea
              id="payload_sample"
              rows={4}
              value={form.payload_sample}
              onChange={(e) => updateField("payload_sample", e.target.value)}
              placeholder="Raw packet or request sample for analysis context"
              disabled={loading}
              className="mt-1.5 w-full resize-none rounded-md border border-line bg-surface-raised px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none disabled:opacity-50"
            />
            <div className="mt-1 flex items-center justify-between">
              {errors.payload_sample ? (
                <p className="text-xs text-danger">{errors.payload_sample}</p>
              ) : (
                <span />
              )}
              <span className="tabular-nums text-xs text-ink-faint">{form.payload_sample.length}/1000</span>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-md bg-accent px-4 py-2.5 text-sm font-semibold text-background transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? (
              <>
                <Spinner size="sm" />
                Running simulation…
              </>
            ) : (
              "Run Simulation"
            )}
          </button>
        </form>

        <div className="min-h-[420px] rounded-lg border border-line bg-surface p-6">
          {errorPresentation && requestError ? (
            <div className={`mb-6 rounded-md border p-4 ${TONE_CLASSES[errorPresentation.tone]}`}>
              <p className="text-sm font-semibold">{errorPresentation.title}</p>
              <p className="mt-1 text-sm text-ink-muted">{requestError.message}</p>
            </div>
          ) : null}

          {loading ? (
            <div className="flex min-h-[320px] flex-col items-center justify-center gap-3 text-ink-muted">
              <Spinner size="lg" />
              <p className="text-sm">Awaiting SentinelX analysis…</p>
            </div>
          ) : result ? (
            <div className="space-y-6">
              <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line pb-4">
                <div>
                  <p className="text-sm text-ink-muted">
                    <span className="text-ink">{result.device_id}</span> · {result.attack_type}
                  </p>
                  <p
                    className="mt-1 font-mono text-xs text-ink-faint"
                    title={result.analysis_id}
                  >
                    Analysis ID: {truncateHex(result.analysis_id, 8, 4)}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-sm text-ink">{new Date(result.timestamp).toLocaleString()}</p>
                  <p className="text-xs text-ink-faint">{relativeTime(result.timestamp)}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                <RiskTierBadge score={result.risk_score} />
                <div className="rounded-md border border-line bg-surface-raised p-4">
                  <p className="text-xs uppercase tracking-wide text-ink-faint">AI Confidence</p>
                  <p className="tabular-nums mt-2 text-2xl font-semibold text-ink">
                    {result.ai_confidence.toFixed(1)}%
                  </p>
                </div>
                <StatTile
                  label="Threat Detected"
                  value={result.threat_detected ? "Yes" : "No"}
                  tone={result.threat_detected ? "danger" : "success"}
                />
                <StatTile
                  label="Blockchain Logged"
                  value={result.blockchain_logged ? "Yes" : "No"}
                  tone={result.blockchain_logged ? "success" : "neutral"}
                />
                <StatTile
                  label="Rolling Key Rotated"
                  value={result.key_rotated ? "Yes" : "No"}
                  tone={result.key_rotated ? "warning" : "neutral"}
                />
                <div className="rounded-md border border-line bg-surface-raised p-4">
                  <p className="text-xs uppercase tracking-wide text-ink-faint">Blockchain Tx Hash</p>
                  {result.blockchain_tx ? (
                    <p className="mt-2 font-mono text-sm text-accent" title={result.blockchain_tx}>
                      {truncateHex(result.blockchain_tx)}
                    </p>
                  ) : (
                    <p className="mt-2 text-sm text-ink-faint">Not logged</p>
                  )}
                </div>
              </div>

              <div className="border-l-2 border-accent bg-surface-raised py-3 pl-4 pr-4">
                <p className="text-xs uppercase tracking-wide text-ink-faint">AI Recommendation</p>
                <p className="mt-1 text-sm text-ink">{result.action_taken}</p>
              </div>
            </div>
          ) : (
            <div className="flex min-h-[320px] flex-col items-center justify-center gap-2 text-center text-ink-faint">
              <p className="text-sm">No simulation has been run yet.</p>
              <p className="text-xs">Fill in the form and run a simulation to see AI analysis results here.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
