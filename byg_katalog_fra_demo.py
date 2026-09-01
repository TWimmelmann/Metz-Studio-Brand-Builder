#!/usr/bin/env python3
"""
byg_katalog_fra_demo.py — bygger SKUS-arrayet forfra ud fra demoshoppens
egen visningsrækkefølge.

Forskellen på denne og opdater_katalog.py:

  opdater_katalog.py henter shoppen over HTTP og TILFØJER nye varer til det
  katalog der allerede ligger i index.html. Rækkefølgen er "det gamle først,
  det nye bagefter".

  Denne bygger kataloget HELT FORFRA ud fra rå-udtræk der er taget i en
  browser på selve kategorisiden — og det er pointen. Shoppen sorterer
  produktgitteret i browseren efter data-sort-number, så den rækkefølge
  serveren leverer HTML i er ikke den rækkefølge kunden ser. Et HTTP-hent
  rammer altså den forkerte orden. Udtrækkene i .scrape/ er læst af det
  færdigtegnede gitter og har derfor kundens rækkefølge.

  Samme grund til at lagerteksten ("På lager: 25.228 stk") kun findes her:
  den skrives ind af shoppens eget javascript efter sideindlæsning.

Rå-udtrækkenes format, én liste pr. vare:
  [varenummer, navn, brand, materiale, pris, lager, billed-hale]

Kør fra repo-roden:
    python3 byg_katalog_fra_demo.py --dry-run
    python3 byg_katalog_fra_demo.py
"""

import argparse
import json
import sys
from pathlib import Path

import opdater_katalog as ok

IMG_PREFIX = "https://img.metz.dk/cdn-cgi/image/width=600,height=600,f=auto/"
SCRAPE = Path(".scrape")

# Rækkefølgen her er den rækkefølge kategorierne står i shoppens menu, og
# dermed den rækkefølge varerne skal ligge i kataloget.
SOURCES = [
    ("merchandise",     ["merchandise_a.json", "merchandise_b.json"]),
    ("beklaedning",     ["beklaedning_a.json", "beklaedning_b.json",
                         "beklaedning_c.json", "beklaedning_d.json"]),
    ("tasker",          ["tasker.json"]),
    ("onboarding",      ["onboarding.json"]),
    ("laekkerier",      ["laekkerier.json"]),
    ("anledningsgaver", ["anledningsgaver.json"]),
    ("forespoergsler",  ["forespoergsler.json"]),
]

# Underkategori -> familie. Familien afgør hvor logoet lander som standard,
# og den kan ikke altid udledes af navnet: "Brownsville Unisex" og
# "V150 Engineered Men" siger intet om hvad varen er. Shoppens egne
# underkategorier ved det.
#
# Rækkefølgen er ikke ligegyldig: første træf vinder, og enkelte varer ligger
# i to underkategorier (CUT-352412WH står både under sko og skjorter).
SUBCAT_FAMILY = [
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
]


def load_subcat_family():
    """varenummer (små bogstaver) -> familie."""
    raw = json.loads((SCRAPE / "subcats.json").read_text(encoding="utf-8"))
    out = {}
    for path, fam in SUBCAT_FAMILY:
        for num in raw.get(path, []):
            out.setdefault(num.lower(), fam)
    return out


def art_of(number):
    """
    'PFC-10792701' -> '10792701'.

    Leverandørpræfikset er husets, ikke varens. Varenumrene i det gamle katalog
    står uden, så de bliver stående som de er hvis nogen slår op i dem.
    """
    n = (number or "").strip()
    if "-" in n:
        n = n.split("-", 1)[1]
    return n


def build():
    subfam = load_subcat_family()
    skus, seen, warnings = [], set(), []

    for cat, files in SOURCES:
        rows = []
        for name in files:
            path = SCRAPE / name
            if not path.exists():
                sys.exit(f"Mangler {path} — kør browser-udtrækket igen.")
            rows += json.loads(path.read_text(encoding="utf-8"))

        for number, prodname, brand, mat, price, stock, img_tail in rows:
            key = (cat, (number or "").lower())
            if key in seen:          # samme vare to gange på samme side
                continue
            seen.add(key)

            name = " ".join((prodname or "").replace("\xa0", " ").split())
            if not name:
                warnings.append(f"{cat}: {number} uden navn — sprunget over")
                continue

            model, colour = ok.split_name(name)
            colour = ok.canon_colour(colour)

            fam = subfam.get((number or "").lower())
            if not fam:
                fam = ok.family_of(name, cat)

            skus.append({
                "img": (IMG_PREFIX + img_tail) if img_tail else "",
                "name": name,
                "model": model,
                "colour": colour,
                "brand": (brand or "").strip(),
                "mat": (mat or "").strip(),
                "price": (price or "").strip(),
                "stock": (stock or "").strip(),
                "fam": fam,
                "dark": ok.colour_is_dark(colour),
                "mkey": ok.slugify(model),
                "art": [art_of(number)] if number else [],
                "cat": cat,
            })

    return skus, warnings


def write_skus(html, blob):
    start = html.index("[", html.index("const SKUS = "))
    depth = 0
    for j in range(start, len(html)):
        if html[j] == "[":
            depth += 1
        elif html[j] == "]":
            depth -= 1
            if depth == 0:
                return html[:start] + blob + html[j + 1:]
    raise RuntimeError("Kunne ikke finde slutningen på SKUS-arrayet i index.html")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    skus, warnings = build()

    from collections import Counter
    print(f"{len(skus)} varer bygget")
    for cat, n in Counter(s["cat"] for s in skus).items():
        print(f"  {cat:18} {n}")

    # Farver uden hex står grå på produktkortet, og logoet må gætte pladen.
    # Bedre at få dem at vide her end at opdage det i en kundepræsentation.
    unknown = sorted({s["colour"] for s in skus
                      if s["colour"] != "—" and s["colour"] not in ok.PALETTE})
    if unknown:
        print(f"\n!! {len(unknown)} farver mangler i PALETTE/SWATCH:")
        for c in unknown:
            print(f"   {c}")

    noimg = [s for s in skus if not s["img"]]
    if noimg:
        print(f"\n   {len(noimg)} varer uden billede (viser pladsholder):")
        for s in noimg:
            print(f"     {s['cat']}: {s['name']}")

    for w in warnings:
        print("  !", w)

    if args.dry_run:
        print("\n--dry-run: intet skrevet.")
        return

    blob = json.dumps(skus, ensure_ascii=False, indent=1)
    html = Path("index.html").read_text(encoding="utf-8")
    Path("index.html").write_text(write_skus(html, blob), encoding="utf-8")
    Path("catalogue.json").write_text(blob, encoding="utf-8")
    print("\nSkrevet til index.html og catalogue.json.")


if __name__ == "__main__":
    main()
