# Bijlage 1 — normatieve JSON-contracten

Deze bijlage fixeert de buitenvormen die implementaties onder contractversie `topo.cli/0.1` moeten ondersteunen. JSON Schema Draft 2020-12 is de schema-taal die `contract schema` publiceert. Velden zijn gesloten (`additionalProperties: false`), behalve expliciet gemarkeerde modulepayloads; onbekende enumwaarden of major-contractversies worden geweigerd.

De voorbeelden laten UUIDv7-waarden verkort leesbaar zien. Een echte implementatie valideert volledige UUIDv7's, RFC 3339 timestamps en ISO 8601-datums.

## 1. Primitieven

| Type | Normatieve vorm |
|---|---|
| `id` | lowercase UUIDv7-string |
| `date` | `YYYY-MM-DD` |
| `instant` | RFC 3339 met tijdzone |
| `decimal` | decimale string, nooit JSON floating point |
| `currency` | ISO 4217 uppercase code |
| `ref` | `{ "ref_type": <stable enum>, "id": <id> }` |
| `period` | `{ "start": <date>, "end_exclusive": <date|null> }` |
| `money` | `{ "amount": <decimal>, "currency": <currency> }` |
| `share` | decimale string in `[0,1]` |

Een ontbrekend gegeven wordt weggelaten of expliciet `null` wanneer het schema dat toestaat; sentinelbedragen zoals `0`, lege strings of verzonnen defaults zijn verboden.

## 2. Collectiebestand

Ieder canoniek collectiebestand heeft deze buitenvorm:

```json
{
  "schema_version": "topo.context/0.1",
  "records": []
}
```

`records` is oplopend op `id`. Duplicaten zijn ongeldig. JSON-serialisatie gebruikt UTF-8, LF, vaste inspringing en een eindnewline. Object key ordering mag door de serializer worden gefixeerd, maar checksums worden altijd berekend over exact de gepubliceerde bytes.

## 3. Entity

```json
{
  "id": "018f...",
  "entity_type": "account",
  "module_id": "domain.accounts",
  "created_at": "2026-08-25T10:00:00+02:00"
}
```

Verplicht: `id`, `entity_type`, `module_id`, `created_at`. Een entity bevat geen veranderlijke naam, status, saldo, eigenaar of classificatie als mutable profielveld.

## 4. Assertion

Eigenschap en relatie gebruiken één vorm. Precies één van `object_value` en `object_ref` is aanwezig.

```json
{
  "id": "018f...",
  "subject_ref": { "ref_type": "entity", "id": "018f..." },
  "predicate": "domain.accounts/balance",
  "object_value": {
    "value_type": "money",
    "value": { "amount": "12500.00", "currency": "EUR" }
  },
  "valid_time": { "start": "2026-08-25", "end_exclusive": null },
  "recorded_at": "2026-08-25T10:05:00+02:00",
  "knowledge_type": "user_provided",
  "verification_status": "confirmed",
  "provenance": [
    { "ref_type": "evidence", "id": "018f..." }
  ],
  "supersedes": null,
  "module_data": {}
}
```

Voor een relatie vervangt `object_ref` het value-object. `module_data` is de enige open modulepayload, is namespaced door de eigenaar van `predicate` en wordt door diens schema gevalideerd.

## 5. Evidence en bronrecord

```json
{
  "id": "018f...",
  "evidence_type": "source_record",
  "source": {
    "adapter_id": "adapter.tally",
    "adapter_version": "0.1.0",
    "source_id": "household-main",
    "record_id": "bank:2026-07:line-104",
    "record_checksum": "sha256:..."
  },
  "record_path": "evidence/records/018f....json",
  "recorded_at": "2026-08-25T10:00:00+02:00",
  "supersedes": null
}
```

Andere `evidence_type`-waarden zijn `user_statement` en `derived_from_assertions`. Een afleiding vermeldt alle assertionrefs plus `producer_id`, `producer_version` en een stabiele `reason_ref`. Een evidence-record bewaart de gebruikte genormaliseerde bronvelden zelfvoorzienend; een externe locatie is slechts metadata.

## 6. Proposal

```json
{
  "id": "018f...",
  "proposal_type": "assertion",
  "producer": {
    "producer_type": "rule_module",
    "producer_id": "domain.cashflow.recognition",
    "producer_version": "0.1.0"
  },
  "proposed_assertion": {
    "subject_ref": { "ref_type": "entity", "id": "018f..." },
    "predicate": "domain.cashflow/frequency",
    "object_value": { "value_type": "code", "value": "monthly" },
    "valid_time": { "start": "2026-06-01", "end_exclusive": null },
    "knowledge_type": "inferred"
  },
  "evidence_refs": [
    { "ref_type": "evidence", "id": "018f..." }
  ],
  "reason_ref": "rule:salary-monthly/0.1.0",
  "detection": {
    "scheme": "domain.cashflow.pattern_score/0.1",
    "score": "0.94"
  },
  "status": "open",
  "created_at": "2026-08-25T10:10:00+02:00",
  "decision": null
}
```

`detection` is optioneel en producent-specifiek; EngineCore vergelijkt scores uit verschillende schemes niet. Proposalstatus is `open`, `confirmed`, `corrected`, `rejected` of `superseded`. Een decision verwijst naar actor, tijd, mutation en eventuele gevormde assertion, maar verandert de oorspronkelijke proposalpayload niet.

## 7. Muterend request

Alle muterende commando's embedden:

```json
{
  "contract_version": "topo.cli/0.1",
  "operation_id": "018f...",
  "context_id": "018f...",
  "expected_generation": "018f...",
  "actor": {
    "actor_type": "human",
    "actor_id": "local-user"
  },
  "reason": "Confirm the reviewed monthly salary pattern",
  "authorization": null
}
```

`actor_type` is `human`, `agent`, `rule_module`, `source_adapter` of `system`. `authorization` is verplicht waar een previewgrens geldt en bevat `preview_ref`, `authorized_by` en `authorized_at`. De authorizer moet een mens of een expliciet door lokaal beleid toegestane actor zijn; een agent mag menselijke autorisatie niet afleiden.

## 8. Response-envelope

```json
{
  "contract_version": "topo.cli/0.1",
  "command": "proposal confirm",
  "operation_id": "018f...",
  "context_id": "018f...",
  "generation_before": "018f...",
  "generation_after": "018f...",
  "outcome": "succeeded",
  "result": {},
  "diagnostics": [],
  "next_actions": [],
  "trace": {
    "normalized_request": {},
    "refs": []
  }
}
```

`generation_after` is gelijk aan `generation_before` voor effectvrije, afgewezen, conflicterende of no-change uitkomsten. `outcome` is `succeeded`, `no_change`, `rejected`, `conflict` of `requires_authorization`.

## 9. Diagnostic

```json
{
  "code": "STALE_GENERATION",
  "message_key": "diagnostic.stale_generation",
  "severity": "error",
  "path": "/expected_generation",
  "params": {
    "expected": "018f...old",
    "actual": "018f...current"
  },
  "retryable": true,
  "effect": "none",
  "related_refs": [
    { "ref_type": "generation", "id": "018f...current" }
  ]
}
```

Severity is `info`, `warning` of `error`; effect is `none` voor ieder mutatiefalen. `path` is een JSON Pointer.

## 10. Next action

```json
{
  "action_id": "018f...",
  "action_type": "answer_question",
  "action_contract_version": "topo.workflow-action/0.1",
  "priority": "required",
  "reason_code": "NET_WORTH_MISSING_DEBT_BALANCE",
  "affected_component": "analysis.net_worth/total",
  "related_refs": [],
  "command": "proposal submit",
  "request_template": {},
  "input_schema_ref": "topo://schema/proposal-submit/0.1",
  "requires_user_input": true,
  "requires_authorization": false
}
```

`priority` is `blocking`, `required`, `helpful` of `optional`. `command` is een commando-ID, nooit een shellstring.

## 11. Analyseverzoek

```json
{
  "contract_version": "topo.cli/0.1",
  "analysis_id": "analysis.net_worth",
  "analysis_contract_version": "0.1",
  "context_id": "018f...",
  "analysis_scope": {
    "scope_type": "household",
    "entity_id": "018f..."
  },
  "as_of_date": "2026-08-25",
  "period": null,
  "reporting_currency": {
    "currency": "EUR",
    "allowed_rate_assertion_refs": []
  },
  "scenario": null
}
```

`period` is verplicht voor transactiegebonden analyses en gebruikt `start_date` inclusief, `end_date` exclusief. `reporting_currency` mag ontbreken; zonder koers blijven bedragen per valuta.

## 12. Analysecomponent

```json
{
  "component_id": "analysis.net_worth/total",
  "status": "provisional",
  "value": { "amount": "85000.00", "currency": "EUR" },
  "used_assertion_refs": [],
  "used_evidence_refs": [],
  "assumptions": [],
  "calculation_steps": [
    {
      "step_id": "subtract-debts",
      "operation": "subtract",
      "inputs": [],
      "unrounded_result": { "amount": "85000.00", "currency": "EUR" }
    }
  ],
  "rounding": {
    "mode": "currency_default",
    "presented_decimals": 2
  },
  "requirements": [],
  "warnings": [],
  "next_question": null,
  "explain_ref": { "ref_type": "analysis_component", "id": "018f..." }
}
```

Status is `complete`, `provisional` of `unavailable`. Een unavailable component heeft geen verzonnen `value`. De totale analysis result bevat analyse-ID en versie, scope, peildatum/periode, gebruikte generatie en een deterministische result-ID over contractversie, genormaliseerd request en generatie.

## 13. Scenario-aanname

Precies een van de volgende gesloten vormen is toegestaan:

```json
{
  "assumption_type": "recurring_cashflow_change",
  "target_ref": { "ref_type": "entity", "id": "018f..." },
  "change": "replace",
  "money": { "amount": "2500.00", "currency": "EUR" },
  "effective_date": "2027-01-01",
  "reason": "Explicit household assumption"
}
```

```json
{
  "assumption_type": "one_off_cashflow",
  "target_ref": { "ref_type": "entity", "id": "018f..." },
  "direction": "outflow",
  "money": { "amount": "5000.00", "currency": "EUR" },
  "effective_date": "2027-03-01",
  "reason": "Explicit household assumption"
}
```

```json
{
  "assumption_type": "value_override",
  "target_ref": { "ref_type": "entity", "id": "018f..." },
  "money": { "amount": "180000.00", "currency": "EUR" },
  "effective_date": "2027-12-31",
  "reason": "Explicit household assumption"
}
```

Procentuele mutaties zonder doelbedrag, vrije formules, code en impliciete spaar- of financieringsregels worden schema- of capabilitymatig geweigerd.

## 14. Generatiemanifest

```json
{
  "schema_version": "topo.manifest/0.1",
  "context_id": "018f...",
  "generation_id": "018f...",
  "based_on": "018f...",
  "package_version": "0.1",
  "context_schema_version": "topo.context/0.1",
  "mutation_id": "018f...",
  "recorded_at": "2026-08-25T10:20:00+02:00",
  "modules": [
    {
      "module_id": "domain.accounts",
      "module_version": "0.1.0",
      "checksum": "sha256:..."
    }
  ],
  "active_rule_packages": [],
  "files": {
    "entities.json": "sha256:...",
    "assertions.json": "sha256:...",
    "evidence.json": "sha256:...",
    "proposals.json": "sha256:..."
  }
}
```

Een ontbrekende `based_on` is alleen geldig voor de eerste generatie of wanneer een waardevrije compactieregistratie de verwijderde parent verklaart.

## 15. Regel-YAML

```yaml
rule_id: salary-monthly
rule_version: 0.1.0
rule_type: recognition
input_view: domain.cashflow.transactions-by-counterparty/0.1
when:
  all:
    - predicate: transaction_count_at_least
      args: { count: 3 }
    - predicate: interval_matches
      args: { frequency: monthly }
then:
  outcome: proposal
  assertion_template: domain.cashflow/recurring_cashflow
```

De parser accepteert uitsluitend het capabilityschema van het regeltype. YAML anchors mogen alleen worden toegestaan als het geëxpandeerde document aantoonbaar binnen omvangslimieten blijft; custom tags, objectconstructie en executable expressions zijn altijd verboden.
