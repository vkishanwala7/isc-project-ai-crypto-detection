import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Aperture, Camera, CameraOff, Circle, Square, Upload } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api, type CaseDetail } from "../lib/api";
import { SigningResult } from "../components/SigningResult";
import { Button, Dropzone, ErrorNote, PageHeader, Panel, Skeleton, cx } from "../components/ui";

type CamState = "idle" | "starting" | "live" | "denied" | "unsupported" | "error";
const MAX_RECORD_S = 10;

function pickRecorderType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  // MP4 can carry an embedded C2PA manifest; WebM cannot (it gets the detached envelope only).
  for (const t of ["video/mp4;codecs=avc1", "video/mp4", "video/webm;codecs=vp9", "video/webm"]) if (MediaRecorder.isTypeSupported(t)) return t;
  return undefined;
}

export default function Capture() {
  const qc = useQueryClient();
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recRef = useRef<MediaRecorder | null>(null);
  const [cam, setCam] = useState<CamState>("idle");
  const [camError, setCamError] = useState("");
  const [recording, setRecording] = useState(0);
  const [result, setResult] = useState<CaseDetail | null>(null);
  const [upload, setUpload] = useState<File | null>(null);

  const sign = useMutation({
    mutationFn: ({ file, source }: { file: File; source: "browser_capture" | "upload" }) => api.sign(file, source),
    onSuccess: (c) => { setResult(c); qc.invalidateQueries({ queryKey: ["dashboard"] }); toast.success("Signed and verified", { description: c.share_ref }); },
  });

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setCam("idle");
  }, []);
  useEffect(() => stop, [stop]);

  const start = async () => {
    if (!navigator.mediaDevices?.getUserMedia) { setCam("unsupported"); return; }
    setCam("starting");
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
      streamRef.current = s;
      if (videoRef.current) { videoRef.current.srcObject = s; await videoRef.current.play().catch(() => undefined); }
      setCam("live");
    } catch (e) {
      const name = (e as DOMException).name;
      if (name === "NotAllowedError" || name === "SecurityError") setCam("denied");
      else { setCam("error"); setCamError(name === "NotFoundError" ? "No camera was found on this device." : `Camera could not start (${name}).`); }
    }
  };

  const still = () => {
    const v = videoRef.current;
    if (!v || !v.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = v.videoWidth;
    canvas.height = v.videoHeight;
    canvas.getContext("2d")!.drawImage(v, 0, 0);
    canvas.toBlob((b) => {
      if (!b) { toast.error("Could not encode the captured frame."); return; }
      const f = new File([b], `capture-${new Date().toISOString().replace(/[:.]/g, "-")}.jpg`, { type: "image/jpeg" });
      // The exact encoded bytes are submitted immediately for signing.
      sign.mutate({ file: f, source: "browser_capture" });
    }, "image/jpeg", 0.95);
  };

  const record = () => {
    const s = streamRef.current;
    const type = pickRecorderType();
    if (!s || !type) { toast.error("Video recording (MediaRecorder) is not supported in this browser."); return; }
    const chunks: Blob[] = [];
    const rec = new MediaRecorder(s, { mimeType: type });
    recRef.current = rec;
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    rec.onstop = () => {
      setRecording(0);
      const base = type.split(";")[0];
      const blob = new Blob(chunks, { type: base });
      const f = new File([blob], `capture-${Date.now()}.${base === "video/mp4" ? "mp4" : "webm"}`, { type: base });
      sign.mutate({ file: f, source: "browser_capture" });
    };
    rec.start();
    const t0 = Date.now();
    setRecording(1);
    const iv = setInterval(() => {
      const el = Math.floor((Date.now() - t0) / 1000);
      if (rec.state !== "recording") { clearInterval(iv); return; }
      setRecording(el + 1);
      if (el >= MAX_RECORD_S) { rec.stop(); clearInterval(iv); }
    }, 250);
  };

  return (
    <div>
      <PageHeader title="Capture & sign"
        lede="Capture a still (or a short clip) in the browser. The exact bytes are sent to the VERIFRAME demo service, which embeds a C2PA Content Credential, adds a detached Ed25519 envelope, and immediately re-verifies the result." />

      <div className="mb-6 rounded-[var(--radius-panel)] border border-seal/25 bg-seal-wash/50 px-5 py-3.5 text-[13px] leading-relaxed text-ink/85">
        <span className="font-medium text-seal">Signed by this VERIFRAME demo service after browser capture.</span>{" "}
        A browser cannot prove which physical camera produced the frames, so no hardware attestation, secure sensor pipeline or manufacturer identity is claimed. The signer is a local demo certificate that is not on the public C2PA trust list.
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <Panel title="Camera" description="Uses getUserMedia. Nothing is recorded until you press a capture button.">
          <div className={cx("viewfinder m-1.5", recording > 0 && "[--vf-color:var(--color-bad)]")}>
            <span className="vf-b" aria-hidden />
            <div className="relative flex aspect-video items-center justify-center overflow-hidden rounded-lg bg-ink">
              <video ref={videoRef} playsInline muted className={cx("size-full object-cover", cam !== "live" && "hidden")} aria-label="Live camera preview" />
              {cam !== "live" && (
                <div className="px-6 text-center text-white/70">
                  {cam === "denied" ? <CameraOff className="mx-auto mb-2 size-7" /> : <Camera className="mx-auto mb-2 size-7" />}
                  <p className="text-sm">
                    {cam === "idle" && "Camera is off."}
                    {cam === "starting" && "Waiting for camera permission…"}
                    {cam === "denied" && "Camera permission was denied. Allow access in the browser's site settings, or upload a file instead."}
                    {cam === "unsupported" && "This browser does not support camera capture here (it needs HTTPS or localhost). Upload a file instead."}
                    {cam === "error" && camError}
                  </p>
                </div>
              )}
              {recording > 0 && <div className="absolute top-3 left-3 flex items-center gap-2 rounded-full bg-bad px-3 py-1 text-[12px] font-medium text-white"><Circle className="size-2.5 fill-white" /> REC {recording}s / {MAX_RECORD_S}s</div>}
            </div>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            {cam !== "live" ? (
              <Button onClick={start} loading={cam === "starting"} icon={<Camera className="size-4" />}>Start camera</Button>
            ) : (
              <>
                <Button onClick={still} loading={sign.isPending} disabled={recording > 0} icon={<Aperture className="size-4" />}>Capture still & sign</Button>
                {recording > 0 ? (
                  <Button variant="danger" onClick={() => recRef.current?.stop()} icon={<Square className="size-4" />}>Stop & sign</Button>
                ) : (
                  <Button variant="secondary" onClick={record} disabled={sign.isPending || !pickRecorderType()} icon={<Circle className="size-4" />}>Record clip (≤{MAX_RECORD_S}s)</Button>
                )}
                <Button variant="ghost" onClick={stop} disabled={recording > 0}>Turn off camera</Button>
              </>
            )}
          </div>
          {cam === "live" && pickRecorderType()?.startsWith("video/webm") && (
            <p className="mt-3 text-[12px] text-muted">This browser records WebM, which the C2PA SDK cannot embed into. Clips will receive the detached Ed25519 envelope only, and the result will say so.</p>
          )}
        </Panel>

        <Panel title="Or upload & sign" description="For files not captured here. The credential then records only that VERIFRAME received these bytes (c2pa.opened), not how they were created.">
          <Dropzone accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,.jpg,.jpeg,.png,.webp,.mp4,.mov" file={upload} onFile={setUpload} disabled={sign.isPending}
            hint="JPEG, PNG, WebP, MP4 or MOV get an embedded C2PA credential." />
          <Button className="mt-4" variant="secondary" disabled={!upload} loading={sign.isPending && !!upload} onClick={() => upload && sign.mutate({ file: upload, source: "upload" })} icon={<Upload className="size-4" />}>
            Sign uploaded file
          </Button>
        </Panel>
      </div>

      <div className="mt-8" aria-live="polite">
        {sign.isError && <ErrorNote title="Signing failed" message={(sign.error as Error).message} />}
        {sign.isPending && <Skeleton className="h-[320px]" />}
        {result && !sign.isPending && <SigningResult c={result} />}
      </div>
    </div>
  );
}
