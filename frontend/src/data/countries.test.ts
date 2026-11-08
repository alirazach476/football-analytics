import { describe, expect, it } from "vitest";
import { abbr, flagCode, isPlaceholder } from "./countries";

describe("country flags", () => {
  it("maps names, variants and home nations to the right flag and never to a wrong one", () => {
    expect(flagCode("Argentina")).toBe("ar"); expect(flagCode("France")).toBe("fr"); expect(flagCode("Germany")).toBe("de");
    expect(flagCode("England")).toBe("gb-eng"); expect(flagCode("Scotland")).toBe("gb-sct"); expect(flagCode("Wales")).toBe("gb-wls"); expect(flagCode("Northern Ireland")).toBe("gb-nir");
    expect(flagCode("Curaçao")).toBe("cw"); expect(flagCode("Curacao")).toBe("cw"); expect(flagCode("USA")).toBe("us"); expect(flagCode("Korea Republic")).toBe("kr"); expect(flagCode("Türkiye")).toBe("tr");
    expect(flagCode("Republic of Ireland")).toBe("ie"); expect(flagCode("Ireland")).toBe("ie"); expect(flagCode("Kosovo")).toBe("xk"); expect(flagCode("DR Congo")).toBe("cd");
  });
  it("gives defunct states and placeholders no flag", () => {
    expect(flagCode("Yugoslavia")).toBeUndefined(); expect(flagCode("Serbia and Montenegro")).toBeUndefined(); expect(flagCode("Winner Group A")).toBeUndefined(); expect(flagCode(undefined)).toBeUndefined();
    ["A1", "Winner Group A", "Runner-up Group B", "3rd Group A/B/C", "Winner Match 37"].forEach((p) => expect(isPlaceholder(p), p).toBe(true));
    expect(isPlaceholder("Argentina")).toBe(false); expect(abbr("South Africa")).toBe("SA"); expect(abbr("France")).toBe("FRA");
  });
});
