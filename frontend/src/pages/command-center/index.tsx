import { PageHeader } from "../../components/layout/PageHeader";
import { StatCard } from "../../components/dashboard/StatCard";
import { ChartCard } from "../../components/dashboard/ChartCard";
import { StatusCard } from "../../components/dashboard/StatusCard";
import { ThreatTimelineChart, type ThreatTimelinePoint } from "../../components/dashboard/ThreatTimelineChart";
import { RiskDonutChart, type RiskSegment } from "../../components/dashboard/RiskDonutChart";

const THREAT_TIMELINE: ThreatTimelinePoint[] = [
  { label: "00:00", threats: 4 },
  { label: "03:00", threats: 6 },
  { label: "06:00", threats: 5 },
  { label: "09:00", threats: 8 },
  { label: "12:00", threats: 7 },
  { label: "15:00", threats: 9 },
  { label: "18:00", threats: 11 },
  { label: "21:00", threats: 10 },
];

const RISK_DISTRIBUTION: RiskSegment[] = [
  { name: "Low", value: 65, color: "#2f6fed" },
  { name: "Medium", value: 25, color: "#22c3ee" },
  { name: "High", value: 10, color: "#f6923a" },
];

function AircraftIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
      <path
        d="M12 2 L13.5 9 L21 12 L13.5 13 L12 22 L10.5 13 L3 12 L10.5 9 Z"
        fill="currentColor"
      />
    </svg>
  );
}

function ThreatIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
      <path
        d="M12 3 L22 20 H2 Z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path d="M12 9v5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="12" cy="17" r="0.9" fill="currentColor" />
    </svg>
  );
}

function BlocksIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
      <rect x="3" y="3" width="7" height="7" rx="1.5" fill="currentColor" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.55" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.55" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" fill="currentColor" />
    </svg>
  );
}

function GaugeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
      <path
        d="M4 16a8 8 0 1 1 16 0"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <path d="M12 16 L16 10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function LegendDot({ color, label, value }: { color: string; label: string; value: number }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
      <span className="text-ink-muted">{label}</span>
      <span className="tabular-nums font-medium text-ink">{value}%</span>
    </div>
  );
}

export default function CommandCenterPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="Real-time fleet security posture, threat activity, and blockchain integrity."
      />

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Aircraft Health" value="98%" icon={<AircraftIcon />} accent="accent" />
        <StatCard label="Active Threats" value="03" icon={<ThreatIcon />} accent="orange" />
        <StatCard label="Evidence Blocks" value="1,284" icon={<BlocksIcon />} accent="cyan" />
        <StatCard label="Risk Score" value="Low" icon={<GaugeIcon />} accent="success" />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <ChartCard title="Threat Detection Timeline" className="lg:col-span-2">
          <ThreatTimelineChart data={THREAT_TIMELINE} />
        </ChartCard>

        <ChartCard title="Risk Distribution">
          <RiskDonutChart data={RISK_DISTRIBUTION} centerLabel="Low" />
          <div className="mt-5 flex flex-col gap-2">
            {RISK_DISTRIBUTION.map((segment) => (
              <LegendDot key={segment.name} color={segment.color} label={segment.name} value={segment.value} />
            ))}
          </div>
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
        <StatusCard label="Blockchain Status" value="SYNCED" tone="success" />
        <StatusCard label="Authentication Logs" value="Verified" tone="info" />
        <StatusCard label="Maintenance" value="2 Alerts" tone="warning" />
      </div>
    </div>
  );
}
