import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileJson, Printer, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { api, type CaseDetail, type VerifyDetails } from "../lib/api";
import { ACTION_LABEL, KIND_LABEL, fmtBytes, fmtDate } from "../lib/format";
import { AIPanel, EvidenceMatrix, ProvChip, ProvenancePanel } from "../components/evidence";
import { SummaryBanner } from "../components/results";
import { SigningResult } from "../components/SigningResult";
import { LabResult } from "./IntegrityLab";
import { Button, Chip, ConfirmDialog, CopyButton, EmptyState, ErrorNote, Hash, KV, MediaPreview, Panel, Skeleton } from "../components/ui";
import { Wordmark } from "../components/Layout";

export default function CaseDetailPage() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["case", id], queryFn: () => api.case(id) });
  const [confirm, setConfirm] = useState(false);
  const del = useMutation({
    mutationFn: () => api.deleteCase(q.data!.id),
    onSuccess: () => { toast.success("Case deleted"); qc.invalidateQueries(); nav("/cases"); },
    onError: (e) => toast.error((e as Error).message),
  });
  const reverify = useMutation({
    mutationFn: () => api.verifyRef(q.data!.id),
    onSuccess: (r) => { toast.success(`Re-verified: ${r.result.status}`); qc.invalidateQueries({ queryKey: ["case", id] }); },
    onError: (e) => toast.error((e as Error).message),
  });

  if (q.isLoading) return <div className="space-y-4"><Skeleton className="h-24" /><Skeleton className="h-[420px]" /></div>;
  if (q.isError) return (q.error as { status?: number }).status === 404
    ? <EmptyState title="Case not found" action={<Link to="/cases"><Button size="sm">Browse cases</Button></Link>}>No case matches “{id}”. Check the share reference.</EmptyState>
    : <ErrorNote message={(q.error as Error).message} onRetry={() => q.refetch()} />;
  const c = q.data!;
  const primary = c.assets.find((a) => a.role === "original");
  const verifies = c.provenance.filter((p) => p.operation === "verify");

  return (
    <div className="space-y-6">
      {/* print-only letterhead */}
      <div className="hidden items-center justify-between border-b border-ink pb-3 print:flex">
        <div className="rounded-md bg-ink px-3 py-2"><Wordmark /></div>
        <div className="text-right text-[11px]">Evidence report<br />{c.share_ref}<br />Printed {new Date().toLocaleString()}</div>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-[13px] text-muted"><Link to="/cases" className="hover:text-ink no-print">Cases</Link><span className="no-print"> / </span>{KIND_LABEL[c.kind]}</p>
          <h1 className="mt-1 truncate text-[26px] font-semibold tracking-[-0.02em]">{c.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-[13px] text-muted">
            <span className="mono inline-flex items-center gap-1 rounded-md bg-surface px-2 py-0.5 ring-1 ring-line">{c.share_ref}<CopyButton value={c.share_ref} label="Copy share reference" what="Share reference copied" /></span>
            <span>Created {fmtDate(c.created_at)}</span>
            {c.is_sample && <Chip tone="seal">Demo sample, dataset label “{c.sample_label}”</Chip>}
          </div>
        </div>
        <div className="no-print flex flex-wrap gap-2">
          {c.assets.some((a) => a.role === "signed") && <Button variant="secondary" size="sm" onClick={() => reverify.mutate()} loading={reverify.isPending} icon={<RefreshCw className="size-4" />}>Re-verify</Button>}
          <a href={`/api/cases/${c.id}/report.json`}><Button variant="secondary" size="sm" icon={<FileJson className="size-4" />}>JSON report</Button></a>
          <Button variant="secondary" size="sm" onClick={() => window.print()} icon={<Printer className="size-4" />}>Print / PDF</Button>
          <Button variant="ghost" size="sm" onClick={() => setConfirm(true)} icon={<Trash2 className="size-4" />}>Delete</Button>
        </div>
      </div>

      {c.kind === "integrity_lab" ? <LabResult c={c} /> : c.kind === "signing" ? <SigningResult c={c} /> : (
        <>
          <SummaryBanner c={c} />
          <div className="grid gap-6 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
            <Panel title="Media & file metadata">
              {primary && <MediaPreview src={primary.url} mime={primary.mime} alt={c.title} />}
              {primary && (
                <KV className="mt-5" rows={[
                  ["Type", primary.mime],
                  ["Size", fmtBytes(primary.size_bytes)],
                  ["Dimensions", primary.width ? `${primary.width} × ${primary.height}px` : "—"],
                  ...(primary.duration_s ? [["Duration", `${primary.duration_s.toFixed(1)} s`] as [string, string]] : []),
                  ["SHA-256", <Hash value={primary.sha256} label="SHA-256" small />],
                  ["pHash", <span className="mono text-[12px]">{primary.phash} <span className="text-faint">(similarity only)</span></span>],
                  ["Case ID", <span className="mono text-[12px]">{c.id}</span>],
                  ...(c.sample_source ? [["Sample source", c.sample_source] as [string, string]] : []),
                ]} />
              )}
            </Panel>
            <div className="space-y-6">
              {c.kind === "analysis" && <AIPanel ai={c.analyses[0]?.details} />}
              <ProvenancePanel v={verifies[0]?.details as VerifyDetails} sha256={primary?.sha256} phash={primary?.phash} />
            </div>
          </div>
          <Panel title="Trust interpretation" description="Where the two independent dimensions place this case under the published rule.">
            <EvidenceMatrix ai={c.summary?.ai_dimension} prov={c.summary?.provenance_dimension} />
          </Panel>
        </>
      )}

      {verifies.length > 1 && (
        <Panel title="Verification history" description="Every verification of assets in this case, newest last.">
          <ul className="divide-y divide-line">
            {verifies.map((v) => (
              <li key={v.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-[13px]">
                <span className="text-ink">{v.details?.label ?? "verification"}</span>
                <span className="flex items-center gap-3"><span className="text-muted">{fmtDate(v.created_at)}</span><ProvChip status={v.status} /></span>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Event timeline" description="Persisted audit events for this case.">
          <Timeline c={c} />
        </Panel>
        <Panel title="Stored files" description="Served by asset id from private storage; your original is never modified.">
          <ul className="divide-y divide-line">
            {c.assets.map((a) => (
              <li key={a.id} className="flex items-center gap-3 py-2.5">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] font-medium">{a.display_name}</p>
                  <p className="text-[11.5px] text-muted">{a.role}, {a.mime}, {fmtBytes(a.size_bytes)}, sha256 {a.sha256.slice(0, 12)}…</p>
                </div>
                <a href={a.download_url} className="no-print" aria-label={`Download ${a.display_name}`}><Button size="sm" variant="ghost" icon={<Download className="size-4" />}>Download</Button></a>
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <p className="text-[12px] leading-relaxed text-muted">
        This report contains forensic indicators, not a guarantee of truth. AI scores are model estimates with documented limitations; provenance shows only whether these bytes match a signed claim and whether the signer is trusted under VERIFRAME's local demo trust policy. Generated by VERIFRAME 1.0.0, a local academic demonstration (ISC, Team 16).
      </p>

      <ConfirmDialog open={confirm} title="Delete this case?" confirmLabel="Delete case" busy={del.isPending}
        body={<>This permanently removes the case, its stored files and its records. The deletion itself is written to the activity log. This cannot be undone.</>}
        onCancel={() => setConfirm(false)} onConfirm={() => del.mutate()} />
    </div>
  );
}

function Timeline({ c }: { c: CaseDetail }) {
  return (
    <ol className="relative ml-1.5 space-y-4 border-l border-line pl-5">
      {c.timeline.map((e, i) => (
        <li key={i} className="relative">
          <span className={`absolute top-1.5 -left-[25px] size-2.5 rounded-full ring-4 ring-surface ${e.action === "analysis" ? "bg-signal" : e.action === "error" ? "bg-bad" : ["sign", "verify", "tamper_test"].includes(e.action) ? "bg-seal" : "bg-ink/40"}`} />
          <p className="text-[13px] font-medium text-ink">{ACTION_LABEL[e.action] ?? e.action} <span className="mono font-normal text-muted">{e.result}</span></p>
          <p className="text-[12px] text-muted">{fmtDate(e.ts)}{e.details && "label" in e.details ? `, ${String(e.details.label)}` : ""}</p>
        </li>
      ))}
    </ol>
  );
}
