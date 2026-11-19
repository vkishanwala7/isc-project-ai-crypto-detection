import { useQuery } from "@tanstack/react-query";
import { ChevronRight, ScrollText } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type ActivityEvent } from "../lib/api";
import { ACTION_LABEL, fmtDate } from "../lib/format";
import { EmptyState, ErrorNote, PageHeader, Panel, Skeleton, cx } from "../components/ui";

const ACTIONS = ["", "upload", "analysis", "sign", "verify", "tamper_test", "report_export", "delete", "error"];

export default function ActivityPage() {
  const [action, setAction] = useState("");
  const q = useQuery({ queryKey: ["activity", action], queryFn: () => api.activity({ action: action || undefined, limit: 300 }), refetchInterval: 15_000 });
  return (
    <div>
      <PageHeader title="Activity log" lede="Persisted audit events for uploads, analyses, signing, verification, tamper tests, exports and errors. Media bytes, private keys and server paths are never logged." />
      <Panel>
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <label className="text-[13px] text-muted" htmlFor="act">Action</label>
          <select id="act" value={action} onChange={(e) => setAction(e.target.value)} className="h-9 rounded-[var(--radius-control)] border border-line-strong bg-surface px-3 text-[13px] focus:border-signal focus:outline-none">
            {ACTIONS.map((a) => <option key={a} value={a}>{a ? ACTION_LABEL[a] ?? a : "All actions"}</option>)}
          </select>
          {q.data && <span className="ml-auto text-[12.5px] text-muted">{q.data.total} event{q.data.total === 1 ? "" : "s"}</span>}
        </div>
        {q.isError ? <ErrorNote message={(q.error as Error).message} onRetry={() => q.refetch()} />
          : q.isLoading ? <div className="space-y-2">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-10" />)}</div>
          : q.data!.items.length === 0 ? <EmptyState icon={<ScrollText className="size-6" />} title="No events recorded">Events are written as you use the application.</EmptyState>
          : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-[13px]">
                <thead className="text-[12px] text-muted">
                  <tr className="border-b border-line"><th className="w-8 py-2" /><th className="py-2 font-medium">Time</th><th className="font-medium">Action</th><th className="font-medium">Result</th><th className="font-medium">Case</th></tr>
                </thead>
                <tbody>{q.data!.items.map((e) => <Row key={e.id} e={e} />)}</tbody>
              </table>
            </div>
          )}
      </Panel>
    </div>
  );
}

function Row({ e }: { e: ActivityEvent }) {
  const [open, setOpen] = useState(false);
  const tone = e.action === "error" || e.result === "TAMPERED_OR_INVALID" ? "text-bad" : e.result === "VALID_PROVENANCE" || e.result === "TAMPER_DETECTED" ? "text-ok" : "text-ink";
  return (
    <>
      <tr className="border-b border-line/70 hover:bg-paper/70">
        <td className="py-2">
          <button onClick={() => setOpen(!open)} aria-expanded={open} aria-label="Toggle technical details" className="rounded p-1 text-faint hover:text-ink">
            <ChevronRight className={cx("size-4 transition-transform", open && "rotate-90")} />
          </button>
        </td>
        <td className="py-2 whitespace-nowrap text-muted">{fmtDate(e.ts)}</td>
        <td className="font-medium">{ACTION_LABEL[e.action] ?? e.action}</td>
        <td className={cx("mono text-[12px]", tone)}>{e.result}</td>
        <td>{e.case_id ? (e.action === "delete" ? <span className="mono text-[12px] text-faint">{e.case_id.slice(0, 8)}</span> : <Link to={`/cases/${e.case_id}`} className="mono text-[12px] text-signal hover:underline">{e.case_id.slice(0, 8)}</Link>) : "—"}</td>
      </tr>
      {open && (
        <tr className="border-b border-line/70 bg-paper/60">
          <td />
          <td colSpan={4} className="py-3 pr-4"><pre className="mono overflow-x-auto text-[11.5px] leading-relaxed whitespace-pre-wrap text-ink/80">{JSON.stringify(e.details ?? {}, null, 2)}</pre></td>
        </tr>
      )}
    </>
  );
}
