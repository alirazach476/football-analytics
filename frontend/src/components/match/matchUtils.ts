export interface MatchRow {
  match_key: number; match_date: string; competition_id: string; competition_name?: string; season_id: string; season_year?: number; stage_name: string; group_name?: string | null; matchday?: number | null;
  home_team_name: string; away_team_name: string; home_score?: number | null; away_score?: number | null; home_pen?: number | null; away_pen?: number | null;
  home_score_ht?: number | null; away_score_ht?: number | null; home_score_ft90?: number | null; away_score_ft90?: number | null;
  went_beyond_90?: boolean | null; had_shootout?: boolean | null; shootout_winner_side?: string | null; status_label: string; is_played: boolean; fixture_detail?: string | null;
  venue_name?: string | null; venue_city?: string | null; venue_country?: string | null; referee_name?: string | null; attendance?: number | null; man_of_the_match_raw?: string | null;
}
export type Status = "Scheduled" | "Live" | "Half Time" | "Full Time" | "Extra Time" | "Penalties" | "Postponed" | "Abandoned" | "Cancelled";

/** Match status taken from the data only. Live, Half Time, Postponed etc. appear only if the source label says so; nothing is inferred as live. */
export function statusOf(m: Pick<MatchRow, "is_played" | "status_label" | "went_beyond_90" | "had_shootout">): { status: Status; detail?: string } {
  const l = (m.status_label || "").toLowerCase();
  if (/live|in play/.test(l)) return { status: "Live" };
  if (/half/.test(l)) return { status: "Half Time" };
  if (/postpon/.test(l)) return { status: "Postponed" };
  if (/abandon/.test(l)) return { status: "Abandoned" };
  if (/cancel/.test(l)) return { status: "Cancelled" };
  if (!m.is_played) return { status: "Scheduled" };
  if (m.had_shootout) return { status: "Penalties", detail: "Decided on penalties" };
  if (m.went_beyond_90) return { status: "Extra Time", detail: "After extra time" };
  return { status: "Full Time" };
}
export const fmtMinute = (minute?: number | null, added?: number | null) => (minute == null ? "" : `${Math.round(minute)}${added ? `+${Math.round(added)}` : ""}'`);
export const dateLabel = (d?: string | null, opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", year: "numeric" }) => (d ? new Date(d).toLocaleDateString("en-GB", opts) : "date to be confirmed");
export const compLabel = (m: Pick<MatchRow, "competition_id">) => ({ WC: "FIFA World Cup", EURO: "UEFA Euro", COPA: "Copa América", UNL: "UEFA Nations League", FIN: "Finalissima" } as Record<string, string>)[m.competition_id] ?? m.competition_id;
export const editionLabel = (season: string) => season.replace(/^[A-Z]+-/, "");
export const stageLine = (m: Pick<MatchRow, "stage_name" | "group_name" | "matchday">) => [m.stage_name, m.group_name ? `Group ${m.group_name}` : null, m.matchday ? `Matchday ${m.matchday}` : null].filter(Boolean).join(" · ");
