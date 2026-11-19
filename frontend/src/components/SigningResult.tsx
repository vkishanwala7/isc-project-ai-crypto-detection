import { Download, FileText } from "lucide-react";
import { Link } from "react-router-dom";
import type { CaseDetail, VerifyDetails } from "../lib/api";
import { fmtBytes, fmtDate } from "../lib/format";
import { ProvChip, Steps } from "./evidence";
import { Button, Chip, CopyButton, Hash, KV, MediaPreview, Panel } from "./ui";

export function SigningResult({ c }: { c: CaseDetail }) {
  const rec = c.provenance.find((p) => p.operation === "sign");
  const original = c.assets.find((a) => a.role === "original");
  const signed = c.assets.find((a) => a.role === "signed");
  const envelope = c.assets.find((a) => a.role === "envelope");
  const post = rec?.details?.post_sign_verification as VerifyDetails | undefined;
  const cert = rec?.details?.signer_certificate as Record<string, string> | undefined;
  const c2pa = rec?.details?.c2pa as { applied: boolean; reason?: string; error?: string } | undefined;
  return (
    <div className="space-y-5">
      <Panel channel="seal" title="Signed and re-verified"
        description={rec?.details?.capture_statement + " The new file was re-opened through the verifier; the status below comes from that independent check, not from the signing call."}
        actions={<Link to={`/cases/${c.id}`}><Button size="sm" variant="secondary" icon={<FileText className="size-4" />}>Evidence report</Button></Link>}>
        <div className="grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <div>
            {(signed ?? original) && <MediaPreview src={(signed ?? original)!.url} mime={(signed ?? original)!.mime} alt="Signed asset" tone="seal" />}
            <div className="mt-4 flex flex-wrap gap-2">
              {signed && <a href={signed.download_url}><Button size="sm" icon={<Download className="size-4" />}>Signed file (C2PA embedded)</Button></a>}
              {envelope && <a href={envelope.download_url}><Button size="sm" variant="secondary" icon={<Download className="size-4" />}>Detached envelope (.json)</Button></a>}
            </div>
            <p className="mt-2 text-[12px] text-muted">The C2PA manifest is embedded inside the signed file, so no separate manifest download is needed. The envelope is a supplementary educational signature.</p>
          </div>
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2">
              <ProvChip status={post?.status ?? rec?.status} />
              {c2pa?.applied ? <Chip tone="seal">C2PA Content Credential embedded</Chip> : <Chip tone="warn">C2PA not applied</Chip>}
            </div>
            {!c2pa?.applied && <p className="text-[12.5px] text-warn">{c2pa?.reason ?? c2pa?.error}</p>}
            <div>
              <p className="mb-1 text-[12.5px] text-muted">SHA-256 of the captured/received bytes</p>
              {original && <Hash value={original.sha256} label="Original SHA-256" small />}
            </div>
            {signed && (
              <div>
                <p className="mb-1 text-[12.5px] text-muted">SHA-256 of the signed file (bytes changed because the manifest was embedded)</p>
                <Hash value={signed.sha256} label="Signed SHA-256" small />
              </div>
            )}
            <KV rows={[
              ["Signer", cert?.subject],
              ["Signer type", cert?.type],
              ["Algorithm", cert?.algorithm],
              ["Certificate fingerprint", cert ? <span className="mono text-[11.5px] break-all">{cert.sha256_fingerprint}</span> : "—"],
              ["Signed at", rec ? fmtDate(rec.created_at) : "—"],
              ["Ed25519 key id", rec?.details?.ed25519_key_id],
              ["Signed file size", signed ? fmtBytes(signed.size_bytes) : "—"],
              ["Share reference", <span className="inline-flex items-center gap-1 mono text-[12.5px]">{c.share_ref}<CopyButton value={c.share_ref} label="Copy share reference" /></span>],
            ]} />
          </div>
        </div>
      </Panel>
      {post && (
        <Panel title="Post-signing verification steps" description="Run by the verifier on the newly signed bytes.">
          <div className="grid gap-6 md:grid-cols-2">
            <div><p className="mb-2 text-[13px] font-medium">C2PA</p><Steps steps={post.c2pa.steps} /></div>
            {post.detached && <div><p className="mb-2 text-[13px] font-medium">Detached Ed25519 envelope <span className="font-normal text-seal">(not a C2PA credential)</span></p><Steps steps={post.detached.steps} /></div>}
          </div>
        </Panel>
      )}
    </div>
  );
}
