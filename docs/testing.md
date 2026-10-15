# Testing and verification

Voor de zelfstandige actuele-toestand-engine `topo2`, zie [Topo 2](topo2.md).
De bestaande generatie- en voorstelcontracten op deze pagina gelden voor `topo`.

The gate has three layers:

1. `tests/` exercises typed units and in-process integration boundaries.
2. `e2e/` invokes `python -m topo` as a real subprocess and verifies both the JSON
   contract and the durable package a user receives.
3. `scripts/verify.sh` runs architecture rules, Ruff, mypy, unit/integration tests,
   and the black-box journey in a stable order.

Run the complete gate with `scripts/verify.sh`. Run only the e2e journey with
`scripts/e2e.sh`; its terminal transcript is saved under
`test-results/e2e/pytest.txt`. Generated evidence is ignored by Git.

The opt-in read-performance gate builds a temporary synthetic package with 7,500
source records, about 30,000 assertions, and six immutable generations. After one
warm-up per command it requires the median of three separate CLI processes for
status, workflow-next, and net-worth analysis to remain below two seconds:

```bash
uv run python scripts/benchmark_reads.py
```

Add `--memory` to report peak resident memory per read process, and
`--include-discover` to measure compact recurring discovery as well. These runs
use generated synthetic records and leave no financial package behind.

The fixture is deleted after the run and never contains personal financial data.
Keep this benchmark separate from the ordinary correctness gate because building
the large immutable history is intentionally expensive.

To compare full-snapshot and delta storage on the same synthetic 21-generation
fixture, including package size, one authorized mutation, full verification, and
peak resident memory, run:

```bash
uv run python scripts/benchmark_reads.py --records 7500 --generations 21 --storage-profile --memory
```

The profile creates a migrated copy at a temporary path. It reports the read gate
separately from the storage comparison and does not use personal financial data.
On a local 7,500-record, 21-generation run on 2026-10-02, the full/delta packages
were 295.4/58.1 MiB. The authorized mutation took 12.8/8.4 seconds and used
about 1,991/776 MiB peak RSS. Full `context verify` took 11.3/13.3 seconds and
used about 1,990/2,172 MiB peak RSS. These are single-run diagnostics, not CI
thresholds. Delta storage met the space target but did not halve mutation or
verification time; full historical semantic validation remains the verify cost.

The initial journey proves contract discovery, first context publication, the
client-visible success envelope, canonical persisted state, empty-context
inventory, deterministic effect-free workflow guidance, unknown major-version
refusal, checksum write blocking, and refusal to replace an already-published
package. There is no auth or external service in v0.1, so an
auth/session helper and sandbox credential guard would be theatre; add them when
such a boundary actually exists.

The workspace journey proves a new directory receives one canonical
`context.topo/`, private import and package ignore rules, automatically discovered
Codex and Claude instructions, a read-only status projection, and an idempotent
second initialization without a new generation. Unit tests additionally prove
managed-block preservation, CRLF handling, safe updates, and fail-closed marker
or package conflicts.

The source journey also proves recurring discovery leaves `CURRENT` and proposals
unchanged, reports insufficient history, and produces a candidate that can be
selected through the ordinary proposal workflow. It also proves two known source
accounts can be answered as one workflow batch, with one new user-statement
evidence record, one open proposal per account, atomic rejection, replay, and no
transaction evidence reused as balance evidence.

The helper journey prepares two synthetic source requests before execution,
refreshes the second request's generation, and previews and authorizes each in
sequence. It checks UUIDv7 and batch IDs, rejects reused operation IDs and
authorized refreshes, and proves schema validation of `proposal.submit` leaves
`CURRENT` unchanged.

The realized-cashflow journey proves half-open month selection, explicit account
allocation and coverage, paired-transfer exclusion, unclassified net movement,
component-local provisional status, and effect-free generation reuse.

The normalized-cashflow journey proves confirmed-current selection, candidate and
expired-fact exclusion, all five frequency factors, decimal intermediates, range
bounds, explicit typical amounts, and effect-free generation reuse.

The net-worth journey proves explicit allocation, per-interest deduplication,
account-plus-asset-minus-debt arithmetic, restricted-pension separation,
original-currency subtotal survival, missing-rate isolation, missing valuation
visibility, conflict localization, and an unavailable empty result without a zero
default.

The rule-package journey proves safe-YAML and capability validation, effect-free
preview traces, explicit human authorization, atomic full-package activation,
checksum-bound manifest pins, and stale-manifest conflict handling.

The context-lifecycle journey proves compatible migration, new-generation restore,
bounded retention with an explicit restore point, package-wide privacy scrub, and
explicit full-history verification through the public CLI. Unit integration tests
additionally prove incompatible migration has no effect, scrubbed assertions are
marked unverifiable, current-only reads omit retained snapshots, recovery artifacts
trigger full recovery, and retained corruption still blocks verification and
mutation.

The proactive-workflow journey validates every generated request against its
published schema, proposes manual accounts plus balances, allocation and coverage
as one batch, verifies checksum-bound authorization and atomic confirmation,
recomputes provisional net worth, and proves that the next missing basis domain is
asked immediately. Separate fixtures cover explicit empty coverage, stale
generations, rejection, replay and all-or-nothing invalid batches.

Together, `tests/` and `e2e/` are the reproducible v0.2 acceptance suite invoked by
`scripts/verify.sh`. They cover the three normative handoff journeys—empty context,
transactions to monthly cashflow, and net worth plus scenario—as well as the
minimum safety fixtures for replay, authorization, correction, stale generations,
constraints, currencies, normalization, restricted pension, explanation,
tampering, and contract-version refusal.

When an e2e test fails, classify it as a product defect, an intentionally changed
contract, or an environment problem. Never remove an assertion just to get green.
For a CLI-visible feature, update the journey and keep evidence synthetic.

CI builds both Linux standalone executables on every change. The Topo 2 smoke
flow uses only synthetic records and proves init, preview, confirmation, summary
and show from the frozen executable; its JSON transcript is a CI artifact. Unix
installer e2e tests exercise both downloads, legacy pinned releases and preservation
of installed commands when the second download is absent or invalid. A release tag
expands this to the five supported platform artifacts and smoke-tests each binary;
only after publication do installer jobs download both released zips and exercise
the installed commands, including the complete synthetic Topo 2 smoke flow.
The upgrade command's tests use synthetic release metadata and archives locally;
they do not contact GitHub or replace a developer's installed CLI.

The proposal-submit-batch CLI journey proves effect-free preview, checksum-bound
human authorization, one generation for several open proposals, per-item results,
replay and schema agreement. Incremental-validation integration tests compare the
full and reused-record validators on a synthetic source chain, including old
literal, reference, duplicate, schema-version and raw-evidence corruption. The
change-set test deliberately supplies a wrong delta and proves publication is
blocked. Fragment-serialization tests compare append, remove, replace, version
changes and noncanonical-layout fallback with complete canonical serialization.

See [Performance measurements](performance.md) for the synthetic 7,500-record,
21-generation fixture, ten-mutation work round and profiling limitations.

## Topo 2-transacties

De transactie-journeys bewijzen JSON/CSV-import, herimport zonder wijziging,
correctie, verwijdering, gecombineerde rekening/transactie-invoer, filters en
paginering. Een versie-1-context blijft bij lezen en preview byte voor byte gelijk;
alleen een bevestigde wijziging slaat versie 2 op. Unit-tests bewaken ook de
volledige bestandsbinding van importtokens, ongeldige CSV, financiële precisie,
gekoppelde verwijdering en opslagfouten zonder gedeeltelijke wijziging.
De bestaande standalone smoke oefent import en zoeken ook vanuit het werkelijk
gebouwde en geïnstalleerde programma uit op alle releaseplatformen.
De synthetische benchmark bevat 10.000 transacties en vereist minder dan één
seconde voor gericht zoeken en een bulkupdate van 1.000 transacties.


## Topo 2-invoer vanaf bronnen

De synthetische [plan-0-journey](plans/topo2-context/00-bewijs.md) start bij een
bankexport, twee fictieve PNG-saldoschermen en een doelbericht. De black-box test
bewijst gecombineerde invoer, bronbinding, identieke heraanlevering zonder schrijven,
verrijkingsbehoud en expliciet wissen/vervangen. Een afzonderlijke agentsessie
registreert de werkelijke visuele bronlezing, vraagbundels en menselijke bevestiging;
gescripte testbevestigingen tellen daarvoor niet mee.

`uv run python scripts/benchmark_topo2.py` meet ook behoud bij import en brongebonden
change bij 1.000 rekeningen en 10.000 transacties. De grens blijft één seconde per
benoemde operatie. `--transactions 100000` geeft een schaalprofiel zonder harde
nieuwe grens. Beide rapporteren uitvoergrootte en piek-RSS per CLI-proces op macOS/Linux.

De plan-1-journey `e2e/test_topo_v2_context_journey.py` bewijst compact lezen van
oude en gedeeltelijke context, gerichte onzekerheid, optionele verklaringen in één
preview, intervalgrenzen en behoud bij import. `tests/test_topo_v2_reading.py`
controleert gekoppelde doelonzekerheid, lege complete inventaris en tokenbinding.
De Topo 2-benchmark meet ook `context` met expliciet ouderdomsbeleid en bewaakt
dat de uitvoergrootte gelijk blijft na toevoegen van transacties. Zie
[het bewijs van plan 1](plans/topo2-context/01-bewijs.md) voor metingen en
[extern gebruiksbewijs 0–2](plans/topo2-context/gebruik-bewijs-00-02.md) voor de
inmiddels geleverde basisjourney, inclusief herstelstappen en beperkingen.


De plan-2-journey `e2e/test_topo_v2_wealth_journey.py` bewijst afzonderlijke valuta,
expliciet eenmaal getelde roodstand, onbekende schuldstanden, optionele
beschikbaarheid, atomaire verwijzingen, gezamenlijke correcties, bronbinding en
behoud bij herimport. Unit-tests dekken bekende nul, schuld-only context,
waardebeschikbaarheid versus inventarisstatus en versie-4-validatie. Oude contexten
blijven bij lezen, preview en identieke invoer byte- en mtime-identiek.
De benchmark bevat nu synthetische schulden en beschikbaarheid en bewaakt dat zowel
summary als context compact blijven bij groei van transacties. Zie
[plan-2-bewijs](plans/topo2-context/02-bewijs.md); gescripte tokens bewijzen geen
menselijke gebruiksbevestiging.


## Topo 2-transactiebetekenis en aggregaties

Plan 6 voegt unit- en black-box controles toe voor gesigneerde correcties,
rekeningbewegingen versus economische cashflow, transferhelften, onbekenden,
valuta-isolatie, grote Decimal-sommen, gecombineerde filters en deterministische
maand-/categoriegroepen. Classificatievolledigheid en expliciete intervaldekking
worden onafhankelijk getoetst. Oude contexten 1–4 migreren pas bij een effectieve
bevestigde wijziging met kind; versie 5 blijft behouden na wissen/verwijderen.

De bronjourney voor vermogen draait ook met voorbereide soorten en bewijst behoud
bij exportupdate en herimport. Alle gescripte tokens blijven uitsluitend technisch
bewijs. De nieuwe menselijke gebruikspoort is afzonderlijk vermeld in
[plan-6-bewijs](plans/topo2-context/06-bewijs.md).

De benchmark meet ook ongesplitste, gefilterde en maand/categorieaggregaties over
meerdere maanden, categorieën, soorten en valuta. Hij meet volledige CLI-processen,
uitvoerbytes en piek-RSS bij 10.000 en 100.000 transacties, met één scan per aanroep
in plaats van per groep. Alleen de bestaande 10.000-grens van één seconde geldt
als harde poort; 100.000 blijft een schaalprofiel. Compacte uitvoer sluit volledig
inlezen en valideren van de JSON-opslag niet uit.


## Topo 2 — verwachtingen en structureel maandbeeld (plan 3)

`tests/test_topo_v2_cashflows.py` toetst vaste factoren, inclusieve datumgrenzen,
naar buiten afgeronde banden, valuta, onbekend/nul, inventaris, schuldverwijzingen
en instellingen. Een onleesbare transactieverzameling bewijst dat de maandprojectie
geen transacties scant. De engine voert geen patroonherkenning of overlapdetectie uit.

`e2e/test_topo_v2_cashflow_journey.py` begint bij de oorspronkelijke plan-0-export,
gebruikt CLI-aggregaties en de expliciete synthetische verwachtingenbron en bewijst
één gezamenlijke target-preview. Een aparte tijdelijke fixturecontext voedt de
CLI-aggregatie vóór die preview; dit is testopstelling, geen extra gebruikersstap.
Alle tokens zijn uitsluitend mechanisch bewijs. De test bewijst tevens behoud van
verwachtingen, instellingen, soorten, schulden, beschikbaarheid en verrijkingen bij
exportupdate/herimport, byte-/mtime-identieke no-ops, oude contexten 1–5 en versie 6.

De benchmark meet monthly-room en het uitgebreide context in volledige processen
bij 10.000/100.000 transacties, inclusief bytes en eigen piek-RSS. Het maandresultaat
blijft exact gelijk na toevoegen/wijzigen van transacties; volledig JSON-inlezen en
valideren blijven wel groeien. Alleen 10.000 heeft de bestaande éénsecondepoort.
Zie [plan-3-bewijs](plans/topo2-context/03-bewijs.md) voor resultaten en open poorten.


Topo 2 plan 4 adds `tests/test_topo_v2_goals.py` and the black-box
`e2e/test_topo_v2_goals_journey.py`: short source input, reservation versus linked
value, unknown/zero, excess/value falls, legacy versions 1–6, source-bound joint
preview, no-write/no-op, migration and export enrichment preservation. The
benchmark includes 100 goals at both transaction scales; goal outcomes must remain
identical after transaction changes. It also measures preview, effective update
and no-op for 100 goal records at both scales. Full CLI latency, output bytes and own-process
peak RSS remain measured. The existing 10k gate stays below one second; 100k is a
scale profile. Mechanical tokens never establish human usage acceptance.


## Topo 2-rapporten (plan 7)

`tests/test_topo_v2_reports.py` controleert aansluiting op gedeelde berekeningen,
onbekend/nul, valuta, selectie, escaping, één snapshot en veilige publicatie.
`e2e/test_topo_v2_report_journey.py` vergelijkt echte HTML-cellen met afzonderlijke
CLI-uitkomsten, leest oude opslagversies zonder migratie, bewaakt contextbytes/mtime
en herhaalt de synthetische bron-/herimportjourney zonder extra inventarisatie.
Testtokens zijn uitsluitend mechanisch bewijs; menselijke gebruikspoorten blijven open.

De bestaande benchmark bevat report_all en report_bounded binnen dezelfde 10k-poort.
`measurements` bevat volledige procesduur, stdout_bytes, html_bytes en piek-RSS.
`report_phases` meet read_validation_seconds, calculation_seconds en rendering_seconds
in een afzonderlijk diagnostisch proces; diens RSS is cumulatief, geen afzonderlijke
geheugenpiek per fase. Beide routes moeten exact dezelfde HTML-bytes/hash produceren
als de overeenkomstige volledige CLI-run. 100k blijft schaalprofiel zonder nieuwe
harde tijdgrens. Voer benchmarks achtereenvolgens zonder tests tegelijk uit.

Visueel bewijs gebruikt uitsluitend synthetische lege/minimale/rijke rapporten op
1440 en 390 pixels breed. Controleer initiële viewport, alle secties, lange tekst,
clipping, leesbaarheid en afwezig netwerkverkeer. Lokale screenshots/ruwe logs staan
buiten Git in test-results/topo2-reports; bevindingen staan in plan-7-bewijs.
