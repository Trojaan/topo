# Topo 2: snel van bronnen naar bruikbaar inzicht

Status: plan 0 technisch geleverd; de menselijke gebruiksbevestiging staat nog
open. Zie [bewijs en beperkingen](00-bewijs.md). Plannen 1–9 zijn niet geïmplementeerd.

Doel: met transacties, screenshots en weinig aanvullende input snel voldoende
actuele context opbouwen om samen met een agent financiële vragen en doelen te
bespreken. Een gedeeltelijk overzicht is een geldig resultaat. Een volledige
financiële administratie is geen toegangseis voor inzicht.

Topo blijft een kleine lokale engine. De agent verwerkt bronnen, bereidt
interpretaties voor en bespreekt uitkomsten; de engine bewaart actuele records en
levert geteste berekeningen. Deze plannen gelden uitsluitend voor `topo2`; de
historische engine is geen afhankelijkheid.

## Ontwerpgrens: gebruiksgemak vóór modelvolledigheid

- Begin bij de vraag van de gebruiker en de bronnen die al beschikbaar zijn.
  Vraag alleen ontbrekende informatie die het gevraagde inzicht wezenlijk verandert.
- Geef vroeg een bruikbare uitkomst met concrete beperkingen. Ontbrekende schulden
  beperken nettovermogen, maar blokkeren geen analyse van dagelijkse uitgaven.
- Laat de agent bekende informatie hergebruiken, exports omzetten en mogelijke
  classificaties en geldstromen voorbereiden. De gebruiker vult geen schema in.
- Bundel samenhangende wijzigingen en interpretaties in één leesbare preview en
  één expliciete menselijke bevestiging. Deelplannen zijn geen gebruikersstappen.
- Maak optionele velden, volledigheidsverklaringen en doelverdelingen nooit
  verplicht om een eerste overzicht te krijgen. Onbekend blijft zichtbaar.
- Voeg een nieuw recordtype pas toe wanneer het aantoonbaar invoerwerk bespaart of
  een concrete gebruikersvraag beantwoordt. Geen administratie ter voorbereiding
  op mogelijk toekomstige functionaliteit.

## Deelplannen en volgorde

Bestaande bestandsnummers blijven behouden als verwijzingen; ze bepalen niet de
uitvoervolgorde. Plan 0 loopt als gebruiksjourney mee met iedere uitbreiding.

| Plan | Vereist | Zelfstandig resultaat |
| --- | --- | --- |
| [0 — Van bronnen naar eerste context](00-invoer.md) | — | Werkende invoerjourney, hergebruik en behoud bij herimport |
| [1 — Compact lezen en gerichte onzekerheid](01-context.md) | 0 als gebruiksgrens | Snel lezen; gedeeltelijke context blijft bruikbaar |
| [2 — Eenvoudige schulden en vermogen](02-vermogen.md) | 1 | Eerste nettovermogensbeeld zonder uitgebreide inventarisatie |
| [7 — Meegroeiende rapportlaag](07-rapportages.md) | 1; verdere gegevens optioneel | Vroege financiële foto, later maandbeeld en doelen |
| [6 — Transactiebetekenis en aggregaties](06-transacties.md) | 0, 1 | Controleerbare totalen met door de agent voorbereide classificaties |
| [3 — Voorlopig structureel maandbeeld](03-geldstromen.md) | 0, 1, 6 | Alleen relevante terugkerende verwachtingen vastleggen |
| [4 — Eenvoudige doelen](04-doelen.md) | 1 | Doelbedrag, datum, optioneel gereserveerd bedrag en maandinleg |
| [8 — Eenvoudige doelberekeningen](08-scenarios.md) | 4; 3 voor toets op maandruimte | Benodigde inleg en haalmaand onder zichtbare aannames |
| [5 — Geplande veranderingen](05-veranderingen.md) | 3 en aangetoonde behoefte | Uitgesteld: concrete toekomstige veranderingen bewaren |
| [9 — Verdeling en gezamenlijke scenario's](09-verdeling-scenarios.md) | 2, 3, 4, 8; 5 voor veranderingen; aangetoonde behoefte | Uitgesteld: onderlinge concurrentie en tijdlijnen |

Aanbevolen uitvoervolgorde: 0 → 1 → 2 → 7 (financiële foto) → 6 → 3 →
7 (maandbeeld) → 4 → 7 (doelen) → 8. Plan 7 wordt bewust in kleine stappen geleverd;
het eerste rapport wacht niet op doelen, classificatie of alle geldstromen.

Plannen 5 en 9 zijn geen automatisch vervolg. Start ze pas wanneer vastgelegde
gebruiksjourneys laten zien welke concrete vraag de eenvoudige variant niet kan
beantwoorden en waarom een agentanalyse met losse aannames niet volstaat. Beperk
het vervolg dan tot die vraag. Geen vooraf gebouwde algemene planningengine.

## Gezamenlijke grenzen

- Records bewaren context; afgeleide uitkomsten worden op aanvraag berekend.
- De agent mag bronnen interpreteren en classificaties of verwachtingen
  voorbereiden. Die interpretaties worden pas opgeslagen na de gezamenlijke
  preview en menselijke bevestiging; geen afzonderlijke voorsteladministratie.
- Vaste financiële berekeningen staan in geteste Python, niet in vrije
  agentformules. De agent bespreekt mogelijkheden en expliciete aannames.
- Geen netwerkafhankelijkheid in de engine, automatische categorisatie in de
  engine, fiscaal advies, productkeuze, generieke regelsengine of historische engine.
- Geen automatische saldoaanpassing door transacties of prognoses.
- Eén bestaande preview/bevestigingsflow voor contextmutaties. Het uitvoeren van
  een plan geeft geen toestemming om persoonlijke financiële feiten te bevestigen.
- Onbekend is geen nul. Valuta worden afzonderlijk behandeld; geld blijft Decimal.
  Onvolledigheid beperkt alleen de uitkomsten waarvoor die gegevens nodig zijn.
- Compatibele bestaande contexten blijven leesbaar; previews herschrijven niets.
  Bepaal en documenteer per plan welke schema- en contractversie nodig is.
- Herimport behoudt bestaande verrijkingen tenzij een vervanging expliciet wordt
  aangevraagd en in de preview zichtbaar is; nooit stilzwijgend terugkerend herstelwerk.
- Alleen synthetische fixtures; persoonlijke context en rapporten blijven buiten Git.

## Gebruiksgemak als acceptatiepoort

Naast technische tests geldt de synthetische journey uit plan 0: een bankexport,
enkele saldoscreenshots en een kort doelbericht leiden tot een bruikbaar eerste
beeld. Controleer dit vanaf de oorspronkelijke bronnen, niet alleen vanaf reeds
perfect ingevulde engine-requests.

Voor de afgesproken, leesbare basisfixture geldt maximaal drie gebundelde
verduidelijkingsvragen en één bevestiging voor de volledige samenhangende wijziging.
Dit is een ontwerpgrens, geen gemeten resultaat. Een vraagbundel mag geen verkapte
lange vragenlijst worden. Niet-wezenlijke hiaten blijven onbekend. Bij onleesbare
of tegenstrijdige bronnen wordt onzekerheid gemeld; de grens geeft nooit toestemming
om waarden te verzinnen of noodzakelijke verduidelijking over te slaan.

Leg per journey vast: bronmateriaal, gebruikersvraag, gestelde vragen, bevestigingen,
tijd tot eerste bruikbaar inzicht, resterende onzekerheden en handmatig herstelwerk.
Herhaal dezelfde aanlevering en een bijgewerkte export: bekende gegevens worden
niet opnieuw uitgevraagd, verrijkingen blijven behouden en identieke invoer vraagt
geen nieuwe bevestiging. Stel op basis van de eerste uitvoering een tijdsbaseline
vast; claim vooraf geen snelheid. Iedere uitbreiding moet binnen het frictiebudget
blijven en mag geen extra verplichte inventarisatie introduceren.

## Uitvoering en afronding per plan

1. Lees het gekozen plan, dit overzicht, `docs/topo2.md` en de actuele contracten.
   Controleer welke afhankelijkheden werkelijk zijn afgerond. Gebruik de kennisgraph
   voor codeverkenning.
2. Beschrijf de concrete gebruikersvraag en invoerjourney. Leg beperkte records en
   CLI-uitkomsten vast; beslis open punten vóór implementatie. Optionele verdieping
   mag de eenvoudige route niet blokkeren.
3. Implementeer alleen die scope, inclusief documentatie en een black-box journey
   voor gewijzigde CLI-contracten. Werk de agentinstructies bij wanneer de invoerflow
   verandert, zodat de gebruiksgrenzen ook operationeel gelden.
4. Run `scripts/verify.sh`, de relevante synthetische performancecheck en de
   gebruiksjourney. CLI-tests alleen bewijzen niet dat een agentsessie weinig vragen kost.
5. Noteer status, geleverde contracten, technisch bewijs, gebruiksbewijs en resterende
   beperkingen. Werk `docs/topo2.md` bij; onderscheid geplande en bestaande functies.

## Performance als vaste grens

Behoud de bestaande benchmarkpoort van minder dan één seconde per gemeten
CLI-operatie bij 1.000 rekeningen en 10.000 transacties. Voeg bij nieuwe lees- en
rekenpaden metingen toe voor diezelfde fixture. Meet daarnaast 100.000 transacties,
uitvoergrootte en piekgeheugen als schaalprofiel; leg vóór een harde nieuwe grens
de baseline en meetomgeving vast. Dit document claimt geen nieuwe meetresultaten.

Vermijd het telkens ophalen of serialiseren van alle transacties. Compacte uitvoer
is geen bewijs van goedkoop inlezen: meet het volledige CLI-proces. Houd de huidige
opslag totdat metingen een concrete bottleneck tonen; een eventuele opslagwijziging
krijgt een afzonderlijk plan. Technische snelheid vervangt de gebruikspoort niet.

## Een volgende sessie starten

Gebruik bijvoorbeeld: “Voer plan 0 uit uit docs/plans/topo2-context/00-invoer.md.
Lees eerst het overzicht, beperk je tot dit plan en werk na verificatie de status bij.”
Ga pas verder wanneer het voorgaande resultaat technisch én in gebruik is gecontroleerd.
