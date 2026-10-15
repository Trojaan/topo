# Plan 3 — Levering en bewijs

Peildatum: 2026-10-15. Technisch geleverd; volledige script-run blijft geblokkeerd door bestaande lintfouten. Uitsluitend synthetische
bronnen en tijdelijke oefencontexten. De externe oefencontext is niet gewijzigd.
De gebruiker heeft technische uitvoering expliciet toegestaan ondanks de open
menselijke gebruikspoort van plan 6. Die poort blijft open; er zijn geen nieuwe
financiële classificaties of verwachtingen menselijk bevestigd.

## Bestaand, toegevoegd en begrensd

Voor uitvoering zijn AGENTS.md, het plannenoverzicht, docs/topo2.md en het bewijs
van plannen 0–2 en 6 gelezen, inclusief het externe basisgebruiksbewijs 0–2.
De kennisgraph kon deze repository niet vinden; code is rechtstreeks gelezen.
Bestaande wijzigingen, waaronder plan 6 en de ongerelateerde onderzoeksmappen,
zijn behouden. Geen vervolgplan, opslagherontwerp of release uitgevoerd.

De bestaande gezamenlijke preview, bronbinding, no-op, importbehoud, aggregaties,
schulden en beschikbaarheid zijn hergebruikt. Nieuw zijn cashflows, eenvoudige
optionele cashflow_settings per valuta en monthly-room. Geen voorkeurenrecords,
patroonherkenning, categorisatie of voorsteladministratie. De agent bereidt enkele
verwachtingen voor; een volledige inventarisatie of bedrag per categorie is geen
voorwaarde. De public API blijft additief topo2.cli/3, nieuwe opslagdata gebruiken
context/6. Alle eerdere opslagversies blijven leesbaar zonder herschrijven.

De ontwerpbesluiten zijn vóór implementatie vastgelegd in 03-geldstromen.md.
Bedragen zijn niet-negatief met expliciet income/expense. Eén amount bevat een
exacte waarde, lower/upper-band of null. Datums zijn inclusief; alleen activiteit
op de expliciete referentiedatum telt. Factoren: 52/12, 13/12, 1, 1/3, 1/12.
Per post wordt naar buiten afgerond op acht decimalen en daarna exact opgeteld.
Geen middenwaarden, impliciete systeemdatum, dagproratering of betaalagenda.

known_room.lower is laagste bekende inkomsten minus hoogste bekende uitgaven.
De bekende deelsommen blijven bruikbaar met onbekende bedragen/inventaris;
room is alleen gevuld wanneer beide compleet zijn. De genormaliseerde postbanden
maken de som controleerbaar. Minimumreserve is de door de gebruiker gekozen
saldodrempel, geen maandelijkse afslag. Vrije toelichting wordt geen rekenregel.

Verwachtingen en gerealiseerde transacties blijven gescheiden. Transactie-import
behoudt verwachtingen, instellingen, verrijkingen en overige records; een betaling
wijzigt geen saldo of schuldstand. Doelinleg wordt niet opnieuw afgetrokken.
De agent omschrijft welke bronselectie een samengevoegde uitgavenpost omvat en
sluit afzonderlijke lasten daarvan uit. Dit is operationele agentdiscipline,
geen automatische engine-overlapdetectie. Eigen overboekingen zijn geen consumptie.

## Technisch bewijs

De cashflow-unittests bewijzen alle factoren, jaarlasten en vierwekelijks inkomen,
geordende niet-negatieve bandbedragen, inclusieve datumgrenzen, onbekend/nul,
negatieve maandruimte, valuta-isolatie, deterministische sortering, grote bedragen
bij lage omgevingsprecisie, schuldverwijzingen en instellingen. Gezamenlijke
schuldverwijzingen worden atomair gevalideerd; een gewijzigde instelling maakt een
oude token ongeldig. Instellingen vervangen alleen opgegeven valuta; null verwijdert.
Een onleesbare transactieverzameling in de context bewijst dat compact maandrekenen
geen transacties doorloopt. De zuivere maandfunctie ontvangt überhaupt geen transacties.

De nieuwe black-box journey begint bij bank.csv, de twee plan-0-PNG's, doel.txt,
vermogen.txt en de nieuwe expliciete synthetische verwachtingen.txt. Een aparte
**tijdelijke technische fixturecontext** voedt de CLI-aggregatie vóór de gezamenlijke
target-preview. Dit is testopstelling, geen extra productstap of menselijke bevestiging.
De verwachtingsvoorbereiding gebruikt de gerealiseerde inkomsten, boodschappen-
groep en transferaantallen. Frequenties en bandbreedte komen expliciet uit de
extra bron, nooit uit één aankoop of automatische patroonherkenning.

Eén target-preview bundelt rekeningen, vermogen, schulden, transactiesoorten,
verwachtingen en instellingen. De journey bewijst schema-overeenkomst, bron- en
requestbinding, exact behoud bij identieke heraanlevering zonder token/schrijven,
bijgewerkte export en standalone correctie met behoud van verrijkingen, soorten,
schulden, beschikbaarheid, toelichtingen, verwachtingen en instellingen.
De maanduitkomst en het vermogensoverzicht veranderen niet door de exportcorrecties.

Compatibiliteitsjourneys lezen versies 1–5, previewen nieuwe velden en bewijzen
byte-/mtime-identieke no-ops. Alleen technische toepassing schrijft versie 6;
die blijft behouden na verwijderen. Onbekende schulden, ID-conflicten en omgekeerde
datums worden zonder schrijven geweigerd. Complete inventaris verandert alleen
de volledigheidsclaim, niet de bekende som. Gescripte tokens zijn mechanisch bewijs.

## Werkelijk voorbereide agentsessie en open gebruikspoort

De oorspronkelijke en bijgewerkte exports, doeltekst, vermogensbron en expliciete
verwachtingenbron zijn gelezen; beide PNG's zijn visueel gecontroleerd:
EUR 2.514,50 betaal en EUR 6.400,00 sparen op 2026-10-04. De oorspronkelijke
export voedt de eerste voorbereiding, niet de latere exportcorrectie.

Voorbereide interpretaties: salaris income, twee eigen overboekingen internal_transfer,
supermarkt expense. De agent berekende plan-6-aggregaties **in geheugen** over de
synthetische kandidaat, zonder die classificaties op te slaan. Die leveren inkomen
EUR 3.000, uitgaven EUR 85,50 en twee transferrecords. Exportdekking blijft onbekend.
Een export van enkele dagen bewijst geen maandpatroon. De aanvullende bron levert
expliciet vierwekelijks salaris, weekband 80–120 voor boodschappen, hypotheek 900
per maand, verzekering 1.200 per jaar en abonnement 75 per kwartaal. De boodschappen-
selectie sluit die drie afzonderlijke lasten expliciet uit. Een onbekende leningbetaling
blijft onbekend, toekomstige/verlopen lasten tellen niet op de referentiedatum.

Het kandidaatmaandbeeld op 2026-10-14: EUR-inkomen 3.250; bekende uitgavenband
1.371,66666666–1.545; bekende ruimte 1.705–1.878,33333334. Dit is een deelsom,
geen volledige bestedingsruimte: leningbetaling en inventaris zijn onbekend.
USD 50 blijft afzonderlijk. De reserve EUR 5.000 wordt niet afgetrokken.
Het bestaande bufferdoel en eigen overboekingen worden niet dubbel afgetrokken.
Schuldstanden, saldi, beschikbaarheid en doelvoortgang blijven afzonderlijke gegevens.

Contract, gezamenlijk request, brongebonden preview, in-geheugenaggregaties en
kandidaatmaandbeeld staan lokaal in test-results/topo2-cashflows/session/.
De echte voorbereiding gebruikte een tijdelijke lege context. Bytes en mtime bleven
identiek; geen token is toegepast en de tijdelijke context is daarna verwijderd.

Voorbereiding: **0,645 s** vanaf contractontdekking tot preview en kandidaatberekening,
inclusief afzonderlijke CLI-processen voor contract/init/preview. Bron- en beeldlezen
en implementatietijd zijn uitgesloten. Dit is één lokale voorbereidingsmeting,
geen gespreksbaseline of tijd tot menselijk bevestigd opgeslagen inzicht.

Financiële verduidelijkingsbundels: **0**, omdat de aanvullende synthetische bron
de gebruikte frequenties en banden expliciet levert. Menselijke bevestigingsvragen:
**0**, ontvangen bevestigingen: **0**, toegepaste tokens: **0**. Handmatig bronherstel:
**0**. De technische journey bewijst geen frictiebudget van een echte mens/agentsessie.
Plan 3's menselijke gebruiksacceptatie en plan 6's nieuwe gebruikspoort blijven open.
Het externe basisbewijs 0–2 blijft geleverd met zijn eigen herstelstappen/beperkingen.

## Verificatie


- Volledige unit-/integratiesuite: **217 geslaagd, 2 bewust overgeslagen**
  (CSV kent geen expliciete null). Dit omvat 24 cashflow-unittests.
- Volledige black-box suite: **73 geslaagd**, inclusief alle bestaande journeys
  van plannen 0–2 en 6 en zes nieuwe cashflowjourneys.
- Architectuurcontrole en mypy slagen. Lint en formattering slagen met uitsluitend
  .scratch/claude-code-security-research/ en .scratch/research/ uitgesloten.
  git diff --check slaagt. De voorbereidingsartefacten voldoen aan de ontdekte schemas.
- De ongewijzigde scripts/verify.sh is uitgevoerd en stopt bij **zes bestaande
  lintfouten** in die twee ongerelateerde mappen: I001/F401/PIE810 in build_report.py
  en I001/PLW1510/B023 in okf-memory-race-test.py. Die bestanden zijn niet gewijzigd.
  De overige poorten zijn afzonderlijk uitgevoerd. Dit is geen geslaagde volledige run.

Ruwe logs staan lokaal in test-results/topo2-cashflows/. Een eerste ontwikkelrun
meldde tevens twee lintfouten in een nieuwe test; die zijn hersteld. De finale
ongewijzigde script-run meldt uitsluitend de zes bestaande fouten. In deze sandbox
is UV_CACHE_DIR=/tmp/topo2-uv-cache gebruikt.

## Performance en stopgrens

Meetomgeving: macOS-27.0.1-arm64-arm-64bit-Mach-O, Python 3.13.11.
1.000 rekeningen en 10.000 respectievelijk 100.000 transacties, meerdere maanden,
soorten, categorieën en EUR/USD. Vijf verwachtingen blijven identiek, inclusief
bandbreedte, jaarlast en onbekende leningbetaling, met optionele EUR-instellingen.
Eén meetronde per schaal; de benchmarks zijn na beide testsuites achtereenvolgens
uitgevoerd zonder overlappende benchmark/tests. Tijd omvat afzonderlijke volledige
CLI-processen: interpreterstart, JSON-inlezen, validatie, berekening en serialisatie
(en opslag bij schrijfoperaties). RSS is van het eigen CLI-proces; bytes zijn van
de volledige JSON-envelope. Dit is een lokale baseline, geen algemene snelheidsclaim.

| Operatie | seconden 10k / 100k | uitvoerbytes 10k / 100k | piek-RSS MiB 10k / 100k |
| --- | ---: | ---: | ---: |
| Maandbeeld | 0.210 / 0.656 | 2,593 / 2,593 | 65.16 / 307.14 |
| Compact context | 0.214 / 0.662 | 608,668 / 608,668 | 67.22 / 307.09 |
| Aggregatie maand + categorie | 0.257 / 1.188 | 156,071 / 157,237 | 66.02 / 307.19 |
| Volledige show | 0.220 / 0.981 | 3,593,551 / 33,656,332 | 73.44 / 402.08 |

Alle **20 benoemde operaties** bij 10.000 blijven onder één seconde;
het maximum is **0.319 s**. Beide benchmarks eindigen succesvol.
Het 100.000-profiel heeft geen nieuwe harde grens; het maximum is
**1.870 s**. De benchmark controleert dat het volledige maandresultaat
exact gelijk blijft na toevoegen en wijzigen van transacties en overeenkomt met
het maandbeeld in compact context. Beide compacte uitvoergroottes blijven gelijk.
Normalisatie gebruikt uitsluitend verwachtingen, geen transacties als analytische
invoer; JSON-inlezen en validatie groeien nog met de contextgrootte. De opslag is
niet herontworpen en er wordt geen constante geheugencomplexiteit geclaimd.

Reproduceren: uv run python scripts/benchmark_topo2.py en dezelfde opdracht met
--transactions 100000. Ruwe resultaten: test-results/topo2-cashflows/benchmark-10000.json
en benchmark-100000.json. Tests: uv run pytest tests en uv run pytest e2e.

Plan 3 is technisch geleverd. Menselijke gebruiksacceptatie blijft open, evenals
plan 6's nieuwe poort; technische tokens en synthetische bronnen vervangen geen
menselijke beoordeling. De externe oefencontext is ongemoeid gebleven.
Geen plan 4–5 of 7–9, automatische transfermatching, advies of release uitgevoerd.

