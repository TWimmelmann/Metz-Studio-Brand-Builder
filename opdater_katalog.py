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
import unicodedata
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


# Husets farvekort. Den samme tabel ligger i SWATCH i index.html — retter du
# den ene, så ret den anden.
#
# Tabellen gør to ting på én gang. Den giver farveprikken på produktkortet en
# rigtig farve, og den afgør om logoet skal trykkes i den mørke eller den lyse
# plade. Det sidste blev før styret af en håndholdt liste over "mørke farver",
# og hver gang leverandøren fandt på et nyt farvenavn — Prune Red, Ink, Thyme
# Green — faldt varen igennem og fik et mørkt logo på et mørkt produkt.
# Nu regnes lysstyrken ud af farven selv, så en ny farve rammer rigtigt med det
# samme. Er farven ukendt, står prikken grå og logoet vælger den mørke plade.
PALETTE = {
    "White": "#ffffff", "Off white": "#f4f1ea", "Neutral": "#e8dcc8", "Natur": "#d9c9a8",
    "Creme": "#f0e6d2", "Cream": "#f3ead8", "Cream Beige": "#f0e6d2", "Beige": "#e3d5bd",
    "Ecru": "#efe7d6", "Birch": "#ded7c7", "Hay": "#d8c68c", "Raw": "#d3c7b3",
    "Sand": "#ddd0b8", "Light oak": "#c9a97a", "Cement": "#b5b1a8",
    "Powder grey": "#c4c5c2", "Silver": "#c8ccd0", "Transparent": "#e6edf0",
    "Steel": "#9aa3aa", "Grey": "#8a8f94", "Grey melange": "#9b9fa4",
    "Dark grey": "#5a5f64", "Dark grey melange": "#5f646a", "Charcoal grey": "#43484d",
    "Black": "#1a1a1a", "Ink": "#22262d", "Navy": "#1e2a44", "Dark navy": "#18223a",
    "Midnight blue": "#1b2540", "French blue": "#3d6ea8", "Blue Oxford": "#86a3c5",
    "Light blue": "#a9c4dd", "Green": "#2f5d3f", "Dark green": "#24402f",
    "Pine green": "#1f4738", "Thyme green": "#59684a", "Leaf green": "#4a7c3f",
    "Moss": "#4c5a39", "Red": "#b3261e", "Prune red": "#6e2233", "Mørkerød": "#6a1b1b",
    "Orange": "#e07b39", "Blaze": "#d4551f", "Taupe": "#8b7d6b", "Brun": "#5d4534",
    "Mocha brown": "#5b4636", "—": "#cfcfcf",
}

# Shoppen skriver samme farve på flere måder: "Light Blue", "Light blue".
# Uden ensretning bliver det to prikker på samme vare.
_CANON = {name.lower(): name for name in PALETTE}
_CANON.update({"sort": "Black", "marine": "Navy", "hvid": "White", "brown": "Mocha brown"})

# Ord shoppen af og til lægger i farvefeltet uden at være en farve.
NOT_A_COLOUR = {"rpet", "high sierra", "polyester", "nylon", "one size"}

DARK_THRESHOLD = 0.32   # under denne lysstyrke skal logoet trykkes i den lyse plade


def canon_colour(colour):
    c = " ".join((colour or "").split()).strip(" -,.")
    if c.lower() in NOT_A_COLOUR:
        return "—"
    return _CANON.get(c.lower(), c or "—")


def luminance(hexcode):
    h = hexcode.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def colour_is_dark(colour):
    hexcode = PALETTE.get(canon_colour(colour))
    if not hexcode or canon_colour(colour) == "—":
        return False
    return luminance(hexcode) < DARK_THRESHOLD

# Ord shoppen blander ind i farvefeltet: "Polo knit, Mens Pine Green".
GENDER_WORDS = ("mens", "men", "womens", "women", "ladies", "unisex", "herre", "dame")


def slugify(text):
    """
    Modelnøglen. To varer med samme nøgle er samme model i forskellige farver,
    så nøglen skal være stabil — falder et bogstav ud, splitter modellen i to.

    Danske bogstaver skrives ud (æ -> ae), og accenter fra låneord foldes ned
    til grundbogstavet. Uden det sidste blev "Wengé" til "weng" og
    "ètagére" til "tag-re", fordi de accenterede tegn blev kasseret som
    ulovlige og efterlod huller i nøglen.
    """
    s = text.lower()
    for a, b in (("æ", "ae"), ("ø", "oe"), ("å", "aa"), ("ß", "ss")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def looks_like_colour(tail):
    """
    Er halen af produktnavnet en farve, eller er den en del af modelnavnet?

    Kun farver vi kender fra paletten godtages. Det er med vilje strengt.
    Slap man kravet op til "et par bogstavord", blev
    "Sportstaske/weekendtaske, Wheel-n-Go" til farven "Wheel-n-Go" og
    "Gaveæske - 5 stk. chokoladestænger" til farven "chokoladestænger" — og
    en opdigtet farve splitter en model op i løse produktkort.

    Kender vi ikke halen, står varen som én farveløs vare. Det er den
    harmløse fejl. maybe_colour_report() nedenfor fanger de tilfælde hvor det
    alligevel så ud som en farveserie, så paletten kan holdes ajour.
    """
    t = " ".join((tail or "").split()).strip(" -,.")
    if not t or t.lower() in NOT_A_COLOUR:
        return False
    return canon_colour(t) in PALETTE


def maybe_colour_report(found):
    """
    Varer der ikke fik nogen farve, men som ligner en farveserie.

    Signalet er søskende: står to varer med samme modelnavn og hver sin hale
    ("Mini abe, rød" og "Mini abe, mørkbejdset eg"), er halen med stor
    sandsynlighed en farve vi mangler i paletten.
    """
    families = {}
    for r in found:
        if r["colour"] != "—":
            continue
        for sep in (", ", " - "):
            if sep not in r["name"]:
                continue
            head, _, tail = r["name"].rpartition(sep)
            words = tail.split()
            if 1 <= len(words) <= 2 and all(
                    re.fullmatch(r"[A-Za-zÆØÅæøå]+", w) for w in words):
                families.setdefault((r["cat"], head.lower()), set()).add(tail)
            break
    return {head: tails for (cat, head), tails in families.items() if len(tails) > 1}


def split_name(name):
    """
    'Hoodie Regular Fit Unisex, Navy'             -> ('Hoodie Regular Fit Unisex', 'Navy')
    'Polo knit, Mens Pine Green'                  -> ('Polo knit Mens', 'Pine Green')
    'ADV Explore Pile Fleece Vest Green - Unisex' -> ('ADV Explore Pile Fleece Vest Unisex', 'Green')
    'Urban Hooded Sweatshirt. Unisex Black'       -> ('Urban Hooded Sweatshirt Unisex', 'Black')
    'Avira Alya tumbler 300ML -Black'             -> ('Avira Alya tumbler 300ML', 'Black')
    """
    name = " ".join(name.replace("\xa0", " ").split())
    # Shoppen skriver af og til bindestregen klods op ad farven: "300ML -Black".
    # Uden mellemrummet ser separatorløkken nedenfor ingen separator, farven
    # bliver "—" og modellen bliver hele navnet — så lagde hver enkelt farve sig
    # som sit eget produktkort i stedet for at indgå i farvepaletten.
    name = re.sub(r"\s-(?=[^\s-])", " - ", name)

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
        if words and looks_like_colour(" ".join(words)):
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
    if low in ("fra", "dkk", "eur", "pris", "nyhed", "ny", "stk"):
        return ""
    if low.startswith(("dkk", "fra dkk", "fra eur", "eur", "pris", "forventet",
                       "på lager", "ikke på lager", "udsolgt", "nyhed")):
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
            colour = canon_colour(colour)
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
                "dark": colour_is_dark(colour),
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

    # Farver uden hex står grå på produktkortet, og logoet må gætte pladen.
    # Bedre at få dem at vide her end at opdage det i en kundepræsentation.
    unknown = sorted({r["colour"] for r in found
                      if r["colour"] != "—" and r["colour"] not in PALETTE})
    if unknown:
        print(f"\n!! {len(unknown)} farver mangler i PALETTE — de står grå og")
        print("   logoet vælger den mørke plade som standard:")
        for c in unknown:
            print(f"   {c}")
        print("   Tilføj dem til PALETTE her i scriptet OG til SWATCH i index.html.\n")

    maybe = maybe_colour_report(found)
    if maybe:
        print(f"\n   {len(maybe)} varer står uden farve, men ligner en farveserie:")
        for head, tails in sorted(maybe.items()):
            print(f"     {head}: {', '.join(sorted(tails))}")
        print("     Er det farver, så tilføj dem til PALETTE og kør igen.\n")

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
    counts = Counter(r["img"] for r in found)
    # Et badge rammer snesevis af varer. To varer der deler ét foto er derimod
    # normalt — samme taske i to størrelser. Kun det første er en fejl.
    badges = {u for u, n in counts.items() if n >= 4}
    overlap = {u: n for u, n in counts.items() if 2 <= n < 4}

    if badges:
        print(f"\n!! {len(badges)} billed-URL bruges af mange produkter — de springes over:")
        for url in sorted(badges, key=lambda u: -counts[u]):
            print(f"   {counts[url]:4}x  {url}")
        print("   Det ligner en badge eller pladsholder. Tilføj et ord fra")
        print("   filnavnet til NON_PRODUCT_IMAGES øverst i scriptet.\n")
        found = [r for r in found if r["img"] not in badges]

    if overlap:
        print(f"\n   {len(overlap)} billeder deles af to-tre varer. Tages med:")
        for url, n in overlap.items():
            names = [r["name"] for r in found if r["img"] == url]
            print(f"   {n}x  {', '.join(names)}")
        print()

    # Kender vi varen i forvejen?
    #
    # Billede og navn er ikke nok. Shoppen skifter foto på en vare, og den
    # skriver samme vare på flere måder ("… 300ML - Black" over for
    # "… 300ML -Black"). Da begge dele svigtede samtidig, kom "Avira Alya
    # tumbler 300ML" ind fem gange mere som fem løse kort ved siden af den
    # rigtige vare. Vare-identiteten er kategori + model + farve — den holder,
    # også når fotoet eller stavemåden ændrer sig.
    def identity(sku):
        return (sku.get("cat"), sku.get("mkey"), canon_colour(sku.get("colour")).lower())

    known_ids = {identity(s) for s in existing}
    known = {img_key(s["img"]) for s in existing}
    known |= {s["name"].lower() for s in existing}

    new, batch_seen = [], set()
    dupes = []
    for r in found:
        if identity(r) in known_ids:
            dupes.append(r)
            continue
        if img_key(r["img"]) in known or r["name"].lower() in known:
            continue
        if identity(r) in batch_seen:      # samme vare fundet i to kategorier
            continue
        batch_seen.add(identity(r))
        new.append(r)

    if dupes:
        print(f"   {len(dupes)} varer findes allerede under samme model og farve"
              f" — de springes over (nyt foto eller ny stavemåde):")
        for r in dupes[:12]:
            print(f"     {r['name']}")
        if len(dupes) > 12:
            print(f"     … og {len(dupes) - 12} mere")

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
