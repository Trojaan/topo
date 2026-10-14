# Plan 3 — Een voorlopig structureel maandbeeld

Status: voorgesteld. Vereist: plannen 0, 1 en 6.

## Resultaat

De agent bereidt uit transacties en korte aanvullende input een bruikbaar
structureel maandbeeld voor. De gebruiker hoeft geen tweede uitgavenadministratie
op te bouwen. Een voorlopig beeld met bandbreedtes is een geldig resultaat.

## Scope

- De agent gebruikt aggregaties en zo nodig gerichte transactieselecties om
  mogelijke terugkerende inkomsten en uitgaven voor te bereiden. Geen
  patroonherkenning in de engine en geen aparte kandidaat-/voorstelrecords.
- Bewaar alleen relevante terugkerende verwachtingen: inkomen of uitgave, bedrag
  of bandbreedte, valuta, frequentie, optionele categorie en korte bronvermelding.
  Een samengevoegde variabele-uitgavenpost is toegestaan; niet ieder abonnement
  hoeft een eigen record te krijgen.
- Begin- en optionele einddatum bepalen geldigheid. De agent mag de afgesproken
  referentiedatum als begindatum voorbereiden zonder een historische start te verzinnen.
- Optionele schuldverwijzing. Een betaling verlaagt geen schuldstand automatisch.
- Deterministische maandnormalisatie voor week, vier weken, maand, kwartaal en jaar.
- Optionele minimumreserve per valuta en korte vrije toelichting over prioriteiten
  of flexibiliteit. Geen verplichte voorkeurenvragen of vertaling naar rekenregels.
- Structureel overschot/tekort per valuta met referentiedatum, bandbreedte en lokale
  beperkingen. Gerealiseerde transacties en verwachte geldstromen blijven gescheiden.

## Voor implementatie beslissen

Leg tekenconventie, geldigheidsgrenzen en maandfactoren vast. Sparen naar eigen
rekeningen is geen consumptieve uitgave; doelinleg wordt niet dubbel afgetrokken.
Neem geen impliciet midden van een bandbreedte als verwachting.

Beschrijf hoe de agent dubbeltelling tussen samengevoegde uitgaven en afzonderlijke
lasten voorkomt. Vraag alleen naar materiële afwijkingen, bijvoorbeeld een recente
salariswijziging of jaarlast buiten de exportperiode. Geen maandbedrag per categorie
uitvragen als transacties al een bruikbare schatting ondersteunen. Een wijziging in
historische transacties herschrijft bevestigde verwachtingen niet automatisch.

## Acceptatie en bewijs

- Jaarlasten en vierwekelijks inkomen worden correct genormaliseerd; verlopen en
  nog niet begonnen verwachtingen tellen op de referentiedatum niet mee.
- Voorzichtige ruimte gebruikt laagste inkomsten minus hoogste uitgaven;
  onbekende bedragen en inventaris blijven zichtbaar.
- De invoerjourney begint bij de export. De agent bereidt een compact maandbeeld
  voor, bundelt interpretaties met andere wijzigingen en blijft binnen het budget
  van drie gebundelde vragen en één bevestiging voor de gezamenlijke wijziging.
- Een ontbrekende verwachting blokkeert geen gerealiseerde maandtotalen; een
  voorlopige verwachting wordt niet als gegarandeerd inkomen gepresenteerd.
- Black-box bewijs voor invoer en maandbeeld; meet CLI-latentie zonder alle
  transacties als analytische invoer van de normalisatie te gebruiken.

## Buiten scope

Een sluitend huishoudboekje, enginepatroonherkenning, contractadministratie,
belastingberekening, budgetregels en verplichte voorkeurenprofielen.
