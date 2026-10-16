# Plan 7 — Een vroeg beschikbare, meegroeiende rapportlaag

Status: technisch geleverd; zie [bewijs](07-bewijs.md). De financiële foto,
het maandbeeld en doelen zijn samen geleverd bovenop plannen 1–4 en 6.
Lege en gedeeltelijke contexten blijven bruikbaar. De menselijke gebruikspoorten
van plannen 3, 4 en 6 blijven open; technische autorisatie bevestigt geen feiten.
De volledige verify-run in de oorspronkelijke werkmap blijft geblokkeerd door
bestaande lintfouten in niet meegeleverde onderzoeksmappen.

## Resultaat

De gebruiker krijgt snel een financiële foto van bekende gegevens. Dezelfde dunne
rapportlaag toont daarnaast transactietotalen, verwachtingen en eenvoudige
doelen. Gedeeltelijke context is een normaal rapportresultaat.

## Scope in afzonderlijke leveringen

1. Financiële foto: bekende rekeningen en bezittingen, daarna schulden en bekend
   nettovermogen. Beschikbaarheid alleen voor zover expliciet bekend. Geen
   compleetverklaring of doelverdeling nodig om het rapport te genereren.
2. Maandbeeld: gerealiseerde transactietotalen zodra plan 6 bestaat; structurele
   verwachtingen daarnaast zodra plan 3 bestaat. Verschillende grondslagen worden
   nooit vermengd tot één totaal.
3. Doelen: streefbedrag, datum, expliciet gereserveerd bedrag, resterend bedrag en
   voorgenomen inleg. Geen rekeningverdeling nodig. Resterend bedrag gebruikt
   plan 4; benodigde inleg, haalmaand en scenario’s blijven buiten scope.

Elke levering gebruikt zelfstandige lokale HTML, zonder webserver. Voeg alleen
secties toe waarvoor de capability beschikbaar is; benoem relevante onbekende
gegevens in gewone taal. Geen algemene “onvolledig, eerst invullen”-pagina.

## Voor implementatie beslissen

Kies modulegrens en uitvoerlocatie. Berekeningen komen uit gedeelde geteste
enginefuncties; de renderer dupliceert ze niet. Lees één consistente snapshot.
Metadata bevat referentiedatum, selectieperiode waar relevant, contractversie en
bronidentiteit van de context; dit voegt geen herstelbare historie toe.
Rapportbestanden bevatten persoonlijke gegevens en horen buiten Git.

Houd onderscheid tussen een nog niet gebouwde capability en onbekende persoonlijke
gegevens. Beschrijf per sectie wat de gegevens wel ondersteunen en welke concrete
conclusie nog niet mogelijk is. Geen lange standaardlijst van alle denkbare hiaten.

## Acceptatie en bewijs per levering

- Een minimale gedeeltelijke context levert direct een financiële foto op.
- Nieuwe secties sluiten aan op engine-uitkomsten en breken bestaande rapporten niet.
- Ontbrekende informatie blijft lokaal zichtbaar; HTML escapt alle vrije tekst.
- Genereren wijzigt geen context, vraagt geen bevestiging en werkt offline.
- Black-box bewijs en visuele controle op brede en smalle weergave, ook met weinig data.
- De agentsessie geeft vroeg inzicht zonder eerst ontbrekende domeinen uit te vragen.
- Meet generatietijd en bestandsgrootte; geen detailaanroep per doel/transactie.
  Scheid gegevensberekening van renderkosten.

## Buiten scope

PDF, dashboardhosting, rapportbouwer, grafiekeditor, vrije templates en een
verplichte complete inventaris als rapportvoorwaarde.

## Besluiten vóór implementatie (2026-10-15)

Technische implementatie is geautoriseerd ondanks de open menselijke gebruikspoorten
van plannen 3, 4 en 6. Die blijven open; dit bevestigt geen financiële gegevens.

- Modulegrens: zuivere rapportprojectie → bestaande reading/cashflows/transactions;
  zuivere HTML-renderer → rapportmodellen; CLI orkestreert één storage.read en
  afzonderlijke bestandspublicatie. Geen financiële berekening in de renderer.
- CLI: report --context PATH --output PATH --reference-date YYYY-MM-DD,
  optioneel --from-date en --to-date samen (inclusief). Referentiedatum en output
  zijn verplicht. Additief topo2.cli/3 met ontdekkbare invoer/uitvoerschema's.
- Zonder periode: alle opgeslagen transacties per boekingsmaand, zonder volledige
  maanddekking te suggereren. Geen periode uit transactiedatums afleiden.
  Referentiedatum selecteert actieve verwachtingen, geen historische saldi.
- Metadata: topo2.report/1, CLI-contract, contextschema/context_id, SHA-256 van
  exacte snapshotbytes, referentiedatum en nullable selectiegrenzen. Geen historie.
  Succes-JSON bevat absoluut uitvoerpad, HTML-bytes en metadata.
- Outputdirectory moet bestaan. Bestaand pad wordt geweigerd, ook bij een race;
  geen overschrijfoptie. Privé tijdelijk bestand schrijven, flush/fsync, atomair
  publiceren zonder vervanging en opruimen bij fouten. IO_ERROR bij opslagfout,
  INVALID_DATA bij ongeldige gegevens; bestaande exitcodes blijven gelden.
- Zelfstandige UTF-8 HTML met ingebedde CSS, zonder scripts/externe assets.
  Alle dynamische tekst escapen; Decimal-waarden exact houden. Rapporten buiten Git.
- Bekende uitkomsten direct tonen, onbekend niet als nul; lokale korte beperkingen.
  Realisatie/verwachtingen, gekoppelde waarde/reserveringen en minimumreserve
  afzonderlijk. Geen tweede aftrek van maandinleg of claim van gezamenlijke dekking.
- Bestaande performancepoort blijft gelden, inclusief report bij 10k; 100k is
  schaalprofiel. Meet volledige processen/RSS/HTML-bytes en berekening/rendering
  afzonderlijk. Geen opslagherontwerp, vervolgplan, PDF, hosting of release.


## Geleverd en stopgrens

Alle drie onderdelen zijn technisch geleverd met één effectvrije report-opdracht.
Onderzoek, verificatie, visuele controle, bronjourney en schaalmetingen staan in
[07-bewijs.md](07-bewijs.md). De menselijke gebruikspoorten van plannen 3, 4 en 6
blijven open; technische tests en in-geheugenkandidaten bevestigen geen financiële
gegevens of bedoelingen. Geen plan 5, 8 of 9, opslagherontwerp, PDF, hosting of release.
