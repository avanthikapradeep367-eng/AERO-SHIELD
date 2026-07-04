import { useEffect, useState } from "react";
import type { SubmitEvent } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Spinner } from "../../components/ui/Spinner";
import { LoadingView } from "../../components/ui/LoadingView";
import { getThreatStats, listThreats } from "../../api/threatIntel";
import type { NormalizedError } from "../../api/envelopes";
import type { ThreatEntry, ThreatListQuery, ThreatListResponse, ThreatStats, ThreatStatus, ThreatType } from "../../types/threat";
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

const STATUS_TONE: Record<ThreatStatus, Tone> = {
  ACTIVE: "danger",
  INVESTIGATING: "warning",
  RESOLVED: "success",
  REVOKED: "neutral",
};

const RISK_TIER_TONE: Record<ReturnType<typeof riskTier>, Tone> = {
  CRITICAL: "danger",
  HIGH: "danger",
  MEDIUM: "warning",
  LOW: "success",
};

const THREAT_TYPE_OPTIONS: ThreatType[] = ["DEVICE", "IOC", "SIGNATURE", "REPLAY_ATTACK", "MALWARE", "ANOMALY"];
const STATUS_OPTIONS: ThreatStatus[] = ["ACTIVE", "INVESTIGATING", "RESOLVED", "REVOKED"];

function Pill({ label, tone }: { label: string; tone: Tone }) {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONE_CLASSES[tone]}`}>
      {label}
    </span>
  );
}

function SeverityBar({ level }: { level: number }) {
  const tone: Tone = level >= 8 ? "danger" : level >= 5 ? "warning" : "success";
  return (
    <div className="flex items-center gap-2">
      <span className="tabular-nums text-sm text-ink">{level}/10</span>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-surface-hover">
        <div
          className={`h-full ${tone === "danger" ? "bg-danger" : tone === "warning" ? "bg-warning" : "bg-success"}`}
          style={{ width: `${(level / 10) * 100}%` }}
        />
      </div>
    </div>
  );
}

function RiskBadge({ score }: { score: number }) {
  const tier = riskTier(score);
  return (
    <div className="flex items-center gap-2">
      <span className="tabular-nums text-sm text-ink">{score}</span>
      <Pill label={tier} tone={RISK_TIER_TONE[tier]} />
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

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-line bg-surface-raised p-4">
      <p className="text-xs uppercase tracking-wide text-ink-faint">{label}</p>
      <p className="tabular-nums mt-2 text-2xl font-semibold text-ink">{value}</p>
    </div>
  );
}

function ThreatRow({ threat, expanded, onToggle }: { threat: ThreatEntry; expanded: boolean; onToggle: () => void }) {
  return (
    <>
      <tr className="cursor-pointer hover:bg-surface-hover" onClick={onToggle}>
        <td className="px-4 py-3 font-mono text-xs text-ink-muted" title={threat.threat_id}>
          {truncateHex(threat.threat_id, 8, 4)}
        </td>
        <td className="px-4 py-3 text-ink">{threat.device_id}</td>
        <td className="px-4 py-3 text-ink-muted">
          {threat.threat_type}
          <p className="text-xs text-ink-faint">{threat.threat_category}</p>
        </td>
        <td className="px-4 py-3">
          <SeverityBar level={threat.threat_level} />
        </td>
        <td className="px-4 py-3">
          <RiskBadge score={threat.risk_score} />
        </td>
        <td className="px-4 py-3">
          <Pill label={threat.status} tone={STATUS_TONE[threat.status]} />
        </td>
        <td className="px-4 py-3">
          {threat.on_chain ? (
            <span title={threat.blockchain_tx ?? undefined}>
              <Pill label="On-Chain" tone="success" />
            </span>
          ) : (
            <Pill label="In-Memory Only" tone="neutral" />
          )}
        </td>
        <td className="px-4 py-3 text-ink-muted" title={threat.published_at}>
          {relativeTime(threat.published_at)}
        </td>
      </tr>
      {expanded ? (
        <tr className="bg-surface-raised">
          <td colSpan={8} className="px-4 py-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <p className="text-xs uppercase tracking-wide text-ink-faint">Description</p>
                <p className="mt-1 text-sm text-ink">{threat.description ?? "—"}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-ink-faint">Attack Signatures</p>
                <p className="mt-1 text-sm text-ink">
                  {threat.attack_signatures.length > 0 ? threat.attack_signatures.join(", ") : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-ink-faint">IOC Patterns</p>
                <p className="mt-1 font-mono text-xs text-ink">
                  {threat.ioc_patterns.length > 0 ? threat.ioc_patterns.join(", ") : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-ink-faint">Feed Source</p>
                <p className="mt-1 text-sm text-ink">{threat.feed_source}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-ink-faint">Attack Count</p>
                <p className="tabular-nums mt-1 text-sm text-ink">{threat.attack_count}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-ink-faint">Published By</p>
                <p className="mt-1 text-sm text-ink">{threat.published_by}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-ink-faint">Last Seen</p>
                <p className="mt-1 text-sm text-ink-muted" title={threat.last_seen ?? undefined}>
                  {threat.last_seen ? relativeTime(threat.last_seen) : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-ink-faint">Updated</p>
                <p className="mt-1 text-sm text-ink-muted" title={threat.updated_at}>
                  {relativeTime(threat.updated_at)}
                </p>
              </div>
              {threat.on_chain ? (
                <div className="sm:col-span-2 lg:col-span-4">
                  <p className="text-xs uppercase tracking-wide text-ink-faint">Blockchain Transaction</p>
                  <p className="mt-1 font-mono text-xs text-accent" title={threat.blockchain_tx ?? undefined}>
                    {threat.blockchain_tx ? truncateHex(threat.blockchain_tx, 10, 6) : "—"}
                  </p>
                </div>
              ) : null}
            </div>
          </td>
        </tr>
      ) : null}
    </>
  );
}

export default function ThreatIntelligencePage() {
  const [statsTick, setStatsTick] = useState(0);
  const stats = useResource<ThreatStats>(getThreatStats, statsTick);

  const [statusFilter, setStatusFilter] = useState<ThreatStatus | "">("");
  const [typeFilter, setTypeFilter] = useState<ThreatType | "">("");
  const [minRiskScore, setMinRiskScore] = useState(0);
  const [appliedQuery, setAppliedQuery] = useState<ThreatListQuery>({});
  const [listTick, setListTick] = useState(0);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const list = useResource<ThreatListResponse>(() => listThreats(appliedQuery), listTick);

  const applyFilters = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    setAppliedQuery({
      status: statusFilter || undefined,
      threat_type: typeFilter || undefined,
      min_risk_score: minRiskScore || undefined,
    });
    setListTick((t) => t + 1);
  };

  const resetFilters = () => {
    setStatusFilter("");
    setTypeFilter("");
    setMinRiskScore(0);
    setAppliedQuery({});
    setListTick((t) => t + 1);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Threat Intelligence"
        description="Published threat indicators, classifications, and blockchain blacklist sync status."
      />

      <div className="rounded-lg border border-line bg-surface p-6">
        <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">Threat Statistics</p>
        <div className="mt-4">
          {stats.status === "loading" ? (
            <div className="flex items-center gap-2 text-sm text-ink-muted">
              <Spinner size="sm" />
              Loading…
            </div>
          ) : stats.status === "error" && stats.error ? (
            <SectionError error={stats.error} onRetry={() => setStatsTick((t) => t + 1)} />
          ) : stats.data ? (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
              <StatTile label="Total Threats" value={stats.data.total_threats} />
              <StatTile label="Active" value={stats.data.active_threats} />
              <StatTile label="On-Chain" value={stats.data.on_chain_threats} />
              <StatTile label="High Risk (≥80)" value={stats.data.high_risk_count} />
              <StatTile label="Avg Risk Score" value={stats.data.avg_risk_score} />
              <StatTile label="Avg Severity" value={`${stats.data.avg_threat_level}/10`} />
            </div>
          ) : null}
        </div>
      </div>

      <div className="rounded-lg border border-line bg-surface p-6">
        <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">Filters</p>
        <form onSubmit={applyFilters} className="mt-4 flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="status_filter" className="text-xs font-medium uppercase tracking-wide text-ink-muted">
              Status
            </label>
            <select
              id="status_filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as ThreatStatus | "")}
              className="mt-1.5 rounded-md border border-line bg-surface-raised px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none"
            >
              <option value="">All</option>
              {STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="type_filter" className="text-xs font-medium uppercase tracking-wide text-ink-muted">
              Threat Type
            </label>
            <select
              id="type_filter"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value as ThreatType | "")}
              className="mt-1.5 rounded-md border border-line bg-surface-raised px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none"
            >
              <option value="">All</option>
              {THREAT_TYPE_OPTIONS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="min_risk" className="text-xs font-medium uppercase tracking-wide text-ink-muted">
              Min Risk Score
            </label>
            <input
              id="min_risk"
              type="number"
              min={0}
              max={100}
              value={minRiskScore}
              onChange={(e) => setMinRiskScore(Number(e.target.value))}
              className="mt-1.5 w-28 rounded-md border border-line bg-surface-raised px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none"
            />
          </div>

          <button
            type="submit"
            className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-background transition-colors hover:bg-accent-strong"
          >
            Apply Filters
          </button>
          <button
            type="button"
            onClick={resetFilters}
            className="rounded-md border border-line px-4 py-2 text-sm font-medium text-ink-muted transition-colors hover:border-accent hover:text-accent"
          >
            Reset
          </button>
        </form>
      </div>

      <div className="rounded-lg border border-line bg-surface p-6">
        <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">Threat Entries</p>
        <div className="mt-4">
          {list.status === "loading" ? (
            <LoadingView label="Loading threat intelligence entries…" />
          ) : list.status === "error" && list.error ? (
            <SectionError error={list.error} onRetry={() => setListTick((t) => t + 1)} />
          ) : !list.data || list.data.threats.length === 0 ? (
            <p className="text-sm text-ink-faint">No threat entries match the current filters.</p>
          ) : (
            <div className="overflow-x-auto rounded-md border border-line">
              <table className="w-full min-w-[980px] text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-xs uppercase tracking-wide text-ink-faint">
                    <th className="px-4 py-3 font-medium">Threat ID</th>
                    <th className="px-4 py-3 font-medium">Device / IOC</th>
                    <th className="px-4 py-3 font-medium">Type / Category</th>
                    <th className="px-4 py-3 font-medium">Severity</th>
                    <th className="px-4 py-3 font-medium">Risk Score</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Blockchain</th>
                    <th className="px-4 py-3 font-medium">Published</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {list.data.threats.map((threat) => (
                    <ThreatRow
                      key={threat.threat_id}
                      threat={threat}
                      expanded={expandedId === threat.threat_id}
                      onToggle={() => setExpandedId((id) => (id === threat.threat_id ? null : threat.threat_id))}
                    />
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
