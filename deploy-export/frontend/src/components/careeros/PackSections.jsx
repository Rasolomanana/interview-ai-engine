import { CheckCircle2, XCircle, AlertTriangle, Loader2 } from "lucide-react";
import { IpsGauge } from "./Ips";
import { DocActions, Markdown } from "./DocTools";
import { decisionMd, atsMd, simulationMd, questionsMd, starMd } from "@/lib/packExport";

const Card = ({ title, children, className = "", testid }) => (
  <section data-testid={testid} className={`rounded-2xl border border-white/[0.07] bg-[#121520]/80 p-5 ${className}`}>
    {title && <h3 className="mb-3 font-mono text-[11px] uppercase tracking-[0.18em] text-slate-500">{title}</h3>}
    {children}
  </section>
);

const Bullets = ({ items, icon: Icon, tone }) => (
  <ul className="space-y-2">
    {(items || []).map((x, i) => (
      <li key={i} className="flex gap-2 text-sm text-slate-300"><Icon className={`mt-0.5 h-4 w-4 shrink-0 ${tone}`} />{x}</li>
    ))}
  </ul>
);

export const Pending = ({ label, error }) => (
  <div className="flex items-center gap-3 rounded-2xl border border-dashed border-white/10 p-8 text-sm text-slate-400" data-testid="part-pending">
    {error ? <><XCircle className="h-4 w-4 text-rose-400" /> {label} indisponible : {error}</> : <><Loader2 className="h-4 w-4 animate-spin text-indigo-400" /> {label} en cours de génération…</>}
  </div>
);

const Head = ({ md, name, testid }) => <div className="mb-4 flex justify-end"><DocActions markdown={md} name={name} testid={testid} /></div>;

export const DecisionPanel = ({ d, ips }) => (
  <div className="space-y-4">
    <Head md={decisionMd(d, ips)} name="Decision-CareerOS" testid="decision" />
    <div className="grid gap-4 lg:grid-cols-5">
      <Card className="lg:col-span-2" testid="ips-card">
        <IpsGauge score={ips?.score} priority={ips?.priority} />
        {ips?.knockout && <p className="mt-4 flex gap-2 rounded-lg bg-rose-950/40 p-2 text-xs text-rose-200" data-testid="ips-knockout"><AlertTriangle className="h-4 w-4 shrink-0" />Exigence éliminatoire : {ips.knockout_detail}</p>}
      </Card>
      <Card title="Détail du calcul IPS" className="lg:col-span-3" testid="ips-criteria">
        <div className="space-y-2">
          {(ips?.criteria || []).map((c) => (
            <div key={c.key} className="group" data-testid={`ips-criterion-${c.key}`}>
              <div className="flex items-center justify-between text-xs"><span className="text-slate-300">{c.label} <span className="text-slate-600">×{c.weight}</span></span><span className="font-mono text-slate-400">{c.score}/10 · {c.points} pts</span></div>
              <div className="mt-1 h-1.5 rounded-full bg-white/5"><div className="h-full rounded-full bg-indigo-400/80" style={{ width: `${c.score * 10}%` }} /></div>
              <p className="mt-1 text-[11px] text-slate-500">{c.justification}</p>
            </div>
          ))}
          <p className="pt-2 font-mono text-[10px] text-slate-600">{ips?.formula}</p>
        </div>
      </Card>
    </div>
    <div className="grid gap-4 md:grid-cols-2">
      <Card title="Pourquoi postuler" testid="reasons-apply"><Bullets items={d.reasons_apply} icon={CheckCircle2} tone="text-emerald-400" /></Card>
      <Card title="Pourquoi éviter" testid="reasons-avoid"><Bullets items={d.reasons_avoid} icon={XCircle} tone="text-rose-400" /></Card>
    </div>
    <div className="grid gap-4 md:grid-cols-3">
      <Card title="Impact attendu" testid="expected-impact"><p className="text-sm text-slate-300">{d.expected_impact}</p></Card>
      <Card title="Potentiel salarial"><p className="text-sm text-slate-300">{d.salary_potential}</p></Card>
      <Card title="Potentiel carrière"><p className="text-sm text-slate-300">{d.career_potential}</p></Card>
    </div>
  </div>
);

const Chips = ({ items, tone }) => <div className="flex flex-wrap gap-1.5">{(items || []).map((k, i) => <span key={i} className={`rounded-md px-2 py-1 text-xs ${tone}`}>{k}</span>)}</div>;

export const AtsPanel = ({ d }) => {
  const a = d.ats || {};
  return (
    <div className="space-y-4">
      <Head md={atsMd(d)} name="Analyse-ATS" testid="ats" />
      <Card testid="ats-score-card"><div className="flex items-baseline gap-2"><span className="font-display text-5xl font-bold text-white" data-testid="ats-score">{a.score ?? "—"}</span><span className="text-sm text-slate-500">/100 compatibilité ATS</span></div></Card>
      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Mots-clés présents"><Chips items={a.keywords_found} tone="bg-emerald-500/10 text-emerald-300" /></Card>
        <Card title="Mots-clés manquants" testid="ats-missing"><Chips items={a.keywords_missing} tone="bg-rose-500/10 text-rose-300" /></Card>
        <Card title="Écarts"><Bullets items={a.gaps} icon={AlertTriangle} tone="text-amber-400" /></Card>
        <Card title="Améliorations"><Bullets items={a.improvements} icon={CheckCircle2} tone="text-indigo-300" /></Card>
      </div>
    </div>
  );
};

const VERDICT = { passe: "text-emerald-300 bg-emerald-500/10", limite: "text-amber-300 bg-amber-500/10", rejet: "text-rose-300 bg-rose-500/10" };
const LANES = [["ats", "ATS"], ["ia_recruteur", "IA recruteur"], ["recruteur_humain", "Recruteur humain"], ["gestionnaire", "Gestionnaire recruteur"]];

export const SimulationPanel = ({ d }) => {
  const s = d.recruiter_simulation || {};
  return (
    <div className="space-y-4">
      <Head md={simulationMd(d)} name="Simulation-recruteur" testid="simulation" />
      <div className="grid gap-3 md:grid-cols-4">
        {LANES.map(([k, l], i) => (
          <Card key={k} testid={`sim-lane-${k}`}>
            <div className="mb-2 flex items-center justify-between"><span className="font-mono text-[10px] text-slate-600">0{i + 1}</span><span className={`rounded px-2 py-0.5 text-[11px] font-semibold uppercase ${VERDICT[s[k]?.verdict] || "text-slate-400"}`}>{s[k]?.verdict || "—"}</span></div>
            <p className="text-sm font-semibold text-white">{l}</p>
            <p className="mt-1.5 text-xs leading-relaxed text-slate-400">{s[k]?.commentaire}</p>
          </Card>
        ))}
      </div>
      <Card title="Risques · objections · corrections" testid="sim-risks">
        <div className="divide-y divide-white/5">
          {(d.risks || []).map((r, i) => (
            <div key={i} className="grid gap-2 py-3 text-sm md:grid-cols-3">
              <p className="font-medium text-rose-200">{r.risque}</p>
              <p className="text-slate-400"><span className="text-slate-600">Objection — </span>{r.objection}</p>
              <p className="text-emerald-200/90"><span className="text-slate-600">Correction — </span>{r.correction}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};

const QCATS = [["rh", "RH"], ["gestionnaire", "Gestionnaire"], ["comportementales", "Comportementales"], ["techniques", "Techniques"]];

export const QuestionsPanel = ({ q }) => (
  <div className="space-y-4">
    <Head md={questionsMd(q)} name="Questions-entrevue" testid="questions" />
    <div className="grid gap-4 md:grid-cols-2">
      {QCATS.map(([k, l]) => (
        <Card key={k} title={`Questions ${l}`} testid={`questions-${k}`}>
          <ol className="space-y-3">
            {(q[k] || []).map((x, i) => (
              <li key={i} className="text-sm"><p className="font-medium text-white">{i + 1}. {x.question}</p><p className="mt-1 text-xs text-slate-500">Objectif : {x.objectif}</p><p className="mt-0.5 text-xs text-indigo-200/80">Conseil : {x.conseil}</p></li>
            ))}
          </ol>
        </Card>
      ))}
    </div>
  </div>
);

export const StarPanel = ({ s }) => (
  <div className="space-y-4">
    <Head md={starMd(s)} name="Reponses-STAR" testid="star" />
    {(s.star || []).map((x, i) => (
      <Card key={i} testid={`star-${i}`}>
        <p className="font-semibold text-white">{x.question}</p>
        {x.competence && <p className="mt-1 text-xs text-indigo-300">{x.competence}</p>}
        <div className="mt-3 grid gap-3 md:grid-cols-4">
          {[["S", "Situation", x.situation], ["T", "Tâche", x.tache], ["A", "Action", x.action], ["R", "Résultat", x.resultat]].map(([L, n, v]) => (
            <div key={L} className="rounded-xl bg-black/30 p-3"><p className="font-display text-lg font-bold text-indigo-300">{L}<span className="ml-1 text-[10px] font-normal uppercase tracking-widest text-slate-500">{n}</span></p><p className="mt-1 text-xs leading-relaxed text-slate-300">{v}</p></div>
          ))}
        </div>
      </Card>
    ))}
  </div>
);

export const DocPanel = ({ text, name, kind, testid }) => (
  <div className="space-y-4">
    <Head md={text} name={name} testid={testid} />
    <Card>{kind === "letter" ? <div className="whitespace-pre-wrap text-sm leading-relaxed text-slate-200" data-testid={`${testid}-content`}>{text}</div> : <Markdown text={text} testid={`${testid}-content`} />}</Card>
  </div>
);
