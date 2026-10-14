import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BarChart3 } from "lucide-react";
import { cad, monthLabel, Panel } from "./fmt";

export const FinanceChart = ({ history }) => {
  const data = history.map((h) => ({ m: monthLabel(h.month).replace(" 20", " ’"), Revenus: h.revenue.net, Plateforme: h.platform_cad, IA: h.ai_cad, Marge: h.margin_cad }));
  return (
    <Panel title="Évolution mensuelle (6 mois)" icon={BarChart3} testid="finance-chart">
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%" minWidth={200} initialDimension={{ width: 600, height: 256 }}>
          <ComposedChart data={data} margin={{ top: 5, right: 8, left: -12, bottom: 0 }}>
            <CartesianGrid stroke="rgba(148,163,184,0.12)" vertical={false} />
            <XAxis dataKey="m" tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip formatter={(v) => cad(v)} contentStyle={{ background: "#0f172a", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12, fontSize: 12 }} labelStyle={{ color: "#e2e8f0" }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="Revenus" fill="#10b981" radius={[4, 4, 0, 0]} />
            <Bar dataKey="Plateforme" stackId="c" fill="#6366f1" />
            <Bar dataKey="IA" stackId="c" fill="#f59e0b" radius={[4, 4, 0, 0]} />
            <Line dataKey="Marge" stroke="#f43f5e" strokeWidth={2} dot={{ r: 3 }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
};
