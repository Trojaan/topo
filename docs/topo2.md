# Topo 2: het actuele vermogensoverzicht

Topo 2 is een zelfstandige lokale engine naast de bestaande Topo. Het bewaart
uitsluitend de laatste toestand van rekeningen, bezittingen en doelen. Een
wijziging vervangt de eerdere gegevens: er is geen financiële historie, changelog,
herstel naar eerdere standen of gegevensmigratie. Gebruik een nieuwe context.

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
  "contract_version": "topo2.cli/1",
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

`add`, `update` en `delete` zijn beschikbaar onder `accounts`, `assets` en `goals`.
`update` vervangt een compleet record, inclusief optionele velden; haal het huidige
record eerst op met `show`. `delete` bevat IDs. Een ID mag per sectie slechts één
keer worden gewijzigd. IDs zijn globaal uniek, stabiel en onafhankelijk van labels.
Verwijzingen moeten na de hele wijziging geldig zijn: verwijder doelkoppelingen
of brokerkoppelingen samen met het gekoppelde record. Een inhoudelijk lege wijziging
wordt geweigerd.

De token bindt het genormaliseerde request, het absolute contextpad en alle actuele
bestandsbytes. Na een tussentijdse verandering volgt `STALE_CONFIRMATION`; maak dan
een nieuwe preview en vraag opnieuw goedkeuring. Herhalen van een al toegepaste
wijziging is geen replay en schrijft niets opnieuw. De token is een lokale
consistentiecontrole, geen bewijs van menselijke identiteit of toestemming.

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
  zonder afronding voor presentatie of begrenzing op 100%.
- `summary` geeft `wealth_overview`, subtotalen met `known_total`, `missing_ids`,
  `complete` en doelvoortgang. Een lege context heeft geen subtotalen. Onbekend wordt
  niet als bekend nul gepresenteerd. Dit is geen volledig nettovermogen: afzonderlijke
  schulden zijn nog niet gemodelleerd.

## Agentinstructies voor een financiële werkmap

Neem de volgende instructies over in de `AGENTS.md` van de financiële werkmap:

> Gebruik voor deze context uitsluitend `topo2` en ontdek het contract met
> `topo2 contract`. Lees complete records met `show`. Combineer samenhangende
> wijzigingen in één `change`-request. Toon de oude en nieuwe waarden, EUR als
> standaardvaluta en eventuele ontbrekende waarden. Vraag één expliciete menselijke
> bevestiging voor de volledige preview. Gebruik de token pas na deze bevestiging.
> Bij annuleren voer je niets uit. Bij een gewijzigde context maak je een nieuwe
> preview en vraag je opnieuw bevestiging. Bewerk `context.json` nooit rechtstreeks.
> Brokerrekeningen bevatten alleen geldsaldo; ETF-records bevatten totale
> positiewaarden. Noem de uitkomst een vermogensoverzicht. Verzin geen waarden,
> valutaomrekening of financiële adviezen.

Houd contextbestanden, lockbestanden en requests buiten Git. `topo2 init` maakt
geen agentbestanden of ignore-regels; gebruik een eigen afgeschermde werkmap.

## Implementatie en verificatie

`src/topo_v2` importeert de oude `topo` niet. CLI → engine → opslag/modellen;
modellen importeren geen opslag of orchestration. Pydantic-modellen zijn zowel
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

Deze meet afzonderlijke CLI-processen met 1.000 records en vereist minder dan één
seconde voor lezen, samenvatten, preview en bevestigde bulkupdate. Hij leest geen
persoonlijke gegevens en verwijdert de tijdelijke context na afloop.

Tally-import, migratie, cashflow, afzonderlijke schulden,
projecties en een gebruikersinterface vallen buiten deze eerste versie.
