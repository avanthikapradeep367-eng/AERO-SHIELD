import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

export interface RiskSegment {
  name: string;
  value: number;
  color: string;
}

interface RiskDonutChartProps {
  data: RiskSegment[];
  centerLabel: string;
  centerSublabel?: string;
}

export function RiskDonutChart({ data, centerLabel, centerSublabel }: RiskDonutChartProps) {
  return (
    <div className="relative mx-auto h-64 w-64">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            innerRadius="72%"
            outerRadius="98%"
            paddingAngle={3}
            stroke="none"
            startAngle={90}
            endAngle={-270}
          >
            {data.map((segment) => (
              <Cell key={segment.name} fill={segment.color} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="rounded-full bg-accent px-5 py-4 text-lg font-semibold text-white shadow-lg shadow-accent/40">
          {centerLabel}
        </span>
        {centerSublabel ? <span className="mt-2 text-xs text-ink-faint">{centerSublabel}</span> : null}
      </div>
    </div>
  );
}
