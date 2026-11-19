import { useQuery } from "@tanstack/react-query";
import {
  Activity, BookOpen, Camera, FlaskConical, FolderSearch, Gauge, PanelLeftClose, PanelLeftOpen, ScanFace, Search, ShieldCheck, Brain, Menu, X,
} from "lucide-react";
import { type FormEvent, Suspense, useEffect, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { cx } from "./ui";

export function Mark({ className }: { className?: string }) {
  // Original mark: viewfinder corners (frame) + check stroke (verification)
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <path d="M7 12V7h5M20 7h5v5M25 20v5h-5M12 25H7v-5" fill="none" stroke="var(--color-signal-bright)" strokeWidth="2.4" strokeLinecap="round" />
      <path d="M11.5 16.5l3.2 3.2 5.8-6.6" fill="none" stroke="var(--color-seal-bright)" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Wordmark({ collapsed }: { collapsed?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <Mark className="size-8 shrink-0" />
      {!collapsed && (
        <div className="leading-none">
          <div className="text-[17px] font-semibold tracking-[0.14em] text-white">VERIFRAME</div>
          <div className="mt-1 text-[11px] text-white/50">Media authenticity intelligence</div>
        </div>
      )}
    </div>
  );
}

const NAV = [
  { to: "/dashboard", label: "Overview", icon: Gauge },
  { to: "/analyze", label: "Analyze media", icon: ScanFace },
  { to: "/capture", label: "Capture & sign", icon: Camera },
  { to: "/verify", label: "Verify a file", icon: ShieldCheck },
  { to: "/integrity-lab", label: "Integrity lab", icon: FlaskConical },
  { to: "/cases", label: "Cases", icon: FolderSearch },
  { to: "/model-lab", label: "Model & dataset", icon: Brain },
  { to: "/activity", label: "Activity log", icon: Activity },
  { to: "/about", label: "About & method", icon: BookOpen },
];

const TITLES: Record<string, string> = Object.fromEntries(NAV.map((n) => [n.to, n.label]));

function SystemStatus() {
  const { data, isError } = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 30_000 });
  const ok = data?.status === "ok";
  const label = isError ? "Backend offline" : !data ? "Checking…" : ok ? "All systems ready" : "Degraded";
  const detail = data ? Object.entries(data.subsystems).map(([k, v]) => `${v.ok ? "✓" : "✗"} ${k}: ${v.detail}`).join("\n") : isError ? "The API at /api is not reachable." : "";
  return (
    <div className="flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1.5 text-[12.5px] text-muted" title={detail}>
      <span className={cx("size-2 rounded-full", isError ? "bg-bad" : !data ? "bg-faint" : ok ? "bg-ok" : "bg-warn")} />
      <span className="hidden sm:inline">{label}</span>
    </div>
  );
}

export default function Layout() {
  const [collapsed, setCollapsed] = useState(() => localStorageGet("vf-sidebar") === "1");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [q, setQ] = useState("");
  const nav = useNavigate();
  const loc = useLocation();
  const reduce = useReducedMotion();
  const base = "/" + (loc.pathname.split("/")[1] ?? "");
  const title = loc.pathname.startsWith("/cases/") ? "Evidence report" : TITLES[base] ?? "VERIFRAME";

  useEffect(() => { setMobileOpen(false); }, [loc.pathname]);
  useEffect(() => { document.title = `${title} — VERIFRAME`; }, [title]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const v = q.trim();
    if (!v) return;
    nav(/^VF-[0-9A-F]{8}-[0-9A-F]{4}$/i.test(v) || /^[0-9a-f]{32}$/i.test(v) ? `/cases/${v}` : `/cases?q=${encodeURIComponent(v)}`);
    setQ("");
  };

  const sidebar = (
    <nav aria-label="Main" className="flex h-full flex-col bg-ink px-3 py-4 text-white">
      <div className={cx("mb-6 flex items-center px-2", collapsed ? "justify-center" : "justify-between")}>
        <NavLink to="/dashboard" aria-label="VERIFRAME home"><Wordmark collapsed={collapsed} /></NavLink>
      </div>
      <ul className="flex-1 space-y-0.5">
        {NAV.map(({ to, label, icon: Icon }) => (
          <li key={to}>
            <NavLink
              to={to}
              title={collapsed ? label : undefined}
              className={({ isActive }) => cx(
                "group flex items-center gap-3 rounded-lg px-3 py-2 text-[13.5px] transition-colors",
                collapsed && "justify-center px-0",
                isActive ? "bg-white/[0.09] text-white" : "text-white/60 hover:bg-white/[0.05] hover:text-white",
              )}
            >
              {({ isActive }) => (
                <>
                  <Icon className={cx("size-[18px] shrink-0", isActive ? "text-signal-bright" : "text-white/45 group-hover:text-white/80")} />
                  {!collapsed && <span>{label}</span>}
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
      {!collapsed && (
        <div className="mt-4 rounded-lg border border-white/10 px-3 py-3 text-[11.5px] leading-relaxed text-white/55">
          ISC project, Team 16
          <div className="mt-1 text-white/40">Local academic demonstration</div>
        </div>
      )}
      <button
        type="button"
        onClick={() => { const v = !collapsed; setCollapsed(v); localStorageSet("vf-sidebar", v ? "1" : "0"); }}
        className="mt-3 hidden items-center justify-center gap-2 rounded-lg py-2 text-[12px] text-white/50 hover:bg-white/5 hover:text-white lg:flex"
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? <PanelLeftOpen className="size-4" /> : <><PanelLeftClose className="size-4" /> Collapse</>}
      </button>
    </nav>
  );

  return (
    <div className="flex min-h-screen">
      <aside className={cx("no-print sticky top-0 hidden h-screen shrink-0 transition-[width] duration-200 lg:block", collapsed ? "w-[72px]" : "w-[248px]")}>{sidebar}</aside>
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-ink/50" onClick={() => setMobileOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-[260px]">{sidebar}</div>
          <button className="absolute top-4 left-[272px] rounded-full bg-surface p-2" onClick={() => setMobileOpen(false)} aria-label="Close navigation"><X className="size-4" /></button>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="no-print sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-line bg-paper/85 px-4 backdrop-blur-md sm:px-6">
          <button className="rounded-lg p-2 text-muted hover:bg-ink/5 lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu className="size-5" /></button>
          <p className="truncate text-[15px] font-semibold text-ink">{title}</p>
          <form onSubmit={submit} className="ml-auto hidden md:block" role="search">
            <label className="relative block">
              <span className="sr-only">Search cases or open a share reference</span>
              <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-faint" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search cases or paste VF-reference"
                className="h-9 w-[280px] rounded-full border border-line bg-surface pr-3 pl-9 text-[13px] placeholder:text-faint focus:border-signal focus:outline-none"
              />
            </label>
          </form>
          <SystemStatus />
          <div className="hidden items-center gap-2 rounded-full bg-ink px-3 py-1.5 text-[12px] text-white/85 sm:flex" title="No accounts: this is a single-user local demo workspace">
            <span className="size-1.5 rounded-full bg-seal-bright" /> Demo workspace
          </div>
        </header>
        <main className="print-full mx-auto w-full max-w-[1280px] flex-1 px-4 py-7 sm:px-6 lg:px-8">
          <motion.div key={loc.pathname} initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22, ease: "easeOut" }}>
            <Suspense fallback={<div className="space-y-4"><div className="skeleton h-10 w-64" /><div className="skeleton h-[360px]" /></div>}>
              <Outlet />
            </Suspense>
          </motion.div>
        </main>
        <footer className="no-print border-t border-line px-6 py-3 text-center text-[12px] text-muted">
          Results are forensic indicators, not a guarantee of truth. Missing provenance does not mean media is fake; a valid signature does not prove the depicted event is true.
        </footer>
      </div>
    </div>
  );
}

function localStorageGet(k: string): string | null {
  try { return window.localStorage.getItem(k); } catch { return null; }
}
function localStorageSet(k: string, v: string) {
  try { window.localStorage.setItem(k, v); } catch { /* storage unavailable */ }
}
