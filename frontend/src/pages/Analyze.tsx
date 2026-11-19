import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, Database, FolderOpen, Loader2, ScanFace } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { api, type CaseDetail } from "../lib/api";
import { AnalysisResult } from "../components/results";
import { Button, Chip, Dropzone, EmptyState, ErrorNote, MediaPreview, PageHeader, Panel, Skeleton, cx } from "../components/ui";
import { LiveCamera } from "../components/LiveCamera";

const ACCEPT = "image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm,.jpg,.jpeg,.png,.webp,.mp4,.mov,.webm";

export default function Analyze() {
  const qc = useQueryClient();
  const cfg = useQuery({ queryKey: ["config"], queryFn: api.config });
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState<"file" | "camera">("file");
  const [result, setResult] = useState<CaseDetail | null>(null);
  const preview = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const done = (c: CaseDetail) => {
    setResult(c);
    qc.invalidateQueries({ queryKey: ["dashboard"] });
    toast.success("Analysis stored as a case", { description: c.share_ref });
  };
  const run = useMutation({ mutationFn: (f: File) => api.analyze(f), onSuccess: done });
  const sample = useMutation({ mutationFn: (id: string) => api.analyzeSample(id), onSuccess: (c) => { setFile(null); done(c); } });
  const busy = run.isPending || sample.isPending;
  const err = (run.error ?? sample.error) as Error | null;
  const maxBytes = (cfg.data?.max_video_mb ?? 60) * 1048576; // per-type limit enforced by the server

  return (
    <div>
      <PageHeader
        title="Analyze media"
        lede="Choose an image or video from your computer, or capture a photo or clip with your camera. VERIFRAME runs the face-manipulation classifier and, separately, inspects any embedded C2PA provenance. The two results are reported side by side."
      />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
        <Panel title="Media" description={cfg.data ? `JPEG, PNG or WebP up to ${cfg.data.max_image_mb} MB; MP4, MOV or WebM up to ${cfg.data.max_video_mb} MB and ${cfg.data.max_video_seconds} s.` : "Loading limits…"}>
          <div className="mb-4 inline-flex rounded-lg bg-paper p-1" role="tablist" aria-label="Media source">
            {([["file", "From my computer", FolderOpen], ["camera", "Use camera", Camera]] as const).map(([k, label, Icon]) => (
              <button key={k} role="tab" aria-selected={source === k} disabled={busy}
                onClick={() => { setSource(k); setFile(null); setResult(null); run.reset(); }}
                className={cx("inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-[13px]", source === k ? "bg-surface font-medium text-ink shadow-sm" : "text-muted hover:text-ink")}>
                <Icon className="size-4" />{label}
              </button>
            ))}
          </div>
          {source === "file" ? (
            <Dropzone accept={ACCEPT} file={file} onFile={(f) => { setFile(f); setResult(null); run.reset(); }} maxBytes={maxBytes} disabled={busy}
              hint="Pick any photo or clip saved on your computer. Faces work best: the model classifies detected face crops." />
          ) : (
            <>
              <LiveCamera busy={run.isPending} photoLabel="Capture photo & analyze" clipLabel="Record clip & analyze"
                onCapture={(f) => { setFile(f); setResult(null); run.reset(); run.mutate(f); }} />
              <p className="mt-3 text-[12px] text-muted">The captured photo or clip is analysed straight away. It is not signed here; use Capture &amp; sign for that.</p>
            </>
          )}
          {preview && file && <div className="mt-5"><p className="mb-1 text-[12.5px] text-muted">{source === "camera" ? "Captured: " : ""}{file.name}</p><MediaPreview src={preview} mime={file.type} alt={`Preview of ${file.name}`} /></div>}
          <div className="mt-5 flex items-center gap-3">
            <Button onClick={() => file && run.mutate(file)} disabled={!file} loading={run.isPending} icon={<ScanFace className="size-4" />}>{source === "camera" && file ? "Analyze again" : "Run analysis"}</Button>
            {busy && <span className="text-[13px] text-muted">Server is detecting faces, scoring crops and inspecting provenance…</span>}
          </div>
        </Panel>

        <div className="space-y-6">
          <Panel title="What runs" description="Two independent jobs on the server, against the bytes you upload.">
            <ol className="space-y-3 text-[13px]">
              {[
                ["Validation & hashing", "Magic-byte format check, size limits, safe decode, SHA-256 and pHash.", "ink"],
                ["Face detection + classifier", "MTCNN face crops scored by an EfficientNet-B0 trained in this project; video uses evenly sampled frames.", "signal"],
                ["Provenance inspection", "C2PA manifest discovery, content binding, signature and signer trust via the official SDK.", "seal"],
              ].map(([t, d, c]) => (
                <li key={t} className="flex gap-3">
                  {busy ? <Loader2 className={`mt-0.5 size-4 animate-spin text-${c === "ink" ? "muted" : c}`} /> : <span className={`mt-1.5 size-2 shrink-0 rounded-full ${c === "signal" ? "bg-signal" : c === "seal" ? "bg-seal" : "bg-ink/40"}`} />}
                  <div><p className="font-medium text-ink">{t}</p><p className="text-muted">{d}</p></div>
                </li>
              ))}
            </ol>
          </Panel>
          <DemoWorkspace onAnalyze={(id) => sample.mutate(id)} busyId={sample.isPending ? sample.variables : undefined} disabled={busy} />
        </div>
      </div>

      <div className="mt-8" aria-live="polite">
        {err && <ErrorNote title="Analysis failed" message={err.message} />}
        {busy && !result && <div className="grid gap-5 xl:grid-cols-2"><Skeleton className="h-[360px]" /><Skeleton className="h-[360px]" /></div>}
        {result && <AnalysisResult c={result} />}
      </div>
    </div>
  );
}

function DemoWorkspace({ onAnalyze, busyId, disabled }: { onAnalyze: (id: string) => void; busyId?: string; disabled: boolean }) {
  const q = useQuery({ queryKey: ["samples"], queryFn: api.samples });
  return (
    <Panel title={<span className="flex items-center gap-2"><Database className="size-4 text-muted" /> Demo workspace</span>}
      description="Held-out samples with labels documented by their source. They are stored as sample cases and excluded from dashboard statistics. Model errors are shown as-is.">
      {q.isLoading ? <Skeleton className="h-24" /> : !q.data?.samples.length ? (
        <EmptyState title="No sample manifest found">Add <code className="mono">data/samples/samples.json</code> or run <code className="mono">python scripts/fetch_demo_samples.py</code>.</EmptyState>
      ) : (
        <ul className="divide-y divide-line">
          {q.data.samples.map((s) => (
            <li key={s.id} className="flex items-center gap-3 py-2.5">
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-medium text-ink">{s.label_text}</p>
                <p className="truncate text-[11.5px] text-muted" title={s.source}>{s.media_type}, {s.used_for_training ? "seen in training" : "never used for training"}, {s.license}</p>
              </div>
              <Chip tone={s.label === "manipulated" ? "bad" : s.label === "real" ? "ok" : "seal"}>{s.label}</Chip>
              <Button size="sm" variant="secondary" disabled={!s.available || disabled} loading={busyId === s.id} onClick={() => onAnalyze(s.id)}
                title={s.available ? "Analyze this sample" : `Not downloaded — run ${q.data.fetch_command}`}>
                {s.available ? "Analyze" : "Not fetched"}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
