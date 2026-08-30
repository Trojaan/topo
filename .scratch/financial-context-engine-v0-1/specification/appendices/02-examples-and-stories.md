# Bijlage 2 — voorbeelden en end-to-end-verhalen

Alle voorbeelden zijn normatieve gedragsvoorbeelden onder `topo.cli/0.1`; IDs zijn voor leesbaarheid verkort. Weggelaten envelopevelden volgen [bijlage 1](01-json-contracts.md). De voorbeelden vormen acceptatiefixtures, geen volledige testsuite.

## 1. Capabilityvoorbeelden

### 1.1 Contract discovery

Input:

```json
{ "contract_version": "topo.cli/0.1" }
```

`topo contract describe --json` retourneert `outcome: succeeded`, de ondersteunde command-ID's en schema-refs. `topo contract schema proposal.confirm --json` retourneert een Draft 2020-12 schema waarin mutationmetadata, immutable proposalref en preview-autorisatie verplicht zijn.

Een request met `topo.cli/1.0` wordt technisch niet uitgevoerd: non-zero exit, stdout bevat indien mogelijk één fout-envelope, `diagnostics[0].code: INCOMPATIBLE_CONTRACT_VERSION`, `effect: none`.

### 1.2 Letterlijke bronimport

Input voor `source import`:

```json
{
  "contract_version": "topo.cli/0.1",
  "operation_id": "0191...001",
  "context_id": "0191...ctx",
  "expected_generation": "0191...g1",
  "actor": { "actor_type": "source_adapter", "actor_id": "adapter.tally" },
  "reason": "Import July statement",
  "adapter": { "adapter_id": "adapter.tally", "adapter_version": "0.1.0" },
  "records": [{
    "source_id": "main-account",
    "record_id": "2026-07-25:salary",
    "booking_date": "2026-07-25",
    "money": { "amount": "3200.00", "currency": "EUR" },
    "description": "SALARY ACME",
    "source_classification": {
      "category": "Inkomen",
      "rule_version": "tally-rules-17",
      "explanation": "Matched employer rule"
    }
  }]
}
```

Verwacht: de letterlijke datum, money, description en bronidentiteit worden immutable observation evidence en transactieassertions. De Tally-classificatie wordt een proposal, niet een bevestigd feit. `generation_after` is nieuw. Replay van exact `operation_id` retourneert `no_change` met dezelfde oorspronkelijke refs en maakt geen generatie.

### 1.3 Effectvrije discovery

`discover run` over drie vergelijkbare salaristransacties retourneert:

```json
{
  "outcome": "succeeded",
  "generation_before": "0191...g2",
  "generation_after": "0191...g2",
  "result": {
    "candidates": [{
      "candidate_id": "candidate:salary-monthly",
      "proposal_type": "recurring_cashflow",
      "frequency": "monthly",
      "money": { "amount": "3200.00", "currency": "EUR" },
      "evidence_refs": ["tx:may", "tx:june", "tx:july"],
      "deviations": [],
      "producer": "domain.cashflow.recognition/0.1.0",
      "detection": { "scheme": "pattern_score/0.1", "score": "0.94" }
    }]
  }
}
```

Discovery schrijft de kandidaat niet weg. Met slechts twee maandwaarnemingen is `candidates` leeg en bevat `attention_items` de reden `INSUFFICIENT_PATTERN_HISTORY`; Topo verzint geen recurring cashflow.

### 1.4 Proposal submit en expliciete bevestiging

`proposal submit` slaat één geselecteerde kandidaat immutable op en maakt een generatie. `proposal confirm` zonder autorisatie retourneert exitcode 0:

```json
{
  "outcome": "requires_authorization",
  "generation_before": "0191...g3",
  "generation_after": "0191...g3",
  "result": {
    "preview_ref": "preview:0191...p1",
    "effects": [{ "action": "create_confirmed_assertion", "proposal_ref": "proposal:salary" }]
  },
  "diagnostics": [],
  "next_actions": [{
    "action_type": "authorize_preview",
    "priority": "blocking",
    "requires_user_input": false,
    "requires_authorization": true
  }]
}
```

Een tweede request met dezelfde basisgeneratie, immutable proposalref en menselijke autorisatie van `preview:0191...p1` maakt een confirmed assertion en een nieuwe generatie. De proposal blijft bestaan met decision-ref.

### 1.5 Correctie en afwijzing

Bij `proposal correct` geeft de gebruiker gestructureerd aan dat `3200.00` moet zijn `3250.00`. Verwacht: originele proposalpayload onveranderd, proposalstatus `corrected`, nieuw `user_statement` evidence, confirmed assertion `3250.00` die naar bronbewijs én correctie verwijst. Geen tweede bevestigingsronde na de expliciete correctie.

`proposal reject` maakt geen assertion; het bewaart actor, reden en decision in proposalhistorie.

### 1.6 Validatie en invalid mutation refusal

Een proposal voor een `jurisdiction.nl/valuation/woz` zonder waardepeildatum:

```json
{
  "outcome": "rejected",
  "generation_before": "0191...g4",
  "generation_after": "0191...g4",
  "diagnostics": [{
    "code": "NL_WOZ_AS_OF_DATE_REQUIRED",
    "severity": "error",
    "path": "/proposal/proposed_assertion/module_data/valuation_date",
    "retryable": true,
    "effect": "none"
  }]
}
```

Een expliciet volledige ownershipverdeling van `0.60 + 0.30` wordt eveneens zonder write geweigerd. Een onbekende optionele hypotheekrente blijft daarentegen geldige context en wordt een analyse-aandachtspunt.

### 1.7 Stale generation refusal

Een muterend request noemt `expected_generation: g4` terwijl `CURRENT` inmiddels `g5` is. Verwacht: `outcome: conflict`, exitcode 0, geen nieuwe generatie, diagnostic `STALE_GENERATION`, `retryable: true`, `effect: none`. De aanroeper moet actuele toestand lezen, zo nodig opnieuw previewen en bewust opnieuw autoriseren.

### 1.8 Analyze en lokale onzekerheid

Een net-worthrequest met EUR-spaargeld en USD-beleggingen maar zonder wisselkoers retourneert:

- EUR-subtotaal `complete`;
- USD-subtotaal `complete`;
- geconverteerd totaal `unavailable` met `MISSING_EXCHANGE_RATE`;
- geen impliciete koers en geen mislukte procesexit.

Een ontbrekende optionele assetwaardering maakt het relevante totaal `provisional` en laat het object afzonderlijk zien. Een echt overlappend conflict in dezelfde exclusieve debt balance maakt alleen de afhankelijke component `unavailable`.

### 1.9 Explain

`explain --ref analysis_component:0191...ac1` retourneert betekenis, gebruikte generatie, assertions en evidence, module- en contractversies, aannames, alle rekenstappen, afronding, ontbrekende requirements en de reden voor de next question. Menselijke tekst mag deze structuur samenvatten maar niet aanvullen met een nieuwe financiële reden.

### 1.10 Workflow next

Bij een bijna lege graph retourneert `workflow next` bijvoorbeeld:

```json
{
  "outcome": "succeeded",
  "result": {
    "actions": [{
      "action_type": "answer_question",
      "priority": "required",
      "reason_code": "NET_WORTH_NEEDS_ACCOUNT_BALANCE",
      "affected_component": "analysis.net_worth/total",
      "command": "proposal submit",
      "request_template": { "proposal_type": "account_balance" },
      "requires_user_input": true,
      "requires_authorization": false
    }]
  }
}
```

Er staat geen shellstring in het resultaat en het commando wordt niet uitgevoerd.

### 1.11 Regelpreview en activatie

Een regelpakket met vrije expressie `eval: "..."`, onbekende predicate of cross-viewveld wordt semantisch geweigerd. Een geldig pakket doorloopt `validate`, compatibiliteitscontrole en effectvrije preview. Activatie zonder expliciete autorisatie geeft `requires_authorization`; met stale actief-manifest geeft `conflict`; alleen geldige actuele autorisatie wisselt het volledige manifest atomair.

### 1.12 Storage recovery

Na een crash met complete staging maar ongewijzigde `CURRENT` opent Topo de geldige huidige generatie, ruimt aantoonbaar veilige orphan/stagingdata op en publiceert de orphan nooit. Bij checksumtampering blijven veilige reads/diagnostiek beschikbaar, maar mutations en migrations falen technisch met `PACKAGE_INTEGRITY_FAILED` en `effect: none`.

## 2. End-to-end-verhaal A — weinig gegevens, niets verzinnen

### Situatie

Noor maakt een leeg contextpakket, voegt zichzelf en huishouden `Noor` toe en vraagt naar nettovermogen. Er zijn nog geen rekeningen, saldi, assets of debts.

### Route

1. De pakketinitialisatie publiceert generatie `g1` met context-, persoon- en huishoudentity en hun expliciete membershipassertion.
2. `analyze run` voor `analysis.context_inventory` op `2026-08-25` retourneert zelf `complete`.
3. De vereistenmatrix meldt voor `analysis.net_worth/total` ontbrekende rekeningen/saldi, assets/waarderingen en debts/standen. De status van die net-worthcomponent is `unavailable`.
4. `workflow next` kiest de eerste doelgebonden vraag over aanwezige rekeningen en saldi als `required`; het retourneert een requesttemplate, geen uitvoering.
5. Een direct net-worthrequest retourneert geen `0.00`. Het resultaat bevat geen value, de requirements en één next question.

### Verwachte kernuitvoer

```json
{
  "component_id": "analysis.net_worth/total",
  "status": "unavailable",
  "requirements": [
    { "requirement": "account_balances", "state": "missing", "impact": "blocks_component" }
  ],
  "next_question": "Which accounts and balances belong to this scope as of 2026-08-25?"
}
```

### Veiligheidsbewijs

Topo behandelt onbekend vermogen niet als nul, neemt geen EUR aan voordat het bedrag is ingevuld, neemt geen partner of 50/50-toerekening aan en maakt geen financieel advies van de vervolgvraag.

## 3. End-to-end-verhaal B — banktransacties naar herleidbaar maandbeeld

### Situatie

Huishouden De Vries importeert drie maanden transacties uit Tally: salaris, huur, boodschappen en transfers tussen betaal- en spaarrekening.

### Route

1. `source import` schrijft iedere letterlijke banktransactie als immutable observation met Tally-bronref. Tally-labels en uitleg worden proposals.
2. De importpreview laat zien welke records nieuw zijn. Autorisatie betreft de bronimport; afgeleide classificaties worden niet stil bevestigd.
3. `discover run` vindt maandelijks salaris en huur, maar produceert bij variabele boodschappen alleen een kandidaatbandbreedte wanneer drempel en intervalregels dat toelaten. De run is effectvrij.
4. `proposal submit` bewaart de geselecteerde kandidaten. De gebruiker bekijkt de proposalpreview en bevestigt salaris en huur. Een verkeerd Tally-label wordt met `proposal correct` hersteld.
5. Bevestigde paired transfers krijgen classificatie `internal_transfer`; een ongepaarde overschrijving blijft zichtbaar en voorlopig.
6. `analysis.realized_monthly_cashflow` over `[2026-07-01, 2026-08-01)` telt alle boekingen in net movement, sluit confirmed internal transfers uit income/expense en toont unclassified afzonderlijk.
7. Omdat beide opgenomen rekeningen volledige transactiedekking en bekende huishoudtoerekening hebben, zijn de kerncomponenten `complete`; de ongepaarde overschrijving maakt alleen de categorieverdeling `provisional`.
8. `analysis.normalized_monthly_cashflow` gebruikt uitsluitend confirmed recurring cashflows. Salaris `3200` en huur `1200` leveren exacte maandbedragen; kandidaten tellen niet mee.
9. `explain` op normalized net toont proposal, bevestiging, bewijsrecords, frequentiefactoren en ongeronde tussenstappen.

### Verwachte kernuitvoer

```json
{
  "components": [
    { "component_id": "realized/net_movement", "status": "complete", "value": { "amount": "850.00", "currency": "EUR" } },
    { "component_id": "realized/category_breakdown", "status": "provisional", "warnings": ["UNCLASSIFIED_TRANSACTION"] },
    { "component_id": "normalized/income", "status": "complete", "value": { "amount": "3200.00", "currency": "EUR" } },
    { "component_id": "normalized/fixed_expense", "status": "complete", "value": { "amount": "1200.00", "currency": "EUR" } }
  ]
}
```

### Veiligheidsbewijs

Discovery schrijft niets, Tally is geen bron van bevestigde betekenis, transfers worden niet dubbel geteld, incomplete classificatie tast alleen afhankelijke uitsplitsing aan en iedere uitkomst blijft naar boekingen en beslissingen herleidbaar.

## 4. End-to-end-verhaal C — spaargeld, schulden en één toekomstige verandering

### Situatie

Huishouden Jansen legt op `2026-08-25` een EUR-spaarrekening van `30000.00`, woningwaardering `350000.00` en twee hypotheekdelen van samen `240000.00` vast. De woning is via expliciete huishoudtoerekening volledig in scope. Een pensioenrekening heeft `retirement_restriction` en wordt apart getoond. Het huishouden wil vergelijken wat een vanaf `2027-01-01` €500 lagere maandelijkse uitgave betekent op `2027-12-31`.

### Route

1. De gestructureerde invoer wordt gevalideerd. De WOZ-assertion bevat eigen waardepeildatum en herkomst; hypotheekdelen zijn afzonderlijke debts; rekening en saldo worden niet als extra asset gedupliceerd.
2. Net worth op `2026-08-25` berekent `30000 + 350000 - 240000 = 140000 EUR`. Pensioen staat in een aparte restricted sectie en telt niet automatisch mee.
3. Het scenario bevat één `recurring_cashflow_change` van `-500.00 EUR` per maand vanaf `2027-01-01`, met doelobject, datum en reden. Het is een expliciete aanname en geen canonical mutation.
4. De scenariovergelijking toont normalized monthly cashflow van baseline en scenario en een delta van `+500.00 EUR` per maand.
5. Net worth op `2027-12-31` verandert niet door die cashflowaanname alleen. De uitvoer waarschuwt `CASHFLOW_DESTINATION_NOT_MODELED`: Topo spaart het overschot niet automatisch.
6. Als het huishouden ook een expliciete `value_override` voor de spaarrekening op `2027-12-31` opgeeft, mag projected net worth die gebruiken en toont de engine aanname en delta.

### Verwachte kernuitvoer

```json
{
  "baseline": {
    "normalized_monthly_cashflow": { "amount": "900.00", "currency": "EUR" },
    "net_worth": { "amount": "140000.00", "currency": "EUR" }
  },
  "scenario": {
    "normalized_monthly_cashflow": { "amount": "1400.00", "currency": "EUR" },
    "net_worth": { "amount": "140000.00", "currency": "EUR" },
    "warnings": ["CASHFLOW_DESTINATION_NOT_MODELED"]
  },
  "delta": {
    "normalized_monthly_cashflow": { "amount": "500.00", "currency": "EUR" },
    "net_worth": { "amount": "0.00", "currency": "EUR" }
  },
  "knowledge_type": "projected"
}
```

### Veiligheidsbewijs

Het scenario schrijft geen feiten, voorspelt geen rendement of belasting, gebruikt geen rente-op-rente of productadvies, telt pensioen niet als vrij vermogen en maakt de niet-gemodelleerde bestemming van het overschot expliciet.

## 5. Minimale acceptatiefixtures

Een implementatie bevat ten minste geautomatiseerde fixtures voor:

- lege inventory en unavailable net worth zonder nuldefault;
- idempotente importreplay;
- effectvrije discovery met voldoende en onvoldoende historie;
- confirm zonder autorisatie en confirm met geldige autorisatie;
- correction met behoud van oorspronkelijke proposal;
- stale-generation conflict zonder effect;
- constraint refusal zonder partiële generatie;
- multi-currency subtotalen met unavailable geconverteerd totaal;
- realized cashflow met transfer en unclassified transactie;
- weekly en four-weekly maandnormalisatie met decimale tussenstappen;
- restricted pension buiten net worth;
- scenario zonder impliciete vermogensopbouw;
- explaintrace die alle gebruikte refs teruggeeft;
- checksumtampering die writes blokkeert;
- onbekende major-contractversie die technisch faalt.
