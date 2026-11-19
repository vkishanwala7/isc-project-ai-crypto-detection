import { useQuery } from "@tanstack/react-query";
import { FolderSearch, Search } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { KIND_LABEL } from "../lib/format";
import { CaseRow } from "../components/evidence";
import { Button, EmptyState, ErrorNote, PageHeader, Panel, Skeleton, cx } from "../components/ui";

const KINDS = ["", "analysis", "signing", "verification", "integrity_lab"];

export default function Cases() {
  const [params, setParams] = useSearchParams();
  const kind = params.get("kind") ?? "";
  const q = params.get("q") ?? "";
  const [text, setText] = useState(q);
  const list = useQuery({ queryKey: ["cases", kind, q], queryFn: () => api.cases({ kind: kind || undefined, q: q || undefined, limit: 200 }) });
  const set = (k: string, v: string) => { const p = new URLSearchParams(params); if (v) p.set(k, v); else p.delete(k); setParams(p); };

  return (
    <div>
      <PageHeader title="Cases" lede="Every analysis, signing, verification and lab run is stored as a durable case with an immutable identifier and its own evidence report." />
      <Panel>
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <div className="flex flex-wrap gap-1 rounded-lg bg-paper p-1" role="tablist" aria-label="Filter by type">
            {KINDS.map((k) => (
              <button key={k} role="tab" aria-selected={kind === k} onClick={() => set("kind", k)}
                className={cx("rounded-md px-3 py-1.5 text-[13px]", kind === k ? "bg-surface font-medium text-ink shadow-sm" : "text-muted hover:text-ink")}>
                {k ? KIND_LABEL[k] : "All"}
              </button>
            ))}
          </div>
          <form className="ml-auto flex gap-2" onSubmit={(e) => { e.preventDefault(); set("q", text.trim()); }}>
            <label className="relative">
              <span className="sr-only">Search by filename or reference</span>
              <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-faint" />
              <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Filename or VF-reference" className="h-9 w-64 rounded-[var(--radius-control)] border border-line-strong bg-surface pr-3 pl-9 text-[13px] focus:border-signal focus:outline-none" />
            </label>
            <Button size="sm" variant="secondary" type="submit">Search</Button>
          </form>
        </div>
        {list.isError ? <ErrorNote message={(list.error as Error).message} onRetry={() => list.refetch()} />
          : list.isLoading ? <div className="space-y-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-14" />)}</div>
          : list.data!.items.length === 0 ? (
            <EmptyState icon={<FolderSearch className="size-6" />} title={q || kind ? "No cases match these filters" : "No cases yet"}
              action={<Link to="/analyze"><Button size="sm">Analyze media</Button></Link>}>
              {q || kind ? "Try clearing the search or choosing another type." : "Cases appear here as soon as you analyse, sign or verify a file."}
            </EmptyState>
          ) : (
            <>
              <p className="mb-2 text-[12.5px] text-muted">{list.data!.total} case{list.data!.total === 1 ? "" : "s"}</p>
              <div className="-mx-3 divide-y divide-line/70">{list.data!.items.map((c) => <CaseRow key={c.id} c={c} />)}</div>
            </>
          )}
      </Panel>
    </div>
  );
}
