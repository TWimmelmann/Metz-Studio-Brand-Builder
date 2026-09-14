#!/usr/bin/env python3
"""
markeder.py — det der adskiller det danske og det amerikanske værktøj.

Builderen er den samme for begge markeder. Det eneste der skifter er
sortimentet, kategorinavnene, valutaen og et par sproglige særheder i den
måde shoppen skriver produktnavne på. Alt det står her, så en rettelse i
logikken kun skal laves ét sted.

Tilføjer Metz et marked mere, er det en ny post i MARKEDER — ikke en ny
kopi af scripts.
"""

import re

# ── Fælles ────────────────────────────────────────────────────────────────

# Farver der ikke står i det danske farvekort. Lysstyrken afgør om logoet
# trykkes i den mørke eller den lyse plade, så en farve der mangler her
# giver en grå prik og et gæt på pladen.
US_PALETTE = {
    "Royal Blue": "#2b4ea8",
    "Blue": "#2f5fa8",
    "Cobalt Blue": "#1f4fa0",
    "Natural": "#e8dcc8",
    "Clear": "#e6edf0",
    "Charcoal": "#43484d",
    "Vanilla": "#f0e6d2",
}

# Samme farve skrevet på to måder. Uden ensretning bliver "Navy" og
# "Navy Blue" til to ens prikker på det samme produktkort.
#
# DN-varerne hedder både "Navy" og "Dark Navy" i shoppen, og NVBU-varerne
# både "Navy" og "Navy Blue" — det er den samme vare, ikke to farver.
US_ALIAS = {
    "navy blue": "Navy",
    "dark navy": "Navy",
    "translucent charcoal": "Charcoal",
}

# Haler shoppen hænger på produktnavnet som ikke er en del af navnet:
# antal trykfarver inkluderet i prisen, filtnummer, køn.
US_STOEJ = re.compile(
    r"\s*\((?:\d+\s*C(?:olou?r)?s?\.?\s*incl\.?|felt\s*\d+|incl\.[^)]*|Mens|Womens|Unisex)\)\s*$",
    re.I)

# Leverandørens farvekode i varenummeret, for de varer hvor farven slet ikke
# står i navnet. Resten læres af navnene under kørslen — det her er kun de
# koder der aldrig optræder med et farvenavn nogen steder i shoppen.
#
# Farverne er aflæst på produktbillederne 14. september 2026. Skifter
# leverandøren kode, opdager byg_katalog_fra_demo.py det og siger til.
US_KODE_FARVE = {
    "LYN": "Navy",
    "CC":  "Grey",
    "FB":  "French blue",
    "LTB": "Light blue",
}

# Varenummer -> (grundnummer, farvekode). MCW00138LTB -> ('MCW00138', 'LTB')
US_KODE_RE = re.compile(r"^([A-Z]{2,4}\d{4,6})([A-Z]{1,4})$")

# Navneregler der skal slå de fælles igennem. Den fælles liste sætter "bag"
# før "tote", fordi en dansk mulepose ikke hedder "bag" — men her hedder de
# allesammen "Tote Bag", og en mulepose skal have muleposens logoplacering.
US_FAMILIE_FOERST = [
    ("tote",  ["tote bag", "sports pack"]),
    ("cap",   ["cap", "beanie", "visor", "headwear"]),
]


MARKEDER = {
    "dk": {
        "navn":      "Danmark",
        "base":      "https://shop.metz.dk/metz-studio-demo-alt/da",
        "scrape":    ".scrape",
        "index":     "index.html",
        "catalogue": "catalogue.json",
        "valuta":    "DKK",
        "sprog":     "da",
        # Rækkefølgen er den rækkefølge kategorierne står i shoppens menu.
        "kilder": [
            ("merchandise",     ["merchandise_a.json", "merchandise_b.json"]),
            ("beklaedning",     ["beklaedning_a.json", "beklaedning_b.json",
                                 "beklaedning_c.json", "beklaedning_d.json"]),
            ("tasker",          ["tasker.json"]),
            ("onboarding",      ["onboarding.json"]),
            ("laekkerier",      ["laekkerier.json"]),
            ("anledningsgaver", ["anledningsgaver.json"]),
            ("forespoergsler",  ["forespoergsler.json"]),
        ],
        "underkategori_familie": [
            ("beklaedning/bukser",        "pants"),
            ("beklaedning/haettetroejer", "sweat"),
            ("beklaedning/jakker",        "jacket"),
            ("beklaedning/poloshirts",    "polo"),
            ("beklaedning/skjorter",      "shirt"),
            ("beklaedning/sko",           "shoes"),
            ("beklaedning/sportstoej",    "sport"),
            ("beklaedning/strik",         "knit"),
            ("beklaedning/sweatshirts",   "sweat"),
            ("beklaedning/t-shirts",      "tshirt"),
            ("beklaedning/veste",         "vest"),
            ("tasker/computertasker",     "bag"),
            ("tasker/rejsetasker",        "bag"),
            ("tasker/rygsaekke",          "bag"),
            ("tasker/sportstasker",       "bag"),
        ],
        "palette_ekstra": {},
        "alias_ekstra":   {},
        "stoej":          None,
        "kode_farve":     {},
        "familie_foerst": [],
        "mkey_med_serie": False,
    },

    "us": {
        "navn":      "USA",
        "base":      "https://shop.metz.dk/metz-us-studio-demo/en",
        "scrape":    ".scrape-us",
        "index":     "us/index.html",
        "catalogue": "us/catalogue.json",
        "valuta":    "USD",
        "sprog":     "en",
        # "new" udelades med vilje: alle 220 varer på den side ligger også i
        # deres egen kategori, præcis som nyheds-siden gør i den danske demo.
        "kilder": [
            ("merchandise", ["merchandise.json"]),
            ("apparel",     ["apparel.json"]),
            ("bags",        ["bags.json"]),
            ("onboarding",  ["onboarding.json"]),
        ],
        "underkategori_familie": [
            ("apparel/dress-shirts", "shirt"),
            ("apparel/headwear",     "cap"),
            ("apparel/jackets",      "jacket"),
            ("apparel/polo-shirts",  "polo"),
            ("apparel/sweatshirts",  "sweat"),
            ("apparel/t-shirts",     "tshirt"),
            ("apparel/vests",        "vest"),
            ("bags/tote-bags",       "tote"),
            ("bags/backpacks",       "bag"),
            ("bags/computer-bags",   "bag"),
            ("bags/sports-bags",     "bag"),
            ("bags/travel-bags",     "bag"),
        ],
        "palette_ekstra": US_PALETTE,
        "alias_ekstra":   US_ALIAS,
        "stoej":          US_STOEJ,
        "kode_farve":     US_KODE_FARVE,
        "familie_foerst": US_FAMILIE_FOERST,
        # Den amerikanske shop genbruger produktnavne på tværs af leverandørens
        # varelinjer: 3031, 3330 og 3333 hedder alle tre "Tote Bag (80 gsm)" og
        # fås alle tre i Black. Uden varelinjen i modelnøglen smelter ni
        # forskellige poser sammen til ét kort med ni ens sorte prikker — og
        # sælgeren kan ikke se hvilken pose han lægger et logo på.
        "mkey_med_serie": True,
    },
}


def hent(navn):
    if navn not in MARKEDER:
        raise SystemExit(f"Ukendt marked {navn!r}. Vælg mellem: {', '.join(MARKEDER)}")
    return MARKEDER[navn]
