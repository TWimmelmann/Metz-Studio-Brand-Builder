#!/usr/bin/env python3
"""
byg_us_builder.py — genererer us/index.html ud fra index.html.

Den amerikanske builder er ikke en kopi, den er et udtryk af den danske.
Det er med vilje: retter du en fejl i logoplaceringen, i eksporten eller i
produktsiden, så retter du den i index.html og kører den her — så har begge
markeder fixet. Kopierede du filen i stedet, ville de to drive fra hinanden
i løbet af et par måneder, og så er der to værktøjer at vedligeholde.

Hvad der laves om:
  * sproget i brugerfladen og i begge eksportskabeloner
  * kategorierne, størrelsesrækkerne og farvekortet
  * sprog- og valutavælgeren i shoppens topbjælke, og flaget
  * SKUS tømmes — byg_katalog_fra_demo.py --market us fylder det amerikanske
    sortiment i bagefter

Kør begge trin fra repo-roden:
    python3 byg_us_builder.py
    python3 byg_katalog_fra_demo.py --market us

Rammer en oversættelse ikke, siger scriptet til frem for at skrive en fil
med halvt dansk i. Det sker når teksten er rettet i index.html — så ret
teksten her i listen, ikke i us/index.html.
"""

import re
import sys
from pathlib import Path

KILDE = Path("index.html")
MAAL = Path("us/index.html")

# ── Kategorier, størrelser, farver ────────────────────────────────────────

US_CATS = '''const CATS=[
  {key:"merchandise",name:"Merchandise"},
  {key:"apparel",name:"Apparel",caret:true},
  {key:"bags",name:"Bags",caret:true},
  {key:"onboarding",name:"Onboarding"}
];'''

# Den amerikanske demo har ingen bukser og ingen sko, men den har caps og
# muleposer som selvstændige familier.
US_SIZES = '''const SIZES={sweat:["XS","S","M","L","XL","2XL","3XL"],polo:["XS","S","M","L","XL","2XL","3XL"],
 tshirt:["XS","S","M","L","XL","2XL","3XL"],jacket:["XS","S","M","L","XL","2XL","3XL"],
 vest:["XS","S","M","L","XL","2XL"],knit:["XS","S","M","L","XL","2XL"],
 shirt:["S","M","L","XL","2XL"],sport:["XS","S","M","L","XL"],
 cap:["One size"],tote:["One size"],bag:["One size"]};'''

# Farver den amerikanske shop bruger, som ikke står i det danske kort.
# Samme tabel ligger i US_PALETTE i markeder.py — hold dem ens.
US_SWATCH_EKSTRA = ('"Royal Blue":"#2b4ea8","Blue":"#2f5fa8","Cobalt Blue":"#1f4fa0",'
                    '"Natural":"#e8dcc8","Clear":"#e6edf0","Charcoal":"#43484d",'
                    '"Vanilla":"#f0e6d2",')

US_FAM = '''const FAM_DA={pen:"Pens",notebook:"Notebooks",bottle:"Bottles",mug:"Mugs",umbrella:"Umbrellas",
 tote:"Tote bags",lanyard:"Lanyards",cap:"Headwear",tech:"Tech",bag:"Bags",food:"Treats",
 gift:"Gifts",sweat:"Sweatshirts",polo:"Polo shirts",tshirt:"T-shirts",jacket:"Jackets",
 vest:"Vests",knit:"Knitwear",shirt:"Dress shirts",pants:"Pants",sport:"Sportswear",shoes:"Shoes"};'''

# Det amerikanske flag i topbjælken, i samme lille format som det danske.
US_FLAG = ('<svg class="flag" viewBox="0 0 16 12" aria-hidden="true">'
           '<rect width="16" height="12" fill="#b22234"></rect>'
           '<rect y="1.5" width="16" height="1.5" fill="#fff"></rect>'
           '<rect y="4.5" width="16" height="1.5" fill="#fff"></rect>'
           '<rect y="7.5" width="16" height="1.5" fill="#fff"></rect>'
           '<rect y="10.5" width="16" height="1.5" fill="#fff"></rect>'
           '<rect width="7" height="6.5" fill="#3c3b6e"></rect></svg>')

DK_FLAG = re.compile(r'<svg class="flag"[^>]*>.*?</svg>', re.S)


# ── Oversættelser ─────────────────────────────────────────────────────────
#
# (dansk, engelsk, forventet_antal). Antallet er med vilje: rammer en
# tekst flere gange end ventet, er søgestrengen for løs og kan ramme noget
# den ikke skal.

TEKSTER = [
    # Topbjælken
    ('<label for="co">Kunde</label>', '<label for="co">Client</label>', 1),
    ('<label for="cat">Kategori</label>', '<label for="cat">Category</label>', 1),
    ('<span class="dot"></span>Mørk<input', '<span class="dot"></span>Dark<input', 2),
    ('<span class="dot"></span>Lys<input', '<span class="dot"></span>Light<input', 2),
    ('id="bNew">Ny kunde<', 'id="bNew">New client<', 1),
    ('id="bSetup">Kort<', 'id="bSetup">Map<', 1),
    ('id="bPrev">Vis ren<', 'id="bPrev">Preview<', 1),
    ('id="bExp">Eksportér shop<', 'id="bExp">Export shop<', 1),
    ('id="bSheet">Kundeoversigt<', 'id="bSheet">Client overview<', 1),

    # Kort-skuffen
    ('<p>Placeringskortet hører til <b>varen</b>, ikke kunden. Dubletter gemmes med hver sin '
     'placering, så du kan vise samme model i flere farver med forskellige tryk. Kopiér kortet '
     'én gang og genbrug det på hver prospect.</p>',
     '<p>The placement map belongs to the <b>item</b>, not the client. Duplicates keep their own '
     'placement, so you can show one model in several colors with different decoration. Copy the '
     'map once and reuse it on every prospect.</p>', 1),
    ('placeholder="Placeringskort (JSON)"', 'placeholder="Placement map (JSON)"', 1),
    ('id="bCopy">Kopiér kort<', 'id="bCopy">Copy map<', 1),
    ('id="bLoad">Indlæs kort<', 'id="bLoad">Load map<', 1),
    ('id="bReset">Nulstil<', 'id="bReset">Reset<', 1),

    # Tom inspektør
    ('<p>Klik en vare for at placere logoet. Dupliker en vare for at vise samme model i flere '
     'farver, hver med sin egen placering.</p>',
     '<p>Click an item to place the logo. Duplicate an item to show the same model in several '
     'colors, each with its own placement.</p>', 1),
    ('<li>Upload logo 1 og 2, mørk og lys</li>', '<li>Upload logo 1 and 2, dark and light</li>', 1),
    ('<li>Vælg kategori og farve</li>', '<li>Pick category and color</li>', 1),
    ('<li>Træk logoet på plads</li>', '<li>Drag the logo into place</li>', 1),
    ('<li>Dupliker for flere farvevarianter</li>', '<li>Duplicate for more colorways</li>', 1),
    ('<li>Eksportér ren shop</li>', '<li>Export the clean shop</li>', 1),

    # Inspektøren
    ('<h3>Farve</h3>', '<h3>Color</h3>', 1),
    ('<h3>Placering</h3>', '<h3>Placement</h3>', 1),
    ('<h3>Vare</h3>', '<h3>Item</h3>', 1),
    ('class="lbl">Vandret<', 'class="lbl">Horizontal<', 1),
    ('class="lbl">Lodret<', 'class="lbl">Vertical<', 1),
    ('class="lbl">Størrelse<', 'class="lbl">Size<', 1),
    ('class="lbl">Hurtig<', 'class="lbl">Quick<', 1),
    ('class="lbl">Dækning<', 'class="lbl">Opacity<', 1),
    ('class="lbl">Krumning<', 'class="lbl">Curvature<', 1),
    ('class="lbl">Tryk<', 'class="lbl">Decoration<', 1),
    ('class="lbl">Plade<', 'class="lbl">Plate<', 1),
    ('class="lbl">Logo på<', 'class="lbl">Logo on<', 1),
    ('class="lbl">Med i shop<', 'class="lbl">In shop<', 1),
    ('<button data-c="0">Flad</button><button data-c="1">Rundt om</button>',
     '<button data-c="0">Flat</button><button data-c="1">Wrap</button>', 1),
    ('<button data-m="0">Farve</button><button data-m="1">Sort/hvid</button>',
     '<button data-m="0">Color</button><button data-m="1">Mono</button>', 1),
    ('<button data-i="0">Auto</button><button data-i="1">Invertér</button>',
     '<button data-i="0">Auto</button><button data-i="1">Invert</button>', 1),
    ('<button data-l="1">Ja</button><button data-l="0">Nej</button>',
     '<button data-l="1">Yes</button><button data-l="0">No</button>', 1),
    ('<button data-n="1">Ja</button><button data-n="0">Nej</button>',
     '<button data-n="1">Yes</button><button data-n="0">No</button>', 1),
    ('id="bDup">Dupliker vare<', 'id="bDup">Duplicate item<', 1),
    ('id="bDel">Fjern dublet<', 'id="bDel">Remove duplicate<', 1),
    ('id="bPdp">Åbn produktside<', 'id="bPdp">Open product page<', 1),
    ('id="bCat2">Kopiér til gruppe<', 'id="bCat2">Copy to group<', 1),
    ('id="bRes">Nulstil<', 'id="bRes">Reset<', 1),
    ('Træk logoet på billedet. <kbd>←↑↓→</kbd> nudger, <kbd>+</kbd><kbd>−</kbd> skalerer, '
     '<kbd>[</kbd><kbd>]</kbd> roterer, <kbd>D</kbd> duplikerer, <kbd>Esc</kbd> lukker.',
     'Drag the logo on the image. <kbd>←↑↓→</kbd> nudges, <kbd>+</kbd><kbd>−</kbd> scales, '
     '<kbd>[</kbd><kbd>]</kbd> rotates, <kbd>D</kbd> duplicates, <kbd>Esc</kbd> closes.', 1),
    ('id="exit">Tilbage til redigering<', 'id="exit">Back to editing<', 1),

    # Shoppens egen krom — står både i værktøjet og i shop-eksporten
    ('aria-label="Søg"', 'aria-label="Search"', 2),
    ('<span>Opret konto / Log ind</span>', '<span>Create account / Sign in</span>', 2),
    ('<a href="#">Opret konto / Log ind</a>', '<a href="#">Create account / Sign in</a>', 2),
    ('<a href="#">Kontakt os</a>', '<a href="#">Contact us</a>', 2),
    ('<a href="#">Vilkår og betingelser</a>', '<a href="#">Terms and conditions</a>', 2),
    ('<a href="#">Forespørgsel</a>', '<a href="#">Enquiry</a>', 2),
    ('<a href="#">Cookies og datasikkerhed</a>', '<a href="#">Cookies and data privacy</a>', 2),
    ('<h4>Kundeservice</h4>', '<h4>Customer service</h4>', 2),
    ('<h4>Kontakt oplysninger</h4>', '<h4>Contact details</h4>', 2),
    ('<h4 id="footTitle">Om Metz</h4>', '<h4 id="footTitle">About Metz</h4>', 1),
    ('<h4>Om ${co}</h4>', '<h4>About ${co}</h4>', 1),
    ('<li>CVR: 27171508</li>', '<li>Company reg. 27171508</li>', 2),
    ('CVR 27171508 · metz.dk', 'Company reg. 27171508 · metz.dk', 1),
    ('Webshoppen udbydes i samarbejde med Metz A/S. Metz står for IT-hosting, drift og '
     'lagerstyring af mere end 200 kundespecifikke webshops.',
     'The webshop is operated in partnership with Metz A/S, who handle hosting, operations and '
     'inventory for more than 200 client-specific webshops.', 2),
    ('el("footTitle").textContent="Om "+DEFAULT_CO;',
     'el("footTitle").textContent="About "+DEFAULT_CO;', 1),

    # Sorteringsbjælken
    ('<label>Sortér efter:</label>', '<label>Sort by:</label>', 1),
    ('<option>Standard</option><option>Nyeste</option><option>Pris lav-høj</option>'
     '<option>Pris høj-lav</option><option>Titel</option><option>Brand</option>',
     '<option>Default</option><option>Newest</option><option>Price low-high</option>'
     '<option>Price high-low</option><option>Title</option><option>Brand</option>', 1),

    # Mærkater på produktkortet i værktøjet
    ('b.textContent="Fravalgt"', 'b.textContent="Excluded"', 1),
    ('b.textContent="Dublet"', 'b.textContent="Duplicate"', 1),
    ('b.textContent="Placeret"', 'b.textContent="Placed"', 1),
    ('b.textContent=dup?"Dublet":"Standard"', 'b.textContent=dup?"Duplicate":"Default"', 1),

    # Produktsiden — står to gange: i værktøjet og i shop-eksporten
    ('"Kontakt os for pris og mindsteantal"', '"Contact us for price and minimums"', 2),
    ('"Pris ekskl. moms"', '"Price excl. tax"', 2),
    ('" · logotryk inkluderet"', '" · logo decoration included"', 2),
    ('"Send forespørgsel":"Læg i kurv"', '"Send enquiry":"Add to cart"', 2),
    ('<h4>Størrelse</h4>', '<h4>Size</h4>', 2),
    ('<h4>Farve: ${esc(sku.colour)}</h4>', '<h4>Color: ${esc(sku.colour)}</h4>', 2),
    ('<b>Varenr.</b>', '<b>Item no.</b>', 2),
    ('<b>Materiale</b>', '<b>Material</b>', 2),
    ('<b>Levering</b>', '<b>Delivery</b>', 2),
    ('"Bestilles hjem"', '"Made to order"', 2),
    ('<b>Tryk</b>', '<b>Decoration</b>', 2),
    ('"Logo påføres i én farve (gravering/debossering)"',
     '"Logo applied in one color (engraving/debossing)"', 2),
    ('"Logo påføres af Metz før forsendelse"', '"Logo applied by Metz before shipping"', 2),
    ('"Leveres uden logo — branding på emballage"',
     '"Ships without a logo — branding on the packaging"', 2),
    ('Standardvare fra ${esc(m.brand)}, leveret gennem ${co}s Metz Studio-webshop. Alle varer '
     'påføres jeres logo efter gældende designmanual, og lagerføres af Metz, så afdelinger kan '
     'bestille direkte uden at binde kapital i varelager.',
     'Stock item${m.brand?` from ${esc(m.brand)}`:""}, supplied through the Metz Studio webshop '
     'for ${co}. Every item is decorated with your logo to your brand guidelines and held in stock '
     'by Metz, so teams can order directly without tying up capital in inventory.', 1),
    ('content:"Billede utilgængeligt"', 'content:"Image unavailable"', 1),
    ("""<div class="desc">Standardvare fra ${esc(m.brand)}, leveret gennem ${esc(state.company)}s
          Metz Studio-webshop. Alle varer påføres jeres logo efter gældende designmanual, og
          lagerføres af Metz, så afdelinger kan bestille direkte uden at binde kapital i varelager.</div>""",
     """<div class="desc">Stock item${m.brand?` from ${esc(m.brand)}`:""}, supplied through the
          Metz Studio webshop for ${esc(state.company)}. Every item is decorated with your logo to your
          brand guidelines and held in stock by Metz, so teams can order directly without tying up
          capital in inventory.</div>""", 1),
    ('← Tilbage til ${esc(c.name)}', '← Back to ${esc(c.name)}', 2),
    ('>Forside</a>', '>Home</a>', 3),
    ('Ingen produkter i denne kategori endnu.', 'No products in this category yet.', 2),

    # Kundeoversigten
    ('<title>${co} — Produktudvalg</title>', '<title>${co} — Product selection</title>', 1),
    ('<title>Metz Studio · Brand Builder</title>', '<title>Metz Studio · Brand Builder (US)</title>', 1),
    ('toLocaleDateString("da-DK"', 'toLocaleDateString("en-US"', 1),
    ('<b>Produktudvalg til ${co}</b>', '<b>Product selection for ${co}</b>', 1),
    ('${inc.length} varer', '${inc.length} items', 1),
    ('Priser er vejledende og ekskl. moms.<br>Logotryk er inkluderet i prisen hvor intet andet '
     'er angivet.',
     'Prices are indicative and exclude tax.<br>Logo decoration is included unless stated '
     'otherwise.', 1),

    # Kvitteringer og dialoger
    ('flash("bDup","Duplikeret")', 'flash("bDup","Duplicated")', 1),
    ('flash("bCopy","Kopieret")', 'flash("bCopy","Copied")', 1),
    ('flash("bCopy","Markeret")', 'flash("bCopy","Selected")', 1),
    ('flash("bLoad",`Indlæst ${out.length}`)', 'flash("bLoad",`Loaded ${out.length}`)', 1),
    ('flash("bLoad","Ugyldig JSON")', 'flash("bLoad","Invalid JSON")', 1),
    ('flash("bReset","Nulstillet")', 'flash("bReset","Reset")', 1),
    ('flash("bExp","Eksporteret")', 'flash("bExp","Exported")', 1),
    ('flash("bSheet","Hentet")', 'flash("bSheet","Downloaded")', 1),
    ('flash("bCat2",n?`Kopieret til ${n}`:"Ingen andre")',
     'flash("bCat2",n?`Copied to ${n}`:"No others")', 1),
    ('"Ryd kunde? Logoer, navn og farve nulstilles. Husets placeringskort beholdes."',
     '"Clear client? Logos, name and color are reset. The house placement map is kept."', 1),
    ('el("bPdp").textContent=state.pdp===i?"Tilbage til oversigt":"Åbn produktside"',
     'el("bPdp").textContent=state.pdp===i?"Back to grid":"Open product page"', 1),
    ('state.company=el("co").value||"Kunde"', 'state.company=el("co").value||"Client"', 1),
    ('el("tally").textContent=`${n} varer · ${p} placeret`;',
     'el("tally").textContent=`${n} items · ${p} placed`;', 1),
    ('`${artOf(SKUS[t.sku])} · ${m.skus.length} farve${m.skus.length>1?"r":""}`',
     '`${artOf(SKUS[t.sku])} · ${m.skus.length} color${m.skus.length>1?"s":""}`', 1),
    ('` · logo ${t.set==="b"?"2":"1"} mangler`', '` · logo ${t.set==="b"?"2":"1"} missing`', 1),
    ('` · ${sibs} varianter i shop`', '` · ${sibs} variants in shop`', 1),
    ('${pf.v==="light"?"lys":"mørk"} plade', '${pf.v==="light"?"light":"dark"} plate', 1),
]


def main():
    if not KILDE.exists():
        sys.exit(f"Mangler {KILDE} — kør scriptet fra repo-roden.")
    html = KILDE.read_text(encoding="utf-8")

    # SKUS tømmes. byg_katalog_fra_demo.py --market us fylder det amerikanske
    # sortiment i bagefter, så produktdata aldrig går gennem oversættelsen.
    start = html.index("[", html.index("const SKUS = "))
    dybde = 0
    for j in range(start, len(html)):
        if html[j] == "[":
            dybde += 1
        elif html[j] == "]":
            dybde -= 1
            if dybde == 0:
                html = html[:start] + "[]" + html[j + 1:]
                break

    fejl = []

    def erstat(gammel, ny, ventet):
        nonlocal html
        fundet = html.count(gammel)
        if fundet != ventet:
            fejl.append(f"{fundet} af {ventet} træf: {gammel[:70]!r}")
            if fundet == 0:
                return
        html = html.replace(gammel, ny)

    # Tabellerne først
    for gammel_start, ny in ((("const CATS=["), US_CATS),
                             (("const SIZES={"), US_SIZES),
                             (("const FAM_DA={"), US_FAM)):
        i = html.find(gammel_start)
        if i < 0:
            fejl.append(f"fandt ikke {gammel_start!r}")
            continue
        j = html.index("};" if gammel_start.endswith("{") else "];", i) + 2
        html = html[:i] + ny + html[j:]

    # Farvekortet udvides frem for at blive skrevet om — de danske farver
    # skal blive, fordi en amerikansk shop også sælger "Navy" og "White".
    if 'const SWATCH={"White"' in html:
        html = html.replace('const SWATCH={"White"', 'const SWATCH={' + US_SWATCH_EKSTRA + '"White"', 1)
    else:
        fejl.append("fandt ikke SWATCH")

    for gammel, ny, antal in TEKSTER:
        erstat(gammel, ny, antal)

    # Sprog, valuta og flag i shoppens topbjælke
    html = html.replace('<html lang="da">', '<html lang="en">')
    html = DK_FLAG.sub(US_FLAG, html)
    erstat('</svg>da<span class="caret">', '</svg>en<span class="caret">', 2)
    erstat('</svg>dkk<span class="caret">', '</svg>usd<span class="caret">', 2)

    # Versionsnummeret skal kunne skelnes fra det danske i en fejlmelding.
    html = re.sub(r'const VERSION = "([^"]+)";', r'const VERSION = "\1 US";', html, count=1)

    if fejl:
        print("!! Oversættelser der ikke ramte som forventet:\n")
        for f in fejl:
            print("   ", f)
        print("\nTeksten er sandsynligvis rettet i index.html. Ret søgestrengen i")
        print("TEKSTER her i scriptet — ikke i us/index.html, den bliver overskrevet.")
        sys.exit(1)

    MAAL.parent.mkdir(parents=True, exist_ok=True)
    MAAL.write_text(html, encoding="utf-8")
    tilbage = len(re.findall(r"[æøåÆØÅ]", html))
    print(f"Skrevet {MAAL} ({len(html):,} tegn).")
    print(f"{len(TEKSTER)} tekster oversat. {tilbage} danske tegn tilbage i filen.")
    print("\nNæste skridt:  python3 byg_katalog_fra_demo.py --market us")


if __name__ == "__main__":
    main()
