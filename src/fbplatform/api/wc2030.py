"""FIFA World Cup 2030: static facts for the 'coming soon' page. Every item carries its status; nothing unconfirmed is presented as settled.
Facts come from the pages listed in SOURCES (retrieved 2026-11-06): FIFA, Wikipedia, Al Jazeera, Sky Sports, plus press coverage of the March 2024 bid identity.
This tournament is NOT in the dataset: no matches, no results."""

SOURCES = [
    {"label": "FIFA: 2030 FIFA World Cup", "url": "https://www.fifa.com/en/tournaments/mens/worldcup/2030"},
    {"label": "FIFA: who are the hosts and who has qualified", "url": "https://www.fifa.com/en/articles/world-cup-2030-hosts-qualified-bidding-spain-argentina-morocco-uruguay-portugal-paraguay"},
    {"label": "Wikipedia: 2030 FIFA World Cup", "url": "https://en.wikipedia.org/wiki/2030_FIFA_World_Cup"},
    {"label": "Al Jazeera: when is the next World Cup (2030 hosts, dates and format)", "url": "https://www.aljazeera.com/news/2026/7/19/when-is-the-next-fifa-world-cup-2030-hosts-dates-and-format"},
    {"label": "Sky Sports: World Cup 2030 dates, schedule, hosts, stadiums and qualification", "url": "https://www.skysports.com/football/news/13565160/world-cup-2030-dates-schedule-hosts-stadiums-and-how-qualification-works"},
    {"label": "Yabiladi: 'YallaVamos 2030' bid slogan and visual identity", "url": "https://en.yabiladi.com/articles/details/147877/yallavamos-2030-morocco-portugal-spain.html"},
]

FACTS = {
    "status": "COMING SOON",
    "title": "FIFA World Cup 2030",
    "edition": "24th FIFA World Cup",
    "tagline": "Yalla Vamos 2030 · For Football. For the World.",
    "hosts": [{"country": "Morocco", "role": "co-host"}, {"country": "Portugal", "role": "co-host"}, {"country": "Spain", "role": "co-host"}],
    "centenary": {
        "text": "To mark 100 years since the first World Cup (Uruguay, 1930), one match is planned in each of the three South American countries tied to that history.",
        "matches": [
            {"country": "Uruguay", "city": "Montevideo", "stadium": "Estadio Centenario", "note": "special match and celebration"},
            {"country": "Argentina", "city": "Buenos Aires", "stadium": "Estadio Monumental", "note": "one match"},
            {"country": "Paraguay", "city": "Asunción", "stadium": "stadium reported differently by sources (Estadio General Pablo Rojas / Estadio Osvaldo Domínguez Dibb)", "note": "one match"},
        ],
        "proposedDates": "8-9 June 2030 (FIFA's proposed schedule)", "status": "proposed",
    },
    "dates": {"value": "8 June to 21 July 2030", "status": "as listed by Wikipedia; centenary matches proposed for 8-9 June, main tournament opening about 13-14 June; match schedule, opening match and final date are not officially detailed"},
    "format": {"teams": "48 teams under the current World Cup format; CONMEBOL proposed a one-off 64-team tournament (announced by its president on 20 July 2026) - FIFA has NOT confirmed this",
               "matches": "not confirmed (104 matches with the current 48-team format)", "status": "undecided"},
    "selection": {"decision": "Confirmed on 11 December 2024 at an extraordinary (virtual) FIFA Congress, alongside the award of 2034 to Saudi Arabia",
                  "bid": "Spain and Portugal announced a joint bid in October 2020; Morocco joined on 14 March 2023; the joint bid was the only candidate"},
    "identity": {"name": "Yalla Vamos 2030", "meaning": "'let's go' in Arabic and Spanish",
                 "status": "bid identity/slogan unveiled in Lisbon on 19 March 2024; the final official FIFA tournament emblem is not confirmed in the sources used", "mascot": "not announced", "matchBall": "not announced"},
    "qualification": {
        "hosts": "All six host countries (Morocco, Portugal, Spain, Uruguay, Argentina, Paraguay) qualify automatically",
        "concacaf": "Format announced 6 February 2026: multi-round, play-in to intercontinental play-offs; final-round matches 2028-2029, play-in matches November 2029",
        "uefa": "Format announced 20 May 2026: tied to the 2028-29 UEFA Nations League (League 1 / League 2; top 36 teams in three groups of 12); best-ranked group teams qualify and the rest go to play-offs; details expected late 2026 or early 2027",
        "slots": "slot allocation per confederation not yet announced", "draw": "draw date not announced",
    },
    "venues": {
        "status": "provisional: 20 stadiums in 17 cities were on the candidate list; Málaga withdrew (July 2025) and A Coruña withdrew (March 2026); Spain reportedly bid Nou Mestalla (Valencia) and Balaídos (Vigo) as replacements, so about 23 venues are under consideration",
        "list": [
            {"country": "Morocco", "city": "Agadir", "stadium": "Adrar Stadium", "capacity": 46000},
            {"country": "Morocco", "city": "Casablanca", "stadium": "Hassan II Stadium (new)", "capacity": 115000},
            {"country": "Morocco", "city": "Fez", "stadium": "Fez Stadium", "capacity": 55800},
            {"country": "Morocco", "city": "Marrakesh", "stadium": "Marrakesh Stadium", "capacity": 45860},
            {"country": "Morocco", "city": "Rabat", "stadium": "Prince Moulay Abdellah Stadium (new)", "capacity": 69500},
            {"country": "Morocco", "city": "Tangier", "stadium": "Tangier Grand Stadium", "capacity": 75500},
            {"country": "Portugal", "city": "Lisbon", "stadium": "Estádio da Luz", "capacity": 68100},
            {"country": "Portugal", "city": "Lisbon", "stadium": "Estádio José Alvalade", "capacity": 52095},
            {"country": "Portugal", "city": "Porto", "stadium": "Estádio do Dragão", "capacity": 50033},
            {"country": "Spain", "city": "Barcelona", "stadium": "Camp Nou", "capacity": 105000},
            {"country": "Spain", "city": "Barcelona", "stadium": "RCDE Stadium", "capacity": 40500},
            {"country": "Spain", "city": "Bilbao", "stadium": "San Mamés", "capacity": 53331},
            {"country": "Spain", "city": "Las Palmas", "stadium": "Gran Canaria Stadium", "capacity": 44500},
            {"country": "Spain", "city": "Madrid", "stadium": "Santiago Bernabéu", "capacity": 83186},
            {"country": "Spain", "city": "Madrid", "stadium": "Metropolitano Stadium", "capacity": 70692},
            {"country": "Spain", "city": "San Sebastián", "stadium": "Anoeta Stadium", "capacity": 42300},
            {"country": "Spain", "city": "Seville", "stadium": "Estadio de La Cartuja", "capacity": 70000},
            {"country": "Spain", "city": "Valencia", "stadium": "Nou Mestalla (new)", "capacity": 70044},
            {"country": "Spain", "city": "Vigo", "stadium": "Balaídos Stadium", "capacity": 44000},
            {"country": "Spain", "city": "Zaragoza", "stadium": "La Romareda", "capacity": 43110},
        ],
        "finalVenue": "not decided",
    },
    "undecided": ["Final team count (64 proposed by CONMEBOL, unconfirmed)", "Final venue list, and the venues of the opening match and the final", "Match schedule and exact opening/final dates",
                  "Qualification slots per confederation", "Draw date", "Official tournament emblem, mascot and match ball"],
    "note": "This tournament has not been played: the dashboard shows no matches, results, standings or awards for it, and the machine-learning models make no predictions for it.",
}
