#!/usr/bin/env python3
"""
opdater_katalog.py — henter Metz Studio demo-sortimentet og opdaterer
SKUS-arrayet i index.html (samt catalogue.json).

Retter fejlen hvor produkter med et "Nyhed"-badge blev droppet i stilhed,
fordi badge-billedet lå foran produktbilledet i produktgitteret.

Brug:
    pip3 install requests beautifulsoup4
    python3 opdater_katalog.py --dry-run     # vis hvad der ville ske
    python3 opdater_katalog.py               # skriv ændringerne

Kør den fra repo-roden, hvor index.html ligger.
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://shop.metz.dk/metz-studio-demo-alt/da"
IMG_HOST = "img.metz.dk"

# Shop-sti -> (builder-kategori, produktfamilie).
#
# Familien styrer hvor logoet lander som standard, og den kan ikke altid udledes
# af navnet: "Brownsville Unisex" og "V150 Engineered Men" siger intet om hvad
# de er. Shoppens egne underkategorier ved det, så dem bruger vi.
# Er familien None, gættes den ud fra navnet.
CATEGORIES = {
    "beklaedning/bukser":        ("beklaedning", "pants"),
    "beklaedning/haettetroejer": ("beklaedning", "sweat"),
    "beklaedning/jakker":        ("beklaedning", "jacket"),
    "beklaedning/poloshirts":    ("beklaedning", "polo"),
    "beklaedning/skjorter":      ("beklaedning", "shirt"),
    "beklaedning/sko":           ("beklaedning", "shoes"),
    "beklaedning/sportstoej":    ("beklaedning", "sport"),
    "beklaedning/strik":         ("beklaedning", "knit"),
    "beklaedning/sweatshirts":   ("beklaedning", "sweat"),
    "beklaedning/t-shirts":      ("beklaedning", "tshirt"),
    "beklaedning/veste":         ("beklaedning", "vest"),
    # Nyheder til sidst som sikkerhedsnet. Varerne her ligger også i deres egen
    # underkategori ovenfor, så normalt fanges alt inden vi når hertil.
    "beklaedning/nyheder":       ("beklaedning", None),
    "merchandise":               ("merchandise", None),
    "tasker":                    ("tasker", None),
    "laekkerier":                ("laekkerier", None),
    "anledningsgaver":           ("anledningsgaver", None),
    "forespoergsler":            ("forespoergsler", None),
    # "beklaedning/udgaar" udelades bevidst — udgåede varer skal ikke vises
    # til en prospect.
}

# Ordene tjekkes i rækkefølge; første træf vinder. Rækkefølgen er ikke tilfældig:
# "fleece vest" skal ramme vest, ikke jacket.
FAMILY_RULES = [
    ("vest",     ["vest", "bodywarmer"]),
    ("jacket",   ["jacket", "jakke", "parka", "fleece", "softshell", "shell", "anorak",
                  "coat", "hood unisex", "fz hood", "hybrid"]),
    ("polo",     ["polo"]),
    ("sweat",    ["hoodie", "sweatshirt", "sweat", "crewneck"]),
    ("tshirt",   ["t-shirt", "tshirt", "t shirt", "tee"]),
    ("shirt",    ["shirt", "skjorte", "oxford", "overshirt"]),
    ("knit",     ["knit", "strik", "cardigan", "half zip", "1/4 zip", "pullover",
                  "jumper", "merino"]),
    ("pants",    ["pants", "bukser", "shorts", "chino", "trousers"]),
    ("sport",    ["tights", "cykel", "bike", "running", "training", "cycling"]),
    ("shoes",    ["sko", "sneaker", "shoe", "boot"]),
    ("cap",      ["cap", "hue", "beanie", "hat"]),
    ("bag",      ["taske", "rygsaek", "rygsæk", "backpack", "duffel", "trolley",
                  "rucksack", "bag"]),
    ("tote",     ["tote", "mulepose", "shopper", "net"]),
    ("bottle",   ["flaske", "bottle", "drikkedunk", "termo", "thermo", "tumbler", "cup"]),
    ("mug",      ["krus", "mug", "kop"]),
    ("pen",      ["kuglepen", "pen", "pencil", "blyant"]),
    ("notebook", ["notesbog", "notebook", "kalender", "notesblok"]),
    ("umbrella", ["paraply", "umbrella"]),
    ("lanyard",  ["lanyard", "noeglesnor", "nøglesnor", "keyhanger"]),
    ("tech",     ["powerbank", "højttaler", "speaker", "oplader", "charger", "usb",
                  "musemåtte", "headset"]),
    ("food",     ["chokolade", "lakrids", "kaffe", "slik", "honning", "vin", "bolsjer"]),
]

# Ord der skal matche som helt ord. Uden det matcher "tee" inde i "Steel" og
# "net" inde i "Magnet". Alt andet matches som understreng, fordi danske
# sammensatte ord ellers falder igennem: "regnjakke", "drikkeflaske", "poloshirt".
WHOLE_WORD_ONLY = {"tee", "net", "bag", "cap", "mus", "pen", "hat", "sko", "usb",
                   "vin", "hue", "kop", "mug", "shoe", "coat", "bike", "shell", "cup"}

# Nogle kategorier er entydige uanset produktnavn.
CAT_FAMILY_OVERRIDE = {"laekkerier": "food", "anledningsgaver": "gift"}


DARK_COLOURS = {
    "black", "navy", "dark navy", "midnight blue", "dark grey", "dark grey melange",
    "grey", "charcoal grey", "red", "prune red", "blaze", "taupe", "dark green",
    "thyme green", "leaf green", "green", "pine green", "moss", "mocha brown",
    "brown", "ink", "raw", "sort", "marine",
}

# Ord shoppen blander ind i farvefeltet: "Polo knit, Mens Pine Green".
GENDER_WORDS = ("mens", "men", "womens", "women", "ladies", "unisex", "herre", "dame")


def slugify(text):
    s = text.lower()
    for a, b in (("æ", "ae"), ("ø", "oe"), ("å", "aa")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def split_name(name):
    """
    'Hoodie Regular Fit Unisex, Navy'             -> ('Hoodie Regular Fit Unisex', 'Navy')
    'Polo knit, Mens Pine Green'                  -> ('Polo knit Mens', 'Pine Green')
    'ADV Explore Pile Fleece Vest Green - Unisex' -> ('ADV Explore Pile Fleece Vest Unisex', 'Green')
    'Urban Hooded Sweatshirt. Unisex Black'       -> ('Urban Hooded Sweatshirt Unisex', 'Black')
    """
    name = " ".join(name.replace("\xa0", " ").split())

    for sep in (", ", " - ", ". "):
        if sep not in name:
            continue
        head, _, tail = name.rpartition(sep)
        if not head or len(tail) > 30 or re.search(r"\d", tail):
            continue

        words = tail.split()
        # Køn/fit-ord der står foran farven hører til modellen, ikke farven.
        while len(words) > 1 and words[0].lower().strip(",") in GENDER_WORDS:
            head += " " + words.pop(0).strip(",")
        # '... Vest Green - Unisex': halen er rent et køn, farven står i hovedet.
        if len(words) == 1 and words[0].lower() in GENDER_WORDS:
            hw = head.split()
            if len(hw) > 2:
                return " ".join(hw[:-1]).strip() + " " + words[0], hw[-1]
            continue
        if words:
            return head.strip(), " ".join(words).strip()

    # Sidste udvej: "... Unisex Black" uden nogen separator.
    words = name.split()
    for i, w in enumerate(words[:-1]):
        if w.lower() in GENDER_WORDS and i >= len(words) - 3:
            return " ".join(words[:i + 1]), " ".join(words[i + 1:])

    return name, "—"


# Ord der afslører at teksten beskriver et materiale frem for et brand.
MATERIAL_WORDS = {
    "plastik", "polyester", "bomuld", "uld", "læder", "stål", "silikone",
    "genanvendt", "recycled", "nylon", "elastan", "viskose", "akryl", "merino",
    "polyamid", "polyamide", "spandex", "rpet", "organic", "cotton", "økologisk",
}


def clean_brand(candidate, name, known):
    """
    Brand vises over produktnavnet i mockuppen, så feltet skal være rent.
    Gitteret placerer ikke altid brandet samme sted, og uden filter havner
    materialebeskrivelser ("Yderside i genanvendt polyester") og hele
    produktnavne ("Stanley Everyday 236 ml termokop - Black") i feltet.
    """
    if not candidate:
        return ""
    c = " ".join(candidate.split()).strip(" -,.")
    low = c.lower()

    if low in known:                     # kendt brand -> brug husets stavemåde
        return known[low]
    if "%" in c or len(c) > 28:           # materialebeskrivelse
        return ""
    if re.search(r"\d\s*(ml|l|cm|mm|g|kg|stk|\")", low):
        return ""
    if low and (low in name.lower() or name.lower().startswith(low)):
        return ""                         # gentagelse af produktnavnet
    if low.startswith(("yderside", "foer", "materiale")):
        return ""
    # Pris, lagerstatus og lignende gitter-tekst er ikke et brand.
    if low.startswith(("dkk", "fra dkk", "eur", "pris", "forventet", "på lager",
                       "ikke på lager", "udsolgt", "nyhed")):
        return ""
    # Materialebetegnelser der ligner et brand: "Tritan™ Renew plastik".
    # Matches som helt ord, ellers ryger rigtige brands som "High Sierra RECYCLEX".
    words = set(re.findall(r"[a-zæøå]+", low))
    if words & MATERIAL_WORDS:
        return ""
    return c


def _pattern(word):
    esc = re.escape(word)
    if word in WHOLE_WORD_ONLY:
        return re.compile(r"(?<![a-z])" + esc + r"(?![a-z])", re.I)
    return re.compile(esc, re.I)


_FAM_RE = [(fam, [_pattern(w) for w in words]) for fam, words in FAMILY_RULES]


def family_of(name, cat=None):
    if cat in CAT_FAMILY_OVERRIDE:
        return CAT_FAMILY_OVERRIDE[cat]
    for fam, pats in _FAM_RE:
        if any(p.search(name) for p in pats):
            return fam
    return "gift"


def fetch(session, url, tries=3):
    for n in range(tries):
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
            return r.text
        except Exception as exc:
            if n == tries - 1:
                raise
            print(f"    genforsøg ({exc}) …", file=sys.stderr)
            time.sleep(2 * (n + 1))


# Grafik der ligger på img.metz.dk uden at være et produktbillede.
# "badge-new-da.png" er Nyhed-banneret og lå foran produktet på 85 varer.
NON_PRODUCT_IMAGES = ("badge", "sprite", "placeholder", "icon", "logo")


def _candidates(soup_or_tile):
    """Alle billeder fra img.metz.dk som ikke er badges eller anden pynt."""
    out = []
    for img in soup_or_tile.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if IMG_HOST not in src:
            continue
        filename = src.rsplit("/", 1)[-1].lower()
        if any(w in filename for w in NON_PRODUCT_IMAGES):
            continue
        out.append((filename, re.sub(r"width=\d+,height=\d+",
                                     "width=600,height=600", src)))
    return out


def product_image(tile, session, detail_url, cache, key):
    """
    Vælger produktbilledet ud fra filnavnet frem for ud fra rækkefølgen.

    To fælder ligger her. Nyhed-varer får et badge lagt foran produktbilledet,
    og badget ligger på samme domæne som produkterne — så "tag det første
    billede fra img.metz.dk" gav banneret på 85 varer. Filnavnet er derimod
    entydigt: produktet new-3440010na har billedet new-3440010na_1.jpg.
    """
    for source in (tile, None):
        if source is None:
            if detail_url in cache:
                return cache[detail_url]
            source = BeautifulSoup(fetch(session, detail_url), "html.parser")

        found = _candidates(source)
        # Filnavn der starter med varenummeret er utvetydigt det rigtige.
        for filename, src in found:
            if key and filename.startswith(key.lower()):
                if source is not tile:
                    cache[detail_url] = src
                return src
        # Ellers: første rigtige produktbillede i feltet.
        if found and source is tile:
            return found[0][1]
        if found:
            cache[detail_url] = found[0][1]
            return found[0][1]

    cache[detail_url] = None
    return None


def scrape(session, known_brands):
    found, no_image = [], []
    detail_cache = {}
    seen = set()

    for path, (cat, cat_fam) in CATEGORIES.items():
        url = f"{BASE}/categories/{path}"
        print(f"  {path} …", end="", flush=True)
        soup = BeautifulSoup(fetch(session, url), "html.parser")

        tiles = []
        for a in soup.select('a[href*="/products/"]'):
            tile = a.find_parent(
                lambda t: t.name in ("li", "article", "div") and t.find("h6" ) is not None
            ) or a.parent
            if tile not in tiles:
                tiles.append(tile)

        count = 0
        for tile in tiles:
            link = tile.select_one('a[href*="/products/"]')
            if not link:
                continue
            href = link["href"]
            key = href.rsplit("/", 1)[-1].split("--")[0]
            if key in seen:
                continue

            heading = tile.find(["h6", "h5", "h4", "h3"])
            name = (heading.get_text(" ", strip=True) if heading
                    else link.get("title") or link.get_text(" ", strip=True))
            name = " ".join(name.replace("\xa0", " ").split())
            if not name:
                continue
            seen.add(key)

            texts = [t.strip() for t in tile.stripped_strings]
            brand = ""
            for t in texts:
                if not t or t == name or t == "Product badge":
                    continue
                brand = clean_brand(t, name, known_brands)
                if brand:
                    break
            mat = next((t for t in texts if "%" in t), "")
            price = next((t for t in texts if t.startswith(("Fra DKK", "DKK", "Pris"))), "")
            stock = next((t for t in texts if t.startswith(("Forventet", "På lager", "Ikke på lager"))), "")

            detail = href if href.startswith("http") else "https://shop.metz.dk" + href
            img = product_image(tile, session, detail, detail_cache, key)

            model, colour = split_name(name)
            rec = {
                "img": img,
                "name": name,
                "model": model,
                "colour": colour,
                "brand": brand,
                "mat": mat,
                "price": price,
                "stock": stock,
                "fam": cat_fam or family_of(name, cat),
                "dark": colour.lower() in DARK_COLOURS,
                "mkey": slugify(model),
                "art": None,
                "cat": cat,
                "_key": key,
            }
            if img:
                found.append(rec)
            else:
                no_image.append(rec)
            count += 1

        print(f" {count} produkter")
        time.sleep(0.5)

    return found, no_image


def load_skus(html):
    start = html.index("[", html.index("const SKUS = "))
    depth = 0
    for j in range(start, len(html)):
        if html[j] == "[":
            depth += 1
        elif html[j] == "]":
            depth -= 1
            if depth == 0:
                return json.loads(html[start:j + 1]), start, j + 1
    raise RuntimeError("Kunne ikke finde slutningen på SKUS-arrayet i index.html")


def img_key(url):
    m = re.search(r"/([^/]+?)(?:_\d+)?\.(?:jpg|jpeg|png|webp)", url or "", re.I)
    return m.group(1).lower() if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="vis diffen, skriv ikke")
    ap.add_argument("--index", default="index.html")
    ap.add_argument("--catalogue", default="catalogue.json")
    args = ap.parse_args()

    index_path = Path(args.index)
    if not index_path.exists():
        sys.exit(f"Finder ikke {index_path} — kør scriptet fra repo-roden.")

    html = index_path.read_text(encoding="utf-8")
    existing, start, end = load_skus(html)
    print(f"index.html indeholder {len(existing)} SKU'er\n")

    # Husets stavemåder. Retter bl.a. "TEE JAYS" til "Tee Jays", så samme
    # leverandør ikke optræder som to brands i mockuppen.
    known_brands = {}
    for sku in existing:
        b = (sku.get("brand") or "").strip()
        if b:
            known_brands.setdefault(b.lower(), b)

    print("Henter shoppen:")
    session = requests.Session()
    session.headers["User-Agent"] = "metz-brand-builder-katalogopdatering"
    found, no_image = scrape(session, known_brands)
    print(f"\nShoppen gav {len(found) + len(no_image)} produkter")

    # HØJLYDT FEJL. Den gamle scraper sprang de her over uden at sige noget,
    # og det er præcis derfor hættetrøjerne forsvandt.
    if no_image:
        print(f"\n!! {len(no_image)} produkter uden billede — de springes over:")
        for r in no_image:
            print(f"   {r['_key']:22} {r['name']}")
        print("   Tjek dem i shoppen før du kører videre.\n")

    # Sikkerhedsnet. To produkter må aldrig dele billede — sker det, har vi
    # grebet noget generisk (et badge, en pladsholder) i stedet for varen.
    # Det var præcis sådan Nyhed-banneret nåede ud på 85 produkter.
    from collections import Counter
    shared = {u: n for u, n in Counter(r["img"] for r in found).items() if n > 1}
    if shared:
        print(f"\n!! {len(shared)} billed-URL bruges af flere produkter — de springes over:")
        for url, n in sorted(shared.items(), key=lambda x: -x[1]):
            print(f"   {n:4}x  {url}")
        print("   Ser det ud som en badge eller pladsholder, så tilføj et ord")
        print("   fra filnavnet til NON_PRODUCT_IMAGES øverst i scriptet.\n")
        found = [r for r in found if r["img"] not in shared]

    known = {img_key(s["img"]) for s in existing}
    known |= {s["name"].lower() for s in existing}

    new, batch_seen = [], set()
    for r in found:
        if img_key(r["img"]) in known or r["name"].lower() in known:
            continue
        fingerprint = (r["name"].lower(), r["img"])
        if fingerprint in batch_seen:      # samme vare fundet i to kategorier
            continue
        batch_seen.add(fingerprint)
        new.append(r)

    print(f"Allerede i kataloget: {len(found) - len(new)}")
    print(f"NYE der tilføjes:     {len(new)}\n")

    if not new:
        print("Intet at gøre — kataloget er ajour.")
        return

    by_brand = {}
    for r in new:
        by_brand.setdefault(r["brand"] or "(uden brand)", []).append(r)
    for brand, rows in sorted(by_brand.items(), key=lambda x: -len(x[1])):
        print(f"  {brand} ({len(rows)})")
        for r in rows:
            print(f"     {r['name']}")

    if args.dry_run:
        print("\n--dry-run: intet skrevet.")
        return

    merged = existing + [{k: v for k, v in r.items() if k != "_key"} for r in new]
    blob = json.dumps(merged, ensure_ascii=False, indent=1)

    index_path.write_text(html[:start] + blob + html[end:], encoding="utf-8")
    Path(args.catalogue).write_text(blob, encoding="utf-8")

    print(f"\nSkrevet. {len(existing)} -> {len(merged)} SKU'er.")
    print("Åbn index.html lokalt og se produkterne efter, før du pusher.")


if __name__ == "__main__":
    main()
