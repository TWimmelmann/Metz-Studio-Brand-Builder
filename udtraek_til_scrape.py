#!/usr/bin/env python3
"""
udtraek_til_scrape.py — pakker browser-udtrækket ud i .scrape-mapper.

Browser-udtrækket (se udtraek.js) gemmer alle kategorier i én fil, hvor hver
vare er en streng med felterne adskilt af "|;|". Det format er valgt fordi
udtrækket skal kunne hentes ud af browseren i ét stykke.

Denne pakker det ud til det format byg_katalog_fra_demo.py læser: én JSON-fil
pr. kategori, med én liste pr. vare:

    [varenummer, navn, brand, materiale, pris, lager, billed-hale]

Brug:
    python3 udtraek_til_scrape.py ~/Downloads/us-scrape.json --ud .scrape-us
"""

import argparse
import json
from pathlib import Path

FELTER = 7
SEP = "|;|"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kilde", help="JSON-filen browseren hentede")
    ap.add_argument("--ud", default=".scrape-us", help="mappe der skrives til")
    args = ap.parse_args()

    data = json.loads(Path(args.kilde).read_text(encoding="utf-8"))
    ud = Path(args.ud)
    ud.mkdir(exist_ok=True)

    for navn, indhold in data.items():
        if navn == "__subcats":
            (ud / "subcats.json").write_text(
                json.dumps(indhold, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  subcats.json        {len(indhold)} underkategorier")
            continue

        raekker = []
        for linje in indhold:
            felter = linje.split(SEP)
            if len(felter) != FELTER:
                # Et "|;|" i selve produktnavnet ville splitte forkert. Sker det,
                # er det bedre at vide det end at skrive en skæv række.
                print(f"  ! {navn}: {len(felter)} felter i {felter[0]!r} — sprunget over")
                continue
            raekker.append(felter)

        (ud / f"{navn}.json").write_text(
            json.dumps(raekker, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  {navn + '.json':20} {len(raekker)} varer")


if __name__ == "__main__":
    main()
