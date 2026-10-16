# Plan 1 — Compact lezen en gerichte onzekerheid

Status: technisch en voor de uitgevoerde synthetische basisjourney in gebruik
geleverd. Zie [extern gebruiksbewijs 0–2](gebruik-bewijs-00-02.md), inclusief
herstelstappen, beperkte tijdmeting en niet uitgevoerde optionele proeven.


## Resultaat

De agent leest de actuele context zonder alle transacties op te halen en ziet
welke onzekerheden relevant zijn voor de concrete vraag. Gedeeltelijke context
blijft een bruikbaar resultaat; er is geen verplichte onboardingchecklist.

## Scope

- Een compacte leesuitkomst met rekeningen, bezittingen en doelen; geen lijst
  transactierecords. Laat het bestaande volledige `show` beschikbaar.
- Waardepeildata en ontbrekende waarden zichtbaar tonen. Veroudering krijgt een
  expliciete referentiedatum en grens, geen verborgen oordeel.
- Optionele kleine volledigheidsrecords per domein: onbekend, gedeeltelijk of door
  de gebruiker compleet verklaard, met controledatum. Een lege complete inventaris
  is betekenisvol; het ontbreken van zo'n verklaring blokkeert geen leesuitkomst.
- Optionele transactiedekking per rekening als expliciet bevestigde datumintervallen.
  De eerste en laatste transactie bewijzen geen volledige dekking. De agent kan een
  expliciete exportperiode voorbereiden voor dezelfde gezamenlijke preview.
- Uitkomsten onderscheiden bekende totalen, ontbrekende waarden binnen bekende
  records en onbekende inventaris/dekking. Geen algemeen volledigheidspercentage.

## Voor implementatie beslissen

Kies de naam van de compacte CLI-uitkomst, het kleine domeinenregister en de
betekenis van intervalgrenzen. Afwezigheid van een nieuw veld betekent onbekend.
Latere domeinen kunnen worden toegevoegd zonder pluginstelsel.

Leg per uitkomst vast welke hiaten de betekenis beperken. Geen universele blokkade
op basis van ontbrekende context en geen automatische uitvraaglijst. De agent
beslist welke verduidelijking de huidige gebruikersvraag wezenlijk helpt.

## Acceptatie en bewijs

- Een oude context leest zonder herschrijven en levert direct een compacte uitkomst.
- “Geen schulden opgegeven” verschilt van “bevestigd geen schulden”, maar beide
  laten een overzicht van bekende rekeningen en dagelijkse uitgaven toe.
- Een ontbrekende transactieperiode wordt niet impliciet volledig gemaakt; beschikbare
  totalen blijven leesbaar met de betreffende beperking.
- Een black-box journey bewijst optionele volledigheid, preview en bevestiging van
  dekking. De invoerjourney werkt ook zonder volledigheidsverklaringen.
- De gebruiksjourney uit plan 0 blijft binnen het frictiebudget; geen aparte vragen
  per domein uitsluitend om de inventaris compleet te verklaren.
- Bij 10.000 en 100.000 transacties groeit compacte uitvoer niet mee met het aantal
  transacties; meet ook latentie en piekgeheugen volgens het overzicht.

## Buiten scope

Enginegestuurde vragenlijsten, historie, rapportopmaak en analyses.
