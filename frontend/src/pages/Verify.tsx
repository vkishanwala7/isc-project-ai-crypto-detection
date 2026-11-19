import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Hash as HashIcon, ShieldCheck } from "lucide-react";
import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { api, type CaseDetail, type VerifyDetails } from "../lib/api";
import { ProvenancePanel } from "../components/evidence";
import { SummaryBanner, primaryVerify } from "../components/results";
import { Button, Dropzone, ErrorNote, MediaPreview, PageHeader, Panel, Skeleton } from "../components/ui";

export default function Verify() {
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const [file, setFile] = useState<File | null>(null);
  const [cred, setCred] = useState<File | null>(null);
  const [ref, setRef] = useState(params.get("ref") ?? "");
  const [result, setResult] = useState<CaseDetail | null>(null);
  const [refResult, setRefResult] = useState<{ case_id: string; result: VerifyDetails; sha256: string; phash: string | null; name: string } | null>(null);
  const preview = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const verify = useMutation({
    mutationFn: () => api.verify(file!, cred),
    onSuccess: (c) => { setResult(c); setRefResult(null); qc.invalidateQueries({ queryKey: ["dashboard"] }); toast.success("Verification stored", { description: c.share_ref }); },
  });
  const byRef = useMutation({
    mutationFn: (r: string) => api.verifyRef(r),
    onSuccess: (r) => { setRefResult({ case_id: r.case_id, result: r.result, sha256: r.asset.sha256, phash: r.asset.phash, name: r.asset.display_name }); setResult(null); },
  });
  const submitRef = (e: FormEvent) => { e.preventDefault(); if (ref.trim()) byRef.mutate(ref.trim()); };
  const original = result?.assets.find((a) => a.role === "original");

  return (
    <div>
      <PageHeader title="Verify a file"
        lede="Check provenance independently of any AI prediction. Upload a file with embedded Content Credentials, optionally add a detached credential, or re-verify a case created here by its share reference." />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <Panel title="File to verify" description="Images (JPEG, PNG, WebP) or videos (MP4, MOV, WebM). The upload is never rewritten.">
          <Dropzone accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm,.jpg,.jpeg,.png,.webp,.mp4,.mov,.webm" file={file} onFile={(f) => { setFile(f); setResult(null); }} disabled={verify.isPending} />
          <div className="mt-4">
            <p className="mb-2 text-[13px] font-medium text-ink">Detached credential <span className="font-normal text-muted">(optional)</span></p>
            <Dropzone accept=".json,.c2pa,application/json,application/c2pa" file={cred} onFile={setCred} disabled={verify.isPending}
              hint="A VERIFRAME envelope (.veriframe-sig.json) or a C2PA sidecar manifest store (.c2pa)." />
          </div>
          <Button className="mt-5" onClick={() => verify.mutate()} disabled={!file} loading={verify.isPending} icon={<ShieldCheck className="size-4" />}>Verify provenance</Button>
        </Panel>
        <div className="space-y-6">
          <Panel title="Verify by share reference" description="Re-runs verification on the signed asset stored for a VERIFRAME case.">
            <form onSubmit={submitRef} className="flex gap-2">
              <label className="flex-1">
                <span className="sr-only">Share reference or case id</span>
                <input value={ref} onChange={(e) => setRef(e.target.value)} placeholder="VF-1A2B3C4D-5E6F" className="mono h-10 w-full rounded-[var(--radius-control)] border border-line-strong bg-surface px-3 text-[13px] focus:border-signal focus:outline-none" />
              </label>
              <Button type="submit" variant="secondary" loading={byRef.isPending} icon={<HashIcon className="size-4" />}>Re-verify</Button>
            </form>
          </Panel>
          {preview && file && <Panel title="Preview"><MediaPreview src={preview} mime={file.type} alt={`Preview of ${file.name}`} tone="seal" /></Panel>}
          <Panel title="What “no provenance” means">
            <p className="text-[13px] leading-relaxed text-muted">Most authentic photos online carry no Content Credentials, and metadata is easily stripped by re-encoding or screenshots. A missing manifest therefore says nothing about whether content is real or fake. It only means origin cannot be verified cryptographically.</p>
          </Panel>
        </div>
      </div>

      <div className="mt-8 space-y-5" aria-live="polite">
        {verify.isError && <ErrorNote title="Verification failed to run" message={(verify.error as Error).message} />}
        {byRef.isError && <ErrorNote title="Reference lookup failed" message={(byRef.error as Error).message} />}
        {(verify.isPending || byRef.isPending) && <Skeleton className="h-[360px]" />}
        {result && (
          <>
            <SummaryBanner c={result} />
            <ProvenancePanel v={primaryVerify(result)} sha256={original?.sha256} phash={original?.phash} />
          </>
        )}
        {refResult && (
          <>
            <div className="rounded-[var(--radius-panel)] border border-line bg-surface px-5 py-4 text-[14px]">
              Re-verified <span className="font-medium">{refResult.name}</span> from case{" "}
              <Link className="text-signal hover:underline" to={`/cases/${refResult.case_id}`}>{refResult.case_id.slice(0, 8)}</Link>. The result was added to that case's timeline.
            </div>
            <ProvenancePanel v={refResult.result} sha256={refResult.sha256} phash={refResult.phash} />
          </>
        )}
      </div>
    </div>
  );
}
