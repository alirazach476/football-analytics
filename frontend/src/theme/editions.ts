// One visual theme per tournament edition, derived from its logo (colours extracted from the artwork, then curated) and its banner art.
// The Nations League has ONE logo, so all its editions share the 'unl' theme. 'wc-2030' is the coming-soon page.
import auto from "../data/themes.auto.json";

export type Mode = "light" | "dark";
export interface Theme {
  key: string;
  name: string;
  comp: "WC" | "EURO" | "COPA" | "UNL" | "FIN";
  mode: Mode;
  primary: string;
  secondary: string;
  accent: string;
  bg: string; // page background
  heroFrom: string;
  heroTo: string;
  pattern: "dots" | "stripes" | "rings" | "waves" | "grid" | "flags";
  tagline: string;
  logo: string;
  banner?: string | null;
}

type Def = Omit<Theme, "key" | "logo" | "banner" | "name" | "comp"> & { name: string };
const D: Record<string, Def> = {
  "wc-2002": { name: "FIFA World Cup 2002", mode: "light", primary: "#c8102e", secondary: "#c9a227", accent: "#0a5399", bg: "#fff8ee", heroFrom: "#b3261e", heroTo: "#c9a227", pattern: "rings", tagline: "Korea · Japan — the first World Cup in Asia" },
  "wc-2006": { name: "FIFA World Cup 2006", mode: "dark", primary: "#2fb36a", secondary: "#2f86d6", accent: "#f08a3c", bg: "#0a0d10", heroFrom: "#0a2540", heroTo: "#14532d", pattern: "dots", tagline: "Germany — a time to make friends" },
  "wc-2010": { name: "FIFA World Cup 2010", mode: "light", primary: "#e8590c", secondary: "#074a96", accent: "#f5b700", bg: "#fff6ee", heroFrom: "#d9480f", heroTo: "#7a1d00", pattern: "stripes", tagline: "South Africa — Ke Nako, it is time" },
  "wc-2014": { name: "FIFA World Cup 2014", mode: "light", primary: "#2f7d32", secondary: "#f2b705", accent: "#00386a", bg: "#f6fbef", heroFrom: "#2f7d32", heroTo: "#f2b705", pattern: "waves", tagline: "Brasil — all in one rhythm" },
  "wc-2018": { name: "FIFA World Cup 2018", mode: "dark", primary: "#e0242b", secondary: "#e5c48b", accent: "#2b9bd6", bg: "#0a1230", heroFrom: "#0b2a6b", heroTo: "#8a1020", pattern: "flags", tagline: "Russia — football unites" },
  "wc-2022": { name: "FIFA World Cup 2022", mode: "dark", primary: "#b8174a", secondary: "#e8c3a4", accent: "#f0a35e", bg: "#1a0912", heroFrom: "#4a0d25", heroTo: "#b8174a", pattern: "waves", tagline: "Qatar — the first World Cup in the Arab world" },
  "wc-2026": { name: "FIFA World Cup 2026", mode: "dark", primary: "#d9b45a", secondary: "#e63946", accent: "#3a86ff", bg: "#09090b", heroFrom: "#111827", heroTo: "#4c1d95", pattern: "stripes", tagline: "Canada · Mexico · United States — 48 teams, 104 matches" },
  "euro-2000": { name: "UEFA Euro 2000", mode: "light", primary: "#0a7cc4", secondary: "#ee3430", accent: "#111827", bg: "#f2f8fc", heroFrom: "#0a4d80", heroTo: "#ee3430", pattern: "waves", tagline: "Belgium · Netherlands — the first Euro hosted by two nations" },
  "euro-2004": { name: "UEFA Euro 2004", mode: "dark", primary: "#f37121", secondary: "#00ae68", accent: "#f4c542", bg: "#0e0905", heroFrom: "#3a1a06", heroTo: "#f37121", pattern: "rings", tagline: "Portugal — the heart of the tournament" },
  "euro-2008": { name: "UEFA Euro 2008", mode: "dark", primary: "#ee1c1d", secondary: "#3a8d3f", accent: "#9fb4c8", bg: "#061a3d", heroFrom: "#06265a", heroTo: "#b30f10", pattern: "waves", tagline: "Austria · Switzerland — expect emotions" },
  "euro-2012": { name: "UEFA Euro 2012", mode: "dark", primary: "#e0a526", secondary: "#c0392b", accent: "#2aa4d6", bg: "#1b0b24", heroFrom: "#3b0f4d", heroTo: "#7a1f3d", pattern: "dots", tagline: "Poland · Ukraine — creating history together" },
  "euro-2016": { name: "UEFA Euro 2016", mode: "dark", primary: "#e0262c", secondary: "#2e7fc0", accent: "#f2f4f8", bg: "#061b3d", heroFrom: "#042d60", heroTo: "#0d5aa7", pattern: "grid", tagline: "France — le rendez-vous" },
  "euro-2020": { name: "UEFA Euro 2020", mode: "light", primary: "#0a8aa3", secondary: "#f08a24", accent: "#a7c639", bg: "#f0fafb", heroFrom: "#0a6f86", heroTo: "#2dc0d8", pattern: "flags", tagline: "Played in 2021 — across Europe" },
  "euro-2024": { name: "UEFA Euro 2024", mode: "dark", primary: "#2d7be0", secondary: "#e5262a", accent: "#ffd23f", bg: "#071a3a", heroFrom: "#0a2a63", heroTo: "#1d4ed8", pattern: "stripes", tagline: "Germany — United by football. Vereint im Herzen Europas." },
  "euro-2028": { name: "UEFA Euro 2028", mode: "dark", primary: "#4f46e5", secondary: "#10d98a", accent: "#ff3d6b", bg: "#0b0636", heroFrom: "#1d0a8f", heroTo: "#3b1fd1", pattern: "stripes", tagline: "UK & Ireland — coming soon" },
  "copa-2001": { name: "Copa América 2001", mode: "light", primary: "#433c80", secondary: "#f6c90e", accent: "#e32219", bg: "#faf8ff", heroFrom: "#433c80", heroTo: "#e8b90b", pattern: "rings", tagline: "Colombia" },
  "copa-2004": { name: "Copa América 2004", mode: "light", primary: "#d6001c", secondary: "#0074b6", accent: "#f2f2f2", bg: "#fff6f6", heroFrom: "#b30016", heroTo: "#e2001a", pattern: "stripes", tagline: "Perú — América unida por su pasión" },
  "copa-2007": { name: "Copa América 2007", mode: "light", primary: "#d11f26", secondary: "#035299", accent: "#ffd400", bg: "#fffbea", heroFrom: "#ffcd00", heroTo: "#d11f26", pattern: "flags", tagline: "Venezuela" },
  "copa-2011": { name: "Copa América 2011", mode: "light", primary: "#0693cf", secondary: "#f0b41c", accent: "#8cc6e8", bg: "#f2faff", heroFrom: "#0693cf", heroTo: "#7cc4ea", pattern: "waves", tagline: "Argentina" },
  "copa-2015": { name: "Copa América 2015", mode: "light", primary: "#0b3d86", secondary: "#c4161c", accent: "#2bb3c0", bg: "#f5f8ff", heroFrom: "#0b3d86", heroTo: "#c4161c", pattern: "grid", tagline: "Chile" },
  "copa-2016": { name: "Copa América Centenario 2016", mode: "dark", primary: "#d9ad3a", secondary: "#c02025", accent: "#2f6fb5", bg: "#08101f", heroFrom: "#0c1f44", heroTo: "#5b1020", pattern: "rings", tagline: "USA — 100 years of the Copa, 1916-2016" },
  "copa-2019": { name: "Copa América 2019", mode: "dark", primary: "#7cb518", secondary: "#f5c400", accent: "#2e6fe0", bg: "#041238", heroFrom: "#022a7b", heroTo: "#2a7a1c", pattern: "waves", tagline: "Brasil" },
  "copa-2021": { name: "Copa América 2021", mode: "dark", primary: "#2e6fd0", secondary: "#fcc933", accent: "#e23a3e", bg: "#0a1648", heroFrom: "#0b1f6b", heroTo: "#1d4aa8", pattern: "flags", tagline: "Played in Brasil" },
  "copa-2024": { name: "Copa América 2024", mode: "dark", primary: "#1a6df0", secondary: "#ff3030", accent: "#9cc2ff", bg: "#06194a", heroFrom: "#06226e", heroTo: "#1a56db", pattern: "stripes", tagline: "USA" },
  "copa-2028": { name: "Copa América 2028", mode: "light", primary: "#0d3b9a", secondary: "#d62c20", accent: "#5a8fd0", bg: "#f4f7ff", heroFrom: "#0d3b9a", heroTo: "#3e7fd6", pattern: "waves", tagline: "Paraguay — announced" },
  unl: { name: "UEFA Nations League", mode: "dark", primary: "#2d7fd6", secondary: "#e24a3a", accent: "#f2c230", bg: "#0b1626", heroFrom: "#13243d", heroTo: "#274a7a", pattern: "flags", tagline: "Every edition, one identity" },
  "fin-2022": { name: "Finalissima 2022", mode: "dark", primary: "#e0b33a", secondary: "#6cb4ee", accent: "#e0323f", bg: "#02021f", heroFrom: "#000032", heroTo: "#14146e", pattern: "rings", tagline: "Italy v Argentina · Wembley · 1 June 2022 — the CONMEBOL–UEFA Cup of Champions" },
  "fin-2026": { name: "Finalissima 2026", mode: "dark", primary: "#e5393f", secondary: "#f2b705", accent: "#75b2f0", bg: "#02021f", heroFrom: "#000032", heroTo: "#2a1040", pattern: "rings", tagline: "Spain v Argentina · Lusail, Qatar — cancelled on 15 March 2026" },
  "wc-2030": { name: "FIFA World Cup 2030", mode: "light", primary: "#e20814", secondary: "#08a74d", accent: "#f6c500", bg: "#fffdf5", heroFrom: "#fff3c4", heroTo: "#ffd7d9", pattern: "rings", tagline: "Yalla Vamos · Morocco · Portugal · Spain — coming soon" },
};

const COMP: Record<string, Theme["comp"]> = { wc: "WC", euro: "EURO", copa: "COPA", unl: "UNL", fin: "FIN" };
export const THEMES: Record<string, Theme> = Object.fromEntries(
  Object.entries(D).map(([key, d]) => {
    const a = (auto as Record<string, { logo: string; banner: string | null }>)[key];
    return [key, { key, comp: COMP[key.split("-")[0]], ...d, logo: a?.logo ?? `/logos/${key}.png`, banner: a?.banner ?? null } as Theme];
  }),
);

export const HUB_THEME: Record<string, string> = { WC: "wc-2026", EURO: "euro-2024", COPA: "copa-2024", UNL: "unl", FIN: "fin-2022" };
export const DEFAULT_THEME: Theme = { ...THEMES["wc-2026"], key: "app", name: "Football Analytics", mode: "dark", primary: "#38bdf8", secondary: "#a78bfa", accent: "#f472b6", bg: "#070b14", heroFrom: "#0b1226", heroTo: "#1e1b4b", pattern: "grid", banner: null, tagline: "World Cup · Euro · Copa América · Nations League" };

const hexToRgb = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
export function luminance(hex: string): number {
  const f = (x: number) => ((x /= 255) <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4);
  const [r, g, b] = hexToRgb(hex).map(f);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
export const contrastRatio = (a: string, b: string) => { const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
export const readableOn = (bg: string) => (contrastRatio("#ffffff", bg) >= contrastRatio("#0b0b0b", bg) ? "#ffffff" : "#0b0b0b");

const STYLE: Record<string, { font: string; r: string; clip: string; skew: string }> = {
  WC: { font: '"Oswald"', r: "6px", clip: "polygon(0 0, 100% 0, 100% 100%, 3% 100%, 0 94%)", skew: "-14deg" },
  EURO: { font: '"Barlow Condensed"', r: "26px", clip: "none", skew: "0deg" },
  COPA: { font: '"Bebas Neue"', r: "14px", clip: "polygon(0 0, 100% 0, 100% 94%, 97% 100%, 3% 100%, 0 94%)", skew: "-10deg" },
  UNL: { font: '"Barlow Condensed"', r: "10px", clip: "polygon(0 0, 100% 0, 100% 100%, 0 100%)", skew: "-8deg" },
  FIN: { font: '"Oswald"', r: "12px", clip: "polygon(0 0, 100% 0, 100% 100%, 0 100%)", skew: "-10deg" },
  APP: { font: '"Oswald"', r: "16px", clip: "none", skew: "0deg" },
};
export const styleOf = (t: Theme) => STYLE[t.key === "app" ? "APP" : t.comp] ?? STYLE.APP;

export function cssVars(t: Theme): Record<string, string> {
  const dark = t.mode === "dark"; const st = styleOf(t);
  return {
    "--font-display": `${st.font}, "Inter Variable", system-ui, sans-serif`, "--r": st.r, "--hero-clip": st.clip, "--tab-skew": st.skew,
    "--sidebar-bg": `color-mix(in srgb, ${t.heroFrom} ${dark ? 38 : 22}%, ${dark ? "#0b0f1a" : "#ffffff"})`,
    "--c-primary": t.primary, "--c-secondary": t.secondary, "--c-accent": t.accent, "--c-bg": t.bg,
    "--c-surface": dark ? "rgba(255,255,255,0.06)" : "#ffffff", "--c-surface-solid": dark ? "#12182a" : "#ffffff",
    "--c-ink": dark ? "#f4f6fb" : "#0f172a", "--c-muted": dark ? "#a7b3c7" : "#5b6578", "--c-border": dark ? "rgba(255,255,255,0.12)" : "rgba(15,23,42,0.10)",
    "--c-hero-from": t.heroFrom, "--c-hero-to": t.heroTo, "--c-on-primary": readableOn(t.primary), "--c-on-secondary": readableOn(t.secondary),
  };
}

export const themeFor = (seasonOrKey: string): Theme => {
  const k = seasonOrKey.toLowerCase();
  return THEMES[k.startsWith("unl") ? "unl" : k] ?? DEFAULT_THEME;
};
