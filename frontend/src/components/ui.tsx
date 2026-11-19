import { clsx } from "clsx";
import { Check, Copy, AlertTriangle, CircleCheck, CircleX, CircleMinus, CircleHelp, Upload, Loader2, X } from "lucide-react";
import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { chunkHex, type Tone } from "../lib/format";

export function cx(...a: Parameters<typeof clsx>) {
  return clsx(...a);
}

/* ---------------------------------------------------------------- Button */
type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
  loading?: boolean;
  icon?: ReactNode;
};
export function Button({ variant = "primary", size = "md", loading, icon, className, children, disabled, ...rest }: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-[var(--radius-control)] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-55",
        size === "sm" ? "h-8 px-3 text-[13px]" : "h-10 px-4 text-sm",
        variant === "primary" && "bg-ink text-white hover:bg-ink-3",
        variant === "secondary" && "border border-line-strong bg-surface text-ink hover:border-ink/40 hover:bg-paper",
        variant === "ghost" && "text-muted hover:bg-ink/5 hover:text-ink",
        variant === "danger" && "bg-bad text-white hover:bg-bad/90",
        className,
      )}
    >
      {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
}

/* ---------------------------------------------------------------- Panel */
export function Panel({ title, description, actions, children, className, channel, id }: {
  title?: ReactNode; description?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; channel?: "signal" | "seal"; id?: string;
}) {
  return (
    <section id={id} className={cx("print-break relative min-w-0 rounded-[var(--radius-panel)] border border-line bg-surface", className)}>
      {channel && <span aria-hidden className={cx("absolute inset-y-4 left-0 w-[3px] rounded-r", channel === "signal" ? "bg-signal" : "bg-seal")} />}
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 px-5 pt-4 pb-3 sm:px-6">
          <div className="min-w-0">
            {title && <h2 className="text-[15px] font-semibold tracking-[-0.005em] text-ink">{title}</h2>}
            {description && <p className="mt-0.5 max-w-[68ch] text-[13px] leading-relaxed text-muted">{description}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cx("px-5 pb-5 sm:px-6", !(title || actions) && "pt-5")}>{children}</div>
    </section>
  );
}

/* ---------------------------------------------------------------- Status chip */
const toneCls: Record<Tone, string> = {
  ok: "bg-ok-wash text-ok ring-ok/20",
  warn: "bg-warn-wash text-warn ring-warn/25",
  bad: "bg-bad-wash text-bad ring-bad/20",
  neutral: "bg-ink/[0.05] text-muted ring-ink/10",
  signal: "bg-signal-wash text-signal ring-signal/20",
  seal: "bg-seal-wash text-seal ring-seal/20",
};
export function Chip({ tone = "neutral", children, className, title }: { tone?: Tone; children: ReactNode; className?: string; title?: string }) {
  return (
    <span title={title} className={cx("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-[12px] font-medium ring-1 ring-inset", toneCls[tone], className)}>
      {children}
    </span>
  );
}

export function StateIcon({ state, className }: { state: string; className?: string }) {
  const c = cx("size-[18px] shrink-0", className);
  if (state === "pass") return <CircleCheck className={cx(c, "text-ok")} aria-label="passed" />;
  if (state === "fail") return <CircleX className={cx(c, "text-bad")} aria-label="failed" />;
  if (state === "warn") return <AlertTriangle className={cx(c, "text-warn")} aria-label="warning" />;
  if (state === "absent") return <CircleMinus className={cx(c, "text-faint")} aria-label="absent" />;
  return <CircleHelp className={cx(c, "text-faint")} aria-label="unknown" />;
}

/* ---------------------------------------------------------------- Copy & hash */
export function useCopy() {
  return useCallback(async (text: string, what = "Copied") => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(what);
    } catch {
      toast.error("Clipboard is not available in this browser context.");
    }
  }, []);
}

export function CopyButton({ value, label = "Copy", what }: { value: string; label?: string; what?: string }) {
  const copy = useCopy();
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      onClick={() => { copy(value, what ?? "Copied to clipboard"); setDone(true); setTimeout(() => setDone(false), 1400); }}
      className="no-print inline-flex size-7 items-center justify-center rounded-md text-faint hover:bg-ink/5 hover:text-ink"
      aria-label={label}
      title={label}
    >
      {done ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
    </button>
  );
}

/** SHA-256 rendered in 8-character groups; optional comparison highlights differing characters. */
export function Hash({ value, compare, label, small }: { value: string; compare?: string; label?: string; small?: boolean }) {
  const groups = chunkHex(value);
  return (
    <div className="flex items-start gap-1">
      <code className={cx("mono flex flex-wrap gap-x-1.5 gap-y-0.5 break-all leading-relaxed text-ink", small ? "text-[11.5px]" : "text-[12.5px]")} aria-label={label ?? "hash"}>
        {groups.map((g, gi) => (
          <span key={gi}>
            {compare
              ? g.split("").map((ch, ci) => {
                  const same = compare[gi * 8 + ci] === ch;
                  return <span key={ci} className={same ? "text-faint" : "rounded-[2px] bg-bad-wash text-bad"}>{ch}</span>;
                })
              : g}
          </span>
        ))}
      </code>
      <CopyButton value={value} label={`Copy ${label ?? "hash"}`} what={`${label ?? "Hash"} copied`} />
    </div>
  );
}

/* ---------------------------------------------------------------- Key/value */
export function KV({ rows, className }: { rows: [ReactNode, ReactNode][]; className?: string }) {
  return (
    <dl className={cx("grid grid-cols-[minmax(110px,max-content)_1fr] gap-x-5 gap-y-2.5 text-[13px]", className)}>
      {rows.map(([k, v], i) => (
        <div key={i} className="contents">
          <dt className="text-muted">{k}</dt>
          <dd className="min-w-0 break-words text-ink">{v ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

/* ---------------------------------------------------------------- Skeleton & empty */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("skeleton", className)} aria-hidden />;
}

export function EmptyState({ icon, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-line-strong px-6 py-10 text-center">
      {icon && <div className="mb-3 text-faint">{icon}</div>}
      <p className="text-sm font-medium text-ink">{title}</p>
      {children && <p className="mt-1 max-w-[52ch] text-[13px] leading-relaxed text-muted">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorNote({ title = "Something went wrong", message, onRetry }: { title?: string; message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-xl border border-bad/25 bg-bad-wash px-4 py-3 text-[13px] text-bad">
      <AlertTriangle className="mt-0.5 size-4 shrink-0" />
      <div className="flex-1">
        <p className="font-medium">{title}</p>
        <p className="mt-0.5 text-bad/90">{message}</p>
      </div>
      {onRetry && <Button size="sm" variant="secondary" onClick={onRetry}>Retry</Button>}
    </div>
  );
}

/* ---------------------------------------------------------------- Dropzone */
export function Dropzone({ accept, onFile, file, hint, maxBytes, disabled, label = "Drop a file here, or browse" }: {
  accept: string; onFile: (f: File | null) => void; file: File | null; hint?: ReactNode; maxBytes?: number; disabled?: boolean; label?: string;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const pick = (f: File | undefined | null) => {
    if (!f) return;
    const okTypes = accept.split(",").map((s) => s.trim());
    const ext = "." + (f.name.split(".").pop() ?? "").toLowerCase();
    if (!okTypes.some((t) => t === f.type || t === ext)) {
      toast.error(`“${f.name}” is not an accepted format.`);
      return;
    }
    if (maxBytes && f.size > maxBytes) {
      toast.error(`File is ${(f.size / 1048576).toFixed(1)} MB; the limit is ${(maxBytes / 1048576).toFixed(0)} MB.`);
      return;
    }
    onFile(f);
  };
  return (
    <div
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); if (!disabled) pick(e.dataTransfer.files?.[0]); }}
      className={cx(
        "relative flex min-h-[148px] flex-col items-center justify-center rounded-xl border-[1.5px] border-dashed px-6 py-7 text-center transition-colors",
        over ? "border-signal bg-signal-wash/60" : "border-line-strong bg-paper/60",
        disabled && "opacity-60",
      )}
    >
      <input ref={ref} type="file" accept={accept} className="sr-only" disabled={disabled} onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} aria-label={label} />
      {file ? (
        <div className="flex items-center gap-3 text-left">
          <div className="min-w-0">
            <p className="max-w-[40ch] truncate text-sm font-medium text-ink">{file.name}</p>
            <p className="text-[12px] text-muted">{(file.size / 1024).toFixed(1)} KB, {file.type || "unknown type"}</p>
          </div>
          <button type="button" onClick={() => onFile(null)} disabled={disabled} className="rounded-md p-1 text-faint hover:bg-ink/5 hover:text-ink" aria-label="Remove file">
            <X className="size-4" />
          </button>
        </div>
      ) : (
        <>
          <Upload className="mb-2 size-5 text-faint" aria-hidden />
          <p className="text-sm text-ink">
            Drop a file here, or{" "}
            <button type="button" className="font-medium text-signal underline-offset-2 hover:underline" onClick={() => ref.current?.click()} disabled={disabled}>browse</button>
          </p>
          {hint && <p className="mt-1.5 text-[12px] text-muted">{hint}</p>}
        </>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- Media preview with viewfinder */
export function MediaPreview({ src, mime, alt, className, tone = "signal" }: { src: string; mime: string; alt: string; className?: string; tone?: "signal" | "seal" | "bad" }) {
  const color = tone === "signal" ? "var(--color-signal-bright)" : tone === "seal" ? "var(--color-seal-bright)" : "var(--color-bad)";
  return (
    <div className={cx("viewfinder m-1.5", className)} style={{ ["--vf-color" as string]: color }}>
      <span className="vf-b" aria-hidden />
      <div className="overflow-hidden rounded-lg bg-ink">
        {mime.startsWith("video/") ? (
          <video src={src} controls className="mx-auto max-h-[380px] w-full object-contain" aria-label={alt} />
        ) : (
          <img src={src} alt={alt} className="mx-auto max-h-[380px] w-full object-contain" />
        )}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- Confirm dialog */
export function ConfirmDialog({ open, title, body, confirmLabel, onConfirm, onCancel, busy }: {
  open: boolean; title: string; body: ReactNode; confirmLabel: string; onConfirm: () => void; onCancel: () => void; busy?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog ref={ref} onCancel={(e) => { e.preventDefault(); onCancel(); }} className="m-auto w-[min(440px,calc(100vw-2rem))] rounded-2xl border border-line bg-surface p-0 text-ink shadow-2xl backdrop:bg-ink/50 backdrop:backdrop-blur-[2px]">
      <div className="p-6">
        <h3 className="text-base font-semibold">{title}</h3>
        <div className="mt-2 text-sm leading-relaxed text-muted">{body}</div>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="secondary" onClick={onCancel} disabled={busy}>Cancel</Button>
          <Button variant="danger" onClick={onConfirm} loading={busy}>{confirmLabel}</Button>
        </div>
      </div>
    </dialog>
  );
}

export function PageHeader({ title, lede, actions }: { title: string; lede?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.02em] text-ink sm:text-[30px]">{title}</h1>
        {lede && <p className="mt-1.5 max-w-[72ch] text-[14.5px] leading-relaxed text-muted">{lede}</p>}
      </div>
      {actions && <div className="no-print flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
