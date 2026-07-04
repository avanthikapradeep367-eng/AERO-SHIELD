import { useEffect, useState } from "react";
import type { ReactNode, SubmitEvent } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Spinner } from "../../components/ui/Spinner";
import { LoadingView } from "../../components/ui/LoadingView";
import { getAuthenticationCount, getAuthenticationHistory, getAuthenticationRecord, getLatestAuthentication } from "../../api/authLedger";
import type { NormalizedError } from "../../api/envelopes";
import type { AuthRecord } from "../../types/blockchain";
import { truncateHex } from "../../utils/truncateHex";
import { relativeTime } from "../../utils/relativeTime";

type Tone = "success" | "warning" | "danger" | "neutral";

const TONE_CLASSES: Record<Tone, string> = {
  success: "border-success/40 bg-success-muted text-success",
  warning: "border-warning/40 bg-warning-muted text-warning",
  danger: "border-danger/40 bg-danger-muted text-danger",
  neutral: "border-line-strong bg-surface-hover text-ink-faint",
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
 * Unlike a plain "data !== null means success" check, this tracks success
 * purely via the `ok` flag — GET /blockchain/authentication/latest can
 * legitimately succeed with `data: null` when no events have been recorded
 * yet, which is an empty state, not an error.
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

type HistoryRow =
  | { authId: string; status: "ok"; record: AuthRecord }
  | { authId: string; status: "error"; error: NormalizedError };

interface HistoryState {
  status: "idle" | "loading" | "success" | "error" | "empty";
  deviceId: string;
  rows: HistoryRow[];
  error: NormalizedError | null;
}

function AuthStatusPill({ success }: { success: boolean }) {
  return <Pill label={success ? "SUCCESS" : "FAILED"} tone={success ? "success" : "danger"} />;
}

export default function AuthenticationPage() {
  const [summaryTick, setSummaryTick] = useState(0);
  const count = useResource(getAuthenticationCount, summaryTick);
  const latest = useResource(getLatestAuthentication, summaryTick);

  const [deviceIdInput, setDeviceIdInput] = useState("");
  const [history, setHistory] = useState<HistoryState>({ status: "idle", deviceId: "", rows: [], error: null });

  const runHistoryLookup = async (deviceId: string) => {
    setHistory({ status: "loading", deviceId, rows: [], error: null });

    const historyResult = await getAuthenticationHistory(deviceId);
    if (!historyResult.ok || !historyResult.data) {
      setHistory({ status: "error", deviceId, rows: [], error: historyResult.error });
      return;
    }

    const { auth_ids } = historyResult.data;
    if (auth_ids.length === 0) {
      setHistory({ status: "empty", deviceId, rows: [], error: null });
      return;
    }

    const rows = await Promise.all(
      auth_ids.map(
        async (authId): Promise<HistoryRow> => {
          const recordResult = await getAuthenticationRecord(authId);
          if (recordResult.ok && recordResult.data) {
            return { authId, status: "ok", record: recordResult.data };
          }
          return { authId, status: "error", error: recordResult.error ?? { message: "Failed to load record." } };
        },
      ),
    );

    rows.sort((a, b) => {
      const ta = a.status === "ok" ? a.record.timestamp : 0;
      const tb = b.status === "ok" ? b.record.timestamp : 0;
      return tb - ta;
    });

    setHistory({ status: "success", deviceId, rows, error: null });
  };

  const handleSearchSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const deviceId = deviceIdInput.trim();
    if (!deviceId) return;
    void runHistoryLookup(deviceId);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Authentication"
        description="On-chain rolling-key authentication ledger for registered devices."
      />

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <Card title="Total Authentication Events">
          {count.status === "loading" ? (
            <SectionSpinner />
          ) : count.status === "error" && count.error ? (
            <SectionError error={count.error} onRetry={() => setSummaryTick((t) => t + 1)} />
          ) : (
            <p className="tabular-nums text-3xl font-semibold text-ink">{count.data?.count ?? 0}</p>
          )}
        </Card>

        <Card title="Most Recent Event">
          {latest.status === "loading" ? (
            <SectionSpinner />
          ) : latest.status === "error" && latest.error ? (
            <SectionError error={latest.error} onRetry={() => setSummaryTick((t) => t + 1)} />
          ) : latest.data ? (
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <AuthStatusPill success={latest.data.success} />
                <span className="tabular-nums font-mono text-xs text-ink-faint">
                  key v{latest.data.rolling_key_version}
                </span>
              </div>
              <p className="text-xs text-ink-faint" title={latest.data.timestamp_iso}>
                {relativeTime(latest.data.timestamp_iso)}
              </p>
              <p className="font-mono text-xs text-ink-muted" title={latest.data.authentication_id}>
                {truncateHex(latest.data.authentication_id, 8, 4)}
              </p>
            </div>
          ) : (
            <p className="text-sm text-ink-faint">No authentication events recorded yet.</p>
          )}
        </Card>
      </div>

      <div className="rounded-lg border border-line bg-surface p-6">
        <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">Authentication History</p>
        <form onSubmit={handleSearchSubmit} className="mt-4 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[220px]">
            <label htmlFor="device_id_search" className="text-xs font-medium uppercase tracking-wide text-ink-muted">
              Device ID
            </label>
            <input
              id="device_id_search"
              type="text"
              value={deviceIdInput}
              onChange={(e) => setDeviceIdInput(e.target.value)}
              placeholder="SHIELD-001"
              className="mt-1.5 w-full rounded-md border border-line bg-surface-raised px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={!deviceIdInput.trim() || history.status === "loading"}
            className="flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-background transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-60"
          >
            {history.status === "loading" ? <Spinner size="sm" /> : null}
            View History
          </button>
        </form>

        <div className="mt-6">
          {history.status === "idle" ? (
            <p className="text-sm text-ink-faint">Enter a Device ID above to view its authentication history.</p>
          ) : history.status === "loading" ? (
            <LoadingView label={`Loading authentication history for ${history.deviceId}…`} />
          ) : history.status === "error" ? (
            <div className="rounded-md border border-line bg-surface-raised p-4">
              <p className="text-sm text-danger">{history.error?.message ?? "Failed to load authentication history."}</p>
              <button
                type="button"
                onClick={() => void runHistoryLookup(history.deviceId)}
                className="mt-2 rounded-md border border-line px-3 py-1 text-xs font-medium text-ink-muted transition-colors hover:border-accent hover:text-accent"
              >
                Retry
              </button>
            </div>
          ) : history.status === "empty" ? (
            <p className="text-sm text-ink-faint">No authentication events recorded for "{history.deviceId}" yet.</p>
          ) : (
            <div className="overflow-x-auto rounded-md border border-line">
              <table className="w-full min-w-[820px] text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-xs uppercase tracking-wide text-ink-faint">
                    <th className="px-4 py-3 font-medium">Device ID</th>
                    <th className="px-4 py-3 font-medium">Authentication ID</th>
                    <th className="px-4 py-3 font-medium">Timestamp</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Rolling Key Version</th>
                    <th className="px-4 py-3 font-medium">Blockchain Verification</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {history.rows.map((row) => (
                    <tr key={row.authId} className="hover:bg-surface-hover">
                      <td className="px-4 py-3 text-ink">{history.deviceId}</td>
                      <td className="px-4 py-3 font-mono text-xs text-ink-muted" title={row.authId}>
                        {truncateHex(row.authId, 8, 4)}
                      </td>
                      {row.status === "ok" ? (
                        <>
                          <td className="px-4 py-3 text-ink-muted" title={row.record.timestamp_iso}>
                            {relativeTime(row.record.timestamp_iso)}
                          </td>
                          <td className="px-4 py-3">
                            <AuthStatusPill success={row.record.success} />
                          </td>
                          <td className="px-4 py-3 tabular-nums font-mono text-ink">v{row.record.rolling_key_version}</td>
                          <td className="px-4 py-3">
                            <Pill label="Verified" tone="success" />
                          </td>
                        </>
                      ) : (
                        <td className="px-4 py-3 text-xs text-ink-faint" colSpan={4}>
                          {row.error.message || "Failed to load this record."}
                        </td>
                      )}
                    </tr>
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
