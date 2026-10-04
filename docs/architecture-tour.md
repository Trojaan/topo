# Topo — technisch architectuuroverzicht

> Een begeleide rondleiding door Topo 0.3.0, gebaseerd op de actuele code en
> maintainerdocumentatie. Dit document legt niet alleen uit *wat* de onderdelen
> zijn, maar vooral *waarom* de grenzen zo zijn gekozen en hoe één gebruikersactie
> door het systeem loopt.

## 1. Topo in één minuut

Topo is een lokale financiële context-engine met een command-line-interface. Het
is één Python-proces en één Python-package. Er zijn geen server, database, queue,
container, poort of verplichte netwerkverbinding.

De kernbelofte is:

> Topo bewaart financiële context als herleidbare, tijdsgebonden feiten en verandert
> die context uitsluitend via gevalideerde, atomaire en controleerbare mutaties.

Vier ideeën dragen vrijwel de hele architectuur:

1. **De CLI vertaalt; `EngineCore` beslist.** De CLI leest verzoeken en schrijft
   antwoorden, maar bevat geen financiële betekenis.
2. **Een generatie is immutable.** Een wijziging maakt een volledige nieuwe
   generatie en zet daarna atomair de `CURRENT`-pointer om.
3. **Interpretatie begint als voorstel.** Een agent, regel of herkenner mag betekenis
   voorstellen; alleen expliciete menselijke autorisatie maakt er een bevestigd
   feit van.
4. **Analyses zijn effectvrij.** Ze lezen één gevalideerde generatie en leveren een
   herleidbaar resultaat zonder de financiële context te veranderen.

De beste eerste mentale afbeelding is daarom:

```text
 mens of agent
      │
      ▼
┌───────────────┐    stabiele JSON-contracten
│      CLI      │◄─────────────────────────────► caller
└───────┬───────┘
        │ getypeerd request
        ▼
┌─────────────────────────────────────────────────────────┐
│                     EngineCore                          │
│  autorisatie · betekenis · mutatie · replay · analyse  │
└──────┬────────────────────┬──────────────────────┬───────┘
       │                    │                      │
       ▼                    ▼                      ▼
 modulecatalogus     effectvrije analyses    opslag-interface
 + constraints       + workflowkeuze                │
                                                   ▼
                                         context.topo/ op schijf
```

## 2. Wat Topo wel en niet is

### Wel

- Een local-first engine voor personen en huishoudens.
- Een financiële contextgraph, opgeslagen als gewone, leesbare JSON-bestanden.
- Een deterministische CLI die ook goed door agents te gebruiken is.
- Een auditbaar systeem met historie, bewijs, geldigheidstijd en registratietijd.
- Een rekenengine voor inventarisatie, cashflow, nettovermogen en scenario's.

### Niet

- Geen financieel adviseur: Topo toont feiten, gaten, onzekerheden en scenario's,
  maar schrijft geen product of handelwijze voor.
- Geen agent: een agent kan Topo bedienen, maar is nooit de bron van waarheid.
- Geen database of graphdatabase: “graph” beschrijft het domeinmodel.
- Geen webapp en geen SaaS-platform.
- Geen systeem dat onbekende waarden stilzwijgend als nul behandelt.

Deze begrenzing verklaart veel ontwerpkeuzes. De lokale bestanden moeten zelfstandig
begrijpelijk en verifieerbaar zijn; een gesprek of externe dienst mag niet nodig zijn
om de financiële waarheid te reconstrueren.

## 3. De architectuurlagen

### 3.1 Buitenste adapters

`src/topo/cli.py` is het publieke proces-entrypoint. Het:

- parseert commando's;
- leest JSON of genormaliseerde CSV;
- valideert requests tegen gepubliceerde contracten;
- maakt een opslagadapter en `EngineCore` aan;
- vertaalt fouten en resultaten naar vaste JSON-enveloppen of Nederlandse tekst.

`src/topo/workspace.py` richt een agentvriendelijke werkmap in. Het beheert gemarkeerde
blokken in `AGENTS.md`, `CLAUDE.md` en `.gitignore`, maar schrijft niet zelf in een
canoniek contextpakket. Voor contextinitialisatie roept het `EngineCore` aan.

De seam is belangrijk: andere interfaces—bijvoorbeeld MCP of een desktopapp—kunnen
later dezelfde engine bedienen zonder financiële logica uit de CLI te kopiëren.

### 3.2 Contracten en getypeerde gegevens

`src/topo/contracts.py` publiceert de machinecontracten en JSON Schema's. Een caller
kan deze opvragen met `topo contract describe` en `topo contract schema`.

`src/topo/models.py` bevat de bevroren Pydantic-modellen voor requests, resultaten en
canonieke records. Extra velden zijn verboden. Geldbedragen zijn decimale strings met
een expliciete ISO-valuta; identifiers zijn UUIDv7; datums en tijdstippen hebben een
vaste vorm.

`src/topo/canonical_validation.py` valideert niet alleen losse bestanden maar een
complete snapshot. Het controleert onder andere schema's, checksums, referenties,
lineage en journal-samenhang.

Samen vormen deze modules de vormvaste taal tussen caller, engine en opslag.

### 3.3 `EngineCore`: het semantische transactiepunt

`src/topo/engine.py` is het hart van Topo. `EngineCore` bezit:

- initialisatie en lifecycle;
- validatie vóór publicatie;
- idempotency en replay;
- optimistic concurrency via `expected_generation`;
- voorstellen, batches, correcties en bevestigingen;
- menselijke autorisatie en preview-binding;
- bronimport en bronidentiteit;
- activatie van regelpakketten;
- orchestration van effectvrije analyses en uitleg.

Dit is een diepe module: callers hoeven de publicatievolgorde, checksumopbouw,
historie, herstelregels en bewijsconstructie niet zelf te kennen. Die complexiteit
blijft lokaal in de implementatie van `EngineCore`.

### 3.4 Semantische modules

De financiële betekenis is verder verdeeld over gespecialiseerde modules:

| Module | Verantwoordelijkheid |
| --- | --- |
| `context_inventory.py` | Doelgebonden volledigheid en precies één volgende workflowactie |
| `recognition.py` | Herkenning van terugkerende kasstromen uit waarnemingen |
| `realized_cashflow.py` | Werkelijke geldbewegingen binnen een kalendermaand |
| `normalized_cashflow.py` | Terugkerende kasstromen omgerekend naar maandbasis |
| `net_worth.py` | Bezittingen, rekeningen, schulden, pensioen en valuta per scope |
| `scenario.py` | Effectvrije vergelijking van baseline en expliciete aannames |
| `explanations.py` | Projectie van bewijs en rekenstappen naar uitlegbare resultaten |
| `rules.py` | Gesloten, veilige interpretatie van declaratieve YAML-regels |

De analysefuncties accepteren een `ValidatedPackage` en een getypeerd request. Zij
retourneren data en publiceren geen generatie. Dat maakt hun interface tevens een
natuurlijke test-seam.

### 3.5 Modulecatalogus en constraints

`src/topo/modules.py` definieert `ModuleCatalog`. De catalogus:

- valideert module-identiteit, versie, checksum en enginecompatibiliteit;
- sorteert modules in dependencyvolgorde en weigert cycli;
- bepaalt welke module eigenaar is van een publieke identifier;
- controleert dat de benodigde moduleversies in de generatie zijn gepind;
- voert de constraints van de eigenaar uit.

`src/topo/builtin_modules.py` levert de huidige ingebouwde modules:

```text
topo.core
domain.parties
├── domain.accounts
│   ├── domain.cashflow
│   └── domain.pensions ──► domain.contracts
├── domain.assets
├── domain.debts
├── domain.contracts
│   └── domain.insurance
└── domain.goals

jurisdiction.nl ──► accounts, assets, cashflow, debts, insurance, pensions
```

Universele financiële betekenis leeft in `domain.*`. Alleen echt Nederlandse
betekenis leeft in `jurisdiction.nl`. Presentatietaal is weer een aparte zorg. Zo
blijven technische identifiers stabiel wanneer taal of land verandert.

### 3.6 Opslagadapter

`src/topo/storage.py` definieert een kleine `StorageAdapter`-interface:

```python
load() -> StoredPackageSnapshot | None
commit(publication, expected_generation=...) -> None
```

De filesystemadapter implementeert locking, staging, duurzame writes, atomaire
renames, recovery en retentie. Hij kent echter geen financiële betekenis. De engine
levert een complete `PackageCommit`; de adapter controleert de fysieke samenhang en
publiceert de bytes.

Dit is een echte seam: productie gebruikt `FileSystemStorageAdapter`, terwijl tests
een geheugenadapter gebruiken. De interface is klein, maar verbergt veel gedrag.

## 4. Het canonieke domeinmodel

De contextgraph rust op vier recordcollecties.

### Entiteiten

Een entiteit heeft stabiele identiteit en een type, bijvoorbeeld persoon, huishouden,
rekening, transactie, bezitting, schuld, contract, pensioenaanspraak of doel. Veranderlijke
financiële betekenis staat niet als stil mutable veld op de entiteit.

### Beweringen (`assertions`)

Een bewering koppelt een subject via een predicate aan een andere entiteit of een
getypeerde waarde. Iedere bewering bevat:

- geldigheidstijd: wanneer de uitspraak in de financiële werkelijkheid geldt;
- registratietijd: wanneer Topo de uitspraak vastlegde;
- kennistype: waargenomen, door gebruiker verstrekt, afgeleid, berekend, aangenomen
  of geprojecteerd;
- verificatiestatus;
- herkomstverwijzingen;
- optioneel een voorganger die zij vervangt.

Eigenschappen en relaties gebruiken dus dezelfde grondvorm. Een rekeningsaldo en
huishoudlidmaatschap verschillen inhoudelijk, maar delen historie- en bewijssemantiek.

### Bewijs (`evidence`)

Bewijs legt vast waarop een bewering of voorstel rust. Er zijn gebruikersuitspraken
en bronrecords. Letterlijke bronpayloads staan los in `evidence/records/`; canonieke
records verwijzen ernaar met checksum en stabiele bronidentiteit.

### Voorstellen (`proposals`)

Een voorstel bevat nog niet-bevestigde betekenis, het bewijs en zijn workflowstatus.
Bevestigen maakt een nieuwe assertion én een bewijsrecord van de menselijke beslissing.
Corrigeren en afwijzen bewaren de eerdere context; ze herschrijven die niet stilzwijgend.

## 5. Het pakket op schijf

Een werkelijke context ziet er conceptueel zo uit:

```text
context.topo/
├── CURRENT                         # UUIDv7 van de actieve generatie
├── LOCK                            # single-writer lock
├── generations/
│   ├── <generation-1>/
│   │   ├── manifest.json           # identiteit, pins en checksums
│   │   ├── entities.json
│   │   ├── assertions.json
│   │   ├── evidence.json
│   │   ├── proposals.json
│   │   └── rules/...               # alleen actieve regelartefacten
│   └── <generation-2>/...
├── evidence/
│   └── records/<evidence-id>.json  # letterlijke bronrecords
├── history/
│   ├── journal.json                # operaties en generatie-overgangen
│   └── evidence-inventory/
│       └── <generation>-<sha256>.json
├── derived/
│   └── explanations/...            # herbouwbare, niet-canonieke index/cache
└── staging/                         # alleen tijdens veilige publicatie/herstel
```

Een generatie bevat volledige, gesorteerde collecties. `manifest.json` bevat een
SHA-256-checksum per bestand en pint de gebruikte semantische modules en actieve
regelpakketten. `CURRENT` is de enige aanwijzer naar de actieve toestand.

De explanation-cache mag veranderen zonder een nieuwe generatie: hij bevat geen
financiële waarheid en is alleen bruikbaar zolang de referentie, payload en gebruikte
generatie verifieerbaar blijven.

## 6. Een leesactie stap voor stap

Neem `analyze run` als voorbeeld:

```text
1. Caller stuurt versiegebonden JSON naar de CLI.
2. contracts.py en models.py valideren de vorm.
3. CLI maakt FileSystemStorageAdapter + EngineCore.
4. EngineCore leest de actuele generatie.
5. canonical_validation valideert snapshot, manifest, checksums en verwijzingen.
6. EngineCore kiest de analysefunctie op analysis_id.
7. De analyse bouwt componenten, diagnostics en provenance-referenties.
8. explanations.py indexeert de al genomen rekenbeslissingen.
9. CLI valideert en schrijft het antwoord.
```

Dagelijkse reads laden alleen de actuele generatie. Dat geldt voor status, workflow,
analyses, discovery, uitleg en regelpreview. Als staging- of tijdelijke publicatie-
artefacten worden aangetroffen, valt de opslag eerst terug op volledige recovery.

`context verify` is bewust zwaarder: het leest en valideert alle behouden generaties
en al hun ruwe bewijs. Zo blijft een snelle actuele read mogelijk, terwijl een
expliciete integriteitscontrole de volledige geschiedenis bewijst.

## 7. Een mutatie stap voor stap

Een gewone mutatie volgt een strengere route:

```text
request
  │
  ├─► laad + valideer actuele én behouden generaties
  ├─► zoek operation_id in journal
  │      └─ gevonden: geef eerder resultaat terug (replay)
  ├─► controleer context_id en expected_generation
  ├─► valideer autorisatie, modulepins en domeinconstraints
  ├─► pas de verandering volledig in geheugen toe
  ├─► bouw volledige nieuwe collecties + manifest + journal
  ├─► valideer de voorgenomen generatie opnieuw als snapshot
  └─► StorageAdapter.commit(...)
         ├─ lock
         ├─ herstel/controleer bestaande historie
         ├─ schrijf staging + fsync
         ├─ publiceer generatie en bewijs
         ├─ controleer expected_generation opnieuw
         ├─ vervang CURRENT atomair
         └─ publiceer journal
```

Daaruit volgen drie garanties:

- **Idempotency:** dezelfde `operation_id` geeft het eerder vastgelegde resultaat
  terug en maakt niet nog een generatie.
- **Geen lost updates:** een verouderde `expected_generation` levert een conflict op.
- **Alles of niets:** validatie gebeurt vóór de pointerwissel; callers zien nooit een
  half gepubliceerde generatie.

Mutaties valideren ook de behouden geschiedenis. Beschadiging in een oude generatie
kan daarom een nieuwe mutatie blokkeren, ook als een current-only analyse nog werkt.

## 8. De menselijke autorisatielus

Voor betekenisvolle acties gebruikt Topo een tweestapsprotocol:

```text
agent/caller                  Topo                       mens
     │                         │                          │
     ├─ request zonder auth ──►│                          │
     │◄─ preview + preview_ref─┤                          │
     │                         │                          │
     ├──────── toont exacte effecten ───────────────────►│
     │◄──────── expliciete goedkeuring ──────────────────┤
     │                         │                          │
     ├─ zelfde request + checksumgebonden autorisatie ──►│
     │                         ├─ herbereken + vergelijk  │
     │                         └─ publiceer atomair       │
     │◄──────── resultaat + nieuwe generatie ────────────┤
```

De autorisatie is gebonden aan de preview en de verwachte generatie. Een gewijzigde
context of gewijzigd effect kan dus niet onder een oude toestemming worden uitgevoerd.

Een agent kan daarmee wel orkestreren, vragen stellen en voorstellen indienen, maar
niet zelfstandig interpretaties promoveren tot bevestigde financiële feiten.

## 9. Import, herkenning en analyse zijn verschillende dingen

Deze drie begrippen lijken op elkaar, maar hebben bewust andere bevoegdheden.

### Import

`source import` mag na autorisatie letterlijke waarnemingen opslaan: bronidentiteit,
rekening, datum, bedrag, omschrijving en originele classificatie. De bronclassificatie
is bewijs, niet automatisch Topo-betekenis. Correcties maken opvolgende records.

### Herkenning

`discover run` zoekt patronen in transacties en levert kandidaten. Het maakt geen
generatie. Een kandidaat wordt pas canonieke geschiedenis nadat hij als voorstel is
ingediend; bevestiging blijft een aparte menselijke beslissing.

### Analyse

`analyze run` rekent uitsluitend met gevalideerde context. Resultaten bevatten status
per component—`complete`, `provisional` of `unavailable`—en houden ontbrekende waarden,
conflicten en valutagaten lokaal. Een onvolledig onderdeel hoeft dus niet het hele
resultaat betekenisloos te maken.

De huidige analyses zijn:

- contextinventarisatie;
- gerealiseerde maandcashflow;
- genormaliseerde maandcashflow;
- nettovermogen;
- scenariovergelijking.

Scenario's worden alleen in geheugen toegepast en schrijven nooit terug. Een betere
cashflow wordt ook niet automatisch vermogen: zonder expliciete bestemming meldt Topo
dat de bestemming niet is gemodelleerd.

## 10. Proactieve workflow

`workflow next` combineert contextinventarisatie met actieve analyses en kiest
deterministisch hoogstens één vervolgstap. De prioriteit is grofweg:

1. noodzakelijke migratie of integriteit;
2. open batch die autorisatie nodig heeft;
3. relevant feitenconflict;
4. ontbrekende context voor het actieve analysedoel;
5. ontbrekende basiscontext;
6. optionele verdieping.

De workflow retourneert een getypeerde actie en een gedeeltelijk requesttemplate. Hij
voert die actie niet uit. `workflow respond` vertaalt een gebruikersantwoord naar een
open voorstelbatch; ook die batch moet vervolgens als geheel worden bevestigd of
afgewezen.

Deze grens maakt de workflow bruikbaar voor verschillende agents: Topo bepaalt de
inhoudelijke volgende stap, de agent verzorgt het gesprek.

## 11. Regels versus berekeningen

Declaratieve regels zijn veilige, gesloten YAML-data. `rules.py` accepteert alleen
geregistreerde inputviews, predicates, argumenten en uitkomsten. Vrije expressies,
Python-imports en directe opslag- of mutatietoegang bestaan niet in het regelmodel.

Regelpakketten worden gevalideerd en effectvrij gepreviewd. Activatie is daarna een
normale, geautoriseerde `EngineCore`-mutatie en pint het volledige pakket met checksum
in de nieuwe generatie.

Financiële berekeningen staan juist in gewone, getypeerde en geteste Python. Daarmee
blijven rekenregels reviewbaar en kunnen door een agent wijzigbare YAML-regels nooit
onbegrensd financiële uitkomsten programmeren.

## 12. Lifecycle en de uitzondering op immutability

- **Migrate:** bouwt een volledige opvolgende generatie voor een bekende doelversie.
- **Restore:** kopieert een oude geldige toestand naar een nieuwe generatie; `CURRENT`
  gaat nooit letterlijk terug in de tijd.
- **Compact:** legt eerst een waardevrije retentiebeslissing vast en verwijdert daarna
  niet-beschermde oude generaties.
- **Privacy scrub:** de enige expliciete uitzondering op generatie-immutability.

Een scrub moet gevoelige broninformatie werkelijk uit alle behouden generaties kunnen
verwijderen. Daarom herschrijft `EngineCore` het volledige pakket: bewijs verdwijnt,
afhankelijke voorstellen worden verwijderd, overblijvende assertions worden waar
nodig `unverifiable`, checksums en inventories veranderen en derived uitleg wordt
gewist. Daarna wordt alles opnieuw gevalideerd.

Immutability dient dus auditability, maar privacy heeft een expliciet ontworpen en
controleerbaar sterker recht.

## 13. Afhankelijkheidsrichting

De bedoelde richting is naar binnen:

```text
CLI / workspace
      │
      ▼
EngineCore ───────────────► storage-interface
      │
      ├────────► canonical validation
      ├────────► modulecatalogus + ingebouwde modules
      ├────────► regels
      └────────► analyses / workflow / uitleg
                    │
                    ▼
          models · identifiers · errors
```

Foundationmodules (`models`, `identifiers`, `errors`) importeren geen orchestration of
opslag. Semantische modules kennen CLI en engine niet. `storage.py` kent geen modules
of financiële validatie. Alleen `EngineCore` composeert betekenis en persistentie.

`scripts/check_architecture.py` handhaaft deze regels statisch in de ship-gate. De
architectuur is daarmee niet alleen documentatie, maar deels executable policy.

## 14. Teststrategie

Topo gebruikt drie niveaus:

1. `tests/` voor getypeerde units en in-process integratie, inclusief een
   geheugenimplementatie van de opslag-interface;
2. `e2e/` voor echte subprocess-journeys via `python -m topo`, inclusief controle van
   het pakket dat op schijf achterblijft;
3. `scripts/verify.sh` voor architectuurregels, Ruff, mypy, unit/integratie en e2e.

De e2e-tests zijn vooral waardevol als uitvoerbare architectuurdocumentatie. Zij tonen
complete reizen: lege context, import naar cashflow, nettovermogen, scenario's,
workflow, lifecycle, recovery en tamper-detectie.

Een aparte benchmark bouwt een synthetisch pakket met duizenden bronrecords, circa
30.000 assertions en zes generaties. Current-only status, workflow en nettovermogen
moeten daarna binnen de ingestelde grens blijven.

## 15. Sterke keuzes en groeispanningen

### Wat sterk is

- **Kleine opslag-interface, diepe implementatie.** Callers zien `load` en `commit`;
  crashveiligheid, locking en recovery blijven lokaal.
- **Eén eigenaar van mutaties.** Financiële invarianten lekken niet naar CLI, adapter
  of agent.
- **Herleidbaarheid als modelonderdeel.** Bewijs en tijd zijn geen achteraf toegevoegde
  logging.
- **Onbekend blijft onbekend.** Onvolledigheid wordt per analyseonderdeel gemodelleerd.
- **Architectuur wordt getest.** Importregels en zwarte-doosreizen bewaken de grenzen.

### Waar groei druk kan geven

- `engine.py` bevat ruim drieduizend regels en veel publieke use-cases. De centrale
  verantwoordelijkheid is bewust, maar nieuwe capabilities kunnen de implementatie
  minder lokaal maken. Een latere opsplitsing moet interne seams maken zonder meerdere
  eigenaren van mutaties te creëren.
- `cli.main` is een grote dispatchfunctie. Nieuwe interfaces moeten niet nog meer
  semantiek daarin leggen; een dunne use-case-dispatchlaag kan later nuttig worden.
- Iedere mutatie schrijft volledige collecties. Dat maakt snapshots simpel en
  auditbaar, maar geeft een natuurlijke schaalgrens bij zeer grote contexten.
- De modulecatalogus ondersteunt versionering, dependencies en constraints, maar de
  huidige modules zijn ingebouwd in Python. Dit is nog geen runtime-pluginplatform.
- Analysedispatch gebeurt centraal op `analysis_id`. Bij veel nieuwe analyses wordt
  een expliciet analyseregister waarschijnlijk dieper en beter uitbreidbaar.

Dit zijn geen acute defecten. Het zijn de plekken waar de huidige eenvoud het eerst
zal moeten worden heroverwogen als de schaal of het aantal domeinen sterk groeit.

## 16. Zo lees je de code in een uur

Een praktische route:

1. Lees `README.md` en `docs/domain.md` om product- en veiligheidsgrenzen te kennen.
2. Lees `src/topo/models.py`: begin bij `EntityRecord`, `AssertionRecord`,
   `EvidenceRecord`, `ProposalRecord`, `Manifest` en `JournalEntry`.
3. Lees `EngineCore.initialize`, `submit_proposal` en `confirm_proposal` in
   `src/topo/engine.py`.
4. Volg daarna `_build_update_publication` naar
   `FileSystemStorageAdapter.commit` en `_publish_update`.
5. Lees één effectvrij pad: `EngineCore.analyze` naar bijvoorbeeld
   `analyze_net_worth`.
6. Bekijk `ModuleCatalog.validate_proposed_assertion` en daarna de constraints in
   `builtin_modules.py`.
7. Sluit af met één e2e-journey, bijvoorbeeld `e2e/test_net_worth_journey.py` of
   `e2e/test_context_lifecycle_journey.py`.

Na deze route kun je vrijwel iedere feature plaatsen langs twee assen:

- **verandert dit canonieke financiële context of leest het alleen?**
- **wie bezit de betekenis: EngineCore, een domeinmodule, een analyse of alleen een
  adapter?**

Als die antwoorden onduidelijk zijn, ligt de feature waarschijnlijk over een
architectuurseam heen.

## 17. Begrippenkaart

| Begrip | Korte betekenis |
| --- | --- |
| Contextgraph | Samenhang van financiële entiteiten, beweringen en relaties |
| Generatie | Volledige immutable snapshot van canonieke context |
| Mutatie | Gevalideerde overgang naar een nieuwe generatie |
| Assertion | Tijdsgebonden, herleidbare uitspraak |
| Evidence | Onderbouwing van waarneming, voorstel of beslissing |
| Proposal | Nog niet bevestigde interpretatie |
| Preview | Exact effect waarop menselijke autorisatie wordt gebonden |
| Module | Eigenaar van publieke identifiers en constraints |
| Seam | Plaats waar gedrag via een kleine interface kan variëren |
| Adapter | Concrete implementatie aan zo'n seam |
| Derived data | Herbouwbare uitvoer die geen canonieke waarheid is |

## 18. Samenvatting

Topo is het best te begrijpen als een lokale, event-bewuste snapshotmachine rond een
financiële graph:

- callers spreken versiegebonden JSON;
- `EngineCore` is de enige eigenaar van betekenisvolle toestandsovergangen;
- modules bewaken financiële identifiers en constraints;
- analyses lezen gevalideerde snapshots zonder ze te veranderen;
- de opslagadapter publiceert complete generaties crashveilig;
- bewijs, tijd, onzekerheid en menselijke autorisatie zijn onderdeel van het model;
- agents staan buiten de bron van waarheid en kunnen alleen via de engine handelen.

De architectuur optimaliseert daarmee eerst voor vertrouwen, herleidbaarheid en lokale
controle. Performance en uitbreidbaarheid zijn aanwezig, maar worden bewust begrensd
door het principe dat financiële betekenis nooit impliciet of half gepubliceerd mag
worden.
