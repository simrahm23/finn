// Number and date formatting. Indian grouping (1,23,456), crore units, IST times.

export function crore(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  const abs = Math.abs(v);
  const s = abs >= 1000 ? Math.round(v).toLocaleString("en-IN") : v.toLocaleString("en-IN", { maximumFractionDigits: 1 });
  return s;
}

export function pct(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

export function signClass(v: number | null | undefined): string {
  if (v === null || v === undefined || v === 0) return "";
  return v > 0 ? "up" : "down";
}

export function price(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return v.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const IST = { timeZone: "Asia/Kolkata" } as const;

/** 'Fri 17:40' within the week of `now`, else '24 Oct'. */
export function when(iso: string, now?: string): string {
  const d = new Date(iso);
  const ref = now ? new Date(now) : new Date();
  const days = (ref.getTime() - d.getTime()) / 86400_000;
  if (days < 6) {
    const wd = d.toLocaleDateString("en-IN", { ...IST, weekday: "short" });
    const t = d.toLocaleTimeString("en-IN", { ...IST, hour: "2-digit", minute: "2-digit", hour12: false });
    return `${wd} ${t}`;
  }
  return d.toLocaleDateString("en-IN", { ...IST, day: "numeric", month: "short" });
}

export function dayLabel(isoDate: string): string {
  return new Date(`${isoDate}T12:00:00+05:30`).toLocaleDateString("en-IN", { ...IST, weekday: "short", day: "numeric", month: "short" });
}

/** Strip the exchange's boilerplate so headlines read like headlines. */
export function cleanHeadline(h: string, company: string): string {
  let s = h
    .replace(/^.*?has (informed|submitted to) the Exchange (regarding|about|that|,)?\s*/i, "")
    .replace(/^(the )?Exchange (regarding|about)\s*/i, "")
    .replace(/^In continuation of our letter dated [^,]+,\s*/i, "")
    .replace(/^we wish to inform you that\s*/i, "")
    .replace(/\s+/g, " ")
    .trim();
  if (company && s.toLowerCase().startsWith(company.toLowerCase())) s = s.slice(company.length).trim();
  s = s.replace(/^['"‘’]+|['"‘’.]+$/g, "");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function pdfLink(url: string, page?: number | null): string {
  return page ? `${url}#page=${page}` : url;
}
