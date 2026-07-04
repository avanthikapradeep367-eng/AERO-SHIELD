import { useEffect, useState } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Spinner } from "../../components/ui/Spinner";
import { LoadingView } from "../../components/ui/LoadingView";
import { getDeviceStatus } from "../../api/dashboard";
import { getAuthenticationHistory, getAuthenticationRecord } from "../../api/authLedger";
import type { NormalizedError } from "../../api/envelopes";
import type { DeviceStatusEntry } from "../../types/dashboard";
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

interface AuthStatusInfo {
  status: "loading" | "success" | "error" | "empty";
  success?: boolean;
  rollingKeyVersion?: number;
  timestampIso?: string;
  error?: NormalizedError;
}

interface ListState {
  status: "loading" | "success" | "error";
  devices: DeviceStatusEntry[];
  error: NormalizedError | null;
}

function riskFromThreatBadge(badge: DeviceStatusEntry["threat_badge"]): { label: string; tone: Tone } {
  return badge === "BLACKLISTED" ? { label: "CRITICAL", tone: "danger" } : { label: "LOW", tone: "success" };
}

function AuthCell({ info }: { info: AuthStatusInfo | undefined }) {
  if (!info || info.status === "loading") {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-ink-faint">
        <Spinner size="sm" />
        Checking…
      </span>
    );
  }
  if (info.status === "error") {
    return <span className="text-xs text-ink-faint">Unavailable</span>;
  }
  if (info.status === "empty") {
    return <span className="text-xs text-ink-faint">No records</span>;
  }
  return <Pill label={info.success ? "SUCCESS" : "FAILED"} tone={info.success ? "success" : "danger"} />;
}

function RollingKeyCell({ info }: { info: AuthStatusInfo | undefined }) {
  if (!info || info.status === "loading") {
    return <span className="text-xs text-ink-faint">—</span>;
  }
  if (info.status !== "success" || info.rollingKeyVersion === undefined) {
    return <span className="text-xs text-ink-faint">—</span>;
  }
  return <span className="tabular-nums font-mono text-sm text-ink">v{info.rollingKeyVersion}</span>;
}

export default function DevicesPage() {
  const [list, setList] = useState<ListState>({ status: "loading", devices: [], error: null });
  const [authStatus, setAuthStatus] = useState<Record<string, AuthStatusInfo>>({});
  const [reloadTick, setReloadTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setList({ status: "loading", devices: [], error: null });

    getDeviceStatus().then((result) => {
      if (cancelled) return;
      if (result.ok && result.data) {
        setList({ status: "success", devices: result.data.devices, error: null });
      } else {
        setList({ status: "error", devices: [], error: result.error });
      }
    });

    return () => {
      cancelled = true;
    };
  }, [reloadTick]);

  useEffect(() => {
    if (list.status !== "success" || list.devices.length === 0) {
      return;
    }

    let cancelled = false;
    setAuthStatus(Object.fromEntries(list.devices.map((d) => [d.device_id, { status: "loading" as const }])));

    list.devices.forEach((device) => {
      getAuthenticationHistory(device.device_id).then((historyResult) => {
        if (cancelled) return;

        if (!historyResult.ok || !historyResult.data) {
          setAuthStatus((prev) => ({ ...prev, [device.device_id]: { status: "error", error: historyResult.error ?? undefined } }));
          return;
        }

        const { auth_ids } = historyResult.data;
        if (auth_ids.length === 0) {
          setAuthStatus((prev) => ({ ...prev, [device.device_id]: { status: "empty" } }));
          return;
        }

        const latestAuthId = auth_ids[auth_ids.length - 1];
        getAuthenticationRecord(latestAuthId).then((recordResult) => {
          if (cancelled) return;

          if (!recordResult.ok || !recordResult.data) {
            setAuthStatus((prev) => ({ ...prev, [device.device_id]: { status: "error", error: recordResult.error ?? undefined } }));
            return;
          }

          const record = recordResult.data;
          setAuthStatus((prev) => ({
            ...prev,
            [device.device_id]: {
              status: "success",
              success: record.success,
              rollingKeyVersion: record.rolling_key_version,
              timestampIso: record.timestamp_iso,
            },
          }));
        });
      });
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [list.status, list.devices]);

  return (
    <div className="space-y-6">
      <PageHeader title="Devices" description="Registered device directory and blockchain identity records." />

      {list.status === "loading" ? (
        <div className="rounded-lg border border-line bg-surface p-6">
          <LoadingView label="Loading registered devices…" />
        </div>
      ) : list.status === "error" ? (
        <div className="rounded-lg border border-line bg-surface p-6">
          <div className="space-y-3">
            <p className="text-sm text-danger">{list.error?.message ?? "Failed to load devices."}</p>
            <button
              type="button"
              onClick={() => setReloadTick((t) => t + 1)}
              className="rounded-md border border-line px-3 py-1.5 text-xs font-medium text-ink-muted transition-colors hover:border-accent hover:text-accent"
            >
              Retry
            </button>
          </div>
        </div>
      ) : list.devices.length === 0 ? (
        <div className="rounded-lg border border-line bg-surface p-10 text-center">
          <p className="text-sm text-ink-muted">No devices registered yet.</p>
          <p className="mt-1 text-xs text-ink-faint">
            Devices appear here once they are registered on-chain via the Device Registry.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-line bg-surface">
          <table className="w-full min-w-[840px] text-left text-sm">
            <thead>
              <tr className="border-b border-line text-xs uppercase tracking-wide text-ink-faint">
                <th className="px-4 py-3 font-medium">Device ID</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Last Seen</th>
                <th className="px-4 py-3 font-medium">Authentication</th>
                <th className="px-4 py-3 font-medium">Rolling Key</th>
                <th className="px-4 py-3 font-medium">Risk Level</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {list.devices.map((device) => {
                const risk = riskFromThreatBadge(device.threat_badge);
                return (
                  <tr key={device.device_id} className="hover:bg-surface-hover">
                    <td className="px-4 py-3">
                      <p className="text-ink">{device.device_id}</p>
                      <p className="text-xs text-ink-faint">{device.device_type}</p>
                    </td>
                    <td className="px-4 py-3">
                      <Pill label={device.status_label} tone={device.status_label === "ACTIVE" ? "success" : "neutral"} />
                    </td>
                    <td className="px-4 py-3 text-ink-muted" title={device.updated_at_iso}>
                      {relativeTime(device.updated_at_iso)}
                    </td>
                    <td className="px-4 py-3">
                      <AuthCell info={authStatus[device.device_id]} />
                    </td>
                    <td className="px-4 py-3">
                      <RollingKeyCell info={authStatus[device.device_id]} />
                    </td>
                    <td className="px-4 py-3">
                      <Pill label={risk.label} tone={risk.tone} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
