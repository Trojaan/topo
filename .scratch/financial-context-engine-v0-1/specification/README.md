# Topo v0.1 — implementatiespecificatie

Status: implementation-ready  
Taal van mensgerichte documentatie: Nederlands  
Taal van technische identifiers: Engels  

> **Topo — map your financial world.**

Topo v0.1 is een zelfstandige, local-first financiële contextengine die persoonlijke financiële feiten, relaties, tijd en herkomst vastlegt en daaruit deterministische, herleidbare inzichten maakt. Topo werkt zonder agent en zonder Tally. Een agent of Tally-adapter kan via dezelfde begrensde CLI-contracten samenwerken, maar wordt nooit bron van canonieke financiële waarheid.

Dit document is normatief voor waarneembaar gedrag. Interne code-indeling, programmeertaal, bibliotheken, indexen en andere omkeerbare implementatiekeuzes zijn vrij zolang alle contracten en invarianten behouden blijven.

## 1. Productgrens

Topo levert feiten, berekeningen, onzekerheden, aandachtspunten en scenariovergelijkingen. Topo:

- geeft geen financieel advies en beveelt geen product aan;
- is geen SaaS, dashboard, hostingplatform of multi-tenant systeem;
- vereist geen netwerk, agent, MCP, Tally of database;
- voert in v0.1 geen diepe fiscale, pensioen-, verzekerings- of hypotheekberekeningen uit;
- haalt geen bankdata, referentiedata of wisselkoersen live op;
- bouwt geen dubbelboekhoudjournaal.

Een agentoperator mag buiten de engine niet-bindende begeleiding formuleren op basis van expliciete doelen en zichtbare engine-uitkomsten. Die begeleiding blijft herkenbaar gescheiden van feiten en berekeningen, beveelt in v0.1 geen specifiek product aan en verwijst bij belangrijke of mogelijk gereguleerde keuzes naar een bevoegde deskundige.

## 2. Ontwerpprincipes

1. **Canonical input, derived output.** Schema-gevalideerde contextbestanden en actieve regels zijn canoniek; indexen, analyses en presentaties zijn reproduceerbaar.
2. **Alleen EngineCore muteert context.** Agents en adapters leveren waarnemingen of voorstellen via de CLI en schrijven nooit rechtstreeks canonieke financiële betekenis.
3. **Herleidbaarheid is structureel.** Iedere bewering, afleiding, analyse en mutatie verwijst naar bewijs, versies, aannames en beslis- of rekenstappen.
4. **Tijd is verplicht.** Financiële betekenis heeft geldigheidstijd en registratietijd; analyses hebben een expliciete peildatum en waar nodig een halfopen periode.
5. **Onzekerheid wordt niet gladgestreken.** Ontbrekende, conflicterende, onvoldoende actuele en niet-toegerekende context blijft zichtbaar; Topo verzint geen waarde of verdeling.
6. **Effectvrije voorbereiding, expliciete autorisatie.** Discovery, validatie, analyse, uitleg, workflowadvies en previews muteren niet. Financiële bevestiging of correctie, identity merge en regelactivatie vereisen expliciete autorisatie.
7. **Determinisme en begrenzing.** Regels en analyses hebben versiegebonden input-views, vaste capabilities en reproduceerbare ordening.
8. **Veilige evolutie.** Schema's, modules, regels en CLI-contracten zijn expliciet versieerbaar; incompatibele of onbekende nieuwere hoofdversies worden geweigerd.

## 3. Architectuur en verantwoordelijkheden

### 3.1 EngineCore

EngineCore bezit uitsluitend generieke mechanismen voor:

- stabiele identiteit;
- entiteiten en tijdsgebonden beweringen over eigenschappen en relaties;
- bewijs, herkomst en bronreferenties;
- voorstellen, bevestiging, correctie, afwijzing en opvolging;
- generieke constraints en conflictbewaking;
- atomaire, idempotente contextmutaties;
- generatievalidatie, herstel, retentie, migratie en privacyverwijdering.

EngineCore herkent geen financiële patronen, doet geen landspecifieke interpretatie en kent geen universele `confidence`- of `stale`-status.

### 3.2 Modules en adapters

Iedere vertrouwde codemodule declareert `module_id`, `module_version`, ondersteunde EngineCore-contractversies, dependencies en capabilities. Dependencies zijn acyclisch. Modules gebruiken alleen publieke versiegebonden contracten.

| Extensiepunt | Verantwoordelijkheid | Verboden |
|---|---|---|
| Domain module | Universele financiële classificaties, beweringsvormen, constraints en input-views | Jurisdictie, presentatie, opslag |
| Jurisdiction module | Namespaced landspecifieke kwalificaties en constraints als overlay | Basisschema wijzigen, diepe berekeningen |
| Analysis module | Vereisten, input-view, deterministische berekening en resultaatcontract | Voorstellen indienen of context muteren |
| Rule module | Toegestane views, predicates, uitkomsttypen en schema's registreren | Vrije queries of runtime-code uit YAML |
| Source adapter | Externe bron vertalen naar letterlijke waarnemingen en bewijs | Canonieke betekenis vaststellen of context schrijven |
| Storage adapter | Lezen, staging, locking, atomair publiceren en opruimen | Generatie-, validatie- of historiesemantiek bepalen |
| Presentation layer | Labels, uitlegtemplates en locale-opmaak | Betekenis, standaardvaluta of berekeningen bepalen |

v0.1 laadt alleen meegeleverde, vertrouwde codemodules uit een expliciete catalogus. Runtime-installatie, onbetrouwbare plug-ins en plug-insandboxing vallen buiten scope. Ontbreekt een gepinde semantische module, dan blijven generieke reads en export mogelijk, maar afhankelijke validatie, mutatie en analyse worden geblokkeerd.

## 4. Canoniek meta-model

De normatieve veldcontracten en JSON Schema-fragmenten staan in [JSON-contracten](appendices/01-json-contracts.md).

### 4.1 Records

- **Entity** heeft een UUIDv7 en technisch type. Veranderlijke financiële betekenis staat in assertions, niet in stil overschrijfbare profielvelden.
- **Assertion** beschrijft een eigenschap of relatie met dezelfde grondvorm en bevat altijd geldigheidstijd, registratietijd, kennistype, verificatiestatus en herkomst.
- **Evidence** adresseert een immutable bronrecord, expliciete gebruikersuitspraak of eerdere assertions plus toegepaste regel- of berekeningsversies.
- **Proposal** is een onveranderlijk voorstel met producent, voorgestelde assertion, bewijs en optionele producent-specifieke detectiescore.
- **Mutation** is een atomaire wijzigingsset met actor, reden, operation-ID, basisgeneratie en resultaatgeneratie.

Alle eersteklas identifiers voor context, generatie, entiteit, assertion, evidence, voorstel, mutatie en operatie zijn UUIDv7. Externe identifiers blijven afzonderlijke bronreferenties.

### 4.2 Verplichte dimensies van assertions

`knowledge_type` is precies een van `observed`, `user_provided`, `inferred`, `calculated`, `assumed`, `projected`.

`verification_status` is precies een van `proposed`, `confirmed`, `disputed`, `rejected`, `superseded`.

Deze dimensies zijn onafhankelijk van detectiescores en analysecomponentstatussen.

### 4.3 Invarianten

EngineCore weigert een mutatie wanneer:

- een identifier of referentie ongeldig of ontbrekend is;
- een assertion geen geldige tijd, kennisstatus, verificatiestatus of herkomst heeft;
- een exclusieve betekenis twee overlappende actieve waarheden zou krijgen;
- een moduleconstraint voor cardinaliteit, type, tijdsoverlap of vereist totaal faalt;
- een expliciet volledige verdeling niet tot 100% optelt;
- een identity merge niet expliciet bevestigd is en geen modulegedefinieerde unieke sleutel gebruikt;
- een afgeleid voorstel zonder geldige bevestiging een financieel feit zou worden;
- `expected_generation` niet gelijk is aan de actuele generatie;
- validatie of atomair publiceren niet volledig kan slagen.

Tegenstrijdig bewijs mag naast elkaar bestaan. Alleen relevante echte assertionsconflicten maken afhankelijke analysecomponenten `unavailable`; een losse afwijkende waarneming blijft een waarschuwing of aandachtspunt.

## 5. Financiële domeinsnede

v0.1 composeert een kleine set entiteiten in plaats van producteilanden:

- betrokkenen: `person`, `household`, `organization`;
- geldverkeer: `account`, `transaction`, `recurring_cashflow`;
- vermogen: `asset`, `debt` wanneer het belang een eigen identiteit en levensloop heeft;
- overeenkomsten: `contract`;
- verzekeringen: `coverage` gekoppeld aan contract en verzekerd onderwerp;
- pensioen: `pension_entitlement` als afzonderlijk recht;
- intentie en verandering: `financial_goal`, `financial_event`, `scenario`.

Minimale relaties onderscheiden juridische positie, praktisch gebruik en analyse-toerekening. Zij omvatten huishoudlidmaatschap, bereik, contractpartij, tegenpartij, rekeningbeheerder, begunstigde, rekeninghouder, rechthebbende, schuldenaar, praktisch gebruik, huishoudelijke toerekening, rekeningboeking, transfer-tegenzijde, patroonbewijs, contractkoppeling, veroorzaakte kasstroom, rekeningpositie, onderpand, verzekerd onderwerp en beïnvloede doelen of gebeurtenissen.

Een verdelingsaandeel bestaat alleen voor werkelijk deelbare rechten, verplichtingen of toerekeningen. Topo neemt nooit 50/50 aan. Ieder bedrag heeft een expliciete valuta. Een rapportagevaluta vereist expliciete koersassertions of aannames met peildatum en herkomst.

Een positief of negatief rekeningsaldo wordt niet daarnaast als asset of debt gedupliceerd. Een rekening mag een saldo op peildatum hebben zonder volledige transactiehistorie. Waargenomen, gebruikersgegeven en berekende saldi blijven onderscheiden; verschillen produceren diagnostiek, nooit een verzonnen correctietransactie.

### 5.1 Transacties en kasstromen

Een transactie is één stabiel geïdentificeerde geldbeweging op precies één rekening. De basisclassificatie is `income`, `expense`, `internal_transfer` of `unclassified`. Twee transacties kunnen als zijden van dezelfde interne transfer worden gekoppeld.

Een terugkerende kasstroom heeft frequentie, bedrag of bandbreedte, valuta en geldigheidsperiode. Zij kan direct gestructureerd bevestigd zijn of na patroonherkenning zijn bevestigd, maar vervangt onderliggende transacties nooit.

### 5.2 Nederlandse overlay

`jurisdiction.nl` levert alleen kwalificaties die betekenis of validatie activeren:

- `qualification/retirement_restriction`, `qualification/annuity_restriction`, `qualification/owner_occupied_home_debt`;
- `valuation/woz`;
- `pension_origin/aow`, `pension_origin/employer`, `pension_origin/individual`;
- `income/aow`, `income/allowance`;
- `expense/health_insurance_premium`, `expense/municipal_tax`, `expense/water_authority_tax`;
- dekkingen `basic_health`, `supplementary_health`, `dental`, `building`, `contents`, `glass`, `personal_liability`, `motor_third_party`, `motor_limited_casco`, `motor_full_casco`, `travel`, `cancellation`, `term_life`, `disability`, `accident`, `funeral`, `legal_assistance`, `other` onder `jurisdiction.nl/coverage/`.

Een jurisdictiekwalificatie is bevestigd, tijdsgebonden en herleidbaar. Een WOZ-waarde heeft een waardepeildatum. Hypotheekdelen zijn afzonderlijke debts. Pensioenrekeningen en pensioenaanspraken worden niet vereenzelvigd. Merk-, aanbieder- en productnamen blijven bronmetadata wanneer zij geen betekenisregel activeren.

## 6. Van bron naar bevestigd feit

1. **Import.** Een expliciet geautoriseerde bronadapter importeert uitsluitend letterlijke bronvelden als immutable `observed` evidence. Een broncorrectie wordt een opvolger en overschrijft niets.
2. **Discovery.** Een agent of deterministische rule module herkent effectvrij kandidaten en aandachtspunten. EngineCore herkent zelf geen patronen.
3. **Proposal submit.** Alleen geselecteerde kandidaten worden als immutable proposals opgeslagen. EngineCore valideert vorm, typen, referenties, herkomst en constraints, niet de waarschijnlijkheid.
4. **Preview en autorisatie.** Bevestiging of correctie toont een effectvrije preview tegen een specifieke generatie en vereist expliciete autorisatie.
5. **Confirm/correct/reject.** Bevestiging creëert atomair een afzonderlijke `confirmed` assertion. Een ondubbelzinnige correctie vormt nieuw `user_provided` evidence en een bevestigde assertion; het oorspronkelijke voorstel blijft met uitkomst `corrected` bestaan.
6. **Opvolging.** Nieuwe waarnemingen wijzigen afgeleide bevestigde feiten nooit automatisch. Een producent maakt een opvolgvoorstel; bevestiging sluit de oude geldigheid af en activeert de nieuwe.

Bewust gestructureerde gebruikersinvoer mag direct als bevestigd feit worden ingediend. Vrije tekst die door een LLM is geïnterpreteerd moet altijd eerst een proposal worden.

## 7. Declaratieve regels

Regelpakketten gebruiken veilige YAML zonder custom tags. YAML wordt naar een getypeerd intern model geparseerd; CLI-contracten blijven JSON. Er zijn precies vier capabilitytypen:

| Type | Mag lezen | Enige toegestane uitkomst |
|---|---|---|
| `recognition` | Benoemde herkenningsview | Proposal of attention item |
| `validation` | Benoemde validatieview | Error of warning |
| `completeness` | Analysevereisten | Doelgebonden volledigheidsoordeel |
| `question_priority` | Open vragen en analysevereisten | Rangschikking |

Regels krijgen geen vrije graphquery, opslagtoegang, code, willekeurige formules of mutatiecapability. Vertrouwde modules mogen pure, deterministische, versiegebonden predicates registreren. Alle toepasselijke regels draaien; er is geen algemene `first_match` en bestandsvolgorde heeft geen betekenis.

Vragen worden geordend op `blocking`, `required`, `helpful`, `optional`, daarna modulescore 0–100, ouderdom en rule-ID. Alleen een analysevereiste kan `blocking` toekennen.

Een volledig pakket wordt syntactisch, semantisch en op compatibiliteit gevalideerd, effectvrij gepreviewd en expliciet geactiveerd. Activatie wisselt atomair een manifest met versies en checksums. Iedere evaluatie levert een trace. Een falende regel wordt nooit stil overgeslagen en veroorzaakt nooit een gedeeltelijke mutatie.

## 8. Canonieke opslag en levenscyclus

Een zelfstandige financiële contextgraph leeft in één contextpakket:

```text
<context-package>/
├── CURRENT
├── generations/<generation_uuidv7>/
│   ├── manifest.json
│   ├── entities.json
│   ├── assertions.json
│   ├── evidence.json
│   └── proposals.json
├── evidence/records/<evidence_uuidv7>.json
├── history/journal.json
└── staging/
```

`CURRENT` bevat uitsluitend een generatie-UUIDv7. Iedere generatie is compleet, stabiel geformatteerd, op record-ID gesorteerd en via checksums beschermd. Canonieke collecties zijn JSON met `schema_version` en `records`; JSONL is niet canoniek. Het journal bevat structurele mutatiemetadata zonder gekopieerde financiële waarden en is geen event source.

### 8.1 Atomaire mutatie

Een writer gebruikt een exclusieve package-lock, `operation_id` en optimistic concurrency:

1. open pakket en voer conservatief startup recovery uit;
2. valideer huidige generatie, checksums, referenties, modules en verwachte generatie;
3. bouw een volledige nieuwe generatie in staging;
4. schrijf benodigd evidence vóór publicatie;
5. valideer en synchroniseer de nieuwe generatie volledig;
6. verplaats de generatie en vervang `CURRENT` atomair;
7. werk het waardevrije journal bij.

Een replay van dezelfde `operation_id` retourneert hetzelfde resultaat zonder tweede generatie. Een crash vóór publicatie laat `CURRENT` intact. Recovery publiceert nooit zelf een orphan; bij twijfel blijven reads mogelijk en worden writes geblokkeerd.

### 8.2 Validatie, herstel en evolutie

Topo valideert alle bewaarde generaties, manifests, checksums, schema's, evidenceverwijzingen, lineage en journalconsistentie. Directe bestandswijziging blokkeert mutaties en migraties. Herstel kopieert een vertrouwde oude toestand naar een nieuwe generatie; de pointer wordt niet teruggezet.

Retentie is expliciet en begrensd; de actuele generatie wordt nooit door gewone compactie verwijderd. Schema- en modulemigraties produceren een nieuwe volledig gevalideerde generatie. Een onbekende nieuwere major-versie wordt geweigerd.

Privacyverwijdering scrubt het doel pakketbreed uit actuele en bewaarde generaties, staging, orphans, evidence en mutatievelden en herschrijft manifests en checksums. Alleen waardevrije actiemetadata mag blijven. De garantie geldt niet voor SSD-restdata, OS-snapshots, synckopieën of externe back-ups. v0.1 gebruikt owner-only bestandsrechten en verwacht OS-schijf- of mapversleuteling; eigen applicatieversleuteling valt buiten scope.

## 9. CLI-contract

De CLI heeft smalle commando's en een effectvrij orkestratiecommando:

- `contract describe`, `contract schema <command>`;
- `source import`;
- `discover run`;
- `proposal submit`, `proposal confirm`, `proposal correct`, `proposal reject`;
- `validate`;
- `analyze run`;
- `explain --ref`;
- `workflow next`.

JSON uit bestand of stdin is canonieke invoer. Mensvriendelijke flags normaliseren naar hetzelfde request. `trace.normalized_request` bevat het volledige verzoek inclusief defaults.

Ieder muterend request bevat `operation_id`, `expected_generation`, een getypeerde `actor` en `reason`. Mutaties zijn all-or-nothing. Autorisatie verwijst naar een immutable proposal of preview en controleert de actuele generatie opnieuw.

Iedere response gebruikt één envelope met `contract_version`, `command`, optionele `operation_id`, `context_id`, `generation_before`, `generation_after`, `outcome`, commandospecifiek `result`, `diagnostics`, `next_actions` en `trace`. `outcome` is `succeeded`, `no_change`, `rejected`, `conflict` of `requires_authorization`.

Met `--json` bevat stdout exact één schema-gevalideerd JSON-document; logs gaan naar stderr. Niet-nul exitcodes zijn alleen voor technische niet-uitvoerbaarheid. Verwachte domeinuitkomsten, conflict, afwijzing en `provisional` of `unavailable` analyse blijven exitcode 0.

Diagnostiek gebruikt stabiele Engelstalige codes, `message_key`, severity, JSON Pointer, parameters, `retryable`, `effect` en gerelateerde refs. Een mutatiefout heeft altijd `effect: none`.

`workflow next` retourneert getypeerde acties, nooit shellstrings. `explain --ref` werkt voor proposals, diagnoses, analysecomponenten, mutaties, workflowacties en regeltraces.

## 10. Analysecontracten

Ieder verzoek specificeert analyse-ID en contractversie, `analysis_scope`, `as_of_date`, voor transactieanalyse een halfopen periode en optioneel rapportagevaluta plus toegestane koersassertions of aannames.

Iedere resultaatcomponent heeft status:

- `complete`: alle vereisten zijn geldig en bruikbaar;
- `provisional`: berekenbaar met expliciet onzekere, ontbrekende, onvoldoende actuele, aangenomen, niet-toegerekende of onvolledig gedekte invoer;
- `unavailable`: niet verantwoord berekenbaar door een conflict of ontbrekende harde vereiste.

Resultaten bevatten gebruikte generatie, deterministische resultaat-ID, refs, aannames, rekenstappen, ongeronde tussenuitkomsten, afronding, lokale blockers/warnings en eerstvolgende vraag. Een probleem treft alleen afhankelijke componenten. Oorspronkelijke valuta blijven beschikbaar; alleen een geconverteerd totaal kan door ontbrekende koers `unavailable` zijn.

### 10.1 Context inventory

Altijd uitvoerbaar en zelf `complete`, ook bij een lege graph. Geeft per analysecomponent een vereistenmatrix met aanwezigheid, conflict, doelgebonden actualiteit, tijdsdekking, kennis- en verificatiestatus, toerekening, impact en eerstvolgende vraag. Er is geen algemeen volledigheidspercentage.

### 10.2 Pattern recognition

Ondersteunt `weekly`, `four_weekly`, `monthly`, `quarterly`, `annual`. Een kandidaat vereist minimaal drie vergelijkbare transacties, of twee voor jaarlijks. Vergelijkbaarheid gebruikt richting, tegenpartij/omschrijving, valuta, intervaltolerantie en bedrag/bandbreedte. Te weinig historie maakt geen voorstel. Alleen bevestigde, geldige recurring cashflows tellen in genormaliseerde cashflow.

Een Tally-adapter bewaart de ruwe transactie als observation en Tally-categorie, subcategorie, tags, regelversie en uitleg als classificatieproposal. Niet-eenduidig wordt `unclassified`; bevestiging kan per mapping in batch.

### 10.3 Realized monthly cashflow

Sommeert werkelijke boekingen binnen één kalendermaand en expliciet bereik. Publiceert income, expense, net movement, internal transfers, unclassified movement en uitsplitsingen. Bevestigde interne transfers tellen niet als inkomen/uitgave. Unclassified telt wel in net movement. Volledigheid vereist volledige transactiedekking van alle opgenomen rekeningen en bekende huishoudtoerekening. Saldoreconciliatie is diagnostiek.

### 10.4 Normalized monthly cashflow

Gebruikt alleen bevestigde geldige recurring cashflows. Omrekening:

- weekly × 52 ÷ 12;
- four-weekly × 13 ÷ 12;
- monthly × 1;
- quarterly ÷ 3;
- annual ÷ 12.

Bandbreedtes blijven min/max; alleen een expliciet bevestigd typical amount geeft een verwacht totaal. Berekening is decimaal en afronding gebeurt alleen voor gepresenteerde eindbedragen.

### 10.5 Net worth

`allocated account balances + allocated usable asset values - allocated debt balances` op een expliciete peildatum. Ontbrekende of doelgebonden onvoldoende actuele waarderingen worden niet geschat. Pensioenaanspraken staan apart. Contracten, dekkingen en toekomstige kasstromen tellen niet zelfstandig mee. Dubbeltelling van rekening en saldo, portefeuille en volledige posities, of kredietrekening en aparte debt is verboden.

### 10.6 Scenario comparison

Vergelijkt een expliciete baseline met benoemde scenario's op één toekomstige peildatum. Bekende wijzigingen zitten in de baseline; scenario's bevatten alleen expliciete aannames van type:

- `recurring_cashflow_change`;
- `one_off_cashflow`;
- `value_override`.

Iedere aanname heeft doelobject, bedrag/valuta, datum en reden. Vrije code, algemene formules en ongerichte procentuele mutaties zijn verboden. Uitvoer toont absolute uitkomst en delta voor normalized cashflow, one-offs en waar mogelijk net worth. Een overschot wordt niet automatisch gespaard en een tekort niet automatisch gefinancierd. Scenario's zijn `projected` output en nooit canonieke feiten.

## 11. Implementatievrijheid

De implementatie mag zelfstandig kiezen:

- programmeertaal, package-indeling en dependency injection;
- in-memory indexen en querystrategie;
- precieze lockingprimitieve zolang exclusiviteit en crashgedrag voldoen;
- formattering van mensgerichte tekst en locale-assets;
- testframework en buildtooling;
- interne representatie van gevalideerde JSON en YAML.

Zij mag niet zelf financieel gedrag, productsemantiek, gebruikersautorisatie, conflictbeleid, tijdsbetekenis, analyseformules of veiligheidsgrenzen toevoegen.

## 12. Overdracht en bijlagen

- [Normatieve JSON-contracten](appendices/01-json-contracts.md)
- [Concrete voorbeelden en drie end-to-end-verhalen](appendices/02-examples-and-stories.md)
- [Traceerbaarheid en gereedheidscontrole](appendices/03-readiness-matrix.md)

De gesloten Wayfinder-tickets blijven de detailbron voor de beslisredenering; dit pakket is de samengestelde implementatiehandoff.
