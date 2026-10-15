# Plan 4 — Eenvoudige doelen

Status: [technisch geleverd](04-bewijs.md); menselijke gebruiksacceptatie open.
Vereist: plan 1. Schulden, geldstromen en gedetailleerde
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

## Vastgelegde ontwerpbesluiten (2026-10-15, vóór implementatie)

- target_amount blijft positief; reserved_amount en monthly_contribution zijn
  optionele niet-negatieve Decimal-bedragen, inclusief expliciete nul. Bestaande
  geldgrenzen gelden: maximaal 28 cijfers en acht decimalen. Geen bovengrens
  ten opzichte van doel of vermogen. Afwezig/null blijft onbekend.
- priority is optioneel low/normal/high: uitsluitend menselijke rangorde,
  zonder automatische verdeling of berekening. note is optionele vrije tekst
  van maximaal 256 tekens, geen rekenregel.
- remaining_amount is max(target_amount - reserved_amount, 0), uitsluitend
  wanneer reserved_amount bekend is. Overreservering blijft zichtbaar in het
  opgeslagen bedrag. Geen impliciete nulaanname; expliciet nul is bekend nul.
- Oude koppelingen blijven afzonderlijke linked_value. De bestaande known_amount,
  percentage, missing_ids en complete blijven compatibele gekoppelde-waardevelden.
  Koppelingen tellen nooit bij reserveringen of remaining_amount op.
- reservation_comparison vergelijkt per doelvaluta known_reserved_total met het
  bestaande known_free_total. Zonder vermogensrecords in die valuta is dat null.
  possible_excess is null zonder vergelijking, anders de vergelijking >.
  coverage_unknown is onafhankelijk en waar bij ontbrekende reserveringen,
  middelenwaarden/beschikbaarheid of onvolledige accounts/assets/goals-inventaris.
  Beide signalen kunnen tegelijk bestaan. Inventarissen en ontbrekende IDs blijven
  zichtbaar. Ook zonder hiaten is dit nooit bewijs van gezamenlijke of exclusieve
  dekking. Schulden worden niet opnieuw afgetrokken. Minimumreserve blijft een
  afzonderlijke saldodrempel; geen verrekening met doelreserveringen.
- Maandinleg is opgeslagen intentie, zonder betaling, saldo-/schuldmutatie of
  tweede aftrek in monthly-room. Geen benodigde inleg, haalmaand of haalbaarheid.
- CLI blijft additief topo2.cli/3. Niet-null verrijkingen (ook nul) vereisen
  context/7. Versies 1–6 blijven leesbaar; preview/no-op migreren niet. Versie 7
  blijft behouden na wissen. Oude opslagversies krijgen geen verrijkingsvelden.
- Eén bestaande gezamenlijke preview/bevestiging; geen verplichte inventarisatie,
  verdeling of voorkeurenvragen. Ambigue datums worden niet verzonnen.
  Technische autorisatie bevestigt geen financiële gegevens. De menselijke
  gebruikspoorten van plannen 3 en 6 blijven open.
