# Plan 9 — Verdeling en gezamenlijke scenario's, alleen bij aangetoonde behoefte

Status: uitgesteld ontwerp; niet automatisch uitvoeren. Vereist: plannen 2, 3,
4 en 8; plan 5 alleen voor toekomstige veranderingen en plan 7 voor rapportweergave.

## Startvoorwaarde

Leg met een concrete gebruiksjourney vast waarom eenvoudige gereserveerde
bedragen en losse doelberekeningen tekortschieten. Bijvoorbeeld: twee doelen
concurreren om hetzelfde vermogen op verschillende datums. Onderzoek eerst of een
agentanalyse met expliciete aannames volstaat. Bouw alleen de noodzakelijke stap;
onderstaande mogelijkheden zijn geen vastgestelde implementatiescope.

## Mogelijke vervolgstappen

- Expliciete bedragtoewijzingen van een rekening of bezitting aan een doel, in
  dezelfde valuta. Oude koppelingen en eenvoudige reserveringen worden nooit
  stilzwijgend omgezet of naast nieuwe toewijzingen dubbel opgeteld.
- Nieuwe overtoewijzing weigeren wanneer dekking bekend is; een latere waardedaling
  altijd kunnen opslaan en het ontstane conflict zichtbaar houden. Onbekende
  waarden geven onbekende dekking, geen automatische afwijzing of bevestiging.
- Optionele beschikbaarheidsdatum wanneer een concrete doelvraag dit vereist.
- Een begrensde maandtijdlijn met gezamenlijke ruimte, minimumreserve en concrete
  toekomstige veranderingen; geen algemene planning- of regelsengine.
- Effectvrije vergelijking van een basisplan met enkele expliciete varianten,
  inclusief geselecteerde onzekere veranderingen. Geen scenario-opslag.

## Voor implementatie beslissen

Splits de gekozen vervolgstappen vóór uitvoering. Leg de overgang van eenvoudige
reserveringen naar toewijzingen vast met één leesbare preview, zonder verplichte
migratie voor andere gebruikers. Definieer stortingsmoment, tijdgrenzen, samenloop
van veranderingen en afronding. Ontbrekende toekomstige geldstromen zijn geen nul;
uitkomsten blijven conditioneel, geen kans op succes.

## Acceptatie en bewijs bij uitvoering

- €15.000 spaargeld dekt €10.000 buffer en €5.000 verbouwing; niet twee volledige
  reserveringen van €15.000. Waardedaling behoudt juiste waarde én zichtbaar tekort.
- Extra inleg versnelt een doel alleen wanneer gezamenlijke ruimte en reserve dit
  ondersteunen. Dezelfde middelen worden nooit dubbel als beschikbaar gerekend.
- Veranderingen werken vanaf de juiste maand; scenario's schrijven niets.
- De concrete journey toont minder herhaalde input of beter antwoord dan de
  eenvoudige variant, zonder een verplichte verdeling van alle vermogensposten.
- Black-box bewijs, rapportcontrole en begrensde performancechecks. Transacties
  worden niet per doel, groep of toekomstige maand opnieuw gescand.

## Buiten scope

Verplichte doeladministratie, automatische optimalisatie, Monte Carlo,
productadvies, fiscale simulatie, rendementsvoorspelling en persistent scenariobeheer.
