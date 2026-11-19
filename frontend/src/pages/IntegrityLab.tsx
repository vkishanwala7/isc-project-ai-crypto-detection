import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, ImagePlus, Sparkles } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api, type CaseDetail, type Step } from "../lib/api";
import { ProvChip, Steps } from "../components/evidence";
import { PROVENANCE_LABEL } from "../lib/format";
import { Button, Chip, Dropzone, ErrorNote, Hash, MediaPreview, PageHeader, Panel, Skeleton, cx } from "../components/ui";

export default function IntegrityLab() {
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<CaseDetail | null>(null);
  const run = useMutation({
    mutationFn: (f: File | null) => api.tamperDemo(f),
    onSuccess: (c) => { setResult(c); qc.invalidateQueries({ queryKey: ["dashboard"] }); toast.success("Integrity lab run stored", { description: c.share_ref }); },
  });
  return (
    <div>
      <PageHeader title="Integrity lab"
        lede="A guided, real cryptography experiment. VERIFRAME signs an image, verifies it, then alters two separate copies and verifies them again. Every red result below comes from an actual verification call." />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Panel title="Choose a starting image" description="Use an app-generated demo image (no people), or your own JPEG/PNG. Your original is stored unchanged.">
          <Dropzone accept="image/jpeg,image/png,.jpg,.jpeg,.png" file={file} onFile={setFile} disabled={run.isPending} hint="JPEG or PNG, up to 15 MB." />
          <div className="mt-5 flex flex-wrap gap-2">
            <Button onClick={() => run.mutate(null)} loading={run.isPending && !file} disabled={run.isPending} icon={<Sparkles className="size-4" />}>Run with demo image</Button>
            <Button variant="secondary" onClick={() => file && run.mutate(file)} disabled={!file || run.isPending} loading={run.isPending && !!file} icon={<ImagePlus className="size-4" />}>Run with my image</Button>
          </div>
        </Panel>
        <Panel title="The experiment">
          <ol className="space-y-3 text-[13px]">
            {[
              ["Sign", "Embed a C2PA credential (ES256) and create a detached Ed25519 envelope over the signed file's SHA-256."],
              ["Verify the clean copy", "Expected: valid provenance under the local demo trust policy."],
              ["Byte-level tamper", "Change one byte (a JPEG quantisation coefficient, or one PNG pixel). The image looks the same and the embedded manifest is untouched."],
              ["Visual edit + re-encode", "Brighten a small patch and re-save. Re-encoding strips the embedded manifest, the classic “signature stripping” case."],
              ["Compare", "SHA-256 changes completely; pHash stays close. Similar-looking is not the same as intact."],
            ].map(([t, d], i) => (
              <li key={t} className="flex gap-3">
                <span className="mono mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-ink text-[11px] text-white">{i + 1}</span>
                <div><p className="font-medium text-ink">{t}</p><p className="text-muted">{d}</p></div>
              </li>
            ))}
          </ol>
        </Panel>
      </div>
      <div className="mt-8" aria-live="polite">
        {run.isError && <ErrorNote title="Lab run failed" message={(run.error as Error).message} />}
        {run.isPending && <Skeleton className="h-[480px]" />}
        {result && !run.isPending && <LabResult c={result} />}
      </div>
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Lab = any;

export function LabResult({ c }: { c: CaseDetail }) {
  const rec = c.provenance.find((p) => p.operation === "tamper_test");
  if (!rec) return <ErrorNote message="This case has no lab record." />;
  const lab: Lab = rec.details;
  const asset = (id: string) => c.assets.find((a) => a.id === id);
  const signed = asset(lab.signed.asset_id);
  const exp = lab.expectations_met as Record<string, boolean>;
  const allOk = Object.values(exp).every(Boolean);
  return (
    <div className="space-y-6">
      <div className={cx("flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-panel)] border px-5 py-4", allOk ? "border-ok/25 bg-ok-wash" : "border-bad/25 bg-bad-wash")}>
        <div>
          <p className="text-[12px] text-muted">Lab outcome</p>
          <p className="text-[15px] font-medium text-ink">{c.summary?.headline}</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(exp).map(([k, v]) => <Chip key={k} tone={v ? "ok" : "bad"}>{v ? "✓" : "✗"} {k.replaceAll("_", " ")}</Chip>)}
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        <Copy title="Signed original" tone="seal" a={signed} status={lab.signed.verification.status}
          sub="Clean copy with embedded C2PA credential."
          c2paSteps={lab.signed.verification.c2pa_steps} detSteps={lab.signed.verification.detached_steps} sha={lab.signed.sha256} />
        <Copy title="Byte-level tamper" tone="bad" a={asset(lab.tampered_bytes.asset_id)} status={lab.tampered_bytes.verification.status}
          sub={lab.tampered_bytes.description}
          c2paSteps={lab.tampered_bytes.verification.c2pa_steps} detSteps={lab.tampered_bytes.verification.detached_steps}
          c2paStatus={lab.tampered_bytes.verification.c2pa_status} detStatus={lab.tampered_bytes.verification.detached_status}
          sha={lab.tampered_bytes.sha256} compare={lab.signed.sha256} bits={lab.tampered_bytes.sha256_bits_changed} bytes={lab.tampered_bytes.bytes_changed}
          ph={lab.tampered_bytes.phash_distance_to_signed} phLabel={lab.tampered_bytes.phash_label} />
        <Copy title="Visual edit + re-encode" tone="bad" a={asset(lab.tampered_visual.asset_id)} status={lab.tampered_visual.verification.status}
          sub={lab.tampered_visual.description}
          c2paSteps={lab.tampered_visual.verification.c2pa_steps} detSteps={lab.tampered_visual.verification.detached_steps}
          c2paStatus={lab.tampered_visual.verification.c2pa_status} detStatus={lab.tampered_visual.verification.detached_status}
          sha={lab.tampered_visual.sha256} compare={lab.signed.sha256} bits={lab.tampered_visual.sha256_bits_changed} bytes={lab.tampered_visual.bytes_changed}
          ph={lab.tampered_visual.phash_distance_to_signed} phLabel={lab.tampered_visual.phash_label} />
      </div>

      <Panel title="Why the signature no longer validates">
        <div className="grid gap-6 text-[13.5px] leading-relaxed text-ink/85 md:grid-cols-2">
          <p>The C2PA claim contains a <em>hard binding</em>: a SHA-256 hash of the asset bytes (excluding the manifest itself). The claim is then signed with ECDSA P-256. Changing even one byte changes the SHA-256 completely (about half of its 256 bits flip, the avalanche effect), so the recomputed hash no longer matches the signed one and the verifier reports <span className="mono text-[12.5px]">assertion.dataHash.mismatch</span>. The signature over the claim may still be mathematically valid; it just no longer describes these bytes.</p>
          <p>Re-encoding produces a brand-new file with no embedded manifest at all, so the C2PA check reports <em>no provenance found</em>. That alone would not prove tampering, which is why the detached Ed25519 envelope matters here: its signed digest does not match the edited file. Meanwhile the pHash distance stays small, because pHash measures how an image <em>looks</em>, not what its bytes are. It is useful for finding near-duplicates and useless as an integrity check.</p>
        </div>
        <Link to={`/cases/${c.id}`} className="mt-4 inline-block text-[13px] font-medium text-signal hover:underline">Open the full lab report ({c.share_ref})</Link>
      </Panel>
    </div>
  );
}

function Copy({ title, sub, a, status, c2paSteps, detSteps, sha, compare, bits, bytes, ph, phLabel, tone, c2paStatus, detStatus }: {
  c2paStatus?: string; detStatus?: string; title: string; sub: string; a?: { url: string; mime: string; download_url: string }; status: string; c2paSteps: Step[]; detSteps?: Step[]; sha: string;
  compare?: string; bits?: number; bytes?: number; ph?: number | null; phLabel?: string | null; tone: "seal" | "bad";
}) {
  return (
    <Panel title={title} description={sub} channel={tone === "seal" ? "seal" : undefined}>
      {a && <MediaPreview src={a.url} mime={a.mime} alt={title} tone={tone} />}
      <div className="mt-4 space-y-4">
        <ProvChip status={status} />
        {c2paStatus && (
          <p className="text-[12px] leading-relaxed text-muted">
            C2PA check: <span className="font-medium text-ink">{PROVENANCE_LABEL[c2paStatus]?.text ?? c2paStatus}</span>
            {detStatus && <>; detached envelope: <span className="font-medium text-ink">{PROVENANCE_LABEL[detStatus]?.text ?? detStatus}</span></>}
          </p>
        )}
        <div>
          <p className="mb-1 text-[12px] text-muted">SHA-256{compare ? " (red = differs from signed original)" : ""}</p>
          <Hash value={sha} compare={compare} label={`${title} SHA-256`} small />
          {bits !== undefined && <p className="mt-1 text-[12px] text-muted"><span className="mono text-bad">{bits}</span>/256 digest bits changed after <span className="mono">{bytes}</span> byte{bytes === 1 ? "" : "s"} changed in the file.</p>}
        </div>
        {ph !== undefined && ph !== null && (
          <div className="rounded-lg bg-paper px-3 py-2 text-[12.5px]">
            <span className="text-muted">pHash distance to original: </span><span className="mono font-medium">{ph}/64</span>
            <span className="text-muted">, {phLabel}</span>
          </div>
        )}
        <details className="group">
          <summary className="cursor-pointer text-[12.5px] font-medium text-signal">Verification steps</summary>
          <div className="mt-3 space-y-4">
            <div><p className="mb-1.5 text-[12px] font-medium">C2PA</p><Steps steps={c2paSteps ?? []} /></div>
            {detSteps && <div><p className="mb-1.5 text-[12px] font-medium">Detached Ed25519 envelope <span className="font-normal text-seal">(not C2PA)</span></p><Steps steps={detSteps} /></div>}
          </div>
        </details>
        {a && <a className="inline-block text-[12.5px] text-muted hover:text-ink" href={a.download_url}><FlaskConical className="mr-1 inline size-3.5" />Download this copy</a>}
      </div>
    </Panel>
  );
}
