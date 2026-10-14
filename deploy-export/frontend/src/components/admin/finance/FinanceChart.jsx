import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BarChart3 } from "lucide-react";
import { cad, monthLabel, Panel } from "./fmt";

const SERIES = [["Infrastructure", "infrastructure", "#6366f1"], ["IA", "ia", "#f59e0b"], ["Marketing", "marketing", "#ec4899"], ["Développement", "developpement", "#14b8a6"], ["Autres", "autres", "#94a3b8"]];

export const FinanceChart = ({ history }) => {
  const data = history.map((h) => ({
    m: monthLabel(h.month).replace(" 20", " ’"), Revenus: h.revenue.used, "Marge d'exploitation": h.operating_margin_cad, "Marge nette": h.net_margin_cad,
    ...Object.fromEntries(SERIES.map(([l, k]) => [l, h.families[k].used_cad])),
  }));
  return (
    <Panel title="Évolution mensuelle (6 mois)" icon={BarChart3} testid="finance-chart">
      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%" minWidth={200} initialDimension={{ width: 600, height: 288 }}>
          <ComposedChart data={data} margin={{ top: 5, right: 8, left: -12, bottom: 0 }}>
            <CartesianGrid stroke="rgba(148,163,184,0.12)" vertical={false} />
            <XAxis dataKey="m" tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip formatter={(v) => cad(v)} contentStyle={{ background: "#0f172a", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12, fontSize: 12 }} labelStyle={{ color: "#e2e8f0" }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="Revenus" fill="#10b981" radius={[4, 4, 0, 0]} />
            {SERIES.map(([l, , c]) => <Bar key={l} dataKey={l} stackId="c" fill={c} />)}
            <Line dataKey="Marge d'exploitation" stroke="#38bdf8" strokeWidth={2} dot={{ r: 3 }} />
            <Line dataKey="Marge nette" stroke="#f43f5e" strokeWidth={2} dot={{ r: 3 }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
};
