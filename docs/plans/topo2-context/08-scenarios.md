# Plan 8 — Eenvoudige doelberekeningen

Status: voorgesteld. Vereist: plan 4. Plan 3 is alleen nodig voor toetsing aan
bekende maandruimte; plan 7 alleen voor HTML-weergave. Plan 5 en gedetailleerde
vermogensverdeling zijn geen afhankelijkheid.

## Resultaat

De agent kan benodigde maandinleg en haalmaand voor één doel bespreken onder
expliciete aannames. Dit is geen bewijs dat alle doelen samen haalbaar zijn.

## Scope

- Geteste functies voor resterend doelbedrag, benodigde maandinleg en haalmaand bij
  vaste geplande inleg. Eerste versie zonder rendement of inflatie.
- Gebruik het expliciet gereserveerde doelbedrag. Een onbekende beginstand geeft
  geen exacte uitkomst, tenzij de gebruiker expliciet een aanname vanaf nul kiest.
- Effectvrije invoer voor een ander doelbedrag, datum of maandinleg. Geen opgeslagen
  scenario's en geen contextwijziging of bevestiging voor een losse berekening.
- Vergelijk hoogstens enkele eenvoudige varianten. Toon aannames en, waar bekend,
  verhouding tot structurele maandruimte. Bij meerdere bekende maandinleggen kan
  hun som met die ruimte worden vergeleken; dit is geen gezamenlijke tijdlijn.
- Gebruik de bestaande rapportlaag wanneer beschikbaar; CLI-uitkomsten mogen
  eerder bruikbaar zijn. Onbekende maandruimte blokkeert geen losse rekenvraag.

## Voor implementatie beslissen

Definieer stortingsmoment, gedeeltelijke startmaand, maximaal bereik en afronding.
Houd onderscheid tussen “dit bedrag is maandelijks nodig” en “dit bedrag is voor
jou beschikbaar”. Reserveer dezelfde ruimte niet impliciet volledig voor meerdere
doelen. Zonder volledig gezamenlijk beeld blijft dekking onbekend.

Minimumreserve, gedateerde beschikbaarheid, toekomstige kasstroomwijzigingen en
gezamenlijke tijdlijnen worden pas in plan 9 betrokken. Rendement en inflatie
vereisen eveneens een afzonderlijke, door gebruik gemotiveerde keuze.

## Acceptatie en bewijs

- €4.000 gereserveerd, doel €10.000 en twaalf volledige stortingen vereist €500
  per maand volgens de gepubliceerde conventie.
- Nul inleg, verstreken deadline, al behaald doel, onbekende beginstand en
  onbereikbaar doel leveren expliciete uitkomsten op.
- Ontbrekende maandruimte verhindert geen berekening van benodigde inleg, maar de
  uitkomst claimt dan geen financiële haalbaarheid.
- Varianten schrijven niets en vragen geen nieuwe bevestiging. De gebruiksjourney
  vereist geen extra inventarisatie van vermogen of toekomstige gebeurtenissen.
- Black-box bewijs en waar beschikbaar rapportcontrole; begrens varianten en bereik.
  Geen transactieanalyse of complexe tijdlijn nodig voor deze berekeningen.

## Buiten scope

Gezamenlijke doelplanning, vermogensverdeling, toekomstige gebeurtenissen,
Monte Carlo, automatische optimalisatie, productadvies, fiscale simulatie,
rendementsvoorspelling en persistent scenariobeheer.
