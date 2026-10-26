import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity } from "lucide-react";
import type { MetricSample, TargetTask } from "../types/tasksResources";

interface ResourceTrendProps {
  samples: MetricSample[];
  task: TargetTask;
}

export function ResourceTrend({ samples, task }: ResourceTrendProps) {
  if (samples.length === 0) {
    return <div className="task-resource-empty chart-empty" role="status">No resource samples are available for this task.</div>;
  }

  return (
    <section className="task-resource-panel task-resource-trend" aria-labelledby="task-resource-trend-title">
      <header className="task-resource-panel-heading">
        <div>
          <div className="task-resource-panel-title"><Activity size={15} /><h2 id="task-resource-trend-title">Resource trend</h2></div>
          <p>{task.name} · CPU and memory utilization</p>
        </div>
        <div className="task-chart-legend" aria-label="Chart legend">
          <span><i className="legend-dot cpu-legend" />CPU %</span>
          <span><i className="legend-dot memory-legend" />Memory %</span>
        </div>
      </header>
      <div className="task-phase-legend"><span className="baseline-phase-key" />Baseline <span className="test-phase-key" />Diagnostic period</div>
      <div className="task-resource-chart" role="img" aria-label={`Mock CPU and memory percentage trend for ${task.name}; left points show baseline and shaded right points show diagnostic period`}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={samples} margin={{ top: 10, right: 8, bottom: 4, left: -18 }}>
            <CartesianGrid stroke="#25303d" strokeDasharray="3 4" vertical={false} />
            <XAxis dataKey="time" tick={{ fill: "#6f7d8f", fontSize: 9 }} tickLine={false} axisLine={false} />
            <YAxis
              domain={[0, 100]}
              ticks={[0, 25, 50, 75, 100]}
              tickFormatter={(value: number) => `${value}%`}
              tick={{ fill: "#6f7d8f", fontSize: 9 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              contentStyle={{ border: "1px solid #344355", borderRadius: 5, background: "#182330", color: "#e7ebf2", fontSize: 10 }}
              formatter={(value, name) => [`${value}%`, name === "cpuPercent" ? "CPU" : "Memory"]}
              labelFormatter={(label, payload) => `${label} · ${payload[0]?.payload.phase ?? ""}`}
            />
            <ReferenceArea x1="02m" x2="06m" fill="#263448" fillOpacity={0.45} />
            <Area type="monotone" dataKey="cpuPercent" name="CPU" stroke="#65a4fa" strokeWidth={2} fill="#4d8de812" dot={{ r: 2, fill: "#65a4fa", stroke: "#101722", strokeWidth: 2 }} activeDot={{ r: 4 }} />
            <Area type="monotone" dataKey="memoryPercent" name="Memory" stroke="#4fc3bd" strokeWidth={2} fill="#4fc3bd10" dot={{ r: 2, fill: "#4fc3bd", stroke: "#101722", strokeWidth: 2 }} activeDot={{ r: 4 }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <footer className="task-trend-foot"><span>Mock sample interval · 2 minutes</span><span>Diagnostic period shaded</span></footer>
    </section>
  );
}
