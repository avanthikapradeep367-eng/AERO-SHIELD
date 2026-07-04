import { useEffect, useState } from "react";
import type { ReactNode, SubmitEvent } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Spinner } from "../../components/ui/Spinner";
import { getEvidence, getEvidenceCount, getLatestEvidence } from "../../api/evidenceVault";
import type { NormalizedError } from "../../api/envelopes";
import type { IncidentRecord } from "../../types/blockchain";
import { truncateHex } from "../../utils/truncateHex";
import { relativeTime } from "../../utils/relativeTime";
import { riskTier } from "../../utils/riskTier";

type Tone = "success" | "warning" | "danger" | "neutral";

const TONE_CLASSES: Record<Tone, string> = {
  success: "border-success/40 bg-success-muted text-success",
  warning: "border-warning/40 bg-warning-muted text-warning",
  danger: "border-danger/40 bg-danger-muted text-danger",
  neutral: "border-line-strong bg-surface-hover text-ink-faint",
};

const RISK_TONE: Record<ReturnType<typeof riskTier>, Tone> = {
  CRITICAL: "danger",
  HIGH: "danger",
  MEDIUM: "warning",
  LOW: "success",
};

function Pill({ label, tone }: { label: string; tone: Tone }) {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONE_CLASSES[tone]}`}>
      {label}
    </span>
  );
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-6">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">{title}</p>
      <div className="mt-4">{children}</div>
    </div>
  );
}

function SectionSpinner() {
  return (
    <div className="flex items-center gap-2 text-sm text-ink-muted">
      <Spinner size="sm" />
      Loading…
    </div>
  );
}

function SectionError({ error, onRetry }: { error: NormalizedError; onRetry: () => void }) {
  return (
    <div className="space-y-2">
      <p className="text-sm text-danger">{error.message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="rounded-md border border-line px-3 py-1 text-xs font-medium text-ink-muted transition-colors hover:border-accent hover:text-accent"
      >
        Retry
      </button>
    </div>
  );
}

interface ResourceState<T> {
  status: "loading" | "success" | "error";
  data: T | null;
  error: NormalizedError | null;
}

/**
 * Tracks success purely via the `ok` flag — GET /blockchain/evidence/latest
 * legitimately succeeds with `data: null` when no incidents have been
 * recorded yet, which is an empty state, not an error.
 */
function useResource<T>(fetcher: () => Promise<{ ok: boolean; data: T | null; error: NormalizedError | null }>, tick: number) {
  const [state, setState] = useState<ResourceState<T>>({ status: "loading", data: null, error: null });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading", data: null, error: null });

    fetcher().then((result) => {
      if (cancelled) return;
      if (result.ok) {
        setState({ status: "success", data: result.data, error: null });
      } else {
        setState({ status: "error", data: null, error: result.error });
      }
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick]);

  return state;
}

function RiskBadge({ score }: { score: number }) {
  const tier = riskTier(score);
  return (
    <div className="flex items-center gap-2">
      <span className="tabular-nums text-sm text-ink">{score}</span>
      <Pill label={tier} tone={RISK_TONE[tier]} />
    </div>
  );
}

function EvidenceRow({ record }: { record: IncidentRecord }) {
  return (
    <tr className="hover:bg-surface-hover">
      <td className="px-4 py-3 font-mono text-xs text-ink-muted" title={record.incident_id}>
        {truncateHex(record.incident_id, 8, 4)}
      </td>
      <td className="px-4 py-3">
        <p className="font-mono text-xs text-ink" title={`source_device hash: ${record.source_device}`}>
          {truncateHex(record.source_device, 6, 4)}
        </p>
        <p className="mt-0.5 font-mono text-xs text-ink-faint" title={`target_device hash: ${record.target_device}`}>
          → {truncateHex(record.target_device, 6, 4)}
        </p>
      </td>
      <td className="px-4 py-3 text-ink">{record.attack_type}</td>
      <td className="px-4 py-3">
        <RiskBadge score={record.risk_score} />
      </td>
      <td className="px-4 py-3 tabular-nums text-ink">{record.ai_confidence}%</td>
      <td className="px-4 py-3">
        <Pill label="Verified" tone="success" />
      </td>
      <td
        className="px-4 py-3 text-xs text-ink-faint"
        title="Read endpoints do not return a transaction hash — only the original recording call does."
      >
        Not available
      </td>
      <td className="px-4 py-3 text-ink-muted" title={record.timestamp_iso}>
        {relativeTime(record.timestamp_iso)}
      </td>
    </tr>
  );
}

interface LookupState {
  status: "idle" | "loading" | "error";
  incidentId: string;
  error: NormalizedError | null;
}

export default function EvidencePage() {
  const [summaryTick, setSummaryTick] = useState(0);
  const count = useResource(getEvidenceCount, summaryTick);
  const latest = useResource(getLatestEvidence, summaryTick);

  const [incidentIdInput, setIncidentIdInput] = useState("");
  const [records, setRecords] = useState<IncidentRecord[]>([]);
  const [lookup, setLookup] = useState<LookupState>({ status: "idle", incidentId: "", error: null });

  const runLookup = async (incidentId: string) => {
    setLookup({ status: "loading", incidentId, error: null });

    const result = await getEvidence(incidentId);
    if (!result.ok || !result.data) {
      setLookup({ status: "error", incidentId, error: result.error });
      return;
    }

    const record = result.data;
    setRecords((prev) => [record, ...prev.filter((r) => r.incident_id !== record.incident_id)]);
    setLookup({ status: "idle", incidentId: "", error: null });
  };

  const handleSearchSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const incidentId = incidentIdInput.trim();
    if (!incidentId) return;
    void runLookup(incidentId);
    setIncidentIdInput("");
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Evidence"
        description="Immutable incident evidence sealed in the on-chain Evidence Vault."
      />

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <Card title="Total Incidents Recorded">
          {count.status === "loading" ? (
            <SectionSpinner />
          ) : count.status === "error" && count.error ? (
            <SectionError error={count.error} onRetry={() => setSummaryTick((t) => t + 1)} />
          ) : (
            <p className="tabular-nums text-3xl font-semibold text-ink">{count.data?.count ?? 0}</p>
          )}
        </Card>

        <Card title="Most Recent Incident">
          {latest.status === "loading" ? (
            <SectionSpinner />
          ) : latest.status === "error" && latest.error ? (
            <SectionError error={latest.error} onRetry={() => setSummaryTick((t) => t + 1)} />
          ) : latest.data ? (
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="text-sm text-ink">{latest.data.attack_type}</span>
                <RiskBadge score={latest.data.risk_score} />
              </div>
              <p className="text-xs text-ink-faint" title={latest.data.timestamp_iso}>
                {relativeTime(latest.data.timestamp_iso)}
              </p>
              <p className="font-mono text-xs text-ink-muted" title={latest.data.incident_id}>
                {truncateHex(latest.data.incident_id, 8, 4)}
              </p>
            </div>
          ) : (
            <p className="text-sm text-ink-faint">No incidents recorded yet.</p>
          )}
        </Card>
      </div>

      <div className="rounded-lg border border-line bg-surface p-6">
        <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">Evidence Lookup</p>
        <form onSubmit={handleSearchSubmit} className="mt-4 flex flex-wrap items-end gap-3">
          <div className="min-w-[260px] flex-1">
            <label htmlFor="incident_id_search" className="text-xs font-medium uppercase tracking-wide text-ink-muted">
              Incident ID
            </label>
            <input
              id="incident_id_search"
              type="text"
              value={incidentIdInput}
              onChange={(e) => setIncidentIdInput(e.target.value)}
              placeholder="0xdeadbeef..."
              className="mt-1.5 w-full rounded-md border border-line bg-surface-raised px-3 py-2 font-mono text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={!incidentIdInput.trim() || lookup.status === "loading"}
            className="flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-background transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-60"
          >
            {lookup.status === "loading" ? <Spinner size="sm" /> : null}
            Look Up
          </button>
        </form>
        {lookup.status === "error" ? (
          <div className="mt-4 rounded-md border border-line bg-surface-raised p-4">
            <p className="text-sm text-danger">{lookup.error?.message ?? "Failed to look up this incident."}</p>
            <button
              type="button"
              onClick={() => void runLookup(lookup.incidentId)}
              className="mt-2 rounded-md border border-line px-3 py-1 text-xs font-medium text-ink-muted transition-colors hover:border-accent hover:text-accent"
            >
              Retry
            </button>
          </div>
        ) : null}
        <p className="mt-3 text-xs text-ink-faint">
          There is no bulk evidence listing endpoint — look up incidents by ID one at a time; each successful lookup is
          added to the table below.
        </p>
      </div>

      <div className="rounded-lg border border-line bg-surface p-6">
        <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">Evidence Records</p>
        <div className="mt-4">
          {records.length === 0 ? (
            <p className="text-sm text-ink-faint">
              No incidents looked up yet. Enter an Incident ID above to retrieve and display its evidence record.
            </p>
          ) : (
            <div className="overflow-x-auto rounded-md border border-line">
              <table className="w-full min-w-[960px] text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-xs uppercase tracking-wide text-ink-faint">
                    <th className="px-4 py-3 font-medium">Evidence ID</th>
                    <th className="px-4 py-3 font-medium">Device ID</th>
                    <th className="px-4 py-3 font-medium">Attack Type</th>
                    <th className="px-4 py-3 font-medium">Risk Score</th>
                    <th className="px-4 py-3 font-medium">AI Confidence</th>
                    <th className="px-4 py-3 font-medium">Blockchain Verification</th>
                    <th className="px-4 py-3 font-medium">Transaction Hash</th>
                    <th className="px-4 py-3 font-medium">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {records.map((record) => (
                    <EvidenceRow key={record.incident_id} record={record} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
