// Static data loading. Push data (brief, prices, meta) and pre-built research packs are JSON files in /data.
import { useEffect, useState } from "react";
import type { Brief, Meta, Prices, ResearchPack } from "./types";

const cache = new Map<string, Promise<unknown>>();

function getJson<T>(path: string): Promise<T> {
  if (!cache.has(path)) {
    cache.set(path, fetch(path, { cache: "no-cache" }).then((r) => {
      if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
      return r.json();
    }));
  }
  return cache.get(path) as Promise<T>;
}

export interface Loaded<T> { data: T | null; error: string | null; loading: boolean }

export function useJson<T>(path: string | null): Loaded<T> {
  const [state, set] = useState<Loaded<T>>({ data: null, error: null, loading: !!path });
  useEffect(() => {
    if (!path) return;
    let alive = true;
    set({ data: null, error: null, loading: true });
    getJson<T>(path).then(
      (data) => alive && set({ data, error: null, loading: false }),
      (e: Error) => { cache.delete(path); if (alive) set({ data: null, error: e.message, loading: false }); },
    );
    return () => { alive = false; };
  }, [path]);
  return state;
}

export const useBrief = () => useJson<Brief>("/data/brief.json");
export const usePrices = () => useJson<Prices>("/data/prices.json");
export const useMeta = () => useJson<Meta>("/data/meta.json");
export const useResearch = (symbol: string | null) =>
  useJson<ResearchPack>(symbol ? `/data/research_${symbol.toUpperCase()}.json` : null);

export interface ResearchIndexEntry { symbol: string; name: string; built_at: string | null; mock: boolean }
/** research_index.json lists the pre-built packs. Falls back to the dev mock (LT) when absent. */
export function useResearchIndex(): Loaded<ResearchIndexEntry[]> {
  const idx = useJson<ResearchIndexEntry[]>("/data/research_index.json");
  if (idx.error) return { data: [{ symbol: "LT", name: "Larsen & Toubro", built_at: null, mock: true }], error: null, loading: false };
  return idx;
}
