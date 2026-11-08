# Entity resolution rules (teams, players)

## Teams (`src/fbplatform/ingest/teams.py`)
Order of rules; the rule used for every alias is stored in `data/processed/team_aliases.csv`.
* **R0 placeholders** (`A1`, `Winner Group A`, `3rd Group A/B/C`, `Winner Match 37`) never become teams (Euro 2028 fixtures keep null team ids until real teams are known).
* **R1 curated alias** table (explicit human decisions, e.g. "Club Atlético de Madrid" = "Atlético Madrid", "Côte d'Ivoire" = "Ivory Coast").
* **R2 exact** equality after normalisation (case, accents, punctuation, country-code suffix).
* **R3** equality after removing generic club-form tokens (fc, cf, ac, afc, ...) **only if the country code agrees**.
* **R4** a club with no country code (StatsBomb-only) joins a club iff the stripped names are equal and exactly one such club exists.
* **No fuzzy merging.** Similar-but-unmerged pairs are listed in `entity_resolution_review.csv` (currently 9, all genuinely different: Australia/Austria, Iran/Iraq, North/South Korea, Slovakia/Slovenia, Serbia/Serbia and Montenegro, AC Milan/Inter, Aston Villa/Sevilla, Leicester/Man City, Man City/Man United).
* Validation: distinct national teams per tournament equal the real participant counts (32/16/24/12/10/16/48).
* Not verified yet: `confederation` (null for all teams), `logo_ref` (null: no licensed crest/flag source chosen).
* `Serbia and Montenegro` (WC 2006) and `Serbia` are kept as separate entities; `AS Monaco` carries two source country codes (FRA, MCO) in `country_codes_seen`.

## Players (`ingest/statsbomb_events.py::build_players`)
* Identity = StatsBomb `player_id` (`P-SB-<id>`). **Names are never used to merge**; there are currently 0 cases of one full name with two ids.
* OpenFootball has only scorer names (no ids), so those goals stay as raw text in `source_records` until a documented, team+season+exact-name rule is added. Players are therefore only registered for StatsBomb-covered matches (WC 2018/22, Euro 2020/24, Copa 2024, 14 Champions League finals).
* Date of birth, height, preferred foot: not present in any verified source yet, so null.


## Squad players -> player registry (`ingest/squads.py::link_and_register`)
* **S1** same tournament + team + shirt number as the Fjelstul squad row (World Cup 2002-2022) AND at least one shared name token.
* **S2** same date of birth AND one name's tokens contained in the other's (or two shared tokens), unique on both sides, against
  every player that has a birth date (Wyscout, Fjelstul, enriched StatsBomb).
* **S3** otherwise the player gets `P-SQ-<hash(team, date of birth)>`: the same national team + birth date across tournaments is one person.
  If two players of a team share a birth date (twins, e.g. Angel and Oscar Romero, Jesus and Jose Sagredo) the hash also includes the
  normalised full name, in every tournament.  Nothing is ever merged on name alone.
* Unused squad members linked by S1 are registered from Fjelstul's player file, so every squad row points at a real registry row.
* Match line-ups from Wikipedia carry names only; they are not linked to ids (the squad table has the shirt-number route for that).


## Venues (`ingest/venues.py`)
* A venue is the Wikipedia article of the stadium named in the match box; redirects are resolved through the API so a renamed stadium is one venue.
  Two different stadiums are never merged by name.
* Fixtures without a box take the stadium of their city from the tournament page's host-venue map, only when exactly one stadium matches
  (a hint such as "London (Tottenham)" must match the stadium name, otherwise the venue stays empty).
* A city page is never accepted as a stadium (the article needs a capacity and coordinates for the name-lookup route; the map route only names stadium links).
