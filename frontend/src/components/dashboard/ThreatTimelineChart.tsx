import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export interface ThreatTimelinePoint {
  label: string;
  threats: number;
}

interface ThreatTimelineChartProps {
  data: ThreatTimelinePoint[];
}

export function ThreatTimelineChart({ data }: ThreatTimelineChartProps) {
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <defs>
            <linearGradient id="threatFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2f6fed" stopOpacity={0.28} />
              <stop offset="100%" stopColor="#2f6fed" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 6" stroke="#dde9f5" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: "#93a7bc", fontSize: 12 }}
            axisLine={{ stroke: "#dde9f5" }}
            tickLine={false}
          />
          <YAxis tick={{ fill: "#93a7bc", fontSize: 12 }} axisLine={false} tickLine={false} width={28} />
          <Tooltip
            contentStyle={{
              borderRadius: 12,
              border: "1px solid #dde9f5",
              background: "rgba(255,255,255,0.95)",
              fontSize: 12,
              color: "#10233b",
            }}
          />
          <Area
            type="monotone"
            dataKey="threats"
            stroke="#2f6fed"
            strokeWidth={2.5}
            fill="url(#threatFill)"
            dot={{ r: 4, stroke: "#2f6fed", strokeWidth: 2, fill: "#ffffff" }}
            activeDot={{ r: 6 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
