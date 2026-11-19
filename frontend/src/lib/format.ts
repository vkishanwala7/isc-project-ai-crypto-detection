// Display helpers and the human vocabulary for status codes.

export type Tone = "ok" | "warn" | "bad" | "neutral" | "signal" | "seal";

export const PROVENANCE_LABEL: Record<string, { text: string; tone: Tone; short: string }> = {
  VALID_PROVENANCE: { text: "Valid provenance", short: "Valid", tone: "ok" },
  VALID_BUT_UNTRUSTED_SIGNER: { text: "Valid, signer not trusted", short: "Untrusted signer", tone: "warn" },
  TAMPERED_OR_INVALID: { text: "Tampered or invalid", short: "Failed", tone: "bad" },
  NO_PROVENANCE_FOUND: { text: "No provenance found", short: "None found", tone: "neutral" },
  UNSUPPORTED_OR_UNREADABLE: { text: "Unsupported or unreadable", short: "Unreadable", tone: "neutral" },
  TAMPER_DETECTED: { text: "Tampering detected as expected", short: "Lab passed", tone: "ok" },
  UNEXPECTED_RESULT: { text: "Unexpected lab result", short: "Unexpected", tone: "bad" },
};

export const AI_LABEL: Record<string, { text: string; tone: Tone; short: string }> = {
  LIKELY_MANIPULATED: { text: "Manipulation signal detected", short: "Signal detected", tone: "bad" },
  LOW_MANIPULATION_SIGNAL: { text: "Low manipulation signal", short: "Low signal", tone: "ok" },
  INCONCLUSIVE: { text: "Inconclusive", short: "Inconclusive", tone: "neutral" },
  MODEL_UNAVAILABLE: { text: "Model unavailable", short: "No model", tone: "neutral" },
  FAILED: { text: "Analysis failed", short: "Failed", tone: "bad" },
};

export const KIND_LABEL: Record<string, string> = {
  analysis: "Analysis",
  signing: "Signing",
  verification: "Verification",
  integrity_lab: "Integrity lab",
};

export const ACTION_LABEL: Record<string, string> = {
  upload: "Upload",
  analysis: "AI analysis",
  sign: "Signed",
  verify: "Verification",
  tamper_test: "Tamper test",
  error: "Error",
  report_export: "Report export",
  delete: "Case deleted",
};

export function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

export function fmtDate(iso: string, withTime = true): string {
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  return d.toLocaleString(undefined, withTime ? { dateStyle: "medium", timeStyle: "short" } : { dateStyle: "medium" });
}

export function fmtRelative(iso: string): string {
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z").getTime();
  const s = Math.round((Date.now() - d) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return fmtDate(iso, false);
}

export function pct(x: number | null | undefined, digits = 1): string {
  return x === null || x === undefined || Number.isNaN(x) ? "—" : `${(x * 100).toFixed(digits)}%`;
}

export function chunkHex(hex: string, size = 8): string[] {
  const out: string[] = [];
  for (let i = 0; i < hex.length; i += size) out.push(hex.slice(i, i + size));
  return out;
}

export function shareRef(id: string): string {
  return `VF-${id.slice(0, 8).toUpperCase()}-${id.slice(8, 12).toUpperCase()}`;
}

/** Model scores are estimates; never display them as an exact 0 or 1. */
export function fmtScore(x: number, digits = 3): string {
  const hi = 1 - 0.5 * 10 ** -digits;
  const lo = 0.5 * 10 ** -digits;
  if (x >= hi) return `>${(1 - 10 ** -digits).toFixed(digits)}`;
  if (x <= lo) return `<${(10 ** -digits).toFixed(digits)}`;
  return x.toFixed(digits);
}
