# Topo-capabilities

Dit is de operationele capability-map voor agents en maintainers. Lees deze pagina
voordat je Topo gebruikt. De actuele machinecontracten blijven opvraagbaar met
`uv run topo contract describe --json` en `uv run topo contract schema <command>
--json`.

Topo is een lokale context-engine. Het kan financiële feiten met herkomst en tijd
opslaan, voorstellen door een mens laten autoriseren, analyses uitvoeren en iedere
uitkomst verklaren. Het geeft geen financieel advies, heeft geen webinterface en
veronderstelt geen netwerk of externe credentials.

## Publieke workflows

| Doel | Commando | Effect |
| --- | --- | --- |
| Werkmap en contextpakket maken | `topo init`, `context init` | Nieuwe lokale context |
| Identiteit en integriteit controleren | `context status`, `context verify` | Alleen lezen |
| Context migreren, herstellen, bewaren of scrubben | `context migrate`, `restore`, `compact`, `privacy-scrub` | Nieuwe gecontroleerde generatie; scrub herschrijft expliciet historie |
| Letterlijke brontransacties importeren | `source import` | Preview, daarna geautoriseerde generatie met bewijs en open bronclassificaties |
| Bronclassificaties in bulk naar Topo vertalen | `source classify-batch` | Preview, daarna één generatie met alle bevestigde Topo-classificaties |
| Terugkerende cashflows herkennen | `discover run` | Effectvrije kandidaten; nog geen feiten |
| Een voorstel indienen of beslissen | `proposal submit`, `confirm`, `correct`, `reject`, `confirm-batch`, `reject-batch` | Open voorstel of geautoriseerde beslissing |
| Ontbrekende context bepalen en beantwoorden | `workflow next`, `workflow respond` | Eén deterministische vraag; antwoord wordt een open voorstelbatch |
| Gerealiseerde of genormaliseerde cashflow, vermogen of scenario analyseren | `analyze run` | Effectvrije, traceerbare analyse |
| Veilige declaratieve regels beheren | `rule validate`, `preview`, `activate` | Alleen activatie muteert na autorisatie |
| Herkomst van een uitkomst tonen | `explain --ref` | Alleen lezen |
| Contracten ontdekken | `contract describe`, `contract schema` | Alleen lezen |

Alle mutaties zijn idempotent via `operation_id`, bewaken gelijktijdigheid met
`expected_generation` en publiceren atomair. Een autorisatieplichtig commando
wordt eerst met `authorization: null` aangeroepen. Gebruik daarna dezelfde request
met de teruggegeven `preview_ref` en een expliciete menselijke autorisatie.

## Grote aantallen transacties classificeren

`source import` bewaart de categorie van een adapter als
`domain.cashflow/source_classification`. Dat is broninformatie, niet automatisch
de betekenis die cashflowanalyse gebruikt. Gebruik `source classify-batch` om veel
open bronvoorstellen in één keer naar canonieke Topo-classificaties te vertalen en
te bevestigen.

Een request bevat één `batch_id` en één of meer mappings. Iedere mapping selecteert
exact op `category` en optioneel op `rule_version` en `explanation`. Gebruik
`proposal_refs` binnen de selector wanneer slechts een gecontroleerde subset van
een verder gelijke groep mag worden verwerkt. Selectors mogen niet overlappen en
iedere selector moet minimaal één open bronvoorstel vinden. Een transactie die al
een bevestigde Topo-classificatie heeft, laat de volledige batch veilig falen.

```json
{
  "contract_version": "topo.cli/0.1",
  "operation_id": "<uuid7>",
  "context_id": "<uuid7>",
  "expected_generation": "<uuid7>",
  "actor": {"actor_type": "agent", "actor_id": "local-agent"},
  "reason": "Vertaal gecontroleerde Tally-groepen",
  "batch_id": "<uuid7>",
  "mappings": [
    {
      "source": {
        "category": "Eten",
        "rule_version": "tally-4",
        "explanation": "Boodschappen"
      },
      "target_classification": "groceries_household"
    }
  ],
  "authorization": null
}
```

De preview groepeert de effecten per doelclassificatie en vermeldt zowel het aantal
als alle geraakte voorstel-id's. Na autorisatie worden alle canonieke assertions,
de beslissingen op de oorspronkelijke bronvoorstellen en één gezamenlijk
autorisatiebewijs in één nieuwe generatie gepubliceerd. Ook duizenden transacties
kosten daardoor niet duizenden generaties.

De beschikbare canonieke cashflowclassificaties zijn:

- inkomsten: `income`, `salary`, `holiday_allowance`, `self_employment`,
  `pension_payment`, `social_benefit`, `allowance`, `alimony`, `interest`,
  `dividend`;
- uitgaven: `expense`, `housing`, `groceries_household`, `transport`,
  `healthcare`, `insurance`, `taxes`, `childcare_education`, `subscriptions`,
  `leisure`, `debt_payment`, `other_expense`;
- bijzonder: `internal_transfer` en `unclassified`.

Gebruik brede doelen zoals `income` en `expense` alleen als een specifiekere
classificatie niet verantwoord is. Splits gemengde broncategorieën eerst met de
optionele velden of expliciete `proposal_refs`. De betekenis van deze begrippen en
de veiligheidsgrens staan in [`domain.md`](domain.md) en [`../CONTEXT.md`](../CONTEXT.md).

## Analysevoorwaarden

- Gerealiseerde maandcashflow gebruikt alleen bevestigde
  `domain.cashflow/classification/*`-assertions; bronclassificaties tellen niet mee.
- Interne overboekingen worden alleen uit inkomsten en uitgaven gehouden wanneer
  de relevante transferbetekenis bevestigd is.
- Ontbrekende rekeningtoerekening of transactiedekking maakt totalen onvolledig;
  ontbrekende classificaties maken de categorie-uitsplitsing voorlopig.
- Scenario's blijven projecties en schrijven nooit terug naar de context.
- Onbekende waarden blijven onbekend; Topo maakt daarvan niet stilzwijgend nul.

Zie [`domain.md`](domain.md) voor de volledige veiligheidssemantiek en
[`architecture.md`](architecture.md) voor eigenaarschap en afhankelijkheidsrichting.
