# Plan 7 — Een vroeg beschikbare, meegroeiende rapportlaag

Status: voorgesteld. Eerste stap vereist plan 1; plan 2 verrijkt de financiële
foto. Maandbeeld volgt met plannen 6 en 3; doelenoverzicht volgt met plan 4.
Geen van deze latere stappen blokkeert het eerste rapport.

## Resultaat

De gebruiker krijgt snel een financiële foto van bekende gegevens. Dezelfde dunne
rapportlaag groeit later mee met transactietotalen, verwachtingen en eenvoudige
doelen. Gedeeltelijke context is een normaal rapportresultaat.

## Scope in afzonderlijke leveringen

1. Financiële foto: bekende rekeningen en bezittingen, daarna schulden en bekend
   nettovermogen. Beschikbaarheid alleen voor zover expliciet bekend. Geen
   compleetverklaring of doelverdeling nodig om het rapport te genereren.
2. Maandbeeld: gerealiseerde transactietotalen zodra plan 6 bestaat; structurele
   verwachtingen daarnaast zodra plan 3 bestaat. Verschillende grondslagen worden
   nooit vermengd tot één totaal.
3. Doelen: streefbedrag, datum, expliciet gereserveerd bedrag, resterend bedrag en
   geplande inleg. Geen rekeningverdeling nodig. Berekeningen volgen in plan 8.

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
