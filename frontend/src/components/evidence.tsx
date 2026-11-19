import { Brain, Fingerprint, Info, ScanFace, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import type { AIDetails, CaseSummary, DetachedResult, Step, VerifyDetails } from "../lib/api";
import { AI_LABEL, KIND_LABEL, PROVENANCE_LABEL, fmtRelative, fmtScore } from "../lib/format";
import { Chip, Hash, KV, Panel, StateIcon, cx } from "./ui";

export function ProvChip({ status }: { status: string | null | undefined }) {
  if (!status) return <Chip>Not checked</Chip>;
  const l = PROVENANCE_LABEL[status] ?? { text: status, tone: "neutral" as const };
  return <Chip tone={l.tone} title={status}>{l.text}</Chip>;
}

export function AIChip({ verdict, score }: { verdict: string | null | undefined; score?: number | null }) {
  if (!verdict) return <Chip>Not analysed</Chip>;
  const l = AI_LABEL[verdict] ?? { text: verdict, tone: "neutral" as const };
  return <Chip tone={l.tone} title={verdict}>{l.text}{score !== null && score !== undefined ? <span className="mono opacity-80">{fmtScore(score, 2)}</span> : null}</Chip>;
}

/* ------------------------------------------------------------- score meter */
export function ScoreMeter({ score, threshold, band }: { score: number; threshold: number; band?: [number, number] }) {
  return (
    <div>
      <div className="relative h-2.5 rounded-full bg-gradient-to-r from-ok/25 via-ink/10 to-bad/30" role="img" aria-label={`Model score ${score.toFixed(3)} with threshold ${threshold}`}>
        {band && <div className="absolute inset-y-0 rounded-full bg-ink/10" style={{ left: `${band[0] * 100}%`, width: `${(band[1] - band[0]) * 100}%` }} />}
        <div className="absolute -top-1 bottom-[-4px] w-px bg-ink/60" style={{ left: `${threshold * 100}%` }} />
        <div className="absolute top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] border-white bg-signal shadow" style={{ left: `${score * 100}%` }} />
      </div>
      <div className="mt-2 flex justify-between text-[11.5px] text-muted">
        <span>0, low signal</span>
        <span>threshold {threshold.toFixed(2)}{band ? `, inconclusive ${band[0].toFixed(2)}–${band[1].toFixed(2)}` : ""}</span>
        <span>1, strong signal</span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------- AI panel */
export function AIPanel({ ai, compact }: { ai: AIDetails | null | undefined; compact?: boolean }) {
  return (
    <Panel
      channel="signal"
      title={<span className="flex items-center gap-2"><Brain className="size-4 text-signal" /> AI manipulation signal</span>}
      description="Does the model detect patterns associated with the manipulation classes it was trained on? It cannot say whether the depicted event is true."
    >
      {!ai ? (
        <p className="text-sm text-muted">No AI analysis was run for this case.</p>
      ) : ai.status === "MODEL_UNAVAILABLE" ? (
        <div className="rounded-lg bg-paper p-4 text-sm text-muted"><p className="font-medium text-ink">Model weights unavailable</p><p className="mt-1">{ai.message} No score was produced.</p></div>
      ) : ai.status === "FAILED" ? (
        <div className="rounded-lg bg-bad-wash p-4 text-sm text-bad"><p className="font-medium">Analysis could not complete ({ai.reason})</p><p className="mt-1">{ai.message}</p></div>
      ) : (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-3">
            <AIChip verdict={ai.verdict} />
            {ai.reason === "NO_FACE_DETECTED" && <Chip>No face detected</Chip>}
          </div>
          {ai.score !== null && ai.threshold !== undefined ? (
            <div>
              <div className="mb-3 flex items-baseline gap-2">
                <span className="mono text-[34px] font-medium leading-none tracking-tight text-ink">{fmtScore(ai.score)}</span>
                <span className="text-[13px] text-muted">model estimate of manipulation likelihood</span>
              </div>
              <ScoreMeter score={ai.score} threshold={ai.threshold} band={ai.inconclusive_band} />
            </div>
          ) : (
            <p className="text-sm text-muted">{ai.message}</p>
          )}
          {ai.faces && ai.faces.length > 0 && (
            <div>
              <p className="mb-2 text-[13px] font-medium text-ink">Per-face results ({ai.faces.length})</p>
              <div className="flex flex-wrap gap-2">
                {ai.faces.map((f, i) => (
                  <div key={i} className="rounded-lg border border-line px-3 py-2 text-[12.5px]">
                    <span className="text-muted">Face {i + 1}</span>{" "}
                    <span className="mono font-medium">{fmtScore(f.score)}</span>
                    <span className="ml-2 text-faint">det. {(f.detector_confidence * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {ai.frames && <FrameStrip ai={ai} />}
          {!compact && (
            <KV rows={[
              ["Model", ai.model ? `${ai.model.name} v${ai.model.version}` : "—"],
              ["Architecture", ai.model?.architecture],
              ["Aggregation", ai.aggregation ?? "—"],
              ...(ai.sampling ? [["Sampling", ai.sampling] as [string, string]] : []),
              ["Processing time", ai.duration_ms !== undefined ? `${ai.duration_ms} ms` : "—"],
            ]} />
          )}
          <p className="flex gap-2 rounded-lg bg-signal-wash/60 px-3 py-2.5 text-[12.5px] leading-relaxed text-ink/80">
            <Info className="mt-0.5 size-3.5 shrink-0 text-signal" />
            <span>{ai.score_semantics} {ai.scope_note ?? ""} Expect errors on unseen generators, heavy compression and faces unlike the training data.</span>
          </p>
        </div>
      )}
    </Panel>
  );
}

function FrameStrip({ ai }: { ai: AIDetails }) {
  const frames = ai.frames ?? [];
  return (
    <div>
      <p className="mb-2 text-[13px] font-medium text-ink">
        Sampled frames — {ai.frames_with_faces}/{ai.frames_sampled} with faces in a {ai.duration_s?.toFixed(1)} s clip
        {ai.median_score !== undefined && <span className="font-normal text-muted">, median {fmtScore(ai.median_score)}, max {ai.max_score !== undefined ? fmtScore(ai.max_score) : "—"}</span>}
      </p>
      <div className="flex h-24 items-end gap-1 rounded-lg border border-line bg-paper/60 p-2" role="img" aria-label="Per-frame scores">
        {frames.map((f) => (
          <div key={f.index} className="group relative flex h-full flex-1 flex-col justify-end" title={`t=${f.timestamp_s}s · ${f.status}${f.score !== undefined ? ` · ${f.score}` : ""}`}>
            {f.score !== undefined ? (
              <div className={cx("w-full rounded-sm", ai.threshold !== undefined && f.score >= ai.threshold ? "bg-bad/70" : "bg-signal/70")} style={{ height: `${Math.max(4, f.score * 100)}%` }} />
            ) : (
              <div className="h-1 w-full rounded-sm bg-line-strong" />
            )}
          </div>
        ))}
      </div>
      <div className="mt-1 flex justify-between text-[11px] text-faint"><span>start</span><span>grey = no face / unreadable</span><span>end</span></div>
    </div>
  );
}

/* ------------------------------------------------------------- Provenance panel */
export function Steps({ steps }: { steps: Step[] }) {
  return (
    <ol className="space-y-2.5">
      {steps.map((s) => (
        <li key={s.key} className="flex gap-3">
          <StateIcon state={s.state} className="mt-0.5" />
          <div className="min-w-0">
            <p className="text-[13.5px] font-medium text-ink">{s.label}</p>
            <p className="text-[12.5px] leading-relaxed text-muted">{s.detail}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

export function ProvenancePanel({ v, sha256, phash }: { v: VerifyDetails | null | undefined; sha256?: string; phash?: string | null }) {
  return (
    <Panel
      channel="seal"
      title={<span className="flex items-center gap-2"><ShieldCheck className="size-4 text-seal" /> Cryptographic provenance</span>}
      description="Does this exact file match a signed content binding, and is the signer trusted by this verifier's policy? It does not prove the original scene is factual."
    >
      {!v ? <p className="text-sm text-muted">Provenance was not inspected.</p> : (
        <div className="space-y-5">
          <div>
            <ProvChip status={v.status} />
            <p className="mt-2 max-w-[70ch] text-[13.5px] leading-relaxed text-ink/85">{v.status_text}</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <Dimension label="Signature / binding" value={v.signature_valid === null ? "Not applicable" : v.signature_valid ? (v.status === "TAMPERED_OR_INVALID" ? "Claim signed, binding failed" : "Valid") : "Invalid"} tone={v.signature_valid === null ? "neutral" : v.status === "TAMPERED_OR_INVALID" ? "bad" : v.signature_valid ? "ok" : "bad"} />
            <Dimension label="Signer trust" value={v.signer_trusted === null ? "Not applicable" : v.signer_trusted ? "Trusted (local demo policy)" : "Not trusted"} tone={v.signer_trusted === null ? "neutral" : v.signer_trusted ? "ok" : "warn"} />
            <Dimension label="Provenance availability" value={v.c2pa.manifest_found || v.detached ? "Record present" : "None attached"} tone="neutral" />
          </div>

          <div>
            <p className="mb-2.5 flex items-center gap-2 text-[13px] font-medium text-ink">C2PA Content Credentials <Chip tone="seal">{v.c2pa.sdk?.python_package ?? "c2pa"}</Chip></p>
            <Steps steps={v.c2pa.steps} />
            {v.c2pa.error && <p className="mt-2 text-[12.5px] text-bad">{v.c2pa.error}</p>}
            {v.c2pa.manifest_found && v.c2pa.signer && (
              <KV className="mt-4" rows={[
                ["Signer", `${v.c2pa.signer.common_name ?? "—"} (issuer: ${v.c2pa.signer.issuer ?? "—"})`],
                ["Algorithm", v.c2pa.signer.alg],
                ["Claim generator", v.c2pa.claim_generator?.map((g) => `${g.name} ${g.version ?? ""}`).join(", ")],
                ["Actions", v.c2pa.actions?.map((a) => String(a.action) + (a.digitalSourceType ? ` (${String(a.digitalSourceType).split("/").pop()})` : "")).join(", ") || "—"],
                ["Assertions", v.c2pa.assertions?.join(", ")],
                ["Timestamp", v.c2pa.timestamp ?? v.c2pa.timestamp_note],
                ["Trust policy", v.c2pa.trust_policy],
                ...(v.c2pa.signing_context ? [["Signing statement", String(v.c2pa.signing_context.statement ?? "")] as [string, string]] : []),
              ]} />
            )}
          </div>

          {v.detached && <DetachedBlock d={v.detached} />}

          {(sha256 || v.similar_known_asset) && (
            <div className="grid gap-4 border-t border-line pt-4 md:grid-cols-2">
              {sha256 && (
                <div>
                  <p className="mb-1 flex items-center gap-1.5 text-[12.5px] font-medium text-ink"><Fingerprint className="size-3.5 text-seal" /> SHA-256 of these exact bytes</p>
                  <Hash value={sha256} label="SHA-256" small />
                </div>
              )}
              <div>
                <p className="mb-1 text-[12.5px] font-medium text-ink">pHash similarity <span className="font-normal text-muted">(heuristic, not integrity)</span></p>
                {phash && <p className="mono text-[12px] text-muted">pHash {phash}</p>}
                {v.similar_known_asset?.found ? (
                  <p className="mt-1 text-[12.5px] text-ink/85">
                    Closest stored asset: <Link to={`/cases/${v.similar_known_asset.case_id}`} className="text-signal hover:underline">{v.similar_known_asset.display_name}</Link>{" "}
                    — distance {v.similar_known_asset.distance}/64, {v.similar_known_asset.label}
                    {v.similar_known_asset.exact_byte_match ? "; identical bytes" : ""}.
                  </p>
                ) : (
                  <p className="mt-1 text-[12.5px] text-muted">{v.similar_known_asset?.note ?? "No comparison available."}</p>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}

function DetachedBlock({ d }: { d: DetachedResult }) {
  return (
    <div className="rounded-xl border border-dashed border-seal/35 bg-seal-wash/40 p-4">
      <p className="mb-1 text-[13px] font-medium text-ink">Detached Ed25519 envelope</p>
      <p className="mb-3 text-[12px] font-medium text-seal">VERIFRAME detached-signature demo — not a C2PA Content Credential.</p>
      <div className="mb-3"><ProvChip status={d.status} /></div>
      <Steps steps={d.steps} />
    </div>
  );
}

function Dimension({ label, value, tone }: { label: string; value: string; tone: "ok" | "warn" | "bad" | "neutral" }) {
  return (
    <div className="rounded-lg border border-line px-3 py-2.5">
      <p className="text-[11.5px] text-muted">{label}</p>
      <p className={cx("mt-0.5 text-[13px] font-medium", tone === "ok" && "text-ok", tone === "warn" && "text-warn", tone === "bad" && "text-bad", tone === "neutral" && "text-ink")}>{value}</p>
    </div>
  );
}

/* ------------------------------------------------------------- Evidence matrix (the public interpretation rule) */
const AI_ROWS = [
  { key: "LOW_MANIPULATION_SIGNAL", label: "Low AI signal" },
  { key: "INCONCLUSIVE", label: "Inconclusive / no face" },
  { key: "LIKELY_MANIPULATED", label: "AI signal detected" },
  { key: "NOT_RUN", label: "AI not run / unavailable" },
];
const PROV_COLS = [
  { key: "VALID_PROVENANCE", label: "Valid, trusted" },
  { key: "VALID_BUT_UNTRUSTED_SIGNER", label: "Valid, untrusted" },
  { key: "NO_PROVENANCE_FOUND", label: "No provenance" },
  { key: "TAMPERED_OR_INVALID", label: "Tampered / invalid" },
];
function cellText(ai: string, pv: string): { t: string; tone: string } {
  if (pv === "TAMPERED_OR_INVALID") return { t: "Integrity failed; AI shown separately", tone: "bad" };
  if (pv === "VALID_PROVENANCE" && ai === "LOW_MANIPULATION_SIGNAL") return { t: "Strong provenance, low signal", tone: "ok" };
  if ((pv === "VALID_PROVENANCE" || pv === "VALID_BUT_UNTRUSTED_SIGNER") && ai === "LIKELY_MANIPULATED") return { t: "Signed origin, but AI flags it — inspect edits", tone: "warn" };
  if (pv === "NO_PROVENANCE_FOUND" && ai === "LIKELY_MANIPULATED") return { t: "Unverified origin + AI signal: corroborate", tone: "warn" };
  if (pv === "NO_PROVENANCE_FOUND") return { t: "Origin unverified", tone: "neutral" };
  if (pv === "VALID_BUT_UNTRUSTED_SIGNER") return { t: "Valid credential, unknown signer", tone: "neutral" };
  return { t: "Valid provenance (local policy)", tone: "ok" };
}

export function EvidenceMatrix({ ai, prov, compact }: { ai?: string | null; prov?: string | null; compact?: boolean }) {
  const aiKey = !ai || ai === "MODEL_UNAVAILABLE" || ai === "NOT_RUN" || ai === "FAILED" ? "NOT_RUN" : ai;
  const pvKey = prov === "UNSUPPORTED_OR_UNREADABLE" ? "NO_PROVENANCE_FOUND" : prov ?? "";
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] border-separate border-spacing-1 text-[12px]">
        <caption className="sr-only">Evidence interpretation matrix: AI signal by provenance state</caption>
        <thead>
          <tr>
            <th className="w-[150px] text-left font-normal text-muted"><span className="text-signal">AI</span> × <span className="text-seal">provenance</span></th>
            {PROV_COLS.map((c) => <th key={c.key} scope="col" className="px-2 pb-1 text-left font-medium text-seal">{c.label}</th>)}
          </tr>
        </thead>
        <tbody>
          {AI_ROWS.map((r) => (
            <tr key={r.key}>
              <th scope="row" className="pr-2 text-left font-medium text-signal">{r.label}</th>
              {PROV_COLS.map((c) => {
                const { t, tone } = cellText(r.key, c.key);
                const active = r.key === aiKey && c.key === pvKey;
                return (
                  <td key={c.key} className={cx(
                    "rounded-md px-2.5 py-2 align-top leading-snug transition-colors",
                    active ? "bg-ink text-white ring-2 ring-signal-bright ring-offset-1" : "bg-paper text-ink/70",
                    !active && tone === "bad" && "text-bad/80",
                    !active && tone === "warn" && "text-warn",
                    !active && tone === "ok" && "text-ok",
                    compact && "py-1.5",
                  )} aria-current={active ? "true" : undefined}>
                    {t}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------------------------------------- Case row */
export function CaseRow({ c }: { c: CaseSummary }) {
  return (
    <Link to={`/cases/${c.id}`} className="group flex items-center gap-4 rounded-lg px-3 py-2.5 hover:bg-paper">
      <div className="flex size-11 shrink-0 items-center justify-center overflow-hidden rounded-md bg-ink">
        {c.thumbnail_url ? <img src={c.thumbnail_url} alt="" className="size-full object-cover" loading="lazy" /> : <ScanFace className="size-4 text-white/50" />}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13.5px] font-medium text-ink group-hover:text-signal">{c.title}</p>
        <p className="text-[12px] text-muted">{KIND_LABEL[c.kind]}, {c.media_type}, {fmtRelative(c.created_at)}{c.is_sample ? ", demo sample" : ""}</p>
      </div>
      <div className="hidden flex-wrap justify-end gap-1.5 sm:flex">
        {c.kind === "analysis" && <AIChip verdict={c.ai_verdict} />}
        <ProvChip status={c.provenance_status} />
      </div>
    </Link>
  );
}
