# Plan 6 — Transactiebetekenis en aggregaties

Status: voorgesteld. Vereist: plannen 0 en 1.

## Resultaat

Compacte, reproduceerbare transactietotalen zonder alle records op te halen of de
gebruiker iedere transactie te laten classificeren. De agent bereidt betekenis
voor; de engine valideert en rekent.

## Scope

- Optionele transactiesoort: inkomen, uitgave, interne overboeking of onbekend.
  Bestaande vrije categorie en bron blijven behouden. Geen automatische afleiding
  in de engine; de agent mag interpretaties voorbereiden voor de gezamenlijke preview.
- Eén beperkt aggregatiecontract: periodefilters, rekening, valuta en categorie;
  groepering per kalendermaand en/of categorie. Geen querytaal of formules.
- Ontvangsten, uitgaven, netto geldbeweging, interne overboekingen en onbekende
  classificatie expliciet tonen. Sommeer met Decimal per valuta.
- Voeg bekende transactiedekking en classificatievolledigheid toe. Onbekende
  classificatie beperkt de betreffende uitsplitsing, niet alle leesuitkomsten.
- Breid het importbehoud uit plan 0 uit naar transactiesoort. Oude exportformaten
  zonder dit veld behouden bestaande classificaties. Expliciet vervangen/wissen
  blijft mogelijk en zichtbaar; `change.update` blijft een volledig record vervangen.

## Voor implementatie beslissen

Leg vast hoe correcties met afwijkend teken meetellen. Interne overboekingen tellen
niet als inkomen/uitgave; onbekende transacties blijven wel in netto geldbeweging.
Onderscheid rekeningbewegingen van economische cashflow. Een geselecteerde helft
van een transfer bewijst geen volledig paar. De engine leidt betekenis niet
stilzwijgend af uit categorie, omschrijving of teken.

De agent bundelt duidelijke interpretaties en vraagt alleen over materiële
ambiguïteiten. Geen engine-transfermatcher, afzonderlijke classificatiewizard of
verplichte vraag per transactie. Onopgeloste posten blijven zichtbaar onbekend.

## Acceptatie en bewijs

- Salaris, aankoop, terugbetaling, transfer en onbekende transactie geven verklaarbare
  totalen; detailrecords en aggregaties sluiten aan.
- Onvolledige perioden en onbekende classificaties blijven afzonderlijk zichtbaar;
  een eerste maandbeeld blijft leesbaar.
- Black-box bewijs voor import, oude exportformaten, behoud van verrijkingen,
  expliciet wissen/vervangen en gecombineerde filters.
- De gebruiksjourney laat de agent interpretaties voorbereiden zonder extra
  bevestiging per classificatiegroep en blijft binnen het gezamenlijke frictiebudget.
- Eén aggregatieaanroep vervangt alle pagina's; meet 10.000 en 100.000 transacties,
  geheugen en uitvoergrootte. Geen scan per groep.

## Buiten scope

Enginecategorisatie, engine-transfermatching, Tally-adapter, opgeslagen
classificatievoorstellen en opslagmigratie.
