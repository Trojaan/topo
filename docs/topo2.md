# Topo 2: het actuele vermogensoverzicht

Topo 2 is een zelfstandige lokale engine naast de bestaande Topo. Het bewaart
de laatste toestand van rekeningen, bezittingen, schulden, doelen, transactierecords en terugkerende verwachtingen. Een
wijziging vervangt de eerdere gegevens: er is geen financiële historie, changelog,
herstel naar eerdere standen of import van historische Topo-pakketten. Transacties
uit eerdere jaren blijven gewone records; eerdere versies van die records worden
niet bewaard. Bestaande Topo 2-contexten blijven bruikbaar.

## Beginnen

Vanaf `v0.6.0` leveren de [standalone installers](../README.md#installeren) zowel
`topo` als `topo2`, zonder Python of `uv`. Voer de installer opnieuw uit als je
Topo al hebt geïnstalleerd. Controleer met `topo2 --version` en gebruik `topo2`
rechtstreeks in plaats van `uv run topo2`.

Voor ontwikkelen vanuit deze repository, na `uv sync --frozen`:

```bash
uv run topo2 init --context /pad/naar/mijn-financien/context.json
uv run topo2 contract
uv run topo2 contract change
uv run topo2 show --context /pad/naar/mijn-financien/context.json
uv run topo2 summary --context /pad/naar/mijn-financien/context.json
```

De bovenliggende directory moet bestaan. `init` overschrijft nooit een context.
Alle commando's geven JSON terug; `--json` wordt ook geaccepteerd. Resultaten staan
onder `result`, fouten onder `error` met `code` en `message`. Exitcodes: 0 bij
succes, 1 bij gegevens-/opslagfouten en 2 bij ongeldige CLI-argumenten.
De schemas van `contract` beschrijven de inhoud van `result` en het change-request.

## Eén groep wijzigingen, één bevestiging

Schrijf een request of geef het via stdin door:

```json
{
  "contract_version": "topo2.cli/3",
  "accounts": {
    "add": [
      {
        "id": "spaarrekening",
        "label": "Spaarrekening",
        "type": "savings",
        "balance": "12500.50",
        "currency": "EUR",
        "as_of": "2026-10-04"
      }
    ]
  },
  "goals": {
    "add": [
      {
        "id": "buffer",
        "name": "Buffer",
        "target_amount": "20000",
        "account_ids": ["spaarrekening"]
      }
    ]
  }
}
```

```bash
uv run topo2 change --context /pad/naar/context.json --request /pad/naar/request.json
```

Zonder `confirmation_token` toont dit oude en nieuwe records en een token; het
contextbestand blijft identiek. Toon de preview aan de gebruiker. Voeg na expliciete
menselijke goedkeuring de teruggegeven token toe als `confirmation_token` aan
**hetzelfde request** en voer hetzelfde commando uit. Alle wijzigingen worden
samen opgeslagen of geheel geweigerd. Er zijn geen opgeslagen voorstellen.

`add`, `update` en `delete` zijn beschikbaar onder `accounts`, `assets`, `debts`, `goals`, `transactions` en `cashflows`.
`update` vervangt een compleet record, inclusief optionele velden; haal het huidige
record eerst op met `show`. `delete` bevat IDs. Een ID mag per sectie slechts één
keer worden gewijzigd. IDs zijn globaal uniek, stabiel en onafhankelijk van labels.
Verwijzingen moeten na de hele wijziging geldig zijn: verwijder doelkoppelingen
of brokerkoppelingen samen met het gekoppelde record. Een request zonder bewerkingen
wordt geweigerd. Identieke effectieve updates leveren `status: unchanged`, een lege
`changes` en `confirmation_token: null`, zonder schrijfactie of nieuwe bevestiging.

De token bindt het genormaliseerde request, het absolute contextpad en alle actuele
bestandsbytes. Na een tussentijdse verandering volgt `STALE_CONFIRMATION`; maak dan
een nieuwe preview en vraag opnieuw goedkeuring. Herhalen van een al toegepaste
wijziging is geen replay en schrijft niets opnieuw. De token is een lokale
consistentiecontrole, geen bewijs van menselijke identiteit of toestemming.

Gebruik bij wijzigingen vanaf bronnen herhaaldelijk `--source /pad/naar/bestand`:

```bash
topo2 change --context /pad/naar/context.json --request /pad/naar/request.json \
  --source /pad/naar/export.csv --source /pad/naar/saldo.png \
  --source /pad/naar/doel.txt --source /pad/naar/geconverteerd.json
```

Geef bij bevestiging dezelfde bronnen op. Hun opgeloste absolute paden en exacte
ingelezen bytes binden mee aan de token; ook gewijzigde witruimte blokkeert de
bevestiging. Volgorde en herhaalde vermelding van hetzelfde opgeloste pad maken
geen verschil. Relatieve paden worden vanaf de werkdirectory opgelost. Een
ontbrekende of onleesbare bron geeft een opslagfout zonder contextwijziging.
Bronnen worden niet opgeslagen in de context. Deze binding controleert consistentie,
niet of een agent de bronnen juist heeft geïnterpreteerd.

## Records en uitkomsten

- Rekeningen: `payment`, `savings`, `investment`. `balance` mag negatief of onbekend
  (`null`) zijn. Een brokerrekening bevat uitsluitend geldsaldo.
- Bezittingen: `etf`, `property`, `vehicle`, `cash`, `investment`, `other`.
  `value` is de totale positiewaarde, niet de koers; deze mag onbekend of nul zijn,
  maar niet negatief. `broker_account_id` is optioneel en verwijst naar een
  beleggingsrekening. Portefeuilletotalen worden niet naast ETF-posities ingevoerd.
- Elk bekend saldo of bekende waarde vereist `as_of`. Peildata blijven zichtbaar
  via `show` en previews. Het overzicht gebruikt de laatste opgeslagen waarden,
  ook wanneer de peildata verschillen; het is geen historische peildatumanalyse.
- Geef geldbedragen als decimale strings op, maximaal 28 cijfers waarvan maximaal
  8 achter de komma. Berekeningen gebruiken `Decimal`, nooit floats.
- `currency` is standaard zichtbaar `EUR`; andere drieletterige hoofdlettercodes
  krijgen een eigen subtotaal. Er is geen automatische valutaomrekening.
- Een doel heeft een positief `target_amount`, optionele `target_date`,
  `account_ids` en `asset_ids`. Gekoppelde records moeten dezelfde valuta hebben.
  Elke post telt per doel eenmaal mee; een post kan meerdere doelen dienen zonder
  reservering. Zonder koppelingen is de voortgang nul. Een ontbrekende waarde
  maakt de voortgang onvolledig. Percentage = bekend bedrag / streefbedrag × 100,
  zonder afronding voor presentatie of begrenzing op 100%. Dit zijn uitsluitend
  gekoppelde-waardevelden; reservering en resterend bedrag staan afzonderlijk (plan 4).
- `summary` geeft `wealth_overview`, subtotalen met `known_total`, `missing_ids`,
  `complete` en doelvoortgang. Een lege context heeft geen subtotalen. Onbekend wordt
  niet als bekend nul gepresenteerd. Daarnaast geeft `net_wealth` bekende nettovermogenstotalen met afzonderlijke
  waardebeschikbaarheid en inventarisvolledigheid; zie plan 2 hieronder.

## Transacties importeren en zoeken

Het actuele CLI-contract is `topo2.cli/3`; het basisopslagformaat is
`topo2.context/2`, geïntroduceerd in v0.7.0. Optionele contextverklaringen
gebruiken `topo2.context/3`, zoals beschreven bij compact lezen. Bestanden met
`topo2.context/1` blijven leesbaar zonder herschrijven. Een preview en een
identieke herimport veranderen ze evenmin. De eerstvolgende bevestigde wijziging
slaat de volledige context in versie 2 op (versie 3 met contextverklaringen,
versie 4 met schulden/beschikbaarheid, versie 5 met transactiesoorten,
versie 6 met verwachtingen/instellingen,
of versie 7 met doelverrijkingen)
en behoudt de bestaande gegevens.
Oudere Topo 2-programma’s kunnen versie 2 niet lezen; gebruik de actuele installer.
Nieuwe JSON-aanvragen gebruiken contractversie 3 (ook de standaard bij weglaten).
Expliciete versie-2-change-requests worden met een migratiemelding geweigerd:
ontdek `topo2 contract` opnieuw en bereid de aanvraag voor versie 3 voor.
De versiegrens maakt het nieuwe behoud bij import en de no-op-uitvoer expliciet;
`change.update` blijft volledige records vervangen. Bestaande versie-2-contexten
hebben geen migratie nodig. Lezen, preview en no-op herschrijven niets.

Een transactie bevat een vaste `id`, `account_id`, `booking_date`, getekend
`amount`, expliciete `currency` en `description`. `category` en `source` zijn
optionele vrije labels. De omschrijving mag leeg zijn. Datum en bedrag zijn
verplicht; nul, positieve en negatieve bedragen zijn geldig. IDs zijn globaal
uniek en bestaan uit letters, cijfers, `_` of `-`, maximaal 128 tekens.
De rekening moet bestaan na de volledige batch. De transactievaluta wordt
letterlijk bewaard en hoeft niet gelijk te zijn aan de rekeningvaluta; er vindt
geen omrekening plaats.

Transacties tellen niet nogmaals mee in vermogen of doelvoortgang. Topo leidt
geen saldo af uit transacties. Transactiehistorie is geen wijzigingshistorie:
correcties vervangen een record en verwijderingen bewaren geen oude versie.

### Import

JSON bevat een lijst transactierecords met alle verplichte velden. CSV is UTF-8 (een BOM mag)
met komma als scheidingsteken en dezelfde veldnamen; tekst met komma’s of
regelovergangen wordt gequote. `category` en `source` mogen ontbreken of leeg
zijn. De overige kolommen zijn verplicht; dubbele of onbekende kolommen en
onvolledige rijen worden geweigerd.

```csv
id,account_id,booking_date,amount,currency,description,category,source
bank_tx_001,spaarrekening,2026-10-13,-12.50,EUR,Boodschappen,Boodschappen,Export
```

```bash
topo2 import-transactions --context /pad/naar/context.json \
  --file /pad/naar/transacties.csv --format csv
```

Dit geeft aantallen `added`, `updated`, `skipped`, `total_changes`, maximaal twintig
oude/nieuwe voorbeelden in `changes`, en een `confirmation_token`. `truncated`
geeft aan of er meer wijzigingen zijn; `--details` geeft alle wijzigingen.
Na expliciete menselijke goedkeuring:

```bash
topo2 import-transactions --context /pad/naar/context.json \
  --file /pad/naar/transacties.csv --format csv --confirmation-token TOKEN
```

Vaste IDs bepalen herimport. Verplichte velden vervangen hun eerdere waarden.
Bij bestaande transacties behouden weggelaten `category` en `source` de opgeslagen
labels. Een aangeleverd label vervangt het oude; JSON `null` wist expliciet. Een
lege JSON-string is ongeldig. Bij CSV behouden ook lege optionele cellen bestaande
labels; gebruik JSON `null` om te wissen. Bij nieuwe transacties worden ontbrekende
of lege CSV-labels `null`. Effectief identieke records worden overgeslagen, ook
wanneer bestaande verrijkingen niet opnieuw zijn aangeleverd. Er is geen automatische
deduplicatie op datum, bedrag of omschrijving. Dubbele IDs binnen hetzelfde
bestand en ongeldige records weigeren de gehele import. Een volledig identieke
of lege geldige import retourneert `status: unchanged`, zonder token of schrijfactie.

De bevestiging bindt alle ingelezen bestandsbytes (inclusief overgeslagen records),
het formaat en de actuele context. Ook een gewijzigde overgeslagen regel of
wijziging in witruimte vereist een nieuwe preview. `--details` verandert alleen
de weergave en kan bij bevestiging worden aangepast. Het bronbestand wordt niet
gekopieerd naar de context of als bewijsrecord opgeslagen.

Voor handmatige invoer, correctie en verwijdering bestaat dezelfde
`transactions.add/update/delete`-vorm in `change`. Rekening en transacties kunnen
in één batch worden toegevoegd of samen worden verwijderd; een rekening met
achterblijvende transacties kan niet worden verwijderd.

### Gericht opvragen

```bash
topo2 transactions --context /pad/naar/context.json \
  --account spaarrekening --from-date 2026-10-01 --to-date 2026-10-31 \
  --search boodschappen --currency EUR --min-amount -100 --max-amount 0 \
  --offset 0 --limit 100
```

Alle filters gelden samen. Datums en bedraggrenzen zijn inclusief. `--category`
matcht het vrije label exact; `--search` zoekt letterlijk, zonder onderscheid
tussen hoofdletters, in omschrijving, categorie en bron. Er zijn geen regexes
of uitvoerbare zoekexpressies. Bedragfilters vergelijken de opgegeven getallen,
zonder valutaomrekening; gebruik `--currency` wanneer je één valuta bedoelt.

De uitvoer bevat `records`, het totale aantal treffers `total`, `offset` en
`limit`. De sortering is oplopend op boekingsdatum en vervolgens ID. Standaard
worden honderd records geleverd, maximaal duizend per pagina. Gebruik opeenvolgende
offsets op een ongewijzigde context om alle treffers te lezen. Onbekende
filterwaarden leveren nul treffers op. Er zijn geen financiële subtotalen of
analyses in deze uitvoer; de agent rekent zelf met de gerichte selectie.
`show` blijft de volledige context inclusief alle transacties tonen.

## Agentinstructies voor een financiële werkmap

Neem de volgende instructies over in de `AGENTS.md` van de financiële werkmap:

> Gebruik voor deze context uitsluitend `topo2` en ontdek het contract met
> `topo2 contract`. Lees rekeningen, bezittingen en doelen met `show`. Gebruik
> `transactions` met filters en paginering voor transacties; lees niet steeds
> de hele context. Importeer JSON/CSV met `import-transactions` en vaste IDs.
> Bij import behouden ontbrekende labels en lege CSV-cellen bestaande waarden;
> JSON null wist expliciet. Bij change.update neem je bestaande optionele velden
> zelf mee: dat blijft een volledige-recordvervanging.
> Transacties wijzigen rekeningstanden niet automatisch. Gebruik
> `aggregate-transactions` voor compacte gerealiseerde totalen en gerichte details
> voor verdere analyse. Bereid transactiesoorten expliciet voor in de gezamenlijke
> preview; raad betekenis nooit uit teken, categorie of omschrijving. Terugbetalingen
> verlagen gesigneerd economische uitgaven; transfers en onbekenden staan apart.
> Een geselecteerde transferhelft bewijst geen paar. Dekking en classificatie-
> volledigheid zijn afzonderlijke beperkingen. Behoud ook kind bij herimport.
> Combineer samenhangende
> wijzigingen in één `change`-request. Bind oorspronkelijke bronnen en het
> geconverteerde importbestand met herhaalde --source-opties. Toon de oude en nieuwe waarden, EUR als
> standaardvaluta en eventuele ontbrekende waarden. Vraag één expliciete menselijke
> bevestiging voor de volledige preview. Gebruik de token pas na deze bevestiging.
> Bij annuleren voer je niets uit. Bij een gewijzigde context maak je een nieuwe
> preview en vraag je opnieuw bevestiging. Bewerk `context.json` nooit rechtstreeks.
> Brokerrekeningen bevatten alleen geldsaldo; ETF-records bevatten totale
> positiewaarden. Begin bij de gebruikersvraag, lees screenshots waar mogelijk en
> zet exports om naar het vaste importformaat. Gebruik stabiele IDs uit vaste
> bankreferenties en hergebruik bekende rekeningkoppelingen, categorieën en input.
> Scheid bronwaarden, voorbereide interpretaties en onbekenden in de preview.
> Stel maximaal drie korte vraagbundels over wezenlijke onduidelijkheden; vraag
> geen volledige inventarisatie. Onleesbare of ambigue bronnen worden niet geraden.
> Identieke heraanlevering levert geen nieuwe bevestiging of schrijfactie op.
> Bij bijgewerkte exports neem je bekende verrijkingen mee in volledige updates.
> Benoem ontbrekende schulden of maandinformatie alleen bij de betreffende uitkomst.
> Begin bij lezen met `context`; vraag transacties gericht op.
> Optionele volledigheid en dekking horen bij dezelfde gezamenlijke preview;
> vraag nooit per domein uitsluitend om een compleetverklaring.
> Noem bekende nettosommen uitsluitend volledig nettovermogen als waarden én
> inventarissen compleet zijn. Onbekende schulden zijn geen nul. Leg roodstand
> uitsluitend dubbel vast met een expliciete overdraft-account_id-koppeling;
> controleer bedrag, valuta en peildatum. Raad geen koppelingen op basis van labels.
> Vraag beschikbaarheid alleen bij een concrete vraag naar inzetbaar geld.
> Neem bestaande beschikbaarheid en schuldvelden mee bij volledige updates.
> Gebruik voor maandvragen eerst aggregate-transactions en alleen zo nodig details.
> Bereid enkele cashflows voor, eventueel één samengevoegde variabele-uitgavenpost.
> Gebruik een korte export niet als bewijs van frequentie of complete inventaris.
> Beschrijf in source wat de samengevoegde post omvat; sluit afzonderlijk opgenomen
> lasten uit die selectie uit. Eigen overboekingen en doelinleg leveren geen tweede
> uitgavenpost op. Bespreek de ondergrens van known_room als voorzichtige ruimte
> binnen de bekende posten; ontbrekende bedragen en inventaris blijven beperkingen.
> Reserve en toelichting zijn optioneel; vraag er niet standaard naar.
> Een transactiewijziging geeft geen toestemming om een verwachting te veranderen.
> Neem bestaande verwachtingen en instellingen mee bij heraanlevering.
> Begin doelen met naam en positief bedrag; datum alleen indien voldoende precies.
> Vraag geen inventarisatie, verdeling of voorkeuren voor een eerste doel.
> reserved_amount is optioneel; ontbrekend is onbekend, geen nul. remaining_amount
> gebruikt alleen de expliciete reservering; oude linked_value staat afzonderlijk.
> Een reservering bewijst geen aanwezige of exclusieve middelen. Bespreek mogelijke
> overschrijding en onbekende dekking zonder opslag te blokkeren. Minimumreserve
> blijft een afzonderlijke saldodrempel. monthly_contribution is intentie, zonder
> betaling of tweede maandelijkse aftrek. Neem alle doelverrijkingen mee in updates.
> Prioriteit en toelichting zijn optioneel; geen benodigde inleg of haalmaand.
> De open menselijke gebruikspoorten van plannen 3 en 6 blijven open; technische opdrachten
> bevestigen geen classificaties of verwachtingen.
> Gebruik report met expliciet uitvoerpad en referentiedatum voor vroege lokale HTML.
> Vraag geen financiële bevestiging of extra inventarisatie voor rapportgeneratie.
> Geef transactiegrenzen samen op; zonder grenzen gaat het over alle opgeslagen
> records zonder claim van volledige dekking. Bewaar rapporten buiten Git.
> De menselijke gebruikspoorten van plannen 3, 4 en 6 blijven open.
> Verzin geen waarden,
> valutaomrekening of financiële adviezen.

Houd contextbestanden, lockbestanden en requests buiten Git. `topo2 init` maakt
geen agentbestanden of ignore-regels; gebruik een eigen afgeschermde werkmap.

## Implementatie en verificatie

`src/topo_v2` importeert de oude `topo` niet. CLI → engine → opslag/modellen;
modellen importeren geen opslag of orchestration. De zuivere goals-berekening
ontvangt geen transacties en importeert uitsluitend modellen. De zuivere cashflows-berekening
ontvangt geen context of transacties en importeert alleen modellen. De zuivere leesprojectie in
`reading.py` hergebruikt engineberekeningen en kent geen CLI of opslag. Pydantic-modellen zijn zowel
validatiebron als bron van de versiegebonden JSON-schema's.

Een schrijfvergrendeling op `context.json.lock` omvat lezen, tokencontrole,
validatie en publicatie. Dit is een betekenisloos technisch lockbestand zonder
financiële gegevens. Het nieuwe bestand wordt volledig gevalideerd, in een privé
tijdelijk bestand geschreven, geflusht en atomair vervangen. Lezen ziet een hele
oude of nieuwe toestand. Fouten vóór vervanging behouden het vorige bestand.

`scripts/verify.sh` controleert beide engines. De Topo 2-journey bewijst 20
rekeningen, 5 ETF's, bulkbevestiging en doelvoortgang. De opslagtests controleren
onder meer verouderde tokens, gelijktijdige schrijvers en falende vervanging.
De optionele synthetische prestatiepoort is:

```bash
uv run python scripts/benchmark_topo2.py
```

Deze meet afzonderlijke CLI-processen met 1.000 rekeningen en 10.000 transacties.
Lezen, gericht zoeken, import, behoud bij herimport, previews, bevestigde updates
van 1.000 transacties en brongebonden no-ops moeten binnen één seconde blijven.
Elke meting bevat uitvoergrootte en piek-RSS van het CLI-proces. De RSS-meting
gebruikt `resource` op macOS/Linux. Met `--transactions 100000` wordt dezelfde route
zonder harde tijdgrens als schaalprofiel gemeten. Hij leest geen persoonlijke
gegevens en verwijdert de tijdelijke context na afloop.

De [invoerjourney](plans/topo2-context/00-bewijs.md) beschrijft daarnaast de
synthetische bankexport, twee saldoschermen en het doelbericht, met afzonderlijk
technisch bewijs en de werkelijk uitgevoerde agentsessie.

Een specifieke Tally-adapter, migratie van historische Topo-pakketten,
automatische categorisatie, transferherkenning,
saldo-afleiding, projecties en een gebruikersinterface
vallen buiten deze versie. De agent kan exports omzetten naar het vaste
importformaat en analyses uitvoeren op opgevraagde transacties.

## Geplande uitbreiding

Het [contextplan](plans/topo2-context/README.md) onderscheidt de technische levering
van plannen 0–4 en de transactieaggregaties van plan 6 van de nog niet
geïmplementeerde vervolguitbreidingen. Het [externe gebruiksbewijs 0–2](plans/topo2-context/gebruik-bewijs-00-02.md)
levert de basisjourney met echte bevestigingen, inclusief herstel en beperkingen.
Plan 4 levert eenvoudige doelverrijkingen; zie hieronder. De menselijke gebruikspoorten van de nieuwe classificaties uit plan 6 en de verwachtingen uit plan 3 blijven open. De prioriteit is snel inzicht uit exports, screenshots en weinig
aanvullende input, met één gezamenlijke preview en bevestiging. Gedeeltelijke
context blijft bruikbaar; uitgebreide doelverdeling en gezamenlijke tijdlijnen
zijn uitgesteld tot concrete gebruiksjourneys hun noodzaak aantonen. Behoud van
verrijkingen bij herimport en bronbinding bij gecombineerde invoer zijn beschikbaar
volgens het hierboven beschreven contract.

## Compact lezen en gerichte onzekerheid (plan 1)

Gebruik voor een eerste gesprek `topo2 context --context /pad/naar/context.json`.
Deze route geeft rekeningen, bezittingen, doelen, schulden en de bekende totalen,
zonder transactierecords. `show` blijft de volledige context leveren; haal
transacties gericht op met `transactions`. Het CLI-contract blijft `topo2.cli/3`:
`context` en de optionele change-secties zijn additieve uitbreidingen; bestaande
requests behouden hun betekenis. Ontdek de nieuwe schemas met `contract context`
en `contract change`.

Peildata en onbekende waarden blijven in de records staan. Geef voor een expliciet
ouderdomsoordeel beide opties op:

```bash
topo2 context --context /pad/naar/context.json \
  --reference-date 2026-10-14 --max-age-days 30
```

`age_days` is referentiedatum minus waardepeildatum; `stale` is uitsluitend waar
bij een bekende waarde die **meer dan** de grens oud is. Een toekomstige peildatum
heeft een negatieve leeftijd. Zonder beleid of bekende waarde is `stale: null`;
zonder peildatum of referentiedatum is `age_days: null`. Er is geen impliciete
systeemdatum, standaardgrens of blokkade op lezen.

Optionele verklaringen gaan mee in dezelfde `change`-preview en bevestiging als
andere records. Bijvoorbeeld de volgende *synthetische* uitbreiding:

```json
{
  "inventories": {
    "add": [{"id": "accounts", "status": "partial", "checked_on": "2026-10-14"}]
  },
  "transaction_coverage": {
    "add": [{
      "id": "export_september", "account_id": "spaarrekening",
      "from_date": "2026-09-01", "to_date": "2026-09-30",
      "checked_on": "2026-10-14"
    }]
  }
}
```

Dit voorbeeld vereist een bestaande `spaarrekening`. `inventories` gebruikt de
vaste domein-ID's `accounts`, `assets`, `debts`, `goals`, `cashflows`; deze vormen
een eigen namespace. Status is `unknown`, `partial` of door de mens verklaard
`complete`, met verplichte controledatum `checked_on`. Een afwezig record wordt
gelezen als onbekend, met controledatum `null`. Een lege, compleet verklaarde
inventaris verschilt van een onbekende inventaris. Het is een menselijke verklaring,
geen door de engine afgeleide volledigheid of verplicht invoerveld. Schulden zijn financiële records vanaf plan 2; structurele geldstromen vanaf plan 3.
Verklaar een lege schuldeninventaris alleen compleet bij expliciet bevestigd geen
schulden. Een bekend schuldrecord bewijst geen complete inventaris.

`transaction_coverage` heeft gewone globaal unieke IDs en verwijst naar een
bestaande rekening. Beide datumgrenzen zijn inclusief; één dag is geldig,
omgekeerde grenzen zijn ongeldig. Meerdere, ook overlappende intervallen blijven
letterlijke verklaringen; gaten worden niet opgevuld. Een export bewijst dekking
alleen als zijn periode expliciet bekend en menselijk bevestigd is. De eerste en
laatste transactiedatum bewijzen niets over dekking. Import behoudt verklaringen
en past ze niet automatisch aan. Verwijder rekening en bijbehorende dekking in
één batch wanneer de rekening wordt verwijderd.

De eerste bevestigde wijziging met verklaringen schrijft `topo2.context/3`.
Versie 1 en 2 blijven leesbaar; lezen, preview en no-op herschrijven niets.
Zonder plan-2-velden blijven gewone wijzigingen zonder verklaringen versie 2
schrijven. Versie 3 blijft minimaal versie 3, ook na verwijdering van de laatste
verklaring; schulden/beschikbaarheid verhogen de opslag naar versie 4. Oude
programma's kunnen versie 3 niet lezen. Gebruik de actuele code/installatie.

`context` onderscheidt inventarisstatus, ontbrekende waarden, ouderdom en expliciete
transactiedekking. `summary.complete` blijft uitsluitend betekenen dat bekende
records/koppelingen geen ontbrekende waarden hebben; het zegt niets over onbekende
posten buiten die records. `limitations` benoemt de betreffende uitkomst:
rekening-/bezittingeninventaris en waarden bij het vermogensoverzicht, schulden
bij nettovermogen, gekoppelde ontbrekende/verouderde waarden bij het betreffende
doel, en rekeningdekking bij transactieanalyse. `coverage_limited` betekent alleen
dekking binnen de getoonde intervallen; andere perioden blijven onbekend.
Structurele maandruimte wordt vanaf plan 3 op een expliciete referentiedatum berekend;
nettovermogen wordt vanaf plan 2 berekend. Er is geen
algemeen volledigheidspercentage of automatische vragenlijst. Lokale HTML-rapporten
zijn vanaf plan 7 beschikbaar.

Operationele aanvulling voor de agent: begin met `context`, gebruik `show` alleen
wanneer volledige records voor een wijziging nodig zijn en vraag transacties gericht
op. Bespreek beschikbare uitkomsten direct. Vraag uitsluitend hiaten die de actuele
vraag wezenlijk veranderen; schulden beperken geen dagelijkse transactieanalyse.
Vraag nooit apart per domein om volledigheid te verklaren. Bereid een expliciete
exportperiode of vrijwillige verklaring samen met de broninvoer voor, met maximaal
drie korte verduidelijkingsbundels en één gezamenlijke menselijke bevestiging per
samenhangende wijziging. Bij identieke effectieve aanlevering vervallen schrijven
en bevestiging. De [planstatus en het bewijs](plans/topo2-context/01-bewijs.md)
onderscheiden technische tests en de nog open menselijke gebruikspoort.


## Schulden, nettovermogen en beschikbaarheid (plan 2)

`debts` ondersteunt dezelfde gezamenlijke `change`-preview, bevestiging en
add/update/delete als andere records. Elk schuldrecord heeft `id`, `label`, `type`
(`mortgage`, `loan`, `credit_card`, `overdraft`, `other`), `amount`, `currency`
(standaard EUR) en `as_of`. `amount` is een niet-negatieve decimale string of
`null`; een bekend bedrag vereist een peildatum. Optioneel zijn `interest_rate`
(niet-negatief jaarlijks percentage, dezelfde decimale precisiegrens), `end_date`
en `account_id`. Rente en einddatum leiden niet tot aflossings- of maandlastberekeningen.

Een negatief rekeningsaldo verlaagt het bestaande vermogensoverzicht al.
Een schuld die **dezelfde** roodstand beschrijft moet daarom expliciet via
`account_id` worden gekoppeld, uitsluitend met type `overdraft`. Maximaal één
schuld per rekening; bekende bedragen, dezelfde valuta en dezelfde peildatum zijn
verplicht. `amount` is exact het tegengestelde van het niet-positieve saldo; ook
beide nul is geldig. Tegenstrijdigheden en ongeldige verwijzingen weigeren de
hele wijziging. Wijzig rekening en schuld samen, of verwijder de koppeling/het
schuldrecord expliciet. Ontkoppelen maakt het een afzonderlijk afgetrokken schuld;
zet het bedrag dan alleen over als werkelijk een afzonderlijke schuld bestaat.
Er is geen automatische schuldherkenning: de agent moet bronoverlap expliciet
bespreken. Niet-gekoppelde schuldrecords gelden als afzonderlijke schulden.

`summary` behoudt `kind: wealth_overview`, bestaande `subtotals` en `goals`.
Daarnaast bevat `net_wealth` de inventarisstatus van accounts/assets/debts en
`subtotals` per valuta met:

- `known_account_asset_total`: getekende rekeningstanden plus bezittingswaarden;
- `known_debt_total`: uitsluitend afzonderlijk afgetrokken bekende schuldstanden;
- `known_total`: het verschil; `linked_debt_ids` verklaart welke schuldrecords al
  via hun rekeningsaldo meetellen;
- `missing_ids` en `complete`: ontbrekende bedragen binnen bekende records;
- `inventory_complete`: alle drie inventarissen expliciet compleet verklaard.

Een bekende deelsom met `complete: false` of `inventory_complete: false` is geen
volledig nettovermogen. Een onbekende schuldstand en onbekende schuldeninventaris
blijven afzonderlijk zichtbaar. Alleen schulden geeft een negatieve bekende
nettosom; een lege context krijgt geen verzonnen valuta of totaal. De inventaris-
status blijft ook bij een lege context zichtbaar. Valuta worden nooit omgerekend.

Rekeningen en bezittingen accepteren optioneel `availability` met `free`,
`restricted` of `unknown`, en `availability_note` als korte toelichting. Afwezig of
`null` betekent onbekend. De aparte `summary.availability` toont per valuta
`known_free_total`, `known_restricted_total`, `unknown_availability_ids` en
`missing_ids`. Alleen expliciet verklaarde beschikbaarheid telt mee in de
betreffende categorie; negatieve saldi leveren geen beschikbare middelen.
Een bezitsoort bewijst geen liquiditeit, en een waardering voorspelt geen verkoop-
opbrengst. Dit is geen berekening van bestedingsruimte na schulden of reserveringen.
Vraag deze optionele gegevens uitsluitend bij een concrete bestedingsvraag.

`context` toont ook schuldrecords en hun peildata. Het expliciete ouderdomsbeleid
werkt hetzelfde als voor rekeningen en bezittingen. Onbekende/gedeeltelijke
vermogensinventarissen, ontbrekende bedragen en oude waarden beperken nettovermogen;
schuldonzekerheid beperkt geen doelvoortgang of transactieanalyse. Beschikbaarheid
krijgt eigen beperkingen. Geen transactierecords in `summary` of `context`.

Het CLI-contract blijft additief `topo2.cli/3`. Schulden en beschikbaarheidsvelden
vereisen `topo2.context/4`. Contexten 1–3 blijven leesbaar; een preview of no-op
herschrijft niets. De eerste effectieve bevestigde wijziging met nieuwe velden
schrijft versie 4. Eenmaal versie 4 blijft versie 4, ook na verwijderen van alle
nieuwe gegevens. Zonder deze velden blijven de bestaande versie-2/3-regels gelden.
Oudere programma's kunnen versie 4 niet lezen. Herimport behoudt schulden,
beschikbaarheid, verklaringen en doelen; `change.update` blijft volledige records
vervangen. Ontdek actuele schemas met `topo2 contract`.

Zie [plan-2-bewijs](plans/topo2-context/02-bewijs.md) voor technische journeys,
metingen en de afzonderlijk nog open menselijke gebruikspoorten.


## Transactiebetekenis en compacte aggregaties (plan 6)

Ontdek `topo2 contract aggregate-transactions`. Het CLI-contract blijft
`topo2.cli/3`. Transacties krijgen optioneel `kind`: `income`, `expense`,
`internal_transfer` of `unknown`. Ontbrekend/null en expliciet unknown tellen als
onbekende classificatie. De engine leidt niets af uit teken, categorie of tekst.
Categorie is een onafhankelijk vrij label. Classificaties worden pas opgeslagen
na dezelfde gezamenlijke menselijke preview/bevestiging als overige wijzigingen.

```bash
topo2 aggregate-transactions --context /pad/naar/context.json \
  --from-date 2026-09-01 --to-date 2026-10-31 \
  --group-by month --group-by category
topo2 aggregate-transactions --context /pad/naar/context.json \
  --account betaal --currency EUR --category Boodschappen
```

Datumgrenzen zijn inclusief. Rekening, valuta, categorie, bedraggrenzen en zoektekst
gebruiken dezelfde filters als `transactions`; aggregaties hebben geen paginering.
`--group-by` accepteert elke dimensie maximaal eenmaal. Zonder groepering volgen
alleen valutatalen; groepen bevatten maand (YYYY-MM), categorie (null is onbekend)
en valuta. Alleen aanwezige groepen worden gemaakt, deterministisch gesorteerd op
valuta, maand, categorie (null eerst). `filters` toont de toegepaste selectie.
Een lege selectie heeft count 0, lege totals/groups en classification_complete null.

Per valuta en groep staan `count`, `receipts` (positieve rekeningbedragen),
`outflows` (positieve omvang van negatieve rekeningbedragen) en `net_movement`
(som van alle bedragen). Economisch `income` sommeert alleen income-bedragen;
`expenses` is de negatief genomen som van expense-bedragen. `classified_net_cashflow`
is income minus expenses. Een aankoop -100 en terugbetaling +20, beide expense,
geven uitgaven 80. Teruggevorderd inkomen -50 verlaagt income. Negatieve economische
subtotalen zijn toegestaan; teken geeft richting, kind geeft expliciete betekenis.

`internal_transfers` en `unknown` geven ieder count, receipts, outflows en
net_movement. Zij tellen wel in rekeningbewegingen, niet in economische inkomsten/
uitgaven. Rekeningnetto = classified_net_cashflow + transfernetto + onbekend netto.
Een enkele transferhelft wordt letterlijk geteld; ook netto nul bewijst geen paar.
Alle bedragen zijn Decimal-strings, valuta worden nooit samengevoegd of omgerekend.

`classified_count`, `unknown_count` en `classification_complete` beschrijven alleen
de geselecteerde records. Met onbekenden is de economische nettoflow een deelsom.
Afzonderlijk geeft `coverage` per geselecteerde rekening de expliciete intervallen.
Zonder rekeningfilter blijven alle contextrekeningen zichtbaar, ook zonder treffers;
een onbekende expliciet geselecteerde rekening krijgt status unknown. Met beide
datumgrenzen toetst de engine de vereniging van verklaarde intervallen: complete,
partial (ten minste gedeeltelijke overlap) of unknown. Aansluitende intervallen
sluiten een gat; transactiedatums bewijzen nooit dekking. Zonder beide grenzen is
status declared of unknown, zonder volledige-periodeclaim. Categorie- en valutafilters
veranderen deze rekeningverklaringen niet en bewijzen geen volledige inventaris.

JSON/CSV-import behoudt ontbrekend kind; lege CSV-cellen behouden eveneens.
JSON null wist expliciet, een aangeleverde soort vervangt. Dit geldt ook voor
categorie en bron. `change.update` blijft alle optionele velden volledig vervangen.
Niet-null kind vereist opslag `topo2.context/5`; bestaande versies 1–4 blijven
leesbaar. Alleen een effectieve bevestigde wijziging migreert; lezen, preview en
no-op schrijven niets. Versie 5 blijft na wissen/verwijderen behouden. Oudere
programma's kunnen versie 5 niet lezen. Zonder kind blijven bestaande opslagregels
gelden, met uitsluiting van kind uit oude opslagformaten.

Aggregaties gebruiken één transactiescan met accumulators per valuta/groep, geen
scan per groep. De CLI leest en valideert wel het volledige JSON-bestand: compacte
uitvoer betekent geen constant geheugen. De benchmark meet ook ongesplitste,
gegroepeerde en gefilterde aggregaties bij 10.000 en 100.000 transacties.
Structurele gemiddelden uit verwachtingen zijn vanaf plan 3 beschikbaar;
prognoses, betaalagenda’s en scenario’s worden niet berekend.


## Voorlopig structureel maandbeeld (plan 3)

Begin bij de gebruikersvraag en bestaande bronnen. De agent gebruikt gerealiseerde
aggregaties om een paar verwachtingen voor te bereiden; hij vraagt geen tweede
uitgavenadministratie of bedrag per categorie. Een bandbreedte en gedeeltelijke
inventaris zijn geldig. Alle interpretaties gaan mee in één gezamenlijke preview,
met maximaal drie korte verduidelijkingsbundels en één menselijke bevestiging.
Technische tests en deze implementatieopdracht zijn geen financiële bevestiging.

`cashflows` ondersteunt add/update/delete in dezelfde `change`. Een record bevat
`id`, `label`, `kind` (income/expense), `frequency`, verplichte `start_date`,
standaardvaluta EUR en optioneel `end_date`, `category`, `source`, `debt_id`.
`amount` is één niet-negatieve decimale string, een object met niet-negatieve
geordende `lower` en `upper`, of null/onbekend. Beide grenzen zijn verplicht bij
een band; nul is bekend nul. De bestaande geldprecisie geldt. Een schuldverwijzing
moet bestaan in dezelfde valuta. Verwijder of wijzig verwijzingen samen met de
schuld. Een betaling verlaagt geen schuldstand of saldo.

Voorbeeld van een synthetische gezamenlijke voorbereiding:

```json
{
  "cashflows": {"add": [
    {"id": "salary", "label": "Salaris", "kind": "income", "amount": "3000",
     "frequency": "four_weekly", "start_date": "2026-10-14"},
    {"id": "groceries", "label": "Boodschappen", "kind": "expense",
     "amount": {"lower": "80", "upper": "120"}, "frequency": "weekly",
     "start_date": "2026-10-14", "source": "Voorlopige band; uitsluitend supermarkt"}
  ]},
  "cashflow_settings": {"EUR": {
    "minimum_reserve": "5000", "note": "Boodschappen flexibel; buffer heeft prioriteit"
  }}
}
```

Instellingen zijn optioneel per valuta, zonder voorkeurenrecords of extra IDs.
`minimum_reserve` is een niet-negatieve saldodrempel: een aan te houden bedrag,
geen maandelijkse inhouding. Zij verlaagt de maandruimte niet; er wordt geen
reservedekking berekend. `note` is vrije korte tekst, geen rekenregel. Een change
vervangt het instellingenobject voor een opgegeven valuta; null verwijdert het.
Weggelaten valuta blijven behouden. Een weggelaten veld in een vervangen object
wordt onbekend. Deze wijzigingen delen de bestaande bronbinding en bevestiging.

```bash
topo2 monthly-room --context /pad/naar/context.json --reference-date 2026-10-14
topo2 contract monthly-room
```

De datum is verplicht; er is geen impliciete systeemdatum. Begin/eind zijn inclusief.
Alleen op die dag actieve verwachtingen tellen mee. Dit is een structureel gemiddelde,
geen betaalagenda of tijdlijn. Geen proratering bij een start midden in de maand.
Maandfactoren zijn exact weekly 52/12, four_weekly 13/12, monthly 1,
quarterly 1/3, yearly 1/12, ook in schrikkeljaren. Bedragen zijn positief;
kind bepaalt inkomen of uitgave. Neem nooit het midden van een band.

Per post worden de maandondergrens naar beneden en bovengrens naar boven afgerond
op acht decimalen. Rationale factoren en gehele deling vermijden tussentijdse
factorafronding. Daarna worden de grenzen exact opgeteld met lokale Decimal-precisie.
Een exact bedrag kan hierdoor een minimale afrondingsband krijgen. Geen impliciete
centafronding; de genormaliseerde postbanden zijn controleerbaar in `records`.

De uitkomst bevat referentiedatum, cashflows-inventaris, lokale `limitations` en
`currencies`. Per valuta staan:

- `records`: actieve IDs, kind en `monthly_amount` (lower/upper, of null);
- `known_income`, `known_expenses` en `known_room`: banden van bekende deelsommen;
- `missing_ids`, `complete`: ontbrekende bedragen binnen de actieve records;
- `room`: volledige band alleen bij bekende bedragen én complete inventaris;
- `minimum_reserve` en `note`: letterlijk de optionele instellingen.

`known_room.lower` = laagste bekende inkomsten − hoogste bekende uitgaven;
`known_room.upper` = hoogste bekende inkomsten − laagste bekende uitgaven.
De ondergrens is voorzichtige ruimte **binnen bekende posten**, geen garantie of
volledig besteedbaar bedrag. Bij onbekende leningbetalingen en/of onvolledige
inventaris blijft `room` null, terwijl bekende deelsommen bespreekbaar blijven.
Een nul in een bekende deelsom is geen waarde voor een ontbrekende post: diens
monthly_amount blijft null. Valuta worden afzonderlijk en deterministisch getoond.
Een lege context krijgt geen verzonnen valuta; instellingen zonder verwachtingen
maken alleen de expliciet opgegeven valuta zichtbaar. Inventarisvolledigheid blijft
een afzonderlijke menselijke verklaring, geen verplichte toegang tot inzicht.

`context` bevat ook verwachtingen en instellingen, zonder transactiedetails.
Met het bestaande datum-/ouderdomsbeleid bevat het hetzelfde `monthly_room`;
zonder dat beleid is monthly_room null. Gebruik de losse opdracht voor alleen een
maandbeeld, zonder ouderdomsvraag. `summary` blijft het vermogensoverzicht.

De agent voorkomt dubbeltelling door de selectie achter een samengevoegde post
te benoemen en afzonderlijk opgenomen lasten daarvan uit te sluiten, bijvoorbeeld
boodschappen inclusief supermarkt maar exclusief hypotheek/verzekering/abonnement.
Eigen overboekingen zijn geen consumptieve uitgaven. Doelinleg wordt niet opnieuw
afgetrokken. Geen automatische patroonherkenning, overlapdetectie, categorisatie
of voorsteladministratie in de engine. Historische transactiecorrecties veranderen
verwachtingen niet; herimport behoudt verwachtingen en instellingen.

Nieuwe data vereisen `topo2.context/6`; het CLI-contract blijft additief topo2.cli/3.
Versies 1–5 blijven leesbaar zonder schrijven, preview/no-op migreren niet. Een
effectieve bevestigde wijziging met verwachtingen of instellingen schrijft versie 6;
die blijft na verwijderen behouden. Alle eerdere soorten, schuld-, beschikbaarheids-
en verklaringvelden blijven bewaard. De maandberekening ontvangt uitsluitend
verwachtingen, instellingen, inventaris en datum; opslagvalidatie leest nog wel het
hele JSON-bestand. Zie [plan-3-bewijs](plans/topo2-context/03-bewijs.md).


## Eenvoudige doelen (plan 4)

Een kort bericht “€10.000 voor een verbouwing volgend jaar” is genoeg om naam en
streefbedrag voor te bereiden. Een exacte datum volgt alleen uit voldoende precieze
broninput; geen verzonnen 31 december. Valuta EUR is de bestaande zichtbare standaard.
Geen verplichte rekeningverdeling, inventarisatie of voorkeurenvragen. Alle waarden
gaan mee in de bestaande gezamenlijke preview, met maximaal drie korte
verduidelijkingsbundels en één expliciete menselijke bevestiging.

Goal behoudt id, name, positief target_amount, currency, optionele target_date en
bestaande account_ids/asset_ids. Nieuw en optioneel:

- reserved_amount: expliciet bestemd bedrag; ontbrekend/null is onbekend.
- monthly_contribution: voorgenomen maandinleg, geen automatische betaling.
- priority: low/normal/high als menselijke rangorde, zonder verdelingsregel.
- note: vrije korte toelichting, maximaal 256 tekens, geen rekenregel.

Beide nieuwe bedragen zijn niet-negatief, inclusief nul, met dezelfde 28-cijfer/
acht-decimalengrens als andere geldbedragen. Reservering en maandinleg hebben geen
bovengrens ten opzichte van het doel of aanwezige middelen. Zij wijzigen geen
saldi, schulden of verwachtingen en leveren geen tweede aftrek in monthly-room op.

summary.goals bevat deze velden en remaining_amount: max(target_amount minus
reserved_amount, 0), uitsluitend wanneer de reservering bekend is. 10.000 met
4.000 geeft 6.000; onbekend blijft null; expliciet nul geeft 10.000. Bij 12.000
reservering resteert nul, terwijl 12.000 zichtbaar blijft. Er is geen impliciete
nulaanname of opgeslagen afgeleid bedrag.

linked_value toont de oude gekoppelde waarde met known_amount, percentage,
missing_ids en complete. De gelijknamige bestaande velden op de doeluitkomst zijn
compatibele weergaven van dezelfde gekoppelde waarde. Zonder koppelingen blijft
deze waarde nul, maar dat zegt niets over de reservering. Koppelingen worden niet
omgezet en tellen nooit mee in remaining_amount. Ontbrekende/verouderde gekoppelde
waarden beperken alleen deze gekoppelde uitkomst, niet een bekende reservering.

summary.reservation_comparison bevat per doelvaluta goal_ids, known_reserved_total,
unknown_reservation_ids, known_free_total, missing_value_ids,
unknown_availability_ids, inventories, possible_excess en coverage_unknown.
Vrije waarde hergebruikt plan 2: alleen expliciet vrije positieve bedragen tellen;
negatieve saldi leveren geen beschikbare middelen. Zonder vermogensrecords in de
valuta is known_free_total null. possible_excess is null zonder vergelijking,
anders true wanneer de bekende bestemmingen boven de bekende vrije deelsom liggen.
coverage_unknown is onafhankelijk waar bij ontbrekende reserveringen, waarden,
beschikbaarheid of niet-complete accounts/assets/goals-inventaris. Beide signalen
kunnen tegelijk bestaan. Bekende deelsommen blijven bruikbaar; geen inventaris
hoeft voor een doel compleet te worden verklaard.

Een reservering is een bevestigde bestemming, geen bewijs van aanwezigheid of
exclusieve toewijzing. Ook bij possible_excess false en coverage_unknown false
claimt de engine geen gezamenlijke of exclusieve dekking. Schulden worden niet
opnieuw afgetrokken. minimum_reserve blijft afzonderlijk in cashflow_settings een
saldodrempel en wordt niet stilzwijgend met doelreserveringen verrekend.
Waardedalingen, mogelijke overschrijding en onbekende dekking blokkeren opslag niet.

CLI-contract blijft additief topo2.cli/3. Niet-null doelverrijkingen, inclusief nul,
vereisen topo2.context/7. Versies 1–6 blijven leesbaar; lezen, previews en effectieve
no-ops schrijven/migreren niets. Versie 7 blijft behouden na wissen; oude
opslagversies krijgen geen nieuwe doelvelden. change.update blijft een volledig
record vervangen: neem bekende optionele velden mee. Transactie-import behoudt
alle doelverrijkingen en overige contextgegevens.

De zuivere goals-berekening ontvangt doelen, waarde-index, beschikbaarheid en
inventarissen, geen transacties of opslag. Eén groepering per doelvaluta, geen
transactiescan per doel. De CLI leest en valideert nog het hele JSON-bestand;
compacte uitvoer betekent geen constant geheugen. Geen benodigde inleg, haalmaand,
gezamenlijke haalbaarheid of vervolgplan. Zie [plan-4-bewijs](plans/topo2-context/04-bewijs.md).
De menselijke gebruikspoorten van plannen 3 en 6 blijven expliciet open.

## Lokale HTML-rapportage (plan 7)

```bash
topo2 report --context /pad/buiten-git/context.json \
  --output /pad/buiten-git/financiele-foto.html --reference-date 2026-10-15
topo2 report --context /pad/buiten-git/context.json \
  --output /pad/buiten-git/oktober.html --reference-date 2026-10-15 \
  --from-date 2026-10-01 --to-date 2026-10-31
topo2 contract report
```

Referentiedatum en uitvoerpad zijn verplicht. De uitvoerdirectory moet bestaan;
een bestaand pad wordt altijd geweigerd, ook bij gelijktijdige publicatie. Kies
voor een volgend rapport een nieuw pad. Er is geen overschrijfoptie of browseropening.
Succes geeft de gewone JSON-envelope met absoluut output-pad, html_bytes en metadata.
Ongeldige gegevens geven INVALID_DATA; opslagfouten IO_ERROR (exit 1). Ontbrekende
verplichte CLI-argumenten geven exit 2. Opslagversies en bestaande contractbetekenissen
veranderen niet; report is een additieve topo2.cli/3-opdracht.

Eén ingelezen snapshot voedt de financiële foto, gerealiseerde transactietotalen,
structurele verwachtingen en doelen. De referentiedatum bepaalt alleen welke
verwachtingen actief zijn. Vermogen toont de actuele opgeslagen waarden met hun
eigen peildata; het is geen historische peildatumanalyse. Zonder transactiegrenzen
worden alle opgeslagen transacties per boekingsmaand getoond. Met grenzen zijn beide
verplicht en inclusief. Een aanwezige transactie, ontbrekende maand of onbegrensde
selectie bewijst geen volledige dekking. Classificatie en expliciete rekeningdekking
blijven afzonderlijk zichtbaar.

Gerealiseerde bedragen en verwachtingen worden nooit tot één totaal samengevoegd.
Gekoppelde doelwaarde staat afzonderlijk van expliciete reservering; resterend bedrag
komt alleen uit die reservering. Maandinleg is intentie en verlaagt de maandruimte
niet opnieuw. Mogelijke reserveringsoverschrijding en onbekende dekking zijn signalen,
geen claim van gezamenlijke of exclusieve middelen. Minimumreserve blijft een aparte
saldodrempel. Alle uitkomsten komen uit de bestaande gedeelde enginefuncties.

Lege, minimale en gedeeltelijke contexten zijn normale rapporten: bekende waarden
blijven zichtbaar, onbekend is geen nul en beperkingen staan bij hun uitkomst.
Er zijn geen verplichte inventarisatie-, rekeningverdelings- of voorkeurenvragen.
De huidige software ondersteunt alle drie rapportonderdelen; ontbrekende persoonlijke
gegevens zijn geen ontbrekende softwarefunctionaliteit.

Metadata bevat report_version topo2.report/1, contract_version topo2.cli/3,
context_schema, context_id, context_sha256 (exacte bronbytes), reference_date,
from_date en to_date (null bij onbegrensde selectie). Dit identificeert de gelezen
snapshot zonder historie, bronarchief of herstelmogelijkheid toe te voegen.

HTML werkt volledig offline, met ingebedde CSS en zonder scripts of externe assets.
Vrije tekst wordt ge-escapet en Decimal-waarden blijven exact. Het complete bestand
wordt privé geschreven/geflusht en zonder vervanging atomair gepubliceerd via een
hard link in dezelfde directory. Ondersteunt het bestandssysteem dat niet, dan volgt
een opslagfout; er is geen onveilige kopieerfallback. Fouten vóór publicatie laten geen
gedeeltelijk rapport achter. Rapportgeneratie leest de context zonder schrijflock,
bevestiging of migratie en verandert geen contextbytes of mtime.

Rapporten kunnen gevoelige gegevens bevatten: bewaar ze, contexten en requests buiten
Git. Voor agents: genereer vroeg vanuit bekende gegevens, ontdek contract report,
geef expliciet datum/pad en desgewenst selectieperiode op. Vraag geen financiële
bevestiging voor genereren. Voor nieuwe contextmutaties blijft de bestaande menselijke
preview/bevestigingsflow gelden. De menselijke gebruikspoorten van plannen 3, 4 en 6
blijven open; rapportgeneratie bevestigt geen feiten of bedoelingen.

De zuivere rapportprojectie hergebruikt reading, cashflows en transactions; de renderer
ontvangt uitsluitend rapportdata en doet geen financiële berekeningen. Geen detailaanroep
of transactiescan per doel. De volledige JSON-context wordt nog steeds ingelezen en
gevalideerd. Zie [plan-7-bewijs](plans/topo2-context/07-bewijs.md) voor controles,
bronjourney, visuele inspectie en het schaalprofiel.
