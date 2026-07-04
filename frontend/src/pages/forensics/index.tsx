import { useEffect, useState } from "react";
import type { ReactNode, SubmitEvent } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Spinner } from "../../components/ui/Spinner";
import { LoadingView } from "../../components/ui/LoadingView";
import { generateForensicsReport, hashEvidence } from "../../api/forensics";
import { listCustodyRecords } from "../../api/custody";
import type { NormalizedError } from "../../api/envelopes";
import type {
  CustodyRecord,
  CustodyStatus,
  ForensicReport,
  ForensicVerificationStatus,
  HashResult,
  RiskLevel,
} from "../../types/forensics";
import { truncateHex } from "../../utils/truncateHex";
import { relativeTime } from "../../utils/relativeTime";

type Tone = "success" | "warning" | "danger" | "neutral";

const TONE_CLASSES: Record<Tone, string> = {
  success: "border-success/40 bg-success-muted text-success",
  warning: "border-warning/40 bg-warning-muted text-warning",
  danger: "border-danger/40 bg-danger-muted text-danger",
  neutral: "border-line-strong bg-surface-hover text-ink-faint",
};

const CUSTODY_STATUS_TONE: Record<CustodyStatus, Tone> = {
  COLLECTED: "neutral",
  VERIFIED: "success",
  TAMPERED: "danger",
  INVESTIGATING: "warning",
  RESOLVED: "success",
  CLOSED: "neutral",
};

const VERIFICATION_STATUS_TONE: Record<ForensicVerificationStatus, Tone> = {
  VERIFIED: "success",
  TAMPERED: "danger",
  MISSING: "warning",
  CORRUPTED: "danger",
  ERROR: "danger",
  ON_CHAIN_ONLY: "neutral",
};

const RISK_LEVEL_TONE: Record<RiskLevel, Tone> = {
  LOW: "success",
  MEDIUM: "warning",
  HIGH: "danger",
  CRITICAL: "danger",
};

const GRADE_TONE: Record<ForensicReport["integrity_grade"], Tone> = {
  A: "success",
  B: "success",
  C: "warning",
  D: "danger",
  F: "danger",
};

function Pill({ label, tone }: { label: string; tone: Tone }) {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONE_CLASSES[tone]}`}>
      {label}
    </span>
  );
}

function Card({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-6">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">{title}</p>
      {description ? <p className="mt-1 text-xs text-ink-faint">{description}</p> : null}
      <div className="mt-4">{children}</div>
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

function CustodyRow({ record }: { record: CustodyRecord }) {
  return (
    <tr className="hover:bg-surface-hover">
      <td className="px-4 py-3 font-mono text-xs text-ink-muted" title={record.evidence_id}>
        {truncateHex(record.evidence_id, 8, 4)}
      </td>
      <td className="px-4 py-3 text-ink">{record.evidence_type}</td>
      <td className="px-4 py-3">
        <Pill label={record.current_status} tone={CUSTODY_STATUS_TONE[record.current_status]} />
      </td>
      <td className="px-4 py-3 text-ink-muted">{record.collected_by}</td>
      <td className="px-4 py-3 text-ink-muted">{record.verified_by ?? "—"}</td>
      <td className="px-4 py-3 font-mono text-xs text-ink-muted">
        {record.transaction_hash ? (
          <span title={record.transaction_hash}>{truncateHex(record.transaction_hash)}</span>
        ) : (
          "—"
        )}
      </td>
      <td className="px-4 py-3 tabular-nums text-ink">{record.event_count}</td>
      <td className="px-4 py-3 text-ink-muted" title={record.updated_at}>
        {relativeTime(record.updated_at)}
      </td>
    </tr>
  );
}

interface HashToolState {
  status: "idle" | "loading" | "error" | "success";
  result: HashResult | null;
  error: NormalizedError | null;
}

interface ReportLookupState {
  status: "idle" | "loading" | "error" | "success";
  report: ForensicReport | null;
  error: NormalizedError | null;
}

export default function ForensicsPage() {
  const [custodyTick, setCustodyTick] = useState(0);
  const custody = useResource(listCustodyRecords, custodyTick);

  const [hashText, setHashText] = useState("");
  const [hashTool, setHashTool] = useState<HashToolState>({ status: "idle", result: null, error: null });

  const [incidentIdInput, setIncidentIdInput] = useState("");
  const [currentHashInput, setCurrentHashInput] = useState("");
  const [lookup, setLookup] = useState<ReportLookupState>({ status: "idle", report: null, error: null });

  const handleComputeHash = async (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const text = hashText.trim();
    if (!text) return;

    setHashTool({ status: "loading", result: null, error: null });
    const result = await hashEvidence({ type: "text", text });
    if (result.ok && result.data) {
      setHashTool({ status: "success", result: result.data, error: null });
    } else {
      setHashTool({ status: "error", result: null, error: result.error });
    }
  };

  const runReportLookup = async (incidentId: string, currentHash: string) => {
    setLookup({ status: "loading", report: null, error: null });

    const result = await generateForensicsReport({
      incident_id: incidentId,
      current_hash: currentHash || undefined,
    });

    if (result.ok && result.data) {
      setLookup({ status: "success", report: result.data, error: null });
    } else {
      setLookup({ status: "error", report: null, error: result.error });
    }
  };

  const handleReportSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const incidentId = incidentIdInput.trim();
    if (!incidentId) return;
    void runReportLookup(incidentId, currentHashInput.trim());
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Forensics"
        description="Hash verification, forensic reporting, and chain-of-custody records."
      />

      <Card title="Chain of Custody Records" description="All evidence custody records tracked by the platform.">
        {custody.status === "loading" ? (
          <LoadingView label="Loading chain-of-custody records…" />
        ) : custody.status === "error" && custody.error ? (
          <SectionError error={custody.error} onRetry={() => setCustodyTick((t) => t + 1)} />
        ) : !custody.data || custody.data.records.length === 0 ? (
          <p className="text-sm text-ink-faint">No chain-of-custody records exist yet.</p>
        ) : (
          <div className="overflow-x-auto rounded-md border border-line">
            <table className="w-full min-w-[960px] text-left text-sm">
              <thead>
                <tr className="border-b border-line text-xs uppercase tracking-wide text-ink-faint">
                  <th className="px-4 py-3 font-medium">Evidence ID</th>
                  <th className="px-4 py-3 font-medium">Type</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Collected By</th>
                  <th className="px-4 py-3 font-medium">Verified By</th>
                  <th className="px-4 py-3 font-medium">Transaction Hash</th>
                  <th className="px-4 py-3 font-medium">Events</th>
                  <th className="px-4 py-3 font-medium">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {custody.data.records.map((record) => (
                  <CustodyRow key={record.custody_id} record={record} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card
        title="Compute Evidence Hash"
        description="Generate a SHA-256 hash of text evidence — useful for the Current Hash field below."
      >
        <form onSubmit={handleComputeHash} className="flex flex-wrap items-end gap-3">
          <div className="min-w-[260px] flex-1">
            <label htmlFor="hash_text" className="text-xs font-medium uppercase tracking-wide text-ink-muted">
              Evidence Text
            </label>
            <input
              id="hash_text"
              type="text"
              value={hashText}
              onChange={(e) => setHashText(e.target.value)}
              placeholder="GPS signal anomaly detected on UAV-ALPHA-001"
              className="mt-1.5 w-full rounded-md border border-line bg-surface-raised px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={!hashText.trim() || hashTool.status === "loading"}
            className="flex items-center gap-2 rounded-md border border-line bg-surface-raised px-4 py-2 text-sm font-semibold text-ink transition-colors hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-60"
          >
            {hashTool.status === "loading" ? <Spinner size="sm" /> : null}
            Generate Hash
          </button>
        </form>

        {hashTool.status === "error" && hashTool.error ? (
          <p className="mt-3 text-sm text-danger">{hashTool.error.message}</p>
        ) : hashTool.status === "success" && hashTool.result ? (
          <div className="mt-4 rounded-md border border-line bg-surface-raised p-4">
            <p className="font-mono text-sm text-accent" title={hashTool.result.hash}>
              {hashTool.result.hash}
            </p>
            <p className="mt-1 text-xs text-ink-faint">
              {hashTool.result.algorithm} · {hashTool.result.size_bytes} bytes
            </p>
            <button
              type="button"
              onClick={() => setCurrentHashInput(hashTool.result!.hash)}
              className="mt-3 rounded-md border border-line px-3 py-1 text-xs font-medium text-ink-muted transition-colors hover:border-accent hover:text-accent"
            >
              Use as Current Hash
            </button>
          </div>
        ) : null}
      </Card>

      <Card
        title="Forensic Report Lookup"
        description="Generate a full forensic report for an incident — verification, risk, integrity score, and custody history."
      >
        <form onSubmit={handleReportSubmit} className="flex flex-wrap items-end gap-3">
          <div className="min-w-[240px] flex-1">
            <label htmlFor="report_incident_id" className="text-xs font-medium uppercase tracking-wide text-ink-muted">
              Incident ID
            </label>
            <input
              id="report_incident_id"
              type="text"
              value={incidentIdInput}
              onChange={(e) => setIncidentIdInput(e.target.value)}
              placeholder="0xdeadbeef..."
              className="mt-1.5 w-full rounded-md border border-line bg-surface-raised px-3 py-2 font-mono text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
            />
          </div>
          <div className="min-w-[240px] flex-1">
            <label htmlFor="report_current_hash" className="text-xs font-medium uppercase tracking-wide text-ink-muted">
              Current Hash <span className="normal-case text-ink-faint">(optional)</span>
            </label>
            <input
              id="report_current_hash"
              type="text"
              value={currentHashInput}
              onChange={(e) => setCurrentHashInput(e.target.value)}
              placeholder="0xe3b0c44..."
              className="mt-1.5 w-full rounded-md border border-line bg-surface-raised px-3 py-2 font-mono text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={!incidentIdInput.trim() || lookup.status === "loading"}
            className="flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-background transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-60"
          >
            {lookup.status === "loading" ? <Spinner size="sm" /> : null}
            Generate Report
          </button>
        </form>

        <div className="mt-6">
          {lookup.status === "idle" ? (
            <p className="text-sm text-ink-faint">Enter an Incident ID above to generate its forensic report.</p>
          ) : lookup.status === "loading" ? (
            <LoadingView label="Generating forensic report…" />
          ) : lookup.status === "error" ? (
            <div className="rounded-md border border-line bg-surface-raised p-4">
              <p className="text-sm text-danger">{lookup.error?.message ?? "Failed to generate report."}</p>
              <button
                type="button"
                onClick={() => void runReportLookup(incidentIdInput.trim(), currentHashInput.trim())}
                className="mt-2 rounded-md border border-line px-3 py-1 text-xs font-medium text-ink-muted transition-colors hover:border-accent hover:text-accent"
              >
                Retry
              </button>
            </div>
          ) : lookup.report ? (
            <ForensicReportView report={lookup.report} />
          ) : null}
        </div>
      </Card>
    </div>
  );
}

function ForensicReportView({ report }: { report: ForensicReport }) {
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2 border-b border-line pb-4">
        <Pill label={report.verification_status} tone={VERIFICATION_STATUS_TONE[report.verification_status]} />
        <Pill label={`Risk: ${report.risk_level}`} tone={RISK_LEVEL_TONE[report.risk_level]} />
        <Pill label={`Grade ${report.integrity_grade}`} tone={GRADE_TONE[report.integrity_grade]} />
        <span className="tabular-nums text-sm text-ink-muted">Integrity {report.integrity_score}/100</span>
      </div>

      <p className="text-sm text-ink">{report.verification_result}</p>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-ink-faint">Blockchain Hash</p>
          <p className="mt-1 font-mono text-xs text-ink" title={report.blockchain_hash ?? undefined}>
            {report.blockchain_hash ? truncateHex(report.blockchain_hash, 10, 6) : "—"}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-ink-faint">Current Hash</p>
          <p className="mt-1 font-mono text-xs text-ink" title={report.current_hash ?? undefined}>
            {report.current_hash ? truncateHex(report.current_hash, 10, 6) : "—"}
          </p>
        </div>
      </div>

      {report.incident_record ? (
        <div className="rounded-md border border-line bg-surface-raised p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">Incident Record</p>
          <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-4">
            <div>
              <p className="text-xs text-ink-faint">Attack Type</p>
              <p className="text-ink">{report.incident_record.attack_type}</p>
            </div>
            <div>
              <p className="text-xs text-ink-faint">Risk Score</p>
              <p className="tabular-nums text-ink">{report.incident_record.risk_score}</p>
            </div>
            <div>
              <p className="text-xs text-ink-faint">AI Confidence</p>
              <p className="tabular-nums text-ink">{report.incident_record.ai_confidence}%</p>
            </div>
            <div>
              <p className="text-xs text-ink-faint">Status</p>
              <p className="text-ink">{report.incident_record.status_label}</p>
            </div>
            <div className="col-span-2 sm:col-span-4">
              <p className="text-xs text-ink-faint">Action Taken</p>
              <p className="text-ink">{report.incident_record.action_taken}</p>
            </div>
            <div>
              <p className="text-xs text-ink-faint">Timestamp</p>
              <p className="text-ink-muted" title={report.incident_record.timestamp_iso}>
                {relativeTime(report.incident_record.timestamp_iso)}
              </p>
            </div>
          </div>
        </div>
      ) : (
        <p className="text-sm text-ink-faint">No on-chain incident record available for this ID.</p>
      )}

      {report.chain_of_custody ? (
        <div className="rounded-md border border-line bg-surface-raised p-4">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">Chain of Custody</p>
            <Pill label={report.chain_of_custody.current_status} tone={CUSTODY_STATUS_TONE[report.chain_of_custody.current_status]} />
          </div>
          <p className="mt-2 text-sm text-ink-muted">
            Collected by <span className="text-ink">{report.chain_of_custody.collected_by}</span>
            {report.chain_of_custody.verified_by ? (
              <>
                {" "}
                · Verified by <span className="text-ink">{report.chain_of_custody.verified_by}</span>
              </>
            ) : null}
          </p>
          {report.custody_history && report.custody_history.length > 0 ? (
            <ul className="mt-3 space-y-2 divide-y divide-line">
              {report.custody_history.map((event) => (
                <li key={event.event_id} className="flex items-center justify-between gap-4 pt-2 first:pt-0">
                  <div>
                    <p className="text-sm text-ink">
                      {event.event_type} — {event.actor}
                    </p>
                    {event.notes ? <p className="text-xs text-ink-faint">{event.notes}</p> : null}
                  </div>
                  <div className="flex items-center gap-2">
                    <Pill label={event.status} tone={CUSTODY_STATUS_TONE[event.status]} />
                    <span className="text-xs text-ink-faint" title={event.timestamp}>
                      {relativeTime(event.timestamp)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : (
        <p className="text-sm text-ink-faint">No chain-of-custody record exists yet for this evidence ID.</p>
      )}

      <p className="text-xs text-ink-faint" title={report.generated_at}>
        Report generated {relativeTime(report.generated_at)}
      </p>
    </div>
  );
}
