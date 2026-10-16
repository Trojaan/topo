# Plan 4 — Levering en bewijs

Peildatum: 2026-10-15. Uitsluitend synthetische bronnen en tijdelijke contexten.
Technische uitvoering is expliciet toegestaan ondanks de open menselijke
gebruikspoorten van plannen 3 en 6. Die blijven open; deze opdracht bevestigt
geen financiële feiten, reserveringen of verwachtingen. De externe oefencontext
is niet gelezen of gewijzigd tijdens deze uitvoering. Geen vervolgplan of release.

## Onderzoek, besluiten en levering

AGENTS.md, plannenoverzicht, docs/topo2.md en bewijs van plannen 0–3 en 6 zijn
gelezen, inclusief het afzonderlijke externe basisgebruiksbewijs 0–2. De kennisgraph
meldde dat deze repository niet geïndexeerd is; code is rechtstreeks gelezen.
De reeds aanwezige wijzigingen voor plannen 3 en 6 en ongerelateerde onderzoeksmappen
zijn behouden. De bestaande gezamenlijke preview, bronbinding, no-op, importbehoud,
Decimal-validatie, beschikbaarheid en compacte leesprojectie zijn hergebruikt.

Ontwerpbesluiten staan vóór implementatie vastgelegd in [plan 4](04-doelen.md).
Doelen behouden naam, positief streefbedrag, valuta, optionele datum en koppelingen.
Nieuw: optionele niet-negatieve reserved_amount en monthly_contribution, inclusief
expliciete nul; optionele priority low/normal/high en vrije note tot 256 tekens.
Prioriteit is menselijke rangorde, geen automatische verdeling. Bestaande geldgrenzen
gelden; reservering mag boven streefbedrag of bekend vermogen liggen.

remaining_amount is max(streefbedrag minus expliciete reservering, 0); onbekend
blijft null. Oude koppelingen blijven linked_value. Bestaande known_amount,
percentage, missing_ids en complete blijven compatibele gekoppelde-waardevelden.
Er is geen automatische omzetting of optelling bij reserveringen. Onbekende
gekoppelde waarden blokkeren geen bekende resterende berekening.

reservation_comparison vergelijkt per doelvaluta bekende reserveringen met de
bestaande vrije vermogensdeelsom. Ontbrekende reserveringen, bedragen,
beschikbaarheid en accounts/assets/goals-inventarissen blijven herkenbaar.
possible_excess en coverage_unknown zijn onafhankelijke signalen, nooit opslag-
blokkades. Zonder vermogensrecords blijft de vrije waarde null. Ook zonder hiaten
wordt geen gezamenlijke/exclusieve dekking geclaimd. Reserveringen zijn bestemmingen,
geen bewijs van middelen. Minimumreserve blijft een afzonderlijke saldodrempel;
geen nieuwe afslag voor schulden, reserveringen of maandinleg in het maandbeeld.

CLI blijft additief topo2.cli/3; niet-null doelverrijkingen vereisen context/7.
Oude versies 1–6 blijven leesbaar; previews en no-ops schrijven/migreren niets.
Versie 7 blijft na wissen behouden. Oude opslagformaten krijgen geen nieuwe
verrijkingsvelden. change.update blijft volledige-recordvervanging; transactie-import
bewaart alle doelen en overige contextgegevens. De zuivere goals-module ontvangt
doelen, waarde-index, beschikbaarheid en inventarissen, geen transacties of opslag.

## Technisch en black-box bewijs

31 nieuwe unittests bewijzen onbekend/nul, 10.000 minus 4.000, overreservering,
validatiegrenzen, optionele prioriteit/toelichting, grote Decimal-bedragen bij lage
omgevingsprecisie, valuta-isolatie, afzonderlijke gekoppelde waarde en ontbrekende
waarden. Een onleesbare transactieverzameling bewijst dat summary en compact
context met honderd doelen geen transacties doorlopen. Maandinleg verandert het
maandbeeld of de minimumreserve niet.

Acht nieuwe black-box journeys gebruiken afzonderlijke CLI-processen en controleren
schema-overeenkomst. Kort doelbericht geeft één doel zonder inventaris, koppeling,
prioriteit of verzonnen datum. Onbekende reservering blijft null, nul wordt bekend.
Versies 1–6 blijven byte-/mtime-identiek bij lezen, preview, no-op en geweigerde
verouderde token. Alleen technische toepassing schrijft versie 7; wissen verlaagt
haar niet. Waardedaling en overreservering kunnen worden opgeslagen.

De gezamenlijke bronjourney omvat rekeningen, vermogen, schulden, transactiesoorten,
verwachtingen, instellingen en doelverrijkingen. Zij bewijst bron-/requesttokenbinding,
identieke heraanlevering zonder token/schrijven en behoud bij zowel een exportupdate
als een werkelijk gewijzigde standalone import. Soorten, categorieën, bronlabels,
schulden, beschikbaarheid/toelichtingen, verwachtingen, instellingen en doelen
blijven behouden; saldo-, vermogens-, doel- en maanduitkomsten veranderen niet door
transactiecorrecties. Gescripte tokens zijn uitsluitend mechanisch bewijs.

## Werkelijk voorbereide agentsessie en gebruiksgrens

De oorspronkelijke en bijgewerkte bankexport, doeltekst, vermogensbron,
verwachtingenbron en twee nieuwe doelbronnen zijn gelezen. Beide PNG's zijn
visueel gecontroleerd: betaal EUR 2.514,50 en sparen EUR 6.400,00 op 2026-10-04.
De eerste voorbereiding gebruikt uitsluitend de oorspronkelijke export; de
bijgewerkte export is vervolginput voor technisch herimportbewijs.

De agent heeft contractontdekking, brongebonden gezamenlijke preview en
kandidaatberekeningen uitgevoerd. De kandidaat wordt uitsluitend in geheugen
berekend: EUR 10.000 doel, EUR 4.000 bestemming, EUR 200 voorgenomen maandinleg,
hoge prioriteit en korte toelichting. Resterend EUR 6.000; gekoppelde waarde
EUR 6.400 staat apart. De bekende vrije deelsom is EUR 10.000; mogelijke
overschrijding false, dekking onbekend wegens inventaris/beschikbaarheid. Dit
bewijst geen gezamenlijke of exclusieve dekking. Bekende EUR-nettosom 118.414,50,
USD 900 en maandruimteband 1.705–1.878,33333334 blijven behouden. Minimumreserve
EUR 5.000 blijft afzonderlijk.

Een aparte minimale preview is ook voorbereid vanaf “€10.000 voor een verbouwing
volgend jaar”: alleen naam en streefbedrag, EUR zichtbaar als standaard, datum en
reservering onbekend. Geen verplichte voorkeur- of inventarisvragen. Er is geen
berekening vanaf een stilzwijgende nul.

Artefacten staan lokaal in test-results/topo2-goals/session/: contract, request,
bronlijst, conversie, gezamenlijke/minimale previews en kandidaatuitkomsten.
De tijdelijke lege context bleef byte-/mtime-identiek en is daarna verwijderd.
Geen token is toegepast. Financiële verduidelijkingsbundels: **0**; menselijke
bevestigingsvragen: **0**; ontvangen bevestigingen: **0**; toegepaste tokens: **0**;
bronherstel: **0**. Er is dus geen menselijke bevestiging gesimuleerd.

Voorbereiding vanaf contractontdekking tot previews/kandidaatuitkomsten: **0,794 s**,
inclusief afzonderlijke CLI-processen voor contract/init/beide previews. Bron- en
beeldlezen en implementatietijd zijn uitgesloten; tests liepen gelijktijdig. Dit is
een lokale voorbereidingsmeting, geen gesprekssnelheid of tijd tot bevestigd inzicht.
Technische journeys bewijzen geen daadwerkelijk menselijk frictiebudget. Plan 4's
menselijke gebruiksacceptatie blijft open, evenals de poorten van plannen 3 en 6.
Het externe gebruiksbewijs 0–2 blijft afzonderlijk geleverd met zijn beperkingen.


## Verificatie

- Volledige unit-/integratiesuite: **248 geslaagd, 2 bewust overgeslagen**
  (bestaande CSV-null-skips), inclusief alle 31 nieuwe doeltests.
- Volledige black-box suite: **81 geslaagd**, inclusief journeys van plannen
  0–3 en 6 en acht nieuwe doeljourneys.
- Architectuurcontrole, mypy en git diff --check slagen. Lint en formattering
  slagen met uitsluitend .scratch/claude-code-security-research/ en .scratch/research/
  uitgesloten. Deze ongerelateerde bestanden zijn ongemoeid gebleven.
- De ongewijzigde scripts/verify.sh is uitgevoerd en stopt bij **zes bestaande
  lintfouten**: I001/F401/PIE810 in build_report.py en I001/PLW1510/B023 in
  okf-memory-race-test.py. Dit is geen geslaagde volledige script-run;
  de overige poorten zijn afzonderlijk uitgevoerd.

Ruwe controlelogs staan lokaal in test-results/topo2-goals/. UV_CACHE_DIR is voor
de sandbox ingesteld op /tmp/topo2-uv-cache. De eerste gerichte ontwikkelrun gaf
38 geslaagde tests en één fout in nieuwe testinvoer (datum zonder verplichte
ouderdomsgrens); die is hersteld vóór beide volledige suites. Ook één lintmelding
in een nieuwe Decimal-test is hersteld. Geen bestaande assertions zijn verzwakt.


## Performance en schaalgrens

Meetomgeving: macOS-27.0.1-arm64-arm-64bit-Mach-O, Python 3.13.11.
1.000 rekeningen, 100 doelen, vijf verwachtingen, meerdere valuta en 10.000
respectievelijk 100.000 transacties. De doelen bevatten bekende/nul/onbekende
reserveringen en maandinleg. Meetduur omvat volledige afzonderlijke CLI-processen:
interpreterstart, JSON-inlezen, validatie, berekening, serialisatie en eventuele
opslag. RSS komt uit het eigen CLI-proces; bytes omvatten de volledige envelope.

De definitieve benchmarks zijn na beide volledige testsuites uitgevoerd, zonder
gelijktijdige tests of andere benchmarks. De eerste 100k-run overlapte kort met
statische controles en is daarom behouden als benchmark-100000-initial.json;
de finale 100k-run is zonder die controles herhaald. Eén definitieve meetronde
per schaal: lokale diagnostiek, geen algemene snelheidsclaim.

| Operatie | seconden 10k / 100k | uitvoerbytes 10k / 100k | piek-RSS MiB 10k / 100k |
| --- | ---: | ---: | ---: |
| Doel-/vermogenssamenvatting | 0.202 / 0.630 | 65,805 / 65,805 | 65.83 / 307.75 |
| Compact context | 0.234 / 0.688 | 713,756 / 713,756 | 68.16 / 307.59 |
| 100 doelen preview | 0.235 / 0.803 | 86,443 / 86,443 | 75.89 / 404.75 |
| 100 doelen toepassen | 0.304 / 1.512 | 86,443 / 86,443 | 95.19 / 542.78 |
| 100 doelen identiek | 0.227 / 0.798 | 159 / 159 | 76.36 / 404.59 |
| Volledige show | 0.241 / 0.978 | 3,629,670 / 33,692,451 | 74.09 / 402.69 |
| Aggregatie maand + categorie | 0.248 / 1.152 | 156,071 / 157,237 | 66.45 / 307.58 |

Alle **23 benoemde operaties** bij 10.000 transacties blijven onder één seconde;
maximum **0.304 s**. De bestaande poort is behouden.
Beide benchmarks eindigen met exitcode 0. Het 100.000-profiel heeft geen nieuwe
harde tijdgrens; maximum **1.846 s**. Maximale piek-RSS over
alle gemeten CLI-processen: **98.20 / 568.67 MiB**.

De benchmark bewijst identieke volledige doeluitkomsten en reserveringsvergelijking
vóór/na toevoegen en corrigeren van transacties, plus gelijkblijvende compacte
uitvoergrootte. Preview, toepassing en no-op van honderd doelupdates zijn bij beide
schalen gemeten; maandinlegwijziging verandert monthly-room niet.

De engine leest en valideert nog steeds het volledige JSON-bestand. Compacte
uitvoer en een transactievrije doelberekening betekenen geen constante totale
latentie of constant geheugen. Vooral volledige uitlezing en schrijf-/tokenpaden
blijven met de contextgrootte groeien; geen opslagherontwerp uitgevoerd.

Reproduceren: `uv run python scripts/benchmark_topo2.py` en dezelfde opdracht met
`--transactions 100000`. Alle ruwe procesmetingen staan lokaal in
`test-results/topo2-goals/benchmark-10000.json` en `benchmark-100000.json`.

## Status en stopgrens

Plan 4 is technisch geleverd; menselijke gebruiksacceptatie blijft open. De open
menselijke gebruikspoorten van plannen 3 en 6 blijven expliciet open. Technische
autorisatie en testtokens bevestigen geen financiële feiten of verwachtingen.
De externe oefencontext is ongemoeid gebleven. Geen benodigde maandinleg,
haalmaand, gezamenlijke haalbaarheid, vervolgplan, opslagherontwerp of release.
