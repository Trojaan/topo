# Welk CLI-contract laat mens, engine en agent betrouwbaar samenwerken?

Type: prototype
Status: resolved
Blocked by: 01, 04, 05, 06, 07

## Question

Welke commando's, JSON-contracten, fouttoestanden en workflowresponsen zijn nodig voor import, discovery, voorstellen, bevestiging, validatie, analyse en uitleg, zodat de engine zelfstandig bruikbaar blijft en iedere command-line-agent haar veilig kan orkestreren?

## Answer

Gebruik één versiegebonden CLI met twee lagen: smalle, zelfstandig bruikbare domeincommando's en een effectvrij `workflow next` dat mens of agent helpt orkestreren zonder zelf een vervolgstap uit te voeren. De CLI blijft de primaire technische interface; een agent is een optionele aanroeper en geen onderdeel van het veiligheidsmodel.

### Commando-oppervlak

De minimale commandogroepen zijn:

- `contract describe` en `contract schema <command>` voor machineleesbare capabilities, ondersteunde contractversies en JSON Schema's;
- `source import` voor expliciet geautoriseerde letterlijke bronwaarnemingen;
- `discover run` voor effectvrije herkenning van kandidaatsvoorstellen en aandachtspunten;
- `proposal submit`, `proposal confirm`, `proposal correct` en `proposal reject` voor de afzonderlijke voorstel- en beslisstappen;
- `validate` voor effectvrije schema-, constraint- en pakketvalidatie;
- `analyze run` voor de versiegebonden analyses;
- `explain --ref` voor uitleg van iedere stabiel adresseerbare uitkomst;
- `workflow next` voor geprioriteerde maar niet-uitvoerbare vervolgstappen.

Discovery bewaart niets. Alleen geselecteerde kandidaten gaan via `proposal submit` de toestand in. Bronimport, voorstelindiening, expliciete voorstelbeslissingen en gecontroleerde beheeracties mogen muteren; discovery, validation, analyse, uitleg en workflowadvies blijven effectvrij. Ieder muterend commando ondersteunt een effectvrije preview. Preview is alleen verplicht als onderdeel van de afzonderlijke autorisatiestap voor financiële bevestiging of correctie, identity merge en regelpakketactivatie; letterlijke bronimport en voorstelindiening hoeven geen interactieve tussenstap te krijgen.

### Canonieke invoer en mutatieveiligheid

JSON is de canonieke invoervorm. Inhoudelijke commando's accepteren een requestbestand of JSON via stdin. Mensvriendelijke flags zijn alleen syntactisch gemak en worden eerst naar hetzelfde JSON-request genormaliseerd. Vrije tekst is nooit rechtstreekse engine-invoer: een agent vertaalt haar eerst naar een gestructureerd voorstel. Het resultaat legt onder `trace.normalized_request` het volledige genormaliseerde verzoek vast, inclusief ingevulde standaardwaarden.

Ieder muterend request bevat verplicht:

- een door de aanroeper gekozen `operation_id` voor idempotente replay;
- `expected_generation` voor optimistic concurrency tegen het complete contextpakket;
- een getypeerde en stabiele `actor`;
- een controleerbare `reason`.

De mensvriendelijke CLI mag `operation_id` en de actuele generatie invullen, maar toont en bewaart ze altijd. Machine-aanroepers leveren ze expliciet. Een mutatie wordt volledig toegepast of heeft geen effect. Bevestiging en andere autorisatiegrenzen verwijzen naar een onveranderlijk voorstel of previewresultaat en controleren de actuele generatie opnieuw; een agent leidt nooit zelf gebruikersautorisatie af.

### Gedeelde JSON-envelope

Ieder commando gebruikt dezelfde buitenvorm met minimaal:

- `contract_version` en `command`;
- de eventuele `operation_id`;
- `context_id`, `generation_before` en `generation_after`;
- een uitvoeringsuitkomst `succeeded`, `no_change`, `rejected`, `conflict` of `requires_authorization`;
- een commandospecifiek `result`;
- getypeerde `diagnostics`;
- getypeerde `next_actions`;
- `trace.normalized_request` en waar relevant verdere herleidbaarheid.

Procesuitkomst, mutatiestatus en financiële betekenis blijven gescheiden. `complete`, `provisional` en `unavailable` zijn statussen van analyseonderdelen in `result` en nooit CLI-procesfouten.

Met `--json` bevat stdout exact één schema-gevalideerd JSON-document; logging gaat naar stderr. Een niet-nul exitcode betekent uitsluitend dat het commando technisch niet kon worden uitgevoerd, bijvoorbeeld door ongeldige invoer, een incompatibele contractversie, corrupte opslag of een mislukte atomaire write. Verwachte domeinuitkomsten zoals validatiediagnoses, conflicten, afwijzingen en voorlopige of niet-beschikbare analyses houden exitcode nul zodat een agent ze als betekenisvol resultaat kan verwerken.

Iedere fout of diagnose bevat een stabiele Engelstalige `code`, vertaalbare `message_key`, `severity`, JSON Pointer `path`, parameters, `retryable`, `effect` en gerelateerde referenties. Menselijke tekst is presentatielaag. Een mutatiefout rapporteert altijd `effect: none`; gedeeltelijke canonieke writes bestaan niet.

### Workflow en uitleg

`workflow next` retourneert getypeerde actiebeschrijvingen, nooit shellstrings. Iedere actie benoemt type en contractversie, doelgebonden prioriteit (`blocking`, `required`, `helpful` of `optional`), reden, getroffen analyseonderdeel, relevante referenties, passend CLI-commando, een schema of gedeeltelijk ingevuld request, en of gebruikersinvoer of autorisatie nodig is. Een mens of agent stelt het echte commando daarna bewust samen.

Iedere uitlegbare uitkomst — voorstel, diagnose, analyseonderdeel, mutatie, workflowactie of regeltrace — krijgt een stabiele referentie. `explain --ref` retourneert betekenis, gebruikte bronnen en beweringen, contract-, module- en regelversies, beslis- of rekenstappen, aannames, ontbrekende informatie en de reden voor eventuele vraagprioritering. De mensweergave vat uitsluitend deze JSON-structuur samen.

Prototype primary source: branch `prototype/cli-agent-contract`, commit `88d8f78`, path `.scratch/financial-context-engine-v0-1/assets/cli-agent-contract-prototype/`. De gebruiker heeft de volledige route inclusief idempotente replay, effectvrije discovery, stale-generationconflict, expliciete bevestiging, geldige `provisional` analyse, generieke uitleg en incompatibele contractversie doorlopen en zonder aanpassingen gevalideerd.
