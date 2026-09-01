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
import re
import sys
from collections import defaultdict
from itertools import combinations
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
    Varenummeret som demoen skriver det: 'XDC-P438.020EN', med præfiks.

    Det gamle katalog gemte kun halen efter bindestregen. Præfikset skal med
    nu, fordi det er det der adskiller to varer der hedder det samme: både
    PFC-12071090 og XDC-P762.621 hedder "Mulepose - Black", men det er to
    forskellige poser fra to forskellige leverandører.
    """
    return (number or "").strip()


# ── Prisvarianter og dekorationsvarianter ──────────────────────────────
#
# Shoppen sælger den samme vare flere gange under samme navn:
#
#   PFC-12071090     Mulepose - Black    38,00   100% genanvendt bomuld
#   PFC-12071090F2   Mulepose - Black    45,00   100% genanvendt bomuld
#   XDC-P762.621     Mulepose - Black    31,75   70% rCotton
#   XDC-P762.621F2   Mulepose - Black    36,50   70% rCotton
#
# Værktøjet grupperer farvevarianter af én model på ét produktkort. Fire
# gange "Black" i samme gruppe blev derfor til fire ens sorte farveprikker
# på samme kort. To varer med SAMME farve kan pr. definition ikke være
# farvevarianter af hinanden — de er en anden variant og skal have hvert
# sit kort, ligesom i demoen.
#
# Hvad der adskiller dem, står i varenummeret. Reglen læres af numrene selv
# frem for at være en fast liste over "F2", "EN", "PR" — så fanger den også
# den næste hale leverandøren finder på.


def _split_number(number):
    """'PFC-12071090F2' -> ('PFC', '12071090F2');  'H-HIG-1214' -> ('H', 'HIG-1214')"""
    n = (number or "").strip()
    return tuple(n.split("-", 1)) if "-" in n else ("", n)


def _lcp(a, b):
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    return a[:i]


def variant_tags(items):
    """
    items: [(varenummer, farve), ...] for én model. Returnerer en varianttag
    pr. varenummer — (leverandørpræfiks, hale). Tom hale = grundvarianten.
    """
    tags = {}
    by_prefix = defaultdict(list)
    for num, col in items:
        pre, rest = _split_number(num)
        by_prefix[pre.upper()].append((num, rest, col))

    for pre, group in by_prefix.items():
        # Foreslå haler ud fra de varer der støder sammen på farven.
        vocab = set()
        by_col = defaultdict(list)
        for _, rest, col in group:
            by_col[col].append(rest)
        for rests in by_col.values():
            for a, b in combinations(sorted(set(rests)), 2):
                l = _lcp(a, b)
                for r in (a[len(l):], b[len(l):]):
                    if r and len(r) <= 3 and r.isalnum():
                        vocab.add(r)

        # Luk de falske forslag ude. HIG-1212 og HIG-1214 er to forskellige
        # tasker med samme navn, ikke to varianter — men de adskiller sig i ét
        # tegn, så løkken ovenfor foreslår "2" og "4". En ægte hale sidder
        # enten på flere farver (F2, PR, EN) eller kan pilles af og efterlade
        # et varenummer der findes i forvejen (P på 10690402P).
        alle = {rest for _, rest, _ in group}
        ægte = set()
        for t in vocab:
            bærere = {(rest, col) for _, rest, col in group if rest.endswith(t)}
            if len({col for _, col in bærere}) > 1:
                ægte.add(t)
            elif any(rest[: -len(t)] in alle for rest, _ in bærere):
                ægte.add(t)

        for num, rest, _ in group:
            hale = ""
            for t in ægte:
                if rest.endswith(t) and len(t) > len(hale):
                    hale = t
            tags[num] = (pre, hale)

    # Sidste udvej: står to varer stadig med samme farve og samme hale, er de
    # ikke en systematisk variant. Så skiller hele varenummeret dem ad.
    kollision = defaultdict(list)
    for num, col in items:
        kollision[(tags[num], col)].append(num)
    for nums in kollision.values():
        if len(nums) > 1:
            for num in nums:
                pre, hale = tags[num]
                tags[num] = (pre, (hale + "-" + _split_number(num)[1]).strip("-"))
    return tags


def _mkey_suffix(tag, med_praefiks):
    pre, hale = tag
    dele = [d for d in ([pre.lower()] if med_praefiks else []) + [hale.lower()] if d]
    if not dele:
        return ""
    return "-" + re.sub(r"[^a-z0-9]+", "-", "-".join(dele)).strip("-")


def split_variants(skus):
    """
    Giver varianterne hver sin modelnøgle, så de bliver hver sit produktkort.

    Kun modeller der faktisk har den samme farve to gange røres — resten
    beholder den nøgle de havde, så gamle placeringskort bliver ved med at
    passe.
    """
    grupper = defaultdict(list)
    for s in skus:
        grupper[(s["cat"], s["mkey"])].append(s)

    rapport = []
    for (cat, mkey), varer in grupper.items():
        farver = [v["colour"] for v in varer]
        if len(farver) == len(set(farver)):
            continue
        tags = variant_tags([(v["art"][0], v["colour"]) for v in varer])
        med_praefiks = len({t[0] for t in tags.values()}) > 1
        nye = set()
        for v in varer:
            suffix = _mkey_suffix(tags[v["art"][0]], med_praefiks)
            v["mkey"] = mkey + suffix
            nye.add(v["mkey"])
        rapport.append((cat, mkey, len(varer), sorted(nye)))
    return rapport


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

    rapport = split_variants(skus)
    return skus, warnings, rapport


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

    skus, warnings, rapport = build()

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

    if rapport:
        n = sum(len(r[3]) - 1 for r in rapport)
        print(f"\n   {len(rapport)} modeller havde samme farve flere gange og er delt"
              f" i varianter (+{n} produktkort):")
        for cat, mkey, antal, nye in rapport:
            print(f"     {cat}/{mkey} ({antal} varer) -> {', '.join(nye)}")

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
