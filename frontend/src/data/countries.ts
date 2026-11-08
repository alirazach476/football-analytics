// National team name -> ISO 3166-1 alpha-2 code (or the flag-icons subdivision code for the home nations; 'xk' = Kosovo).
// Names are normalised (lower-case, accents and punctuation removed) so historical spellings map to the same country.
// Deliberately ABSENT: 'Serbia and Montenegro' and 'Yugoslavia' (defunct states without an ISO flag asset): they get a neutral badge, never another country's flag.
const RAW: Record<string, string> = {
  Albania: "al", Algeria: "dz", Andorra: "ad", Angola: "ao", Argentina: "ar", Armenia: "am", Australia: "au", Austria: "at", Azerbaijan: "az", Belarus: "by", Belgium: "be", Bolivia: "bo",
  "Bosnia and Herzegovina": "ba", Brazil: "br", Bulgaria: "bg", Cameroon: "cm", Canada: "ca", "Cape Verde": "cv", Chile: "cl", China: "cn", Colombia: "co", "Costa Rica": "cr", Croatia: "hr",
  "Curaçao": "cw", Cyprus: "cy", "Czech Republic": "cz", "DR Congo": "cd", Denmark: "dk", Ecuador: "ec", Egypt: "eg", England: "gb-eng", Estonia: "ee", "Faroe Islands": "fo", Finland: "fi",
  France: "fr", Georgia: "ge", Germany: "de", Ghana: "gh", Gibraltar: "gi", Greece: "gr", Haiti: "ht", Honduras: "hn", Hungary: "hu", Iceland: "is", Iran: "ir", Iraq: "iq", Israel: "il",
  Italy: "it", "Ivory Coast": "ci", Jamaica: "jm", Japan: "jp", Jordan: "jo", Kazakhstan: "kz", Kosovo: "xk", Latvia: "lv", Liechtenstein: "li", Lithuania: "lt", Luxembourg: "lu", Malta: "mt",
  Mexico: "mx", Moldova: "md", Montenegro: "me", Morocco: "ma", Netherlands: "nl", "New Zealand": "nz", Nigeria: "ng", "North Korea": "kp", "North Macedonia": "mk", "Northern Ireland": "gb-nir",
  Norway: "no", Panama: "pa", Paraguay: "py", Peru: "pe", Poland: "pl", Portugal: "pt", Qatar: "qa", "Republic of Ireland": "ie", Romania: "ro", Russia: "ru", "San Marino": "sm",
  "Saudi Arabia": "sa", Scotland: "gb-sct", Senegal: "sn", Serbia: "rs", Slovakia: "sk", Slovenia: "si", "South Africa": "za", "South Korea": "kr", Spain: "es", Sweden: "se", Switzerland: "ch",
  Togo: "tg", "Trinidad and Tobago": "tt", Tunisia: "tn", Turkey: "tr", Ukraine: "ua", "United States": "us", Uruguay: "uy", Uzbekistan: "uz", Venezuela: "ve", Wales: "gb-wls",
};
// spelling variants seen in other sources
const ALIASES: Record<string, string> = {
  USA: "United States", "United States of America": "United States", "Korea Republic": "South Korea", "Republic of Korea": "South Korea", "IR Iran": "Iran", "Türkiye": "Turkey", Turkiye: "Turkey",
  Czechia: "Czech Republic", "Côte d'Ivoire": "Ivory Coast", "Cote d'Ivoire": "Ivory Coast", "Cabo Verde": "Cape Verde", "Congo DR": "DR Congo", "Democratic Republic of the Congo": "DR Congo",
  Ireland: "Republic of Ireland", Holland: "Netherlands", "Bosnia-Herzegovina": "Bosnia and Herzegovina", Curacao: "Curaçao", "Korea DPR": "North Korea", "FYR Macedonia": "North Macedonia", Macedonia: "North Macedonia",
};
export const norm = (s: string) => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]/g, "");
const MAP = new Map<string, string>();
Object.entries(RAW).forEach(([k, v]) => MAP.set(norm(k), v));
Object.entries(ALIASES).forEach(([k, v]) => MAP.set(norm(k), RAW[v]));
export const FLAG_NAMES = Object.keys(RAW);

/** Flag code for a team name, or undefined when the team is not a recognised country (never guesses). */
export const flagCode = (name?: string | null): string | undefined => (name ? MAP.get(norm(name)) : undefined);
/** Bracket/draw placeholders such as 'A1', 'Winner Group A', '3rd Group A/B/C', 'Winner Match 37': teams not decided yet. */
export const isPlaceholder = (name?: string | null) => !!name && /^([A-H][1-4]|(winner|runner-up|loser|3rd)\b.*)$/i.test(name.trim());
export const abbr = (name?: string | null) => {
  if (!name) return "";
  const w = name.replace(/[^\p{L}\s]/gu, "").trim().split(/\s+/);
  return (w.length > 1 ? w.map((x) => x[0]).join("").slice(0, 3) : name.slice(0, 3)).toUpperCase();
};
