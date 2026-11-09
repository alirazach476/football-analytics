"""CONMEBOL-UEFA Cup of Champions ("Finalissima"): 2022 and 2026 editions.

A separate, curated section: it is NOT part of the four-competition warehouse, so none of the platform's statistics, models or counts change.
Every value below is stated on the cited pages (Wikipedia 2022 / 2026 Finalissima, read 2026-11-09); the goal minutes and scorers of 2022 also agree with the martj42 results data.
Nothing else is filled in: the 2022 page states no assists, and the 2026 match was cancelled, so it has no result, line-ups or statistics.
Source note: martj42 lists the 2022 match in 'Paris, France'; the Wikipedia match report says Wembley Stadium, London, which is used here.
"""
from __future__ import annotations

COMPETITION = "CONMEBOL–UEFA Cup of Champions (Finalissima)"

SOURCES = {
    "FIN-2022": [
        {"label": "Wikipedia: 2022 Finalissima (match report, line-ups, statistics)", "url": "https://en.wikipedia.org/wiki/2022_Finalissima"},
        {"label": "martj42 international results (score and goal minutes cross-check)", "url": "https://github.com/martj42/international_results"},
    ],
    "FIN-2026": [
        {"label": "Wikipedia: 2026 Finalissima", "url": "https://en.wikipedia.org/wiki/2026_Finalissima"},
        {"label": "CONMEBOL announcement (cited by Wikipedia, not scraped)", "url": "https://copaamerica.com/en/news/argentina-spain-finalissima-men-2026"},
        {"label": "UEFA announcement (cited by Wikipedia, not scraped)", "url": "https://www.uefa.com/news-media/news/02a0-1f77c71b0d1a-ebd6b9d309cb-1000--spain-to-face-argentina-in-men-s-finalissima-2026"},
    ],
}


def _p(team, num, name, pos, starter=True, note=None):
    return dict(team_name=team, player=name, jersey_number=num, is_starter=starter, primary_position=pos, note=note)


ITALY = [_p("Italy", 21, "Gianluigi Donnarumma", "Goalkeeper"), _p("Italy", 2, "Giovanni Di Lorenzo", "Right Back"), _p("Italy", 19, "Leonardo Bonucci", "Center Back"),
         _p("Italy", 3, "Giorgio Chiellini", "Center Back"), _p("Italy", 13, "Emerson Palmieri", "Left Back"), _p("Italy", 8, "Jorginho", "Defensive Midfield"),
         _p("Italy", 12, "Matteo Pessina", "Center Midfield"), _p("Italy", 18, "Nicolò Barella", "Center Midfield"), _p("Italy", 10, "Federico Bernardeschi", "Right Wing"),
         _p("Italy", 9, "Andrea Belotti", "Center Forward"), _p("Italy", 22, "Giacomo Raspadori", "Left Wing"),
         _p("Italy", 6, "Manuel Lazzari", None, False, "on 46'"), _p("Italy", 17, "Gianluca Scamacca", None, False, "on 46'"), _p("Italy", 5, "Manuel Locatelli", None, False, "on 46'"),
         _p("Italy", 4, "Leonardo Spinazzola", None, False, "on 62'"), _p("Italy", 23, "Alessandro Bastoni", None, False, "on 77'")]
ARGENTINA = [_p("Argentina", 23, "Emiliano Martínez", "Goalkeeper"), _p("Argentina", 4, "Nahuel Molina", "Right Back"), _p("Argentina", 13, "Cristian Romero", "Center Back"),
             _p("Argentina", 19, "Nicolás Otamendi", "Center Back"), _p("Argentina", 3, "Nicolás Tagliafico", "Left Back"), _p("Argentina", 18, "Guido Rodríguez", "Defensive Midfield"),
             _p("Argentina", 20, "Giovani Lo Celso", "Center Midfield"), _p("Argentina", 7, "Rodrigo De Paul", "Center Midfield"), _p("Argentina", 10, "Lionel Messi", "Right Wing"),
             _p("Argentina", 22, "Lautaro Martínez", "Center Forward"), _p("Argentina", 11, "Ángel Di María", "Left Wing"),
             _p("Argentina", 14, "Exequiel Palacios", None, False, "on 76'"), _p("Argentina", 6, "Germán Pezzella", None, False, "on 85'"), _p("Argentina", 9, "Julián Álvarez", None, False, "on 85'"),
             _p("Argentina", 15, "Nicolás González", None, False, "on 90+1'"), _p("Argentina", 21, "Paulo Dybala", None, False, "on 90+1'")]


def _ev(minute, added, kind, team, side, player, detail=None, scoring_side=None):
    return dict(minute=minute, minute_added=added, kind=kind, detail_type=detail, card=None, team_name=team, player=player, other_player=None, assist=None, side=side, scoring_side=scoring_side or side)


TIMELINE_2022 = [
    _ev(22, None, "Card: Yellow Card", "Argentina", "away", "Nicolás Otamendi"),
    _ev(28, None, "Goal", "Argentina", "away", "Lautaro Martínez"),
    _ev(39, None, "Card: Yellow Card", "Italy", "home", "Leonardo Bonucci"),
    _ev(45, 1, "Goal", "Argentina", "away", "Ángel Di María"),
    _ev(46, None, "Substitution", "Italy", "home", "Manuel Lazzari"), _ev(46, None, "Substitution", "Italy", "home", "Gianluca Scamacca"), _ev(46, None, "Substitution", "Italy", "home", "Manuel Locatelli"),
    _ev(62, None, "Substitution", "Italy", "home", "Leonardo Spinazzola"),
    _ev(72, None, "Card: Yellow Card", "Italy", "home", "Giovanni Di Lorenzo"),
    _ev(76, None, "Substitution", "Argentina", "away", "Exequiel Palacios"),
    _ev(77, None, "Card: Yellow Card", "Italy", "home", "Nicolò Barella"),
    _ev(77, None, "Substitution", "Italy", "home", "Alessandro Bastoni"),
    _ev(85, None, "Substitution", "Argentina", "away", "Germán Pezzella"), _ev(85, None, "Substitution", "Argentina", "away", "Julián Álvarez"),
    _ev(90, 1, "Substitution", "Argentina", "away", "Nicolás González"), _ev(90, 1, "Substitution", "Argentina", "away", "Paulo Dybala"),
    _ev(90, 4, "Goal", "Argentina", "away", "Paulo Dybala"),
]

# Wikipedia match-statistics table (Italy, Argentina). Percentages are fractions; every metric listed on the page is shown, nothing else.
STATS_2022 = [
    {"team_name": "Italy", "possession": 0.45, "shots": 7, "shots_on_target": 3, "saves": 6, "corners_taken": 3, "fouls_committed": 13, "offsides": 3, "yellow_cards": 3, "red_cards": 0},
    {"team_name": "Argentina", "possession": 0.55, "shots": 17, "shots_on_target": 9, "saves": 3, "corners_taken": 4, "fouls_committed": 16, "offsides": 0, "yellow_cards": 1, "red_cards": 0},
]

EDITIONS = {
    "FIN-2022": dict(
        seasonId="FIN-2022", slug="fin-2022", themeKey="fin-2022", competition="FIN", competitionName=COMPETITION, edition="2022 Finalissima", year=2022, host="England (Wembley Stadium, London)",
        start="2022-06-01", end="2022-06-01", teams=2, format="One match: UEFA Euro 2020 winners v Copa América 2021 winners", status="in_data", matchesPlayed=1, matchesComingSoon=0,
        champion="Argentina", runnerUp="Italy", verification="sourced (Wikipedia, martj42)", cancelled=False,
        match=dict(match_key=None, competition_id="FIN", season_id="FIN-2022", season_year=2022, match_date="2022-06-01", stage_name="Final", group_name=None, matchday=None,
                   home_team_name="Italy", away_team_name="Argentina", home_score=0, away_score=3, home_pen=None, away_pen=None, home_score_ht=0, away_score_ht=2, home_score_ft90=0, away_score_ft90=3,
                   went_beyond_90=False, had_shootout=False, shootout_winner_side=None, status_label="Full time", is_played=True, fixture_detail=None,
                   venue_name="Wembley Stadium", venue_city="London", venue_country="England", referee_name="Piero Maza (Chile)", attendance=87112, man_of_the_match_raw="Lionel Messi (Argentina)"),
        kickoff="19:45 BST",
        officials={"Referee": "Piero Maza (Chile)", "Assistant referees": "Christian Schiemann and Claudio Ríos (Chile)", "Fourth official": "Jesús Gil Manzano (Spain)", "VAR": "Alejandro Hernández Hernández (Spain)",
                   "Assistant VARs": "Juan Martínez Munuera (Spain) and Tiago Martins (Portugal)"},
        managers={"home": dict(name="Roberto Mancini", source="wikipedia_match", level="match"), "away": dict(name="Lionel Scaloni", source="wikipedia_match", level="match")},
        timeline=TIMELINE_2022, teamStats=STATS_2022, lineups=ITALY + ARGENTINA, sources=SOURCES["FIN-2022"],
        notes=["Goals: Lautaro Martínez 28', Ángel Di María 45+1', Paulo Dybala 90+4'. The match report states no assists, so none are shown.",
               "Half-time score 0–2 follows from the two first-half goals. Substitution pairings are not given in the source, so only the players who came on are listed.",
               "Positions are as printed in the line-up table (RF/CF/LF are shown as right wing, centre forward, left wing); left-right order of the two centre-backs and two midfielders is not recorded."]),
    "FIN-2026": dict(
        seasonId="FIN-2026", slug="fin-2026", themeKey="fin-2026", competition="FIN", competitionName=COMPETITION, edition="2026 Finalissima", year=2026, host="Qatar (Lusail Stadium, Lusail) — cancelled",
        start="2026-03-27", end="2026-03-27", teams=2, format="One match: UEFA Euro 2024 winners v Copa América 2024 winners", status="cancelled", matchesPlayed=0, matchesComingSoon=0,
        champion=None, runnerUp=None, verification="sourced (Wikipedia)", cancelled=True,
        match=dict(match_key=None, competition_id="FIN", season_id="FIN-2026", season_year=2026, match_date="2026-03-27", stage_name="Final", group_name=None, matchday=None,
                   home_team_name="Spain", away_team_name="Argentina", home_score=None, away_score=None, home_pen=None, away_pen=None, home_score_ht=None, away_score_ht=None, went_beyond_90=None,
                   had_shootout=None, shootout_winner_side=None, status_label="Cancelled", is_played=False,
                   fixture_detail="Cancelled by UEFA on 15 March 2026 because of the security situation in Qatar; the two sides could not agree on another venue. No replacement date.",
                   venue_name="Lusail Stadium", venue_city="Lusail", venue_country="Qatar", referee_name=None, attendance=None, man_of_the_match_raw=None),
        kickoff=None, officials={}, managers={}, timeline=[], teamStats=[], lineups=[], sources=SOURCES["FIN-2026"],
        notes=["Teams: Spain (UEFA Euro 2024 winners) and Argentina (2024 Copa América winners and 2022 Finalissima holders).",
               "UEFA announced the cancellation on 15 March 2026. The stated reason was the security situation in Qatar, and the sides could not agree on a different stadium (the Bernabéu and the Monumental were each proposed).",
               "The match was not rescheduled or replaced. The two teams later met in the 2026 FIFA World Cup final (19 July 2026, MetLife Stadium), a different competition: see the World Cup 2026 page."]),
}


def catalogue_entries() -> list[dict]:
    keys = ("seasonId", "slug", "themeKey", "competition", "competitionName", "edition", "year", "host", "start", "end", "teams", "format", "verification", "status", "matchesPlayed", "matchesComingSoon", "champion", "runnerUp")
    return [{k: e[k] for k in keys} for e in EDITIONS.values()]


def edition(season_id: str) -> dict | None:
    return EDITIONS.get(season_id.upper())
