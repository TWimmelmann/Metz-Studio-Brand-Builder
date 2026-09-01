# Metz Studio Brand Builder

Internt salgsværktøj. Viser en prospects eget logo på en realistisk mock-up af den
webshop vi ville bygge til dem, og eksporterer den som en færdig side vi kan sende
eller hoste.

**Live:** https://metz-studio-brand-builder.vercel.app/

Vercel bygger fra `main`. Ligger en ændring kun på en lokal gren, sker der
ikke noget — den skal pushes og merges til `main`, før den er live.

---

## Filer

| Fil | Hvad det er |
|---|---|
| `index.html` | Hele værktøjet. Katalog, kode og styling i én fil. |
| `catalogue.json` | Katalogdata som selvstændig fil. Bruges **ikke** af værktøjet — se nedenfor. |
| `opdater_katalog.py` | Henter demoshoppens sortiment over HTTP og **tilføjer** nye varer begge steder. |
| `byg_katalog_fra_demo.py` | Bygger kataloget **forfra** ud fra rå-udtræk i `.scrape/`, i demoens egen visningsrækkefølge. |
| `.scrape/*.json` | Rå-udtrækkene. Én liste pr. vare: varenummer, navn, brand, materiale, pris, lager, billed-hale. |
| `README.md` | Denne fil. |

### Hvorfor alt ligger i én fil

Jeg foreslog først at splitte kataloget ud i `catalogue.json` og hente det med
`fetch()`. Det virker ikke: åbner man filen lokalt med dobbeltklik, blokerer
browseren `fetch()` mod `file://`, og siden står tom. Da værktøjet skal kunne
bruges offline hos en kunde uden wifi, ligger kataloget i stedet inde i
`index.html`.

`catalogue.json` ligger med i repoet som læsbar kilde — til at slå varenumre op,
og som datagrundlag hvis værktøjet på et tidspunkt bygges om til en rigtig app.
**Retter du i `catalogue.json` sker der ingenting.** Katalogændringer skal ind i
`SKUS`-arrayet i `index.html`.

### To måder at opdatere kataloget

**Har shoppen fået nye varer, og skal de bare med?** Brug `opdater_katalog.py`.
Den henter shoppen over HTTP og lægger det nye i bunden af kataloget.

**Skal kataloget matche demoen fuldstændigt — samme varer, samme rækkefølge?**
Brug `byg_katalog_fra_demo.py`. To ting kan ikke hentes over HTTP:

* **Rækkefølgen.** Shoppen sorterer produktgitteret i browseren efter
  `data-sort-number`. Den orden serveren leverer HTML i er altså ikke den orden
  kunden ser — på merchandise-siden ligger Lucia-pennen først i HTML'en, men
  Parker Jotter først på skærmen.
* **Lagerteksten.** "På lager: 25.228 stk" skrives ind af shoppens eget
  javascript efter sideindlæsning. Et rent HTTP-hent får kun den skjulte
  "Forventet på lager"-dato.

Derfor tages udtrækkene i en browser på den færdigtegnede side og lægges i
`.scrape/`. Scriptet læser dem og skriver `SKUS` + `catalogue.json` forfra:

```
python3 byg_katalog_fra_demo.py --dry-run
python3 byg_katalog_fra_demo.py
```

`.scrape/subcats.json` er varenumrene pr. underkategori. Den fil er det, der
giver en "Brownsville Unisex" familien `sweat` frem for et gæt ud fra navnet —
og dermed den rigtige logoplacering.

### Opdatering af kataloget (den gamle vej)

```
pip3 install requests beautifulsoup4
python3 opdater_katalog.py --dry-run    # vis hvad der ville ske
python3 opdater_katalog.py              # skriv begge filer
```

Scriptet skriver både `SKUS` i `index.html` og `catalogue.json`, så de to aldrig
kommer ud af trit.

**Farvekortet ligger to steder og skal holdes ens:** `PALETTE` i
`opdater_katalog.py` og `SWATCH` i `index.html`. Tabellen gør to ting. Den giver
farveprikken på produktkortet sin farve, og den afgør ud fra farvens lysstyrke
om logoet skal trykkes i den mørke eller den lyse plade. Mangler en farve i
tabellen, står prikken grå og logoet gætter — så tilføj nye farvenavne begge
steder. Scriptet skriver dem ud til sidst i kørslen, så du ved hvilke der mangler.

En vare er identificeret ved **kategori + model + farve**. Det er den nøgle
scriptet dedupliker på, og den nøgle værktøjet grupperer farvevarianter efter.
Ændrer shoppen et produktfoto eller en stavemåde, kommer varen derfor ikke ind
som en ny, løs vare ved siden af sig selv.

---

## Deploy på Vercel

Engangsopsætning, cirka ti minutter.

1. Opret et GitHub-repo, fx `metz-studio-builder`, og læg de tre filer i roden.
2. Log ind på vercel.com med GitHub-kontoen.
3. **Add New → Project**, vælg repoet.
4. Framework Preset: **Other**. Ingen build command, ingen output directory —
   det er ren HTML.
5. **Deploy**.

Derefter: hvert push til `main` er live cirka 30 sekunder senere. Ingen upload,
ingen versionsforvirring.

**Subdomæne.** Spørg IT om `studio.metz.dk` i stedet for `...vercel.app`. Det
tager dem få minutter (en CNAME), og det er forskellen på om en prospect opfatter
det som et produkt eller et hobbyprojekt.

---

## Sådan rettes en fejl

Alt ligger i `index.html`. Strukturen er:

```
<style>      linje ~10-450     shop-CSS først, derefter editor-CSS
<div id=bench>                 topbjælken
<div id=insp>                  højre panel
<div class=shop>               selve shoppen
<script>                       al logik, ~700 linjer
```

I scriptet, i rækkefølge:

| Blok | Ansvar |
|---|---|
| `VERSION`, `PRESET` | versionsnummer og husets placeringskort |
| `SKUS` | katalogdata, 469 varer |
| `CATS`, `SWATCH`, `SIZES` | kategorier, farvekoder, størrelsesrækker |
| `swatchOf`, `skuIsDark` | slår farven op og afgør om logoet skal være lyst |
| `MODELS` | grupperer varenumre til modeller |
| `FAMILY` | standardplacering pr. varetype |
| `mkItem`, `baseItems` | opretter varerne på hylden |
| `plateFor`, `stampStyle` | vælger logoplade og beregner trykket |
| `render`, `paint`, `pdpHtml` | tegner gitter og produktsider |
| `select` og handlers | inspektøren |
| `buildExport` | genererer den statiske eksportfil |

Deploy et fix ved at pushe. Går noget galt, har Vercel hver tidligere version
gemt — rollback er ét klik under Deployments.

Ret `VERSION` når du laver en ændring. Nummeret vises i topbjælken, så en kollega
kan sige hvilken version fejlen optrådte i.

---

## Standardværdier

Øverst i scriptet:

```js
const DEFAULT_CO     = "Metz";
const DEFAULT_ACCENT = "#1a1a1a";
const METZ_LOGO      = "data:image/png;base64,...";
```

`METZ_LOGO` vises i toppen af kundeoversigten. Skal logoet skiftes: **beskær al
hvid luft omkring logoet først.** Et logo med luft omkring bliver optisk lille,
uanset hvor stor kassen er — luften skalerer med. Gem som PNG med transparent
baggrund, konvertér til base64 og indsæt hele strengen.

Bruges både ved opstart og ved **Ny kunde**. Ret dem ét sted.

---

## Husets placeringskort

Hvor logoet sidder på en Lucia-pen er ens for alle kunder. Derfor sættes det op
**én gang** og bages ind i filen, så ingen sælger skal indsætte JSON.

1. Åbn værktøjet og sæt placeringerne som de skal være.
2. **Kort → Kopiér kort**.
3. Åbn `index.html`, find linjen `const PRESET = null;` (omkring linje 390).
4. Erstat `null` med det kopierede — behold semikolon til sidst:
   `const PRESET = {"v":5,"items":[...]};`
5. Push.

Nu åbner værktøjet færdigopsat for alle. **Nulstil** stiller tilbage til dette
kort, ikke til råt udgangspunkt.

Bliver kortet ugyldigt, falder værktøjet tilbage på familie-standarderne og
skriver en advarsel i browserkonsollen. Det går altså aldrig i sort.

---

## Sådan bruges det

Værktøjet **gemmer intet**. Ingen konto, ingen cookies, ingen server. Hver gang
siden åbnes, starter den forfra. To sælgere kan arbejde samtidig uden at se
hinandens ting.

Skal du skifte kunde midt i det hele, brug **Ny kunde** i topbjælken. Den rydder
navn, farve og alle fire logoer, men beholder husets placeringskort.

Arbejdsgangen pr. prospect:

1. Skriv kundenavn, vælg accentfarve. Værktøjet starter på **Metz** med sort
   accent — det er skabelonen, ikke en kunde.
2. Upload logoer. Logo 1 mørk og lys som minimum — den lyse bruges automatisk på
   mørke varer, ellers forsvinder logoet. Logo 2 er til et sekundært mærke.
3. Vælg kategori, vælg farver der matcher kundens brand.
4. **Dupliker vare** hvis samme model skal vises i flere farver. Dubletten får sin
   egen placering.
5. **Med i shop → Nej** på alt der ikke passer. Skær ned til 15-25 varer — et
   kurateret udvalg sælger bedre end 171 varer.
6. Vælg output:
   - **Kundeoversigt** — de valgte varer med logo på, farvevarianter og priser,
     grupperet efter kategori. Metz-logo i toppen, kundens navn i overskriften.
     Flyder over flere sider ved print. ~25 KB ved 18 varer, ~60 KB ved 60.
   - **Eksportér shop** — den fulde webshop-mock-up med kategorier og
     produktsider. Bruges til demo på skærm, ikke til at maile.

### Del med kunden

**Nemmest: PDF.** Åbn kundeoversigten, tryk `Cmd/Ctrl + P` og vælg *Gem som PDF*.
Siden har et printark bygget ind: A4, tre varer i bredden, og den brækker aldrig
et produkt over to sider. PDF'en kan hænges ved i en mail, printes til et møde og
åbnes af enhver. Ingen opsætning, intet link.

**Vil du hellere sende et link:** filen skal hostes. Opret en mappe `shops/` i
repoet, læg filen som `shops/bain.html`, push, og kunden kan åbne
`.../shops/bain.html`. Det kræver skriveadgang til repoet for den enkelte sælger.

Hostede filer ligger frit tilgængelige for den, der har linket. Sidefilen har
`noindex`, så den ikke ender i Google, men det er ikke adgangskontrol.

Enten som vedhæftet fil, eller — bedre — lagt op så kunden får et link.
Opret en mappe `shops/` i repoet, læg filen som `shops/bain.html`, push, og
kunden kan åbne `.../shops/bain.html`.

Bemærk: hostede eksporter ligger frit tilgængelige for den der har linket.
Sidefilen har `noindex`, så den ikke ender i Google, men det er ikke adgangs-
kontrol. Skal en kundes logo holdes lukket, så send filen i stedet.

---

## Det du skal vide

**Billeder hentes live fra `img.metz.dk`.** Eksporten kræver internet, og hvis
Metz flytter eller omdøber billederne, går gamle eksporter i sort. Filen selv
forbliver lille.

**Trykket er en flad plade med blend mode.** Overbevisende på penne, flasker,
notesbøger, tasker og fladtliggende beklædning. Det bliver aldrig rigtigt på en
blank kromkuglepen eller et foto af en vare på en model — det skal løses med
bedre fotos, ikke med kode.

**Kataloget er 1:1 med demoshoppen** pr. 1. september 2026: 586 varenumre i
demoens egen rækkefølge, hentet fra det færdigtegnede gitter. Den gamle
afkortning af beklædningssiden er væk — alle 344 beklædningsvarer er med.

**Onboarding er med som kategori.** Demoen har den, og dens varer er de samme
varenumre som i Merchandise. Det giver med vilje dubletter på tværs af de to
kategorier — sådan er demoen bygget.

**Gitteret viser én model pr. kort, ikke én farve pr. kort.** Demoen viser hver
farve som sit eget kort; værktøjet samler farverne på ét kort med farveprikker,
fordi det er den enhed sælgeren placerer et logo på og duplikerer. Det er den
ene bevidste afvigelse fra demoens udseende.

**Kuratér før du deler.** Med alle 171 varer fylder shop-eksporten ~850 KB.
Skåret ned til 15-25 varer bliver kundeoversigten omkring 25 KB — og pitchet
skarpere.
