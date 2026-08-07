# Metz Studio Brand Builder

Internt salgsværktøj. Viser en prospects eget logo på en realistisk mock-up af den
webshop vi ville bygge til dem, og eksporterer den som en færdig side vi kan sende
eller hoste.

**Live:** _(indsæt URL når den er deployet)_

---

## Filer

| Fil | Hvad det er |
|---|---|
| `index.html` | Hele værktøjet. Katalog, kode og styling i én fil. |
| `catalogue.json` | Katalogdata som selvstændig fil. Bruges **ikke** af værktøjet — se nedenfor. |
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
| `SKUS` | katalogdata, 326 varer |
| `CATS`, `SWATCH`, `SIZES` | kategorier, farvekoder, størrelsesrækker |
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

**Beklædningssiden blev afkortet under hentningen.** Der mangler et mindre antal
varer i bunden, bl.a. nogle Tee Jays-poloer og Untagged movement-t-shirts.

**Kuratér før du deler.** Med alle 171 varer fylder shop-eksporten ~850 KB.
Skåret ned til 15-25 varer bliver kundeoversigten omkring 25 KB — og pitchet
skarpere.
