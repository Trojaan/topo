# CLI-bruikbaarheid: uitvoeringsroadmap

Deze roadmap houdt de verbeteringen uit de gebruikerssessie over meerdere
werksessies bij. Werk na iedere afgeronde sessie de vakjes, testuitkomsten en
volgende stap bij. Gebruik uitsluitend synthetische pakketten voor verificatie.

**Status:** de afgevinkte taken hieronder beschrijven de afgesproken v0.4.0-scope,
niet alle voorstellen uit de oorspronkelijke observatielijst. De nog open
oorspronkelijke wensen staan onderaan met lege vakjes.

## Besluiten

| ID | Observatie | Oordeel en prioriteit | Acceptatie |
| --- | --- | --- | --- |
| U1 | `contract describe` heeft geen `--package` | Niet toevoegen; laag | Help zegt dat contracten pakket-onafhankelijk zijn. |
| U2 | Request-transport en argv-fouten zijn lastig | Doen; hoog | Iedere request-opdracht toont bestand/stdin in help; `--json` geeft bij gebruiksfouten een JSON-diagnostic met hint. |
| U3 | Analyse-aanroep vraagt veel vaste velden | Doen; middel | Verkorte aanroep leidt versies en unieke scope af; datum blijft verplicht en ambiguïteit geeft een duidelijke fout. |
| U4 | Compact contextoverzicht ontbreekt | Doen; hoog | Eén aanroep geeft aantallen, open voorstellen, huidige saldi en actuele diagnostics zonder ref-dumps. Onbekende saldi worden niet nul. |
| U5 | Schema van canonieke records ontbreekt | Doen; middel | CLI geeft versiegebonden schemas voor entities, assertions, proposals en evidence; docs verklaren encodings. |
| U6 | Oude derived explanations lijken actueel | Deels doen; hoog | Historische uitleg blijft bewaard; de summary toont actuele **net-worth**-diagnostics met explain-refs. |
| U7 | Discovery/analysis zijn te groot | Deels doen; hoog | Compacte JSON is optioneel beschikbaar; volledige detailuitvoer blijft standaard en er is een discovery-tabel. |
| U8 | Contract-ID's zijn niet raadbaar | Vindbaarheid verbeteren; middel | Help en contractoverzicht koppelen CLI-namen aan exacte contract-ID's; bestaande ID's blijven. |
| U9 | Herhaalde queries voelen traag; voorbeeld ontbreekt | Deels doen; middel | De trage discovery-lookup is opgelost en er is een illustratief voorbeeld; herhaalde generatieparsing en de ontbrekende volledige CLI-journey blijven open. |

## Sessies

### 1. CLI-basis

- [x] U1: package-onafhankelijkheid in `contract describe --help`.
- [x] U2: uniform `--request PATH` en stdin in subcommand-help.
- [x] U2: machineleesbare argv-fouten met herstelhint bij `--json`.
- [x] U8: CLI-naam en contract-ID zichtbaar in help en `contract describe`.
- [x] Black-box e2e voor help, request-bestand en foutpad.

### 2. Snelle oriëntatie

- [x] U4: `context summary --package … --as-of DATE --json` via `EngineCore`.
- [x] U6: net-worth-diagnostics voor alleen de huidige generatie, met bruikbare explain-refs.
- [x] Black-box e2e voor aantallen, ontbrekende saldi, huidige generatie en uitleg.

### 3. Uitvoer en bediening

- [x] U7: optionele compacte analyze- en discover-JSON; volledige detailuitvoer blijft beschikbaar.
- [x] U7: scanbare discovery-tabel en gedocumenteerde voorspelde periode.
- [x] U3: verkorte analyze-, discover- en workflow-aanroepen met verplichte datum.
- [x] Gewijzigde publieke responsschemas versioneren; black-box e2e toevoegen.

### 4. Zelfbeschrijving

- [x] U5: recordschema's van `topo.context/0.2` via de CLI.
- [x] U5: waarde-encodings en tijd/provenance in de documentatie.
- [x] U9: illustratief synthetisch voorbeeld van import tot workflowantwoord in `docs/development.md`.
- [x] Contracttests en schemavalidatie van het ingevulde workflowantwoord toevoegen.

### 5. Prestaties

- [x] U9: tijd en piekgeheugen van herhaalde reads op een groot synthetisch pakket meten.
- [x] Alleen bij aangetoonde winst het laden veilig optimaliseren, zonder huidige-generatievalidatie over te slaan.
- [x] `scripts/benchmark_reads.py` en `scripts/verify.sh` uitvoeren.

## Nog open uit de oorspronkelijke lijst

- [ ] U2: beslissen of argv/usage-fouten **ook zonder `--json`** altijd een JSON-envelope moeten geven. v0.4.0 doet dat alleen met `--json`, zoals in het afgesproken plan.
- [ ] U3: bepalen welke verkorte aanroep passend is voor `scenario_comparison`; de huidige `--analysis`-shortcut dekt vier analyses en scenario blijft een expliciete JSON-request vereisen.
- [ ] U4/U6: één actueel overzicht van **alle** blockers en warnings, niet alleen net worth; daarbij een expliciete toegangsvorm zoals `explain --diagnostics` en een heldere lifecycle voor oude derived explanations.
- [ ] U7: compacte analyse- en discovery-uitvoer standaard maken en de volledige ref/proposal-details achter een expliciete optie plaatsen. v0.4.0 vereist `--compact`.
- [ ] U9: een volledig uitvoerbare, synthetische CLI-journey publiceren met ingevulde import-, proposal-, confirm- en workflow-requests. Het huidige document toont die stappen deels als instructies.
- [ ] U9: bij een concrete nieuwe prestatiedoelstelling onderzoeken of herhaalde processen gevalideerde generatiegegevens veilig kunnen hergebruiken. v0.4.0 versnelt discovery zonder cache; iedere query laadt de generatie nog opnieuw.

Bewuste besluiten die niet opnieuw als open taak gelden: `contract describe` krijgt
geen pakketargument; peildata blijven expliciet; bestaande contract-ID's worden
vindbaar gemaakt maar niet hernoemd; oude explanation-bestanden blijven als
historische uitleg bewaard. Deze keuzes zijn tijdens het plannen besproken.

## Voortgangslog

| Datum | Sessie | Commit/PR | Verificatie | Eerstvolgende stap |
| --- | --- | --- | --- | --- |
| 2026-09-29 | CLI-basis, oriëntatie, compacte uitvoer, schemas en voorbeelden | Release v0.4.0 | Architectuurcheck, gerichte Ruff en mypy groen; 74 unit-tests en 37 e2e-tests groen. | Bij nieuwe CLI-wijzigingen passende e2e bijwerken. |
| 2026-09-29 | Prestatiemeting en gerichte discovery-optimalisatie | Release v0.4.0 | 7.500 records: `discover.run --compact` van 51,640 s naar 1,156 s (één gemeten run); status 1,088 s, workflow 1,497 s, analyse 1,096 s. Piekgeheugen 333–346 MiB. | Meet bij toekomstige grotere datasets opnieuw als dit relevant wordt. |
| 2026-09-29 | Status van oorspronkelijke lijst aangescherpt | Documentatiecommit na v0.4.0 | Resterende wensen hierboven expliciet onafgevinkt. | Werk eerst het gewenste standaard-uitvoercontract en diagnostic-overzicht uit. |

`scripts/verify.sh` is uitgevoerd maar stopte bij Ruff op de vooraf bestaande,
niet-getrackte `.scratch/claude-code-security-research/build_report.py`. Die file
is niet onderdeel van deze wijziging en is niet aangepast. Dezelfde checks zijn
apart op `src`, `tests`, `e2e` en `scripts` uitgevoerd en waren groen. De roadmap blijft bruikbaar als
referentie voor latere verbeteringen of regressies.
