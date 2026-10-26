import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ResourcePoint } from "@/types/dashboard";

export interface ResourceTrendChartProps {
  data: ResourcePoint[];
  lastUpdated: string;
}

export function ResourceTrendChart({ data, lastUpdated }: ResourceTrendChartProps) {
  if (data.length === 0) {
    return (
      <section className="panel chart-panel">
        <div className="panel-heading">
          <div>
            <h2>Resource utilization</h2>
            <p>CPU and memory usage across monitored services</p>
          </div>
        </div>
        <div className="chart-empty" role="status">
          No demo resource data is available for this time range.
        </div>
      </section>
    );
  }

  return (
    <section className="panel chart-panel">
      <div className="panel-heading">
        <div>
          <h2>Resource utilization</h2>
          <p>CPU and memory usage across monitored services</p>
        </div>
        <div className="chart-controls">
          <div className="chart-legend">
            <span><i className="legend-dot cpu-legend" />CPU</span>
            <span><i className="legend-dot memory-legend" />Memory</span>
          </div>
          <button className="range-select" type="button">Last 3 hours</button>
        </div>
      </div>
      <div
        className="chart-wrap"
        role="img"
        aria-label="Mock CPU and memory utilization trend over the last three hours"
      >
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 8, bottom: 8, left: -18 }}>
            <CartesianGrid stroke="#25303d" strokeDasharray="3 4" vertical={false} />
            <XAxis
              dataKey="time"
              tick={{ fill: "#6f7d8f", fontSize: 9 }}
              tickLine={false}
              axisLine={false}
              interval={1}
            />
            <YAxis
              domain={[0, 100]}
              ticks={[0, 25, 50, 75, 100]}
              tickFormatter={(value: number) => `${value}%`}
              tick={{ fill: "#6f7d8f", fontSize: 9 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              contentStyle={{
                border: "1px solid #344355",
                borderRadius: 5,
                background: "#182330",
                color: "#e7ebf2",
                fontSize: 11,
              }}
              formatter={(value) => [`${value}%`]}
            />
            <Area
              type="monotone"
              dataKey="cpu"
              name="CPU"
              stroke="#65a4fa"
              strokeWidth={2}
              fill="#4d8de812"
              dot={{ r: 2, fill: "#65a4fa", stroke: "#101722", strokeWidth: 2 }}
              activeDot={{ r: 4 }}
            />
            <Line
              type="monotone"
              dataKey="memory"
              name="Memory"
              stroke="#4fc3bd"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="chart-foot">
        <span>Sample snapshot · {lastUpdated}</span>
        <span>DEMO METRICS · SAMPLE INTERVAL 15 MIN</span>
      </div>
    </section>
  );
}
