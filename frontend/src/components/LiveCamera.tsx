import { Aperture, Camera, CameraOff, Circle, Square } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button, cx } from "./ui";

export const MAX_RECORD_S = 10;

type CamState = "idle" | "starting" | "live" | "denied" | "unsupported" | "error";

export function pickRecorderType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  // MP4 first (can carry C2PA when signed); WebM as fallback (OpenCV decodes both for analysis).
  for (const t of ["video/mp4;codecs=avc1", "video/mp4", "video/webm;codecs=vp9", "video/webm"]) if (MediaRecorder.isTypeSupported(t)) return t;
  return undefined;
}

/** Live camera with "capture photo" and "record clip". Hands the exact encoded bytes to `onCapture`. */
export function LiveCamera({ onCapture, busy, photoLabel = "Capture photo", clipLabel = "Record clip" }: {
  onCapture: (file: File) => void; busy?: boolean; photoLabel?: string; clipLabel?: string;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recRef = useRef<MediaRecorder | null>(null);
  const [cam, setCam] = useState<CamState>("idle");
  const [camError, setCamError] = useState("");
  const [recording, setRecording] = useState(0);

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

  const photo = () => {
    const v = videoRef.current;
    if (!v || !v.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = v.videoWidth;
    canvas.height = v.videoHeight;
    canvas.getContext("2d")!.drawImage(v, 0, 0);
    canvas.toBlob((b) => {
      if (!b) { toast.error("Could not encode the captured frame."); return; }
      onCapture(new File([b], `camera-photo-${new Date().toISOString().replace(/[:.]/g, "-")}.jpg`, { type: "image/jpeg" }));
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
      onCapture(new File([blob], `camera-clip-${Date.now()}.${base === "video/mp4" ? "mp4" : "webm"}`, { type: base }));
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
                {cam === "denied" && "Camera permission was denied. Allow access in the browser's site settings, or choose a file instead."}
                {cam === "unsupported" && "This browser does not support camera capture here (it needs HTTPS or localhost)."}
                {cam === "error" && camError}
              </p>
            </div>
          )}
          {recording > 0 && <div className="absolute top-3 left-3 flex items-center gap-2 rounded-full bg-bad px-3 py-1 text-[12px] font-medium text-white"><Circle className="size-2.5 fill-white" /> REC {recording}s / {MAX_RECORD_S}s</div>}
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {cam !== "live" ? (
          <Button onClick={start} loading={cam === "starting"} icon={<Camera className="size-4" />}>Start camera</Button>
        ) : (
          <>
            <Button onClick={photo} loading={busy && recording === 0} disabled={recording > 0 || busy} icon={<Aperture className="size-4" />}>{photoLabel}</Button>
            {recording > 0 ? (
              <Button variant="danger" onClick={() => recRef.current?.stop()} icon={<Square className="size-4" />}>Stop recording</Button>
            ) : (
              <Button variant="secondary" onClick={record} disabled={busy || !pickRecorderType()} icon={<Circle className="size-4" />}>{clipLabel} (≤{MAX_RECORD_S}s)</Button>
            )}
            <Button variant="ghost" onClick={stop} disabled={recording > 0}>Turn off camera</Button>
          </>
        )}
      </div>
    </div>
  );
}
