import { FileText } from "lucide-react";
import { Link } from "react-router-dom";
import type { CaseDetail, VerifyDetails } from "../lib/api";
import { AIPanel, EvidenceMatrix, ProvenancePanel } from "./evidence";
import { Button, Chip, Panel, cx } from "./ui";

export function primaryVerify(c: CaseDetail): VerifyDetails | null {
  const v = c.provenance.find((p) => p.operation === "verify");
  return v ? (v.details as VerifyDetails) : null;
}

export function SummaryBanner({ c }: { c: CaseDetail }) {
  const tone = c.summary?.tone ?? "neutral";
  return (
    <div className={cx(
      "flex flex-wrap items-center gap-4 rounded-[var(--radius-panel)] border px-5 py-4",
      tone === "positive" && "border-ok/25 bg-ok-wash",
      tone === "warning" && "border-warn/30 bg-warn-wash",
      tone === "critical" && "border-bad/25 bg-bad-wash",
      tone === "neutral" && "border-line bg-surface",
    )}>
      <div className="min-w-0 flex-1">
        <p className="text-[12px] text-muted">Combined evidence summary</p>
        <p className="mt-0.5 text-[15px] font-medium leading-snug text-ink">{c.summary?.headline}</p>
      </div>
      <div className="flex items-center gap-2">
        {c.is_sample && <Chip tone="seal">Demo sample, dataset label “{c.sample_label}”</Chip>}
        <Link to={`/cases/${c.id}`}><Button variant="secondary" size="sm" icon={<FileText className="size-4" />}>Open evidence report</Button></Link>
      </div>
    </div>
  );
}

export function AnalysisResult({ c }: { c: CaseDetail }) {
  const ai = c.analyses[0]?.details ?? null;
  const v = primaryVerify(c);
  const asset = c.assets.find((a) => a.role === "original");
  return (
    <div className="space-y-5">
      <SummaryBanner c={c} />
      <div className="grid gap-5 xl:grid-cols-2">
        <AIPanel ai={ai} />
        <ProvenancePanel v={v} sha256={asset?.sha256} phash={asset?.phash} />
      </div>
      <Panel title="Where this case lands" description="AI dimension × provenance dimension, using the published rule.">
        <EvidenceMatrix ai={c.summary?.ai_dimension} prov={c.summary?.provenance_dimension} />
      </Panel>
    </div>
  );
}
