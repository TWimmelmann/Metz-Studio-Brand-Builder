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
import markeder

IMG_PREFIX = "https://img.metz.dk/cdn-cgi/image/width=600,height=600,f=auto/"

# Markedet sættes af --market og af saet_marked() nedenfor. Uden flaget kører
# scriptet som før: dansk shop, .scrape/, index.html i roden.
#
# Kategorirækkefølgen, underkategori -> familie, farvekortet og shoppens
# sproglige særheder ligger i markeder.py — ikke her. Logikken under er
# fælles for begge markeder, og det er hele pointen: en fejlrettelse i
# navneopdelingen eller varianthåndteringen gælder med det samme for begge.
MARKED = markeder.hent("dk")
SCRAPE = Path(MARKED["scrape"])


def saet_marked(navn):
    """Vælger marked og folder markedets farver ind i det fælles farvekort."""
    global MARKED, SCRAPE
    MARKED = markeder.hent(navn)
    SCRAPE = Path(MARKED["scrape"])

    # Farvekortet ligger i opdater_katalog. Markedets egne farver lægges
    # oveni, så luminansberegningen — og dermed valget mellem den mørke og
    # den lyse logoplade — virker på amerikanske farvenavne uden at det
    # danske kort ændrer sig.
    ok.PALETTE.update(MARKED["palette_ekstra"])
    ok._CANON.update({n.lower(): n for n in MARKED["palette_ekstra"]})
    ok._CANON.update(MARKED["alias_ekstra"])
    return MARKED


def rens_navn(navn):
    """
    Fjerner det shoppen hænger på produktnavnet uden at det er en del af navnet.

    Den amerikanske shop skriver antallet af inkluderede trykfarver ind i
    navnet: "Mug (15 Oz.), Royal Blue (1C incl.)". Uden at pille den hale af
    bliver farven "Royal Blue (1C incl.)" — den findes ikke i farvekortet, så
    varen står uden farve og lægger sig som sit eget produktkort i stedet for
    at indgå i modellens farvepalette.
    """
    n = " ".join((navn or "").replace("\xa0", " ").split())
    stoej = MARKED["stoej"]
    if stoej:
        for _ in range(3):
            kortere = stoej.sub("", n).strip()
            if kortere == n:
                break
            n = kortere
    # "Charter Mens Anorak Jacket,Navy" — komma uden mellemrum efter.
    n = re.sub(r",(?=[^\s])", ", ", n)
    return n


def farve_bagi(navn):
    """
    Sidste udvej: står der en kendt farve som det sidste ord eller de to
    sidste ord, er det farven — også uden komma foran.

    Fanger "Tumbler, single wall (22 Oz.) blue", hvor halen efter kommaet
    indeholder et tal og derfor bliver afvist som farve af den fælles regel.
    """
    ord = navn.split()
    for n in (2, 1):
        if len(ord) > n:
            hale = " ".join(ord[-n:])
            if ok.canon_colour(hale) in ok.PALETTE:
                return " ".join(ord[:-n]).strip(" ,.-"), hale
    return navn, "—"


def kodefarver(raekker):
    """
    Leverandørens farvekode i varenummeret -> farve.

    Cutter & Buck-varerne skriver ikke altid farven i navnet: seks skjorter
    hedder bare "Stretch Oxford Long Sleeve Dress Shirt", og farven står kun
    som en hale på varenummeret (MCW00138LTB). Koden læres af de varer hvor
    farven ER skrevet, så kortet holder sig selv ajour når shoppen får nye
    varer. Kun de koder der aldrig optræder med et farvenavn står fast i
    markeder.py.
    """
    from collections import Counter, defaultdict
    laert = defaultdict(Counter)
    for nummer, farve in raekker:
        if farve == "—":
            continue
        m = markeder.US_KODE_RE.match((nummer or "").replace("-", ""))
        if m:
            laert[m.group(2)][farve] += 1
    kort = {kode: t.most_common(1)[0][0] for kode, t in laert.items()}
    for kode, farve in MARKED["kode_farve"].items():
        kort.setdefault(kode, farve)
    return kort


SERIE_RE = re.compile(r"^([A-Z]+)(\d+)")


def serie(nummer):
    """
    Varelinjen i varenummeret: 'HIT-3333RROYC2' -> 'hit3333'.

    Leverandørpræfiks plus det første tal. Farvekoden og trykfarve-halen
    falder væk, så alle farver af den samme pose deler nøgle — men tre
    forskellige poser der tilfældigvis hedder det samme gør ikke.
    """
    m = SERIE_RE.match((nummer or "").replace("-", "").upper())
    return (m.group(1) + m.group(2)).lower() if m else ""


def familie_foerst(navn):
    """
    Markedets egne navneregler, tjekket før de fælles.

    Den fælles liste sætter "bag" før "tote", fordi en dansk mulepose ikke
    hedder "bag". På den amerikanske shop hedder de allesammen "Tote Bag" —
    og en mulepose skal have muleposens logoplacering, ikke rygsækkens.
    """
    lav = navn.lower()
    for fam, ord in MARKED["familie_foerst"]:
        if any(o in lav for o in ord):
            return fam
    return None


def load_subcat_family():
    """varenummer (små bogstaver) -> familie."""
    raw = json.loads((SCRAPE / "subcats.json").read_text(encoding="utf-8"))
    out = {}
    for path, fam in MARKED["underkategori_familie"]:
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

    for cat, files in MARKED["kilder"]:
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

            name = rens_navn(prodname)
            if not name:
                warnings.append(f"{cat}: {number} uden navn — sprunget over")
                continue

            model, colour = ok.split_name(name)
            colour = ok.canon_colour(colour)
            if colour == "—":
                model, colour = farve_bagi(name)
                colour = ok.canon_colour(colour)

            fam = subfam.get((number or "").lower())
            if not fam:
                fam = familie_foerst(name) or ok.family_of(name, cat)

            mkey = ok.slugify(model)
            if MARKED["mkey_med_serie"]:
                s_ = serie(number)
                if s_:
                    mkey = f"{mkey}-{s_}"

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
                "mkey": mkey,
                "art": [art_of(number)] if number else [],
                "cat": cat,
            })

    # Anden runde: de varer hvor farven slet ikke står i navnet får den fra
    # leverandørens farvekode i varenummeret.
    if MARKED["kode_farve"] or MARKED["stoej"]:
        kort = kodefarver([(s["art"][0] if s["art"] else "", s["colour"]) for s in skus])
        gaettet = 0
        for sku in skus:
            if sku["colour"] != "—" or not sku["art"]:
                continue
            m = markeder.US_KODE_RE.match(sku["art"][0].replace("-", ""))
            farve = kort.get(m.group(2)) if m else None
            if farve:
                sku["colour"] = ok.canon_colour(farve)
                sku["dark"] = ok.colour_is_dark(sku["colour"])
                gaettet += 1
        if gaettet:
            warnings.append(f"{gaettet} varer fik farven fra varenummerets farvekode"
                            f" — shoppen skriver den ikke i navnet")

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
    ap.add_argument("--market", default="dk", choices=sorted(markeder.MARKEDER),
                    help="hvilket marked der bygges (standard: dk)")
    args = ap.parse_args()

    m = saet_marked(args.market)
    print(f"Marked: {m['navn']}  ({m['scrape']} -> {m['index']})\n")

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
    index = Path(MARKED["index"])
    katalog = Path(MARKED["catalogue"])
    if not index.exists():
        sys.exit(f"Mangler {index} — kopiér builderen derhen først.")
    katalog.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(write_skus(index.read_text(encoding="utf-8"), blob), encoding="utf-8")
    katalog.write_text(blob, encoding="utf-8")
    print(f"\nSkrevet til {index} og {katalog}.")


if __name__ == "__main__":
    main()
