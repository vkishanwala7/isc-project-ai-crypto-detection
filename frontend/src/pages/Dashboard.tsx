import { useQuery } from "@tanstack/react-query";
import { Camera, ScanFace, ShieldCheck, Inbox } from "lucide-react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../lib/api";
import { AI_LABEL, PROVENANCE_LABEL } from "../lib/format";
import { CaseRow, EvidenceMatrix } from "../components/evidence";
import { Button, EmptyState, ErrorNote, Panel, Skeleton, cx } from "../components/ui";
import { Mark } from "../components/Layout";

function Stat({ label, value, sub, tone }: { label: string; value: number | undefined; sub?: string; tone?: "signal" | "seal" | "bad" | "ok" }) {
  return (
    <div className="px-5 py-4">
      <p className="text-[12.5px] text-muted">{label}</p>
      {value === undefined ? <Skeleton className="mt-2 h-8 w-14" /> : (
        <p className={cx("mt-1 text-[30px] font-semibold leading-none tracking-[-0.02em]",
          tone === "signal" && "text-signal", tone === "seal" && "text-seal", tone === "bad" && value > 0 && "text-bad", tone === "ok" && "text-ok", !tone && "text-ink")}>{value}</p>
      )}
      {sub && <p className="mt-1.5 text-[11.5px] text-faint">{sub}</p>}
    </div>
  );
}

export default function Dashboard() {
  const q = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  const d = q.data;
  const series = d?.activity_series.map((s) => ({ ...s, day: new Date(s.date + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" }) })) ?? [];
  const hasActivity = series.some((s) => s.analysis + s.sign + s.verify + s.tamper_test > 0);

  return (
    <div className="space-y-6">
      {/* Hero: the two-channel idea, stated in one breath */}
      <section className="relative overflow-hidden rounded-[18px] bg-ink px-6 py-8 text-white sm:px-9 sm:py-10">
        <div aria-hidden className="pointer-events-none absolute -top-24 -right-16 size-[340px] rounded-full bg-signal-bright/10 blur-3xl" />
        <div aria-hidden className="pointer-events-none absolute -bottom-28 right-40 size-[280px] rounded-full bg-seal-bright/10 blur-3xl" />
        <div className="relative grid items-center gap-8 lg:grid-cols-[1.25fr_1fr]">
          <div>
            <div className="mb-5 flex items-center gap-2 text-white/60"><Mark className="size-6" /><span className="text-[13px]">VERIFRAME</span></div>
            <h1 className="max-w-[18ch] text-[34px] font-semibold leading-[1.08] tracking-[-0.025em] sm:text-[44px]">Know what you're looking at.</h1>
            <p className="mt-4 max-w-[56ch] text-[15px] leading-relaxed text-white/70">
              Two independent kinds of evidence, never blended into one number: an AI model that looks for manipulation patterns in faces,
              and cryptographic provenance that checks whether these exact bytes carry a valid, signed origin record.
            </p>
            <div className="mt-7 flex flex-wrap gap-2.5">
              <Link to="/analyze"><Button className="bg-signal-bright text-ink hover:bg-white" icon={<ScanFace className="size-4" />}>Analyze media</Button></Link>
              <Link to="/capture"><Button variant="secondary" className="border-white/20 bg-white/5 text-white hover:bg-white/10" icon={<Camera className="size-4" />}>Capture & sign</Button></Link>
              <Link to="/verify"><Button variant="secondary" className="border-white/20 bg-white/5 text-white hover:bg-white/10" icon={<ShieldCheck className="size-4" />}>Verify a file</Button></Link>
            </div>
          </div>
          <div className="grid gap-3">
            <div className="rounded-xl border border-signal-bright/25 bg-white/[0.04] p-4">
              <p className="text-[13px] font-medium text-signal-bright">AI signal</p>
              <p className="mt-1 text-[13px] leading-relaxed text-white/70">Answers: does a face look like the manipulated examples the model learned from? A score with a disclosed threshold, never a verdict on truth.</p>
            </div>
            <div className="rounded-xl border border-seal-bright/25 bg-white/[0.04] p-4">
              <p className="text-[13px] font-medium text-seal-bright">Cryptographic provenance</p>
              <p className="mt-1 text-[13px] leading-relaxed text-white/70">Answers: does this file match a signed C2PA claim, and do we trust the signer? Missing provenance is not evidence of a fake.</p>
            </div>
          </div>
        </div>
      </section>

      {q.isError && <ErrorNote title="Could not load statistics" message={(q.error as Error).message} onRetry={() => q.refetch()} />}

      <section aria-label="Statistics" className="grid grid-cols-2 divide-line rounded-[var(--radius-panel)] border border-line bg-surface md:grid-cols-3 md:divide-x xl:grid-cols-6">
        <Stat label="Assets analysed" value={d?.counts.assets_analyzed} tone="signal" />
        <Stat label="Assets signed" value={d?.counts.signed_assets} tone="seal" />
        <Stat label="Verifications" value={d?.counts.verifications} />
        <Stat label="Valid provenance" value={d?.counts.valid_provenance} tone="ok" />
        <Stat label="Tampering alerts" value={d?.counts.tampering_alerts} tone="bad" sub="incl. Integrity lab tests" />
        <Stat label="No provenance" value={d?.counts.no_provenance} sub="not a fake verdict" />
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <Panel title="Activity, last 14 days" description="Counted from stored audit events. Demo-sample cases are excluded from these statistics.">
          {q.isLoading ? <Skeleton className="h-[240px] w-full" /> : hasActivity ? (
            <div className="h-[240px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={series} margin={{ top: 8, right: 4, left: -24, bottom: 0 }} barCategoryGap="28%">
                  <CartesianGrid vertical={false} stroke="#e6eaf0" />
                  <XAxis dataKey="day" tick={{ fontSize: 11, fill: "#5a6779" }} tickLine={false} axisLine={false} interval={1} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#5a6779" }} tickLine={false} axisLine={false} />
                  <Tooltip cursor={{ fill: "rgba(14,23,38,0.04)" }} contentStyle={{ borderRadius: 10, border: "1px solid #dce2ea", fontSize: 12 }} />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="analysis" name="AI analyses" stackId="a" fill="#0a8c99" />
                  <Bar dataKey="sign" name="Signings" stackId="a" fill="#5b4bc4" />
                  <Bar dataKey="verify" name="Verifications" stackId="a" fill="#a99bf0" />
                  <Bar dataKey="tamper_test" name="Tamper tests" stackId="a" fill="#0e1726" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState icon={<Inbox className="size-6" />} title="No activity recorded yet" action={<Link to="/analyze"><Button size="sm">Analyze your first file</Button></Link>}>
              The chart fills in from real events as you analyse, sign and verify media. Nothing is pre-seeded.
            </EmptyState>
          )}
        </Panel>

        <Panel title="Outcomes so far" description="Distribution of stored results by dimension.">
          {!d ? <Skeleton className="h-[220px]" /> : (
            <div className="space-y-5">
              <Distribution title="AI dimension" data={d.ai_outcomes} labels={AI_LABEL} color="bg-signal" />
              <Distribution title="Provenance dimension" data={d.provenance_outcomes} labels={PROVENANCE_LABEL} color="bg-seal" />
            </div>
          )}
        </Panel>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_1.35fr]">
        <Panel title="Recent cases" actions={<Link to="/cases" className="text-[13px] font-medium text-signal hover:underline">All cases</Link>}>
          {q.isLoading ? <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-14" />)}</div>
            : d && d.recent_cases.length ? <div className="-mx-3">{d.recent_cases.map((c) => <CaseRow key={c.id} c={c} />)}</div>
            : <EmptyState title="No cases yet">Every analysis, signing, verification and lab run becomes a durable case with its own evidence report.</EmptyState>}
        </Panel>
        <Panel title="How results are combined" description="A public, deterministic rule. The highlighted cell shows where a case lands; there is no hidden truth score.">
          <EvidenceMatrix compact />
          <Link to="/about#evidence" className="mt-3 inline-block text-[13px] font-medium text-signal hover:underline">Read the interpretation rules</Link>
        </Panel>
      </div>
    </div>
  );
}

function Distribution({ title, data, labels, color }: { title: string; data: Record<string, number>; labels: Record<string, { text: string }>; color: string }) {
  const total = Object.values(data).reduce((a, b) => a + b, 0);
  return (
    <div>
      <p className="mb-2 text-[13px] font-medium text-ink">{title} <span className="font-normal text-faint">({total})</span></p>
      {total === 0 ? <p className="text-[12.5px] text-muted">No results yet.</p> : (
        <ul className="space-y-1.5">
          {Object.entries(data).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
            <li key={k} className="grid grid-cols-[1fr_auto] items-center gap-x-3 text-[12.5px]">
              <span className="text-ink/80">{labels[k]?.text ?? k}</span>
              <span className="mono text-muted">{v}</span>
              <div className="col-span-2 h-1.5 rounded-full bg-paper"><div className={cx("h-full rounded-full", color)} style={{ width: `${(v / total) * 100}%` }} /></div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
