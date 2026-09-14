/* ═══════════════════════════════════════════════════════════════════════
   udtraek.js — henter sortimentet ud af en demoshop.

   Kør den i browserens konsol på en kategoriside. Hvorfor i browseren og
   ikke over HTTP: shoppen sorterer produktgitteret efter data-sort-number
   i browseren, og lagerteksten ("In stock 6.253 pcs.") skrives ind af
   shoppens eget javascript efter sideindlæsning. Et rent HTTP-hent får
   altså både den forkerte rækkefølge og en tom lagerkolonne.

   SÅDAN GØR DU
   1. Åbn shoppen og gå til den første kategoriside.
   2. F12 → Console → indsæt hele filen her → Enter.
   3. Kør   udtraek("merchandise")   — kategorinavnet er det navn filen
      skal have, altså det der står i "kilder" i markeder.py.
   4. Gå til næste kategori, indsæt filen igen, kør udtraek("apparel") osv.
      Udtrækkene samler sig i browserens localStorage undervejs.
   5. Til sidst: kør   udtraekUnderkategorier([...])   med stierne fra
      markeder.py, og derefter   gem()   — den lægger en samlet JSON-fil
      i Downloads.
   6. python3 udtraek_til_scrape.py ~/Downloads/us-scrape.json --ud .scrape-us
      python3 byg_katalog_fra_demo.py --market us --dry-run

   Felterne pr. vare, i den rækkefølge byg_katalog_fra_demo.py læser dem:
   [varenummer, navn, brand, materiale, pris, lager, billed-hale]
   ═══════════════════════════════════════════════════════════════════════ */

const NOEGLE = "__usScrape";

/* Lagerteksten kommer efter sideindlæsning. Uden at vente på den står
   lagerkolonnen tom for hele kategorien — og det opdager man først når
   produktsiden i værktøjet siger "Made to order" på alt. */
async function ventPaaLager() {
  for (let i = 0; i < 40; i++) {
    const felter = [...document.querySelectorAll(".js-stock")];
    if (felter.length && felter.filter(e => e.textContent.trim()).length >= felter.length * 0.95)
      return true;
    await new Promise(r => setTimeout(r, 500));
  }
  console.warn("Lagerteksten kom ikke inden for 20 sekunder — tjek udtrækket.");
  return false;
}

function laesGitter() {
  /* Billeder er lazy-loaded. De der aldrig kom i syne har ingen src, og
     varen ville ryge ind i kataloget uden billede. */
  document.querySelectorAll('img[loading="lazy"]').forEach(i => (i.loading = "eager"));

  return [...document.querySelectorAll(".js-product-teaser")].map(t => {
    const img = t.querySelector("img");
    const src = img ? (img.getAttribute("src") || img.getAttribute("data-src") || "") : "";
    const hale = src.match(/f=auto\/(.+)$/);
    const tekst = sel => {
      const e = t.querySelector(sel);
      return e ? e.textContent.replace(/\s+/g, " ").trim() : "";
    };
    return [
      t.dataset.productNumber || "",
      (t.dataset.name || tekst(".card-title")).trim(),
      (t.dataset.brand || "").trim(),
      tekst(".card-body > p"),
      tekst(".customer-price"),
      tekst(".js-stock"),
      hale ? hale[1] : ""
    ].join("|;|");
  });
}

async function udtraek(kategori) {
  await ventPaaLager();
  const raekker = laesGitter();
  const gemt = JSON.parse(localStorage.getItem(NOEGLE) || "{}");
  gemt[kategori] = raekker;
  localStorage.setItem(NOEGLE, JSON.stringify(gemt));

  const udenBillede = raekker.filter(r => !r.split("|;|")[6]).length;
  const udenLager = raekker.filter(r => !r.split("|;|")[5]).length;
  console.log(`${kategori}: ${raekker.length} varer`
    + (udenBillede ? `  !! ${udenBillede} uden billede` : "")
    + (udenLager ? `  !! ${udenLager} uden lagertekst` : ""));
  console.log("gemt indtil nu:", Object.keys(gemt).join(", "));
  return raekker.length;
}

/* Underkategorierne bruges kun til at slå familien op — altså hvor logoet
   lander som standard. Der skal kun varenumre ud, og de står i serverens
   HTML, så de kan hentes uden at åbne hver side. */
async function udtraekUnderkategorier(stier) {
  const rod = location.pathname.split("/categories/")[0] + "/categories/";
  const ud = {};
  for (const sti of stier) {
    const html = await fetch(rod + sti, { credentials: "same-origin" }).then(r => r.text());
    const doc = new DOMParser().parseFromString(html, "text/html");
    ud[sti] = [...doc.querySelectorAll(".js-product-teaser")]
      .map(t => t.dataset.productNumber).filter(Boolean);
    console.log(`  ${sti}: ${ud[sti].length}`);
  }
  const gemt = JSON.parse(localStorage.getItem(NOEGLE) || "{}");
  gemt.__subcats = ud;
  localStorage.setItem(NOEGLE, JSON.stringify(gemt));
  return ud;
}

function gem(filnavn = "us-scrape.json") {
  const gemt = localStorage.getItem(NOEGLE);
  if (!gemt) return console.error("Der er intet gemt endnu.");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([gemt], { type: "application/json" }));
  a.download = filnavn;
  document.body.appendChild(a); a.click(); a.remove();
  console.log("Hentet:", filnavn);
}

function ryd() { localStorage.removeItem(NOEGLE); console.log("Udtrækket er ryddet."); }

console.log("udtraek.js klar. Kør fx:  await udtraek('merchandise')");
