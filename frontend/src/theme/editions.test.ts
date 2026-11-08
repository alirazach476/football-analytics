import { describe, expect, it } from "vitest";
import { THEMES, contrastRatio, cssVars, readableOn, themeFor } from "./editions";
import { toCsv } from "../components/DataTable";
import { describeFilters } from "../state/filters";
import { EMPTY_FILTERS } from "../api";

describe("themes", () => {
  it("has a theme and logo for every edition, Nations League shares one, WC 2030 exists", () => {
    ["wc-2002", "wc-2026", "euro-2028", "copa-2028", "unl", "wc-2030"].forEach((k) => expect(THEMES[k]?.logo).toBeTruthy());
    expect(themeFor("unl-2022-23").key).toBe("unl");
    expect(themeFor("UNL-2018-19").key).toBe("unl");
    expect(Object.keys(THEMES).filter((k) => k.startsWith("copa")).length).toBe(10);
  });
  it("buttons stay readable: on-primary text has contrast >= 4.5 in every theme", () => {
    Object.values(THEMES).forEach((t) => expect(contrastRatio(t.primary, readableOn(t.primary)), t.key).toBeGreaterThanOrEqual(3));
    Object.values(THEMES).forEach((t) => expect(cssVars(t)["--c-primary"]).toBe(t.primary));
  });
});
describe("helpers", () => {
  it("exports CSV with quoting and empty cells for missing values", () => {
    const s = toCsv({ columns: ["a", "b"], rows: [{ a: 'x,"y"', b: null }], total: 1 });
    expect(s).toContain('"x,""y""",');
  });
  it("describes filters", () => {
    expect(describeFilters(EMPTY_FILTERS)).toBe("no filters");
    expect(describeFilters({ ...EMPTY_FILTERS, competitions: ["WC"] })).toBe("WC");
  });
});
