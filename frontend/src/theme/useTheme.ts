import { createContext, useContext, useEffect, useMemo } from "react";
import { useLocation } from "react-router-dom";
import { DEFAULT_THEME, HUB_THEME, Theme, THEMES, cssVars, themeFor } from "./editions";

/** The theme that belongs to the current route: a tournament page uses ITS logo's theme, a competition hub its flagship's, everything else the neutral app theme. */
export function themeForPath(path: string): Theme {
  const t = path.match(/^\/tournament\/([^/]+)/);
  if (t) return themeFor(t[1]);
  if (path.startsWith("/wc-2030")) return THEMES["wc-2030"];
  const c = path.match(/^\/competition\/([^/]+)/);
  if (c) return THEMES[HUB_THEME[c[1].toUpperCase()]] ?? DEFAULT_THEME;
  return DEFAULT_THEME;
}

/** Pages whose theme depends on data (a match page uses its edition's logo theme) set it through this context. */
export const ThemeOverrideCtx = createContext<(key: string | null) => void>(() => {});
export function useThemeOverride(key: string | null | undefined) {
  const set = useContext(ThemeOverrideCtx);
  useEffect(() => { set(key ?? null); return () => set(null); }, [key, set]);
}

export function useRouteTheme(override: string | null = null): Theme {
  const { pathname } = useLocation();
  const theme = useMemo(() => (override ? themeFor(override) : themeForPath(pathname)), [pathname, override]);
  useEffect(() => {
    const root = document.documentElement;
    Object.entries(cssVars(theme)).forEach(([k, v]) => root.style.setProperty(k, v));
    root.style.colorScheme = theme.mode;
    document.body.style.background = theme.bg;
    const link = document.querySelector<HTMLLinkElement>("link[rel=icon]");
    if (link) link.href = theme.key === "app" ? "/logos/fifa.png" : theme.logo;
    document.documentElement.dataset.comp = theme.key === "app" ? "APP" : theme.comp;
    document.title = theme.key === "app" ? "Football Analytics" : `${theme.name} · Football Analytics`;
  }, [theme]);
  return theme;
}
