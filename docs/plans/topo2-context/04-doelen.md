# Plan 4 — Eenvoudige doelen

Status: voorgesteld. Vereist: plan 1. Schulden, geldstromen en gedetailleerde
vermogensverdeling zijn geen voorwaarde om een doel vast te leggen.

## Resultaat

Een kort doelbericht wordt een bruikbaar doel: bedrag, gewenste datum en eventueel
reeds gereserveerd bedrag en geplande maandinleg. Geen verdeling van iedere rekening.

## Scope

- Behoud doelnaam, positief streefbedrag, valuta en optionele gewenste datum.
- Voeg een optioneel expliciet gereserveerd bedrag en geplande maandinleg toe.
  Een ontbrekend gereserveerd bedrag is onbekend, niet automatisch nul.
- Optionele eenvoudige prioriteit en vrije toelichting. Geen verplichte
  flexibiliteitsschaal of tweede uiterste datum naast de gewenste datum.
- Toon resterend bedrag wanneer de benodigde waarden bekend zijn.
- Behoud oude rekening-/bezitskoppelingen als gekoppelde waarde, herkenbaar
  afzonderlijk van expliciete reserveringen. Zet ze niet automatisch om.

## Voor implementatie beslissen

Een gereserveerd bedrag is een door de gebruiker bevestigde bestemming, geen bewijs
van aanwezige of exclusief toegewezen middelen. Zonder dat bedrag kan de gebruiker
expliciet kiezen voor een berekening vanaf nul; presenteer dat als aanname.

Gebruik voor de eenvoudige berekening uitsluitend het expliciete gereserveerde
bedrag; tel gekoppelde waarde er niet bij op. Leg vast hoe bekende totale
reserveringen zich tot bekend vrij vermogen verhouden: toon een mogelijke
overschrijding of onbekende dekking, maar blokkeer het vastleggen van het doel niet.
Geen claim dat alle doelen gezamenlijk gedekt zijn. Een waardedaling vereist geen
handmatige herverdeling voordat actuele waarden kunnen worden opgeslagen.

Verdeling per rekening/bezitting, harde overtoewijzingsregels en gezamenlijke
doelplanning zijn uitgesteld naar plan 9.

## Acceptatie en bewijs

- Een kort bericht “€10.000 voor een verbouwing volgend jaar” levert een doel zonder
  verplichte vragen naar rekeningverdeling, prioriteit of flexibiliteit.
- €4.000 expliciet gereserveerd op een doel van €10.000 geeft €6.000 resterend;
  een ontbrekend bedrag geeft onbekende resterende dekking.
- Oude koppelingen blijven leesbaar zonder dubbeltelling met reserveringen.
- Een mogelijke overschrijding van bekende middelen blijft zichtbaar zonder claim
  van exclusieve dekking. Actuele waardedalingen kunnen altijd worden opgeslagen.
- Black-box bewijs voor oude en nieuwe doelen; de invoerjourney blijft binnen het
  frictiebudget. Berekeningen scannen geen transacties per doel.

## Buiten scope

Toewijzingen per vermogenspost, automatische verdeling, harde reserveringen,
beleggingsadvies, gezamenlijke haalbaarheid en scenario's.
