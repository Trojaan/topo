# Plan 2 — Eenvoudige schulden en vermogen

Status: technisch en voor de uitgevoerde synthetische basisjourney in gebruik
geleverd. Zie [extern gebruiksbewijs 0–2](gebruik-bewijs-00-02.md), inclusief
herstelstappen, beperkte tijdmeting en niet uitgevoerde optionele proeven.


## Resultaat

Een eerste nettovermogensbeeld op basis van bekende rekeningen, bezittingen en
schulden. De gebruiker hoeft geen beschikbaarheidsadministratie te onderhouden.

## Scope

- Schuldrecord met ID, naam, soort, openstaand bedrag of onbekend, valuta en
  waardepeildatum. Bekende rente en einddatum zijn optioneel; geen verplichte vragen
  of opdracht tot een aflossingsberekening.
- Nettovermogen per valuta naast het bestaande vermogensoverzicht. Toon bekende
  totalen, ontbrekende bedragen en onbekende inventaris afzonderlijk.
- Optionele beschikbaarheid op rekeningen en bezittingen: vrij, beperkt of onbekend,
  met korte toelichting. Vraag dit alleen wanneer de gebruiker wil weten welk geld
  voor een concrete besteding inzetbaar is.
- Toon bekende vrij beschikbare middelen afzonderlijk, met onbekende beschikbaarheid
  zichtbaar. Bezitsoort alleen bewijst geen liquiditeit of verkoopwaarde.

## Gekozen behandeling

Negatieve rekeningsaldi tellen eenmaal mee. Een schuldrecord voor dezelfde
roodstand vereist een expliciete rekeningkoppeling met overeenkomend bedrag,
valuta en peildatum; deze schuld wordt niet opnieuw afgetrokken. Geen automatische
schuldherkenning. Ontbrekende schuldinformatie
maakt de nettovermogensclaim beperkt, niet het gehele overzicht onbruikbaar.
Betalingen staan later in plan 3; hier geen tweede maandlastberekening.

Een beschikbaarheidsdatum en tijdafhankelijke inzetbaarheid vallen onder het
uitgestelde plan 9. Houd de eerste variant bij de actuele bekende beschikbaarheid.

## Acceptatie en bewijs

- Woning, hypotheek, spaargeld en negatief banksaldo leveren verklaarbare totalen
  zonder dubbele aftrek; EUR en USD blijven gescheiden.
- Een onbekende schuldstand en onbekende schuldinventaris zijn afzonderlijk zichtbaar.
- Zonder beschikbaarheidsvelden ontstaat direct een financiële foto; bekende
  beperkt beschikbare middelen worden niet als vrij besteedbaar gepresenteerd.
- Black-box bewijs voor atomair wijzigen en geldige verwijzingen, plus de
  gebruiksjourney met slechts een relevante aanvullende schuldvraag waar nodig.
- Meet de uitgebreide samenvatting zonder transactiedetails in de uitvoer.

## Buiten scope

Verplichte liquiditeitsinventarisatie, beschikbaarheidstijdlijnen, hypotheekadvies,
fiscale waardering, aflossingsschema's, pensioenprognoses en valutaomrekening.
