import { useCallback, useEffect, useState } from "react";
import type { BriefItem } from "./lib/types";
import { useBrief, useMeta, usePrices, useResearchIndex } from "./lib/data";
import { loadPrefs, savePrefs, toggleSeenIds, type Prefs } from "./lib/rules";
import { BriefPage } from "./pages/Brief";
import { PortfolioPage } from "./pages/Portfolio";
import { ResearchPage } from "./pages/Research";
import { RulesPage } from "./pages/Rules";
import { DetailSheet } from "./components/DetailSheet";

type Route = { page: "brief" | "portfolio" | "research" | "rules"; symbol: string | null; params: URLSearchParams };

function parse(hash: string): Route {
  const [path, query = ""] = hash.replace(/^#\/?/, "").split("?");
  const [page, symbol] = path.split("/");
  const params = new URLSearchParams(query);
  const p = (["brief", "portfolio", "research", "rules"] as const).find((x) => x === page) ?? "brief";
  return { page: p, symbol: symbol ? decodeURIComponent(symbol).toUpperCase() : params.get("s"), params };
}

function useRoute(): Route {
  const [r, set] = useState(() => parse(location.hash));
  useEffect(() => {
    const on = () => { set(parse(location.hash)); window.scrollTo(0, 0); };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return r;
}

const ICONS = {
  brief: <path d="M4 5h16M4 10h16M4 15h10M4 20h7" />,
  portfolio: <path d="M3 17l5-5 4 4 8-8M15 8h5v5" />,
  research: <><circle cx="10.5" cy="10.5" r="6" /><path d="M15 15l5 5" /></>,
  rules: <path d="M4 7h10M18 7h2M4 17h4M12 17h8M14 4v6M8 14v6" />,
};

export default function App() {
  const route = useRoute();
  const brief = useBrief(), prices = usePrices(), meta = useMeta(), index = useResearchIndex();
  const [prefs, setPrefsState] = useState<Prefs>(loadPrefs);
  const [open, setOpen] = useState<BriefItem | null>(null);
  useEffect(() => setOpen(null), [route]);            // any navigation (incl. back button) closes the sheet
  const setPrefs = useCallback((p: Prefs) => { setPrefsState(p); savePrefs(p); }, []);
  const toggleSeen = useCallback((id: string) => setPrefs({ ...prefs, seen: toggleSeenIds(prefs.seen, id) }), [prefs, setPrefs]);
  const seenAll = useCallback((ids: string[]) => setPrefs({ ...prefs, seen: [...new Set([...prefs.seen, ...ids])] }), [prefs, setPrefs]);
  const now = meta.data?.generated_at ?? brief.data?.generated_at ?? new Date().toISOString();
  const researchable = new Set((index.data ?? []).map((e) => e.symbol));

  let body: JSX.Element;
  if (brief.error && route.page === "brief") body = <div className="empty" style={{ marginTop: 24 }}><b>Couldn't load the brief.</b> {brief.error}</div>;
  else if (route.page === "brief") body = brief.data ? (
    <BriefPage brief={brief.data} prices={prices.data} meta={meta.data} prefs={prefs} symbol={route.symbol} onOpen={setOpen}
               onSeen={toggleSeen} onSeenAll={seenAll} />
  ) : <div className="loading">Loading brief…</div>;
  else if (route.page === "portfolio") body = prices.data
    ? <PortfolioPage prices={prices.data} brief={brief.data} prefs={prefs} /> : <div className="loading">Loading prices…</div>;
  else if (route.page === "research") body = (
    <ResearchPage symbol={route.symbol} tab={route.params.get("q") === "promises" ? "promises" : "snapshot"}
                  allSymbols={Object.keys(prices.data?.symbols ?? {})} />
  );
  else body = <RulesPage prefs={prefs} setPrefs={setPrefs} prices={prices.data} brief={brief.data} now={now} />;

  return (
    <>
      <main className="app">{body}</main>
      {open && <DetailSheet item={open} prices={prices.data} now={now} researchable={researchable.has(open.symbol)}
                            onClose={() => setOpen(null)} seen={prefs.seen.includes(open.id)} onToggleSeen={toggleSeen} />}
      <nav className="nav" aria-label="Main">
        <div className="nav__inner">
          {(["brief", "portfolio", "research", "rules"] as const).map((p) => (
            <a key={p} href={`#/${p}`} aria-current={route.page === p ? "page" : undefined}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{ICONS[p]}</svg>
              {p[0].toUpperCase() + p.slice(1)}
            </a>
          ))}
        </div>
      </nav>
    </>
  );
}
