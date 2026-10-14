# Synthetische invoerbronnen

Alle waarden, bankreferenties en rekeningidentifiers zijn fictief. De PNG's zijn
gegenereerde saldoschermen, geen opnames van een echte bank. De agent leest de
beelden visueel; de CLI bevat geen OCR. `doel.txt` is een fictief gebruikersbericht.

`bank.csv` is een bronexport met puntkomma's, decimale komma's en bankreferenties.
`bank-updated.csv` verandert volgorde en omschrijving, corrigeert SYN004 met één
euro en voegt SYN005 toe. Geen van beide is vooraf een Topo-importrequest.

`e2e/topo2_input_fixture.py` legt de ene reproduceerbare omzetting vast: vaste
rekeningkoppelingen, `syn_` plus bankreferentie als ID, decimale komma naar punt,
letterlijke valuta en omschrijving. De omzetter is uitsluitend fixturegereedschap;
hij herkent geen banken of categorieën. De eerste categorieën zijn door de agent
voorbereide interpretaties en verschijnen in de gezamenlijke preview.

De saldoschermen tonen respectievelijk SYN-BETAAL met EUR 2.514,50 en SYN-SPAAR
met EUR 6.400,00, beide op 2026-10-04. Ze zijn met Pillow getekend op een RGB-canvas
van 1000 × 500, met Arial en expliciet opschrift “SYNTHETISCHE BANK - DEMOSCHERM”.
Pillow is geen engine- of testafhankelijkheid: de vaste PNG-bronnen zitten in Git.

De black-box test start bij CSV en bronbestanden en bewijst de CLI-route. Zijn
hardgecodeerde screenshotverwachtingen bewijzen zelf geen visuele interpretatie.
Dat bewijs staat afzonderlijk in de vastgelegde agentsessie in
`docs/plans/topo2-context/00-bewijs.md`.
