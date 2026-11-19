// Typed client for the VERIFRAME FastAPI backend (proxied at /api by Vite).

export type ProvenanceStatus =
  | "VALID_PROVENANCE"
  | "VALID_BUT_UNTRUSTED_SIGNER"
  | "TAMPERED_OR_INVALID"
  | "NO_PROVENANCE_FOUND"
  | "UNSUPPORTED_OR_UNREADABLE";

export type AIVerdict = "LIKELY_MANIPULATED" | "LOW_MANIPULATION_SIGNAL" | "INCONCLUSIVE";

export interface Asset {
  id: string;
  role: string;
  display_name: string;
  mime: string;
  size_bytes: number;
  sha256: string;
  phash: string | null;
  width: number | null;
  height: number | null;
  duration_s: number | null;
  url: string;
  download_url: string;
}

export interface CaseSummary {
  id: string;
  created_at: string;
  kind: "analysis" | "signing" | "verification" | "integrity_lab";
  title: string;
  media_type: "image" | "video";
  is_sample: boolean;
  sample_label: string | null;
  ai_verdict: string | null;
  ai_score: number | null;
  provenance_status: string | null;
  headline: string | null;
  tone: string | null;
  thumbnail_url: string | null;
}

export interface Step { key: string; label: string; state: "pass" | "fail" | "warn" | "absent" | "unknown"; detail: string }

export interface C2paResult {
  implementation: string;
  status: ProvenanceStatus;
  manifest_found: boolean;
  validation_state?: string;
  signature_valid?: boolean;
  binding_valid?: boolean;
  signer_trusted?: boolean;
  trust_policy?: string;
  signer?: { common_name?: string; issuer?: string; alg?: string; cert_serial_number?: string; time?: string };
  claim_generator?: { name: string; version?: string }[];
  title?: string;
  actions?: Record<string, unknown>[];
  assertions?: string[];
  signing_context?: Record<string, unknown> | null;
  ingredients?: { title?: string; relationship?: string; format?: string }[];
  timestamp?: string | null;
  timestamp_note?: string | null;
  validation_codes?: { success: string[]; failure: { code: string; explanation: string }[]; informational: string[] };
  steps: Step[];
  error?: string;
  sdk?: { python_package: string; native_sdk: string };
}

export interface DetachedResult {
  implementation: string;
  status: ProvenanceStatus;
  signature_valid?: boolean;
  binding_valid?: boolean;
  signer_trusted?: boolean;
  key_id?: string;
  expected_sha256?: string;
  actual_sha256?: string;
  steps: Step[];
  error?: string;
}

export interface SimilarAsset {
  found: boolean;
  distance?: number;
  case_id?: string;
  asset_role?: string;
  display_name?: string;
  exact_byte_match?: boolean;
  label?: string;
  note: string;
}

export interface VerifyDetails {
  status: ProvenanceStatus;
  status_text: string;
  c2pa: C2paResult;
  detached: DetachedResult | null;
  signature_valid: boolean | null;
  signer_trusted: boolean | null;
  similar_known_asset?: SimilarAsset | null;
  label?: string;
  interpretation_rule: string;
}

export interface FaceResult { box: number[]; detector_confidence: number; score: number; verdict: AIVerdict }
export interface FrameResult { index: number; timestamp_s: number; status: string; faces?: number; score?: number }

export interface AIDetails {
  status: "COMPLETED" | "MODEL_UNAVAILABLE" | "FAILED";
  verdict: AIVerdict;
  reason: string | null;
  score: number | null;
  message?: string;
  threshold?: number;
  inconclusive_band?: [number, number];
  score_semantics?: string;
  aggregation?: string;
  model?: { name: string; version: string; architecture: string; checkpoint_sha256: string; trained_by: string };
  faces?: FaceResult[];
  frames?: FrameResult[];
  frames_sampled?: number;
  frames_with_faces?: number;
  total_frames?: number;
  duration_s?: number;
  sampling?: string;
  scope_note?: string;
  median_score?: number;
  max_score?: number;
  duration_ms?: number;
  image_size?: number[];
}

export interface AnalysisRecord {
  id: string;
  created_at: string;
  asset_id: string;
  status: string;
  verdict: string;
  reason: string | null;
  score: number | null;
  threshold: number | null;
  model_name: string | null;
  model_version: string | null;
  duration_ms: number | null;
  details: AIDetails;
}

export interface ProvenanceRecord {
  id: string;
  created_at: string;
  asset_id: string | null;
  operation: "sign" | "verify" | "tamper_test";
  status: string;
  signature_valid: boolean | null;
  signer_trusted: boolean | null;
  signer: string | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  details: any;
}

export interface CaseDetail extends CaseSummary {
  sample_source: string | null;
  summary: { headline: string; tone: string; ai_dimension?: string; provenance_dimension?: string; rule?: string; lab?: boolean } | null;
  assets: Asset[];
  analyses: AnalysisRecord[];
  provenance: ProvenanceRecord[];
  timeline: { ts: string; action: string; result: string; details: Record<string, unknown> | null }[];
  share_ref: string;
}

export interface Health {
  status: "ok" | "degraded";
  version: string;
  time: string;
  subsystems: Record<string, { ok: boolean; detail: string }>;
}

export interface DashboardSummary {
  counts: Record<string, number>;
  ai_outcomes: Record<string, number>;
  provenance_outcomes: Record<string, number>;
  activity_series: { date: string; analysis: number; sign: number; verify: number; tamper_test: number }[];
  recent_cases: CaseSummary[];
  sample_cases_excluded: boolean;
}

export interface ActivityEvent { id: number; ts: string; action: string; case_id: string | null; result: string; details: Record<string, unknown> | null }

export interface Sample {
  id: string;
  filename: string;
  media_type: string;
  label: string;
  label_text: string;
  source: string;
  license: string;
  used_for_training: boolean;
  note?: string;
  available: boolean;
}

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(message: string, code: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError("The VERIFRAME backend is not reachable. Start it with `uvicorn app.main:app --port 8000` in backend/.", "NETWORK", 0);
  }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    let code = "HTTP_" + res.status;
    try {
      const body = await res.json();
      const d = body?.detail;
      if (d && typeof d === "object") {
        msg = d.message ?? msg;
        code = d.code ?? code;
      } else if (typeof d === "string") msg = d;
    } catch {
      /* non-JSON error */
    }
    if (res.status === 502 || res.status === 504) msg = "The backend did not respond. Is the API server running on port 8000?";
    throw new ApiError(msg, code, res.status);
  }
  return res.json() as Promise<T>;
}

function form(fields: Record<string, string | Blob | undefined | null>): FormData {
  const fd = new FormData();
  for (const [k, v] of Object.entries(fields)) {
    if (v === undefined || v === null) continue;
    if (v instanceof File) fd.append(k, v, v.name);
    else if (v instanceof Blob) fd.append(k, v, k);
    else fd.append(k, v);
  }
  return fd;
}

export const api = {
  health: () => request<Health>("/api/health"),
  config: () => request<{ accepted_mime_types: string[]; max_image_mb: number; max_video_mb: number; max_video_seconds: number; video_sample_frames: number; c2pa_sign_mime_types: string[]; signer: Record<string, string>; trust_root: Record<string, string>; ed25519_key_id: string }>("/api/config"),
  dashboard: () => request<DashboardSummary>("/api/dashboard/summary"),
  analyze: (file: File) => request<CaseDetail>("/api/analyze", { method: "POST", body: form({ file }) }),
  sign: (file: File, source: "upload" | "browser_capture", note = "") =>
    request<CaseDetail>("/api/provenance/sign", { method: "POST", body: form({ file, source, note }) }),
  verify: (file: File, credential?: File | null) =>
    request<CaseDetail>("/api/provenance/verify", { method: "POST", body: form({ file, credential: credential ?? undefined }) }),
  verifyRef: (ref: string) =>
    request<{ case_id: string; asset: Asset; result: VerifyDetails }>(`/api/provenance/verify-ref/${encodeURIComponent(ref)}`, { method: "POST" }),
  tamperDemo: (file: File | null) =>
    request<CaseDetail>("/api/integrity/tamper-demo", { method: "POST", body: file ? form({ file }) : form({ use_demo_asset: "true" }) }),
  cases: (params: { kind?: string; q?: string; limit?: number } = {}) => {
    const sp = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v !== undefined && v !== "" && sp.set(k, String(v)));
    return request<{ items: CaseSummary[]; total: number }>(`/api/cases?${sp}`);
  },
  case: (id: string) => request<CaseDetail>(`/api/cases/${encodeURIComponent(id)}`),
  deleteCase: (id: string) => request<{ deleted: string }>(`/api/cases/${encodeURIComponent(id)}`, { method: "DELETE" }),
  activity: (params: { action?: string; limit?: number } = {}) => {
    const sp = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v !== undefined && v !== "" && sp.set(k, String(v)));
    return request<{ items: ActivityEvent[]; total: number }>(`/api/activity?${sp}`);
  },
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  modelInfo: () => request<any>("/api/model/info"),
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  modelMetrics: () => request<any>("/api/model/metrics"),
  samples: () => request<{ samples: Sample[]; fetch_command: string; note: string }>("/api/samples"),
  analyzeSample: (id: string) => request<CaseDetail>(`/api/samples/${encodeURIComponent(id)}/analyze`, { method: "POST" }),
};
