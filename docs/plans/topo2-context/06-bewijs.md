# Plan 6 — Levering en bewijs

Peildatum: 2026-10-14. Uitsluitend synthetische bronnen. Techniek geleverd;
menselijke gebruikspoort voor de nieuwe transactiesoorten blijft open. Geen plan 3
of release uitgevoerd. Externe oefencontext en bronnen zijn niet gewijzigd.

## Bestaand, uitgebreid en besloten

Bestaande importvoorbereiding, brongebonden gezamenlijke preview, no-op, filters,
Decimal-validatie, dekking, schulden en beschikbaarheid zijn hergebruikt. De
graph meldde dat deze repository niet geïndexeerd is; code is rechtstreeks gelezen.
Ongerelateerde ongetrackte onderzoeksmappen zijn ongemoeid gelaten.

Vóór implementatie heeft de gebruiker de softwarekeuze voor gesigneerd corrigeren
bevestigd, na een concreet voorbeeld. Dit is geen financiële bevestiging:
expense -100 plus expense +20 geeft economische uitgaven 80; income -50 verlaagt
inkomsten. Geen automatische betekenis uit teken, categorie of omschrijving.

Het additieve `topo2.cli/3`-contract levert optioneel kind income/expense/
internal_transfer/unknown, een gedeeld filtercontract en aggregate-transactions.
Ontbrekend/null/unknown blijft ongeclassificeerd. Rekeningontvangsten, uitstromen,
netto beweging, economische inkomsten/uitgaven en classified_net_cashflow staan
apart; transfers en onbekenden hebben eigen aantallen en bewegingen. Een transferhelft
of nulsom bewijst geen paar. Valuta blijven afzonderlijk; bedragen blijven Decimal,
met lokale precisie voor grote sommen en gemengde decimale schalen.

Totalen en maand-/categoriegroepen ontstaan in één transactiescan. Dekking gebruikt
uitsluitend expliciete intervallen en blijft onafhankelijk van classificatie.
Aansluitende/overlappende verklaringen kunnen een begrensde periode dekken; gaten
blijven zichtbaar. Alle geselecteerde rekeningen, ook zonder treffers, blijven
zichtbaar. Zonder beide datumgrenzen wordt geen volledige periode geclaimd.

Niet-null kind vereist context/5. Versies 1–4 blijven leesbaar; preview/no-op
schrijven en migreren niets; versie 5 blijft na wissen/verwijderen behouden.
Oude opslagformaten krijgen geen nieuw kind-veld. Omissie/lege CSV-cellen behouden
kind, categorie en bron; JSON null wist expliciet. change.update blijft een
volledig record vervangen. De engine leest nog het hele JSON-contextbestand;
compacte uitvoer is geen constant geheugen of constante latentie.

## Technisch en black-box bewijs

De nieuwe unit- en black-box tests bewijzen terugbetaling, negatief inkomen,
negatieve economische uitgaven, nul, onbekenden, één transferhelft, grote Decimal-
sommen bij lage omgevingsprecisie, valuta-isolatie en aansluiting detail/groep/totaal.
Gecombineerde filters, alle groeperingsvormen, sortering onafhankelijk van
invoervolgorde, lege selecties en ongeldige query's zijn gecontroleerd.

Dekkingstests bewijzen losse, aansluitende, overlappende en onderbroken intervallen,
één dag, maximale datum, onbekende rekening en rekeningen zonder treffers.
Classificatievolledigheid verandert deze dekkingsuitkomsten niet.

Black-box controles gebruiken afzonderlijke CLI-processen en schema-validatie.
Zij bewijzen leesbare oude versies 1–4 zonder schrijven, migratie pas bij toepassing,
behoud van versie 5, expliciet wissen/vervangen, oude JSON/CSV-exportformaten,
lege CSV-cellen, tokenbinding van kind, volledige-recordvervanging en hash-/mtime-
behoud bij preview/no-op.

De oorspronkelijke invoer-, compacte lees- en vermogensjourneys zijn herhaald.
De vermogensbronjourney draait bovendien met expliciet voorbereide soorten en
bewijst behoud bij gecombineerde exportupdate en standalone herimport, inclusief
categorie, bron, schulden, beschikbaarheid/toelichting en onveranderde saldi,
nettovermogen en doelvoortgang. Gescripte testtokens bewijzen uitsluitend mechaniek.

## Werkelijk voorbereide agentsessie

De agent las de oorspronkelijke en bijgewerkte exports, doeltekst en vermogensbron
opnieuw en controleerde beide PNG's visueel: EUR 2.514,50 betaal en EUR 6.400,00
sparen op 2026-10-04. Eerste invoer gebruikt uitsluitend de oorspronkelijke export.
Voorbereide soorten: SYN001 income, SYN002/003 internal_transfer, SYN004 expense.
Deze zijn zichtbare agentinterpretaties, nog niet menselijk bevestigd.

Een gezamenlijke brongebonden preview, ontdekt contract, request en geconverteerde
export staan lokaal in `test-results/topo2-transactions/session/`. De lokale lege
context is byte- en mtime-identiek gebleven; er is geen token toegepast.
De kandidaat is uitsluitend in geheugen berekend, naast compact lezen van de lege
context. Kandidaat: receipts EUR 3.400, outflows EUR 485,50, netto EUR 2.914,50;
economisch inkomen EUR 3.000 en uitgaven EUR 85,50. Beide geselecteerde transfer-
records staan afzonderlijk als EUR 400 ontvangen/uitgestroomd, netto nul, zonder
engineclaim over een paar. Alle vier soorten zijn voorbereid; rekeningdekking is
onbekend. Bekende nettovermogensdeelsom EUR 118.414,50, USD 900 en buffer 64% blijven
ongewijzigd; leningstand, inventaris, beschikbaarheid en structurele maandruimte
blijven onbekend waar de bronnen geen verklaring geven.

Nieuwe financiële verduidelijkingsbundels: 0. Nieuwe financiële bevestigingen
ontvangen/toegepast: 0. De ontwerpbeslissing en implementatieopdracht vervangen
geen menselijke beoordeling van deze financiële preview. De mechanische herhaal-
journeys zijn technisch bewijs; nieuwe menselijke gebruiksacceptatie blijft open.
De [extern geleverde basisjourney 0–2](gebruik-bewijs-00-02.md) is afzonderlijk
verwerkt met alle geregistreerde herstelstappen en tijdbeperkingen.

## Verificatie en blokkade

- Volledige unit-/integratierun: **192 geslaagd, 2 bewust overgeslagen**
  (CSV kent geen expliciete null). De daarna toegevoegde determinismecontrole
  is afzonderlijk geslaagd; de finale gerichte run telt **15 geslaagde tests**
  (12 aggregatie-unittests en 3 nieuwe black-box journeys).
- Volledige black-box suite: **67 geslaagd**, inclusief de oorspronkelijke
  invoer-, compacte lees- en vermogensjourneys en de variant met transactiesoorten.
- Architectuurcontrole, mypy en git diff --check slagen. Lint en formattering
  slagen met uitsluitend de twee ongerelateerde onderzoeksmappen uitgesloten.
- De ongewijzigde scripts/verify.sh is uitgevoerd en stopt bij **zes bestaande
  lintfouten**: I001/F401/PIE810 in .scratch/claude-code-security-research/build_report.py
  en I001/PLW1510/B023 in .scratch/research/okf-memory-race-test.py.
  Deze bestanden zijn niet gewijzigd. Dit is geen geslaagde volledige script-run;
  de overige poorten zijn afzonderlijk uitgevoerd.

Ruwe controlelogs staan lokaal in test-results/topo2-transactions/. In deze sandbox
is UV_CACHE_DIR=/tmp/topo2-uv-cache gebruikt.

## Definitief schaalprofiel

Meetomgeving: macOS-27.0.1-arm64-arm-64bit-Mach-O, Python 3.13.11.
1.000 rekeningen; 10.000 respectievelijk 100.000 synthetische transacties,
drie maanden, elf categorieën, vier soorten en EUR/USD. Eén meetronde per schaal,
afzonderlijke CLI-processen inclusief interpreterstart, inlezen, validatie,
berekening, serialisatie en eventuele opslag. Piek-RSS is die van het eigen
CLI-proces; uitvoergrootte betreft de volledige JSON-envelope. De definitieve
runs zijn na de tests uitgevoerd, achtereenvolgens zonder overlappende benchmark.
Dit is een lokale baseline, geen algemene snelheidsclaim.

| Operatie | 10.000 tijd | 100.000 tijd | uitvoerbytes 10k / 100k | piek-RSS MiB 10k / 100k |
| --- | ---: | ---: | ---: | ---: |
| Alle valutatalen | 0.238 s | 0.979 s | 105,801 / 105,836 | 65.00 / 307.09 |
| Maand + categorie | 0.251 s | 1.209 s | 156,071 / 157,237 | 65.30 / 307.33 |
| Gecombineerd gefilterd | 0.197 s | 0.706 s | 1,942 / 3,324 | 64.39 / 307.59 |

Alle 19 benoemde operaties bij 10.000 blijven onder één seconde;
het maximum is **0.380 s**. Beide benchmarks eindigen succesvol.
Het 100.000-profiel krijgt geen nieuwe harde grens. De aggregatie-uitvoer bevat
geen transactiedetails; ongefilterde uitvoer bevat wel de 1.000 rekeningdekkingen.
66 maand/categorie/valutagroepen vervangen alle detailpagina's. JSON-inlezen en
validatie blijven groeien met de contextgrootte; geen opslagwijziging is gedaan.

De eerste ontwikkelmeting vond een overschrijding bij maandgroepering (circa
1,10 s bij 10k). Profiling wees naar strftime per record; ISO-datumextractie heeft
die bottleneck verwijderd. Die eerste runs overlapten deels en zijn geen zuivere
vergelijkingsbaseline. Ruwe eerste profielen zijn behouden als benchmark-initial-*.
Een aanvankelijk lege benchmarkfilterselectie is vóór de definitieve runs hersteld.

Reproduceren: uv run python scripts/benchmark_topo2.py en dezelfde opdracht met
--transactions 100000. Ruwe definitieve tijd-, bytes- en geheugenmetingen staan
lokaal in test-results/topo2-transactions/benchmark-10000.json en benchmark-100000.json.

## Stopgrens

Plan 6 is technisch geleverd. De nieuwe menselijke gebruikspoort blijft open;
de externe bevestigingen van plannen 0–2 bevestigen geen nieuwe soorten. Geen
structurele geldstromen, transfermatching, automatische classificatie,
opslagherontwerp of release uitgevoerd. Externe oefengegevens blijven ongemoeid.
