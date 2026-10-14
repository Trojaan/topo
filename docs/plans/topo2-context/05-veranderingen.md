# Plan 5 — Geplande veranderingen, alleen bij aangetoonde behoefte

Status: uitgesteld ontwerp; niet automatisch uitvoeren. Vereist: plan 3 en een
vastgelegde gebruikersvraag die de eenvoudige route niet voldoende beantwoordt.

## Startvoorwaarde

Leg eerst met een synthetische gebruiksjourney vast welke concrete verandering
herhaaldelijk nodig is, waarom een losse aanname in het gesprek niet volstaat en
welke onderhoudslast opslag oplevert. De eenvoudige maandbeelden, doelen en
rapporten blijven beschikbaar zonder deze uitbreiding.

## Mogelijk resultaat en begrensde scope

- Kleine records voor eenmalige toekomstige inkomsten/uitgaven en gedateerde
  vervanging of beëindiging van een bestaande terugkerende geldstroom.
- Onderscheid tussen een bevestigde verwachting en een onzekere mogelijkheid,
  met datum, toelichting en valuta. Een bevestigde verwachting blijft onzeker
  over daadwerkelijke realisatie.
- Compact opvragen op periode; geen prognoseresultaten opslaan.

## Voor implementatie beslissen

Herbeoordeel de scope op basis van de aangetoonde vraag. Definieer een beperkte
operatievorm zonder vrije expressies. Veranderingen op dezelfde datum voor dezelfde
stroom worden geweigerd of ondubbelzinnig opgelost. Een verstreken plan wordt niet
automatisch een transactie of actuele geldstroom; voorkom dat de gebruiker eerst
oude plannen moet opruimen om nieuw inzicht te krijgen.

## Acceptatie en bewijs bij uitvoering

- Salariswijziging, eenmalige aankoop en onzeker verlof zijn afzonderlijk leesbaar;
  bevestiging wijzigt geen huidig saldo.
- Achterblijvende verwijzingen bij bronverwijdering worden atomair geweigerd.
- Black-box bewijs voor datumfilters en preview, plus de oorspronkelijke journey
  met minder herhaalde input en zonder extra verplichte bevestigingsrondes.
- Meet een begrensde synthetische tijdlijn zonder transactieanalyse.

## Buiten scope

Agenda, automatische uitvoering, notificaties, verplicht toekomstonderhoud,
scenario-opslag en gebeurtenisgraph.
