# Plan 3 — Een voorlopig structureel maandbeeld

Status: technisch geleverd; zie [bewijs](03-bewijs.md). De volledige verify-run
blijft geblokkeerd door bestaande ongerelateerde lintfouten. Vereist: plannen 0, 1 en 6.
Menselijke gebruiksacceptatie van plan 3 en de nieuwe soorten van plan 6 blijft open.

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

## Vastgelegde ontwerpbesluiten vóór implementatie (2026-10-14)

De gebruiker autoriseert technische uitvoering ondanks de open menselijke
gebruikspoort van plan 6. Dit bevestigt geen classificaties of verwachtingen.
De gebruiksflow blijft: bron → aggregaties → enkele voorbereide verwachtingen →
één gezamenlijke preview. Geen tweede administratie of verplichte inventarisatie.

- Verwachtingen heten `cashflows`. `kind` is income/expense; bedragen zijn
  niet-negatief. Eén `amount` is een decimale string, `{lower, upper}` of null.
  Bandgrenzen zijn beide verplicht, niet-negatief en geordend; geen middenwaarde.
- `start_date` en optionele `end_date` zijn inclusief. De expliciete referentiedatum
  bepaalt activiteit; geen impliciete systeemdatum, proratering of betaalagenda.
- Maandfactoren: weekly 52/12, four_weekly 13/12, monthly 1, quarterly 1/3,
  yearly 1/12. Dit zijn vaste structurele gemiddelden, ook in een schrikkeljaar.
- Reken met exacte rationale factoren. Rond per post de maandondergrens naar
  beneden en bovengrens naar boven op acht decimalen; sommeer daarna exact met
  Decimal, onafhankelijk van omgevingsprecisie. Geen centafronding in de engine.
- Bekende netto-band = [laagste inkomsten − hoogste uitgaven,
  hoogste inkomsten − laagste uitgaven]. De ondergrens is uitsluitend voorzichtige
  ruimte binnen de bekende posten, geen gegarandeerd besteedbaar bedrag.
- Onbekende bedragen krijgen ontbrekende IDs en worden niet als bekende nul
  gepresenteerd. Toon bekende deelsommen ook bij onbekende/gedeeltelijke inventaris;
  een volledige netto-band vereist bekende bedragen én complete cashflows-inventaris.
- Minimumreserve is op verzoek van de gebruiker een saldodrempel, geen maandlast.
  `cashflow_settings` bevat per valuta optioneel minimum_reserve en note. Een change
  vervangt de instellingen van de opgegeven valuta; null verwijdert die sleutel.
  Weggelaten valuta blijven behouden. Geen afzonderlijke voorkeurenrecords of IDs.
- Eigen overboekingen zijn geen consumptieve verwachtingen; doelinleg wordt niet
  opnieuw afgetrokken. De agent omschrijft de selectie van een samengevoegde post
  en sluit afzonderlijk opgenomen lasten daarvan uit. Geen engine-overlapdetectie.
- `debt_id` verwijst optioneel naar een bestaande schuld in dezelfde valuta.
  Betalingen wijzigen geen schuldstand of saldo; transacties wijzigen geen verwachting.
- CLI blijft additief topo2.cli/3; nieuwe data vereisen topo2.context/6. Oude contexten
  blijven leesbaar; preview/no-op schrijven niets. Versie 6 blijft behouden.
