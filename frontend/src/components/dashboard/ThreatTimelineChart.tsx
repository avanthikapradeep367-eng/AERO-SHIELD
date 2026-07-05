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
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -8 }}>
          <defs>
            <linearGradient id="threatFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2f6fed" stopOpacity={0.28} />
              <stop offset="100%" stopColor="#2f6fed" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 6" stroke="#dde9f5" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: "#93a7bc", fontSize: 11 }}
            axisLine={{ stroke: "#dde9f5" }}
            tickLine={false}
            minTickGap={12}
          />
          <YAxis
            tick={{ fill: "#93a7bc", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={30}
            allowDecimals={false}
          />
          <Tooltip
            formatter={(value: unknown) => [`${value ?? 0}`, "Threats"]}
            labelFormatter={(label: unknown) => `Time: ${label ?? "—"}`}
            contentStyle={{
              borderRadius: 12,
              border: "1px solid #dde9f5",
              background: "rgba(255,255,255,0.97)",
              fontSize: 12,
              color: "#10233b",
              boxShadow: "0 10px 30px rgba(16,35,59,0.08)",
            }}
          />
          <Area
            type="monotone"
            dataKey="threats"
            stroke="#2f6fed"
            strokeWidth={2.5}
            fill="url(#threatFill)"
            dot={{ r: 4, stroke: "#2f6fed", strokeWidth: 2, fill: "#ffffff" }}
            activeDot={{ r: 6, strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
