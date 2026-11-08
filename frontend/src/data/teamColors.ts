import colors from "./teamColors.json";
import { flagCode } from "./countries";

const MAP = colors as unknown as Record<string, [string, string]>;
/** National identity colours (primary, secondary) for a team; a neutral steel pair when the team is not a recognised country. */
export function teamPalette(name?: string | null, fallback: [string, string] = ["#64748b", "#94a3b8"]): [string, string] {
  const c = flagCode(name);
  return (c && MAP[c]) || fallback;
}
