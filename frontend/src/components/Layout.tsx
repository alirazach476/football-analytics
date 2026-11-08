import { ReactNode, useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { Activity, BarChart3, Bot, Brain, CalendarDays, ChevronDown, Cog, Crosshair, Database, Home, LineChart, Menu, PieChart, Ruler, Shield, Sigma, Target, Trophy, Users, Wrench, X } from "lucide-react";
import { useHealth, useTournaments } from "../api";
import { ThemeOverrideCtx, useRouteTheme } from "../theme/useTheme";
import { THEMES } from "../theme/editions";
import { Callout, cx } from "./ui";
import { BrandLogos } from "./Brand";

const ANALYTICS = [
  ["/analytics/overview", "Overview", Home], ["/analytics/competition", "Competition analysis", Trophy], ["/analytics/teams", "Team analytics", Shield], ["/analytics/players", "Player analytics", Users],
  ["/analytics/matches", "Match analytics", CalendarDays], ["/analytics/ml", "Machine learning", Bot], ["/analytics/engineering", "Data engineering", Wrench],
] as const;
const LAB = [
  ["/lab/competitions", "Competitions", BarChart3], ["/lab/teams", "Teams", LineChart], ["/lab/players", "Players", Target], ["/lab/matches", "Matches", Crosshair],
  ["/lab/statistics", "Statistics", Ruler], ["/lab/ml", "Machine learning", Brain], ["/lab/engineering", "Data engineering", Cog],
] as const;
const COMPS = [["WC", "FIFA World Cup", "wc-2026"], ["EURO", "UEFA Euro", "euro-2024"], ["COPA", "Copa América", "copa-2024"], ["UNL", "UEFA Nations League", "unl"]] as const;

const link = ({ isActive }: { isActive: boolean }) => cx("flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-medium transition", isActive ? "font-semibold" : "hover:bg-white/5");
const linkStyle = (active: boolean) => ({ background: active ? "color-mix(in srgb, var(--c-primary) 16%, transparent)" : undefined, color: active ? "var(--c-primary)" : "var(--c-ink)" });

function NavItem({ to, children, icon }: { to: string; children: ReactNode; icon?: ReactNode }) {
  return <NavLink to={to} className={link} style={({ isActive }) => linkStyle(isActive)}>{icon}<span className="truncate">{children}</span></NavLink>;
}
const Heading = ({ children }: { children: ReactNode }) => <div className="mb-1 mt-5 px-3 text-[11px] font-bold uppercase tracking-[0.16em]" style={{ color: "var(--c-muted)" }}>{children}</div>;

function Sidebar({ onNavigate }: { onNavigate: () => void }) {
  const { data } = useTournaments(); const { pathname } = useLocation();
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => { const m = pathname.match(/^\/tournament\/([^-]+)/); if (m) setOpen(m[1].toUpperCase()); if (pathname.startsWith("/wc-2030")) setOpen("WC"); }, [pathname]);
  const eds = data?.editions ?? [];
  return (
    <nav className="flex h-full flex-col overflow-y-auto px-3 pb-8 pt-4" onClick={(e) => { if ((e.target as HTMLElement).closest("a")) onNavigate(); }} aria-label="Main">
      <NavLink to="/" className="mb-2 block px-2">
        <BrandLogos size={40} />
        <span className="mt-3 block font-display text-base font-bold leading-tight">Football Analytics</span><span className="block text-[11px]" style={{ color: "var(--c-muted)" }}>Men's national-team tournaments</span>
      </NavLink>
      <Heading>Match center</Heading>
      <NavItem to="/fixtures" icon={<CalendarDays size={17} />}>Fixtures &amp; results</NavItem>
      <Heading>Tournaments</Heading>
      {COMPS.map(([id, label, flag]) => {
        const list = eds.filter((e) => e.competition === id); const isOpen = open === id;
        return (
          <div key={id}>
            <div className="flex items-center">
              <NavLink to={`/competition/${id.toLowerCase()}`} className={link} style={({ isActive }) => ({ ...linkStyle(isActive), flex: 1 })}>
                <img src={THEMES[flag].logo} alt="" className="h-6 w-6 rounded object-contain" loading="lazy" /><span className="truncate">{label}</span></NavLink>
              <button className="rounded-lg p-2" aria-label={`${isOpen ? "Hide" : "Show"} ${label} editions`} aria-expanded={isOpen} onClick={(e) => { e.stopPropagation(); setOpen(isOpen ? null : id); }}>
                <ChevronDown size={15} className={isOpen ? "rotate-180 transition" : "transition"} /></button>
            </div>
            {isOpen && <div className="ml-4 mb-1 space-y-0.5 border-l pl-2" style={{ borderColor: "var(--c-border)" }}>
              {id === "WC" && <NavLink to="/wc-2030" className={link} style={({ isActive }) => ({ ...linkStyle(isActive), paddingTop: 5, paddingBottom: 5 })}><img src={THEMES["wc-2030"].logo} alt="" className="h-5 w-5 rounded object-contain" /><span className="truncate text-[13px]">2030</span><span className="chip chip-soon ml-auto !py-0 !text-[10px]">Soon</span></NavLink>}
              {[...list].reverse().map((e) => (
                <NavLink key={e.seasonId} to={`/tournament/${e.slug}`} className={link} style={({ isActive }) => ({ ...linkStyle(isActive), paddingTop: 5, paddingBottom: 5 })}>
                  <img src={THEMES[e.themeKey]?.logo} alt="" className="h-5 w-5 rounded object-contain" loading="lazy" />
                  <span className="truncate text-[13px]">{e.competition === "UNL" ? e.seasonId.replace("UNL-", "") : e.year}</span>
                  {e.status !== "in_data" && <span className="chip chip-soon ml-auto !py-0 !text-[10px]">Soon</span>}
                </NavLink>))}
            </div>}
          </div>
        );
      })}
      <Heading>Analytics</Heading>
      {ANALYTICS.map(([to, label, Icon]) => <NavItem key={to} to={to} icon={<Icon size={17} />}>{label}</NavItem>)}
      <Heading>Visualization lab</Heading>
      {LAB.map(([to, label, Icon]) => <NavItem key={to} to={to} icon={<Icon size={17} />}>{label}</NavItem>)}
      <div className="mt-6 px-3 text-[11px] leading-relaxed" style={{ color: "var(--c-muted)" }}><Database size={12} className="mr-1 inline" />Licensed/open datasets and Wikipedia. Nothing is invented: missing data stays empty; upcoming fixtures say “Coming soon”.</div>
    </nav>
  );
}

export default function Layout({ children }: { children: ReactNode }) {
  const [override, setOverride] = useState<string | null>(null); const theme = useRouteTheme(override); const { pathname } = useLocation(); const [menu, setMenu] = useState(false); const health = useHealth();
  useEffect(() => { window.scrollTo({ top: 0 }); }, [pathname]);
  return (
    <ThemeOverrideCtx.Provider value={setOverride}><div className="min-h-full" style={{ background: "var(--c-bg)", color: "var(--c-ink)" }} data-theme={theme.key}>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-72 border-r lg:block" style={{ background: "linear-gradient(180deg, var(--sidebar-bg), color-mix(in srgb, var(--sidebar-bg) 70%, #000))", borderColor: "color-mix(in srgb, var(--c-primary) 35%, transparent)" }}><Sidebar onNavigate={() => {}} /></aside>
      <header className="sticky top-0 z-20 flex items-center gap-3 border-b px-4 py-3 backdrop-blur lg:hidden" style={{ background: "color-mix(in srgb, var(--c-bg) 88%, transparent)", borderColor: "var(--c-border)" }}>
        <button onClick={() => setMenu(true)} aria-label="Open menu" className="btn !px-2"><Menu size={18} /></button>
        <BrandLogos size={30} /><span className="font-display font-bold">Football Analytics</span>
        <Activity size={16} className="ml-auto" style={{ color: health.data?.ok ? "#22c55e" : "#ef4444" }} aria-label={health.data?.ok ? "warehouse online" : "warehouse offline"} />
      </header>
      {menu && <div className="fixed inset-0 z-40 lg:hidden"><div className="absolute inset-0 bg-black/60" onClick={() => setMenu(false)} />
        <div className="absolute inset-y-0 left-0 w-72" style={{ background: "var(--sidebar-bg)" }}>
          <button className="absolute right-2 top-2 btn !px-2" onClick={() => setMenu(false)} aria-label="Close menu"><X size={16} /></button><Sidebar onNavigate={() => setMenu(false)} /></div></div>}
      <main className="relative overflow-x-clip lg:pl-72">
        {theme.key !== "app" && <div className="pointer-events-none absolute inset-x-0 top-0 h-[900px] overflow-hidden lg:left-72" aria-hidden>
          <div className="absolute inset-0" style={{ background: `radial-gradient(80% 60% at 85% 0%, color-mix(in srgb, ${theme.primary} 30%, transparent), transparent 70%), radial-gradient(60% 50% at 0% 30%, color-mix(in srgb, ${theme.secondary} 22%, transparent), transparent 70%), linear-gradient(180deg, color-mix(in srgb, ${theme.heroFrom} 80%, transparent), transparent)` }} />
          {theme.banner && <img src={theme.banner} alt="" className="absolute inset-0 h-full w-full object-cover opacity-[0.10] blur-md" />}
          <img src={theme.logo} alt="" className="absolute -right-16 top-24 h-[620px] w-[620px] object-contain opacity-[0.07] grayscale-[.2]" />
          <div className={`pattern-${theme.pattern} absolute inset-0 opacity-40`} /><div className="absolute inset-x-0 bottom-0 h-72" style={{ background: "linear-gradient(180deg, transparent, var(--c-bg))" }} />
        </div>}
        <div className="relative mx-auto max-w-[1400px] px-4 py-6 sm:px-8">
        {health.data && !health.data.ok && <Callout tone="warn" title="Warehouse is offline" className="mb-5">{health.data.message}</Callout>}
        {health.isError && <Callout tone="warn" title="API not reachable" className="mb-5">Start the backend: <code>uvicorn fbplatform.api.main:app --port 8000</code> (with PYTHONPATH=src).</Callout>}
        {children}
      </div></main>
    </div></ThemeOverrideCtx.Provider>
  );
}
