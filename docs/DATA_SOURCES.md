# Data sources

Each source was checked individually (`data/audit/source_coverage_matrix.csv`). The rules: use only sources whose licence/terms allow it, respect rate limits and robots, never bypass access restrictions, keep provenance for every record.

## Used

| Source | Licence / basis | Used for | Attribution |
|---|---|---|---|
| **OpenFootball** (football.json / Football.TXT) | CC0 | WC 2002–26, Euro 2004–28, Copa 2011/21/24 matches; goal lines | – |
| **martj42/international_results** | CC0 | Copa 2004–19 and all Nations League matches; scorers and assist names; shoot-out winners; cross-check of every other match | – |
| **Fjelstul World Cup Database** v1.2.0 | CC BY-SA 4.0 | WC goals, cards, substitutions, line-ups, referees, shoot-outs, date of birth | Fjelstul, J. C. (2023). *The Fjelstul World Cup Database v.1.2.0* |
| **StatsBomb Open Data** | attribution required | full events with coordinates, line-ups, xG (WC 2018/22, Euro 2020/24, Copa 2024) | "Data provided by StatsBomb" |
| **Wyscout public dataset** | CC BY 4.0 | Euro 2016 full events; player date of birth/height/foot | Pappalardo et al. (2019), *Scientific Data* |
| **Wikipedia** (en + es) via the official MediaWiki API | CC BY-SA 4.0 | stage, group, referee, attendance, stadium; squads; match-detail sections (line-ups, cards, substitutions, managers, man of the match); award pages; third source for dates/scores | Wikipedia contributors; page title and revision id stored per row |

Wikipedia, martj42 and the Spanish Wikipedia are **secondary/community** sources: everything they supply is labelled, fill-null only, and cross-checked; disagreements go to `data/quality/` and are never silently resolved.

## Not used (and why)

| Source | Reason |
|---|---|
| FIFA.com | terms prohibit automated collection (clause 6.6) |
| UEFA.com | terms prohibit automated collection (clause 6.2) |
| CONMEBOL | no verifiable permission |
| Forza Football | blocks automated clients (HTTP 403) |
| Google results pages | robots `Disallow: /search` and terms |
| football-data.org | needs a free API key; none configured (it would add an independent check on scores) |
| GitHub datasets without a licence, or derived from FIFA.com | cannot be redistributed/used safely |

## Provenance in the data

Every match row carries `primary_provider`, `source_url` (a line number for text sources) and `retrieval_timestamp`. Event, line-up and squad rows carry `provider`; enrichments carry their own source columns (`assist_source`, `player_id_source`, `minutes_basis`, `attendance_source`, `shootout_winner_source`). Bronze registers every raw file with SHA-256 so any figure can be traced back to a file version.

## Licence notes for redistribution

CC0 sources have no conditions. CC BY / CC BY-SA sources (Fjelstul, Wyscout, Wikipedia) require attribution and share-alike for derived datasets. StatsBomb requires attribution. This repository's derived data inherits those conditions.
