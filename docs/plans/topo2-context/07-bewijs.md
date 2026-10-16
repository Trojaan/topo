# Plan 7 — Levering en bewijs

Peildatum: 2026-10-15. Uitsluitend synthetische bronnen en tijdelijke contexten.
Technische uitvoering is geautoriseerd ondanks de open menselijke gebruikspoorten
van plannen 3, 4 en 6. Die blijven expliciet open. Deze uitvoering bevestigt geen
financiële feiten, reserveringen, classificaties of verwachtingen. De externe
oefencontext is niet gelezen of gewijzigd. Geen vervolgplan of release.

## Onderzoek, besluiten en geleverde grens

AGENTS.md, plannenoverzicht, docs/topo2.md en bewijs van plannen 0–4 en 6 zijn
gelezen, inclusief het afzonderlijke externe basisbewijs 0–2. De kennisgraph meldt
dat de repository niet is geïndexeerd; rechtstreeks codelezen is als fallback
gebruikt. De werkmap bevatte al wijzigingen van eerdere plannen en twee ongerelateerde
onderzoeksmappen. De vooraf aanwezige tracked diffs buiten de voor plan 7 benodigde
bestanden zijn vergeleken met een lokale beginsnapshot en zijn identiek gebleven.

De [ontwerpbesluiten](07-rapportages.md#besluiten-vóór-implementatie-2026-10-15)
zijn vóór implementatie vastgelegd. `report` is additief binnen topo2.cli/3;
HTML-metadata gebruikt topo2.report/1. Er is geen opslagmigratie of nieuwe historie.
Referentiedatum en uitvoerpad zijn verplicht; transactiegrenzen samen en inclusief.
Zonder grenzen: alle opgeslagen records per boekingsmaand, geen verzonnen dekking.
Vermogen gebruikt actuele opgeslagen waarden met eigen peildata; verwachtingen
worden uitsluitend op de referentiedatum geselecteerd.

De CLI leest eenmaal storage.read. De zuivere rapportprojectie gebruikt eenmaal
read_context zonder ouderdomsbeleid, eenmaal monthly_room en eenmaal
aggregate_transactions met maandgroepering. De zuivere renderer rekent geen
financiële uitkomsten uit. Onderliggende modules mogen de rapportlaag niet importeren;
de architectuurpoort bewaakt de grens. Metadata bindt context_id, contextschema,
exacte snapshotbytes via SHA-256, contracten, referentiedatum en nullable selectiegrenzen.

Bestandspublicatie schrijft eerst een privé tijdelijk bestand, flush/fsync en
publiceert het complete inode via een hard link zonder vervanging. Bestaande paden,
ook dangling symlinks en concurrerende schrijvers, worden geweigerd. Geen kopieerfallback
bij een bestandssysteem zonder hard links. Fouten ruimen tijdelijke bestanden op;
contextbytes en mtime blijven behouden. Geen contextlock of financiële bevestiging.

De HTML bevat financiële foto, gerealiseerde maanden, afzonderlijke structurele
verwachtingen en doelen. Oude gekoppelde waarde en reservering blijven afzonderlijk;
minimumreserve is een saldodrempel. Geen tweede aftrek van schulden, reserveringen
of doelinleg en geen gezamenlijke/exclusieve dekkingsclaim. Vrije tekst wordt ge-escapet;
exacte Decimal-waarden worden behouden. Geen scripts, webserver of externe assets.

## Technisch en black-box bewijs

Nieuwe unittests bewijzen exacte aansluiting op bestaande samenvatting, maandruimte
en aggregaties, afzonderlijke valuta, onbekend/nul, gekoppelde roodstand,
gesigneerde terugbetaling, transferhelft, doelreserveringen en aparte gekoppelde waarde.
Maandinleg verandert de maanduitkomst niet. Honderd doelen gebruiken samen één
transactiescan; de renderer veroorzaakt geen aanvullende scan.

Selectietests bewijzen inclusieve grenzen, onbegrensde selectie, onafhankelijke
classificatie/dekking en weigering van halve/omgekeerde periodes. Versies 1–7
leveren leesbare lege rapporten zonder valuta of totalen te verzinnen. Een doel zonder
verdere inventaris staat vóór lege onderdelen. Escapingtests omvatten labels,
contextidentiteit, beschikbaarheidstoelichting, doelnaam/-notitie en verwachtingsbron/
instellingennotitie, plus grote bedragen zonder presentatieafronding.

Een vervangen bronbestand na de enige snapshotlezing verandert de rapportinhoud of
snapshotidentiteit niet. Foutinjecties bij gedeeltelijk schrijven, flush, fsync en
publicatie bewijzen geen beschadigde uitvoer of achtergebleven tijdelijke bestanden.
Een race op het uitvoerpad behoudt de andere schrijver; privérechten zijn op POSIX
gecontroleerd. Bestaand contextpad kan evenmin als rapport worden overschreven.

Black-box tests gebruiken afzonderlijke CLI-processen, ontdekte schema's en een
onafhankelijke HTML-parser. Werkelijke HTML-cellen worden vergeleken met summary,
monthly-room en aggregate-transactions. Lege/oude, minimale, gedeeltelijke en rijkere
contexten houden hun bytes/mtime. Ongeldige context/query, bestaande uitvoer,
ontbrekende directory en ontbrekende verplichte argumenten geven de bestaande
fouten/exitcodes zonder gedeeltelijk rapport.

De bronjourney gebruikt de oorspronkelijke synthetische export, screenshots,
doelbericht, vermogensbron en expliciete verwachtingen. Een bijgewerkte export
verandert gerealiseerde bedragen en behoudt vermogen, doelen en verwachtingen in
een nieuw rapport. Geen inventarisatie of voorkeuren zijn verplicht gemaakt.
Gescripte bevestigingstokens in tests bewijzen uitsluitend mechaniek.

## Werkelijk voorbereide agentsessie en visuele controle

De oorspronkelijke en bijgewerkte exports, beide doelbronnen, vermogensbron en
verwachtingenbron zijn gelezen. Beide PNG's zijn visueel gecontroleerd:
betaal EUR 2.514,50 en sparen EUR 6.400,00 op 2026-10-04. De oorspronkelijke export
voedt de eerste voorbereiding; de bijgewerkte export is vervolginput voor technisch
herimportbewijs. Frequenties en banden komen uit de expliciete verwachtingenbron.

Eén brongebonden gezamenlijke preview is gemaakt in een tijdelijke lege context;
geen token is toegepast. De rijke kandidaat is uitsluitend in geheugen berekend
met de gedeelde functies, zonder financiële gegevens op te slaan. De HTML hiervan
heet uitdrukkelijk rich-unconfirmed-candidate.html; dat is geen rapport van menselijk
bevestigde contextdata. Een afzonderlijk minimaal doelbericht levert naam/bedrag,
met datum, reservering en maandinleg onbekend, zonder aanvullende vragen.
Het lege rapport is via de werkelijke report-CLI gegenereerd.

Kandidaat op 2026-10-14: bekende EUR-nettosom 118.414,50; USD 900 afzonderlijk.
Gerealiseerd EUR-inkomen 3.000 en uitgaven 85,50; twee transferrecords zonder paarclaim.
Verwachtingen: EUR-inkomen 3.250, uitgavenband 1.371,66666666–1.545, voorzichtige
bekende ruimte 1.705 en band tot 1.878,33333334. Onbekende leningbetaling/inventaris
beperken de volledige uitkomst. Doel 10.000, reservering 4.000, resterend 6.000,
voorgenomen inleg 200; gekoppelde waarde 6.400 staat apart. Vrije deelsom 10.000,
geen mogelijke overschrijding, dekking onbekend. Minimumreserve 5.000 apart.

Definitieve voorbereiding vanaf contract/init tot gezamenlijke preview,
leeg CLI-rapport en kandidaatrapporten: **0,914 s**, inclusief afzonderlijke
CLI-processen. Bron-/beeldlezen en implementatie zijn uitgesloten; dit is een lokale
voorbereidingsmeting, geen tijd tot menselijk bevestigd inzicht. Financiële
verduidelijkingsbundels **0**, bevestigingsvragen **0**, ontvangen bevestigingen **0**,
toegepaste tokens **0**, bronherstel **0**. Tijdelijke contextbytes/mtime bleven
identiek en de context is verwijderd. De menselijke gebruikspoorten blijven open.

Visuele QA gebruikt geïsoleerde headless Chrome met uitsluitend file-URL's op
**1440×900 en 390×900**, voor lege, minimale en rijke gedeeltelijke context.
Initiële viewport, hele pagina en rijke secties zijn vastgelegd. Controle omvat
foto, realisatie/dekking, verwachtingen/reserve, doelen/reserveringsvergelijking en
metadata; lange brontoelichting en SHA-256 lopen om. Geen externe verzoeken,
scriptfouten of horizontale overflow; secties/cellen vallen binnen de viewport.

De eerste inspectie vond te veel lege tabellen vóór een minimaal doel en een te
smalle mobiele tabeltitel. Dit is hersteld: onderdelen met bekende gegevens staan
voor lege onderdelen, lege onderdelen blijven kort en mobiele captions gebruiken
de volle breedte. De definitieve minimale doelweergave toont naam en bedrag in de
initiële viewport. Geen afgesneden tekst, overlappende elementen of onleesbare
contrastverschillen gevonden. Rijke mobiele rapporten blijven lange scrollpagina's;
er is geen claim van een compact dashboard.

Browseropstart binnen de sandbox mislukte; de geïnstalleerde Chrome is vervolgens
in een geïsoleerd tijdelijk profiel buiten die procesbeperking gebruikt. Er is geen
browser geïnstalleerd, gebruikersprofiel geopend of webserver gestart. Browsers en
profielen zijn na controle gesloten/opgeruimd. Screenshots en numerieke controles
staan lokaal in test-results/topo2-reports/visual/; voorbereiding in session/.

## Verificatie en performance

- Definitieve volledige unit-/integratiesuite: **272 geslaagd, 2 bewust overgeslagen**
  (bestaande CSV-null-skips), inclusief **24 nieuwe rapporttests**.
- Definitieve volledige black-box suite: **96 geslaagd**, inclusief **15 nieuwe
  rapportjourneys** en relevante journeys van plannen 0–4 en 6.
- Architectuurcontrole, mypy en git diff --check slagen. Lint en formattering
  slagen met uitsluitend .scratch/claude-code-security-research/ en .scratch/research/
  uitgesloten. Deze ongerelateerde bestanden zijn ongemoeid gebleven.
- De ongewijzigde scripts/verify.sh is opnieuw uitgevoerd en stopt bij **zes
  bestaande lintfouten**: I001/F401/PIE810 in build_report.py en I001/PLW1510/B023
  in okf-memory-race-test.py. Dit is **geen geslaagde volledige verify-run**;
  de overige poorten zijn afzonderlijk uitgevoerd.

De eerste gerichte black-box ontwikkelrun vond één fout in een nieuwe assertion:
init had al een lockbestand gemaakt. De test vergelijkt nu de aanwezige entries
vóór/na rapportgeneratie. Nieuwe type-/lintmeldingen zijn eveneens opgelost vóór
de definitieve runs. Geen bestaande assertions zijn verzwakt. De laatste volledige
suites zijn na de presentatieverbeteringen herhaald. Ruwe logs staan lokaal in
unit-final.txt, e2e-final.txt en de afzonderlijke *-final.txt-bestanden.
UV_CACHE_DIR=/tmp/topo2-uv-cache is gebruikt voor de sandbox.

### Definitief schaalprofiel

Meetomgeving: macOS-27.0.1-arm64-arm-64bit-Mach-O, Python 3.13.11.
1.000 rekeningen, 100 doelen, vijf verwachtingen en meerdere valuta/maanden.
10.000 en 100.000 transacties zijn achtereenvolgens gemeten na de tests en visuele
controle, zonder gelijktijdige tests of benchmarks. Eén definitieve meetronde per
schaal: lokale diagnostiek, geen algemene snelheidsclaim.

Volledige rapport-CLI-processen omvatten interpreterstart, inlezen/validatie,
berekening, rendering, UTF-8-uitvoer, flush/fsync en publicatie. Piek-RSS betreft
het eigen CLI-proces; HTML-bytes zijn werkelijk gecontroleerd op het bestand.

| Rapportselectie | seconden 10k / 100k | HTML-bytes 10k / 100k | piek-RSS MiB 10k / 100k |
| --- | ---: | ---: | ---: |
| Alle opgeslagen transacties | 0.274 / 1.146 | 476,235 / 476,363 | 70.05 / 308.09 |
| Expliciete periode | 0.305 / 1.198 | 476,110 / 476,238 | 70.03 / 308.14 |

JSON-stdout is respectievelijk 595 bytes zonder periode en 615 met periode bij
beide schalen (in deze tijdelijke paden). Het bevat metadata en uitvoerlocatie,
geen financiële detailrecords. De HTML bevat wel rekening-/doelgegevens en
compacte maandtotalen; geen transactiedetails. Dezelfde fixture houdt het aantal
rekening-/doelrecords en maandgroepen gelijk, waardoor de HTML-grootte vrijwel
gelijk blijft. Meer maanden of meer vermogens-/doelrecords vergroten het rapport.

Afzonderlijke diagnostische processen meten de fasen vanaf eenzelfde synthetische
snapshot; berekening omvat de zuivere rapportprojectie en gedeelde enginefuncties.
Rendering omvat HTML plus UTF-8-encoding en doet geen financiële berekeningen.
Deze tijden hoeven niet exact op te tellen tot de afzonderlijk gemeten volledige
CLI-duur: startup/publicatie ontbreken en het zijn afzonderlijke processen.

| Selectie | lezen/validatie s 10k / 100k | berekening s 10k / 100k | rendering s 10k / 100k |
| --- | ---: | ---: | ---: |
| all | 0.0501 / 0.5041 | 0.0563 / 0.5075 | 0.0087 / 0.0082 |
| bounded | 0.0532 / 0.4922 | 0.0588 / 0.5138 | 0.0085 / 0.0081 |

De diagnostische RSS is cumulatief voor dat proces, geen afzonderlijke geheugenpiek
per fase. HTML-bytes én SHA-256 sluiten voor iedere fase-run exact aan op het
bijbehorende via CLI gepubliceerde rapport.

Alle **25 benoemde operaties** bij 10.000 transacties blijven onder één seconde;
maximum **0.313 s**. De bestaande performancepoort is behouden en omvat nu
beide rapportselecties. Beide benchmarks eindigen met exitcode 0. Het 100.000-profiel
heeft geen nieuwe harde tijdgrens; maximum over de benoemde operaties **2.143 s**.
Maximale piek-RSS over alle gemeten CLI-processen: **99.23 / 569.22 MiB**.

De 100.000-rapporten duren ruim één seconde en gebruiken circa 308 MiB piek-RSS.
Volledig JSON-inlezen/valideren en de ene aggregatiescan groeien met transacties;
renderkosten blijven in deze fixture klein. Compacte HTML bewijst geen constante
latentie of constant geheugen. Er is geen opslagherontwerp uitgevoerd.

Reproduceren: `uv run python scripts/benchmark_topo2.py` en dezelfde opdracht met
`--transactions 100000`. Ruwe volledige proces-, fase-, byte- en geheugenmetingen
staan lokaal in test-results/topo2-reports/benchmark-10000.json en benchmark-100000.json.

## Status en stopgrens

Plan 7 is technisch geleverd. De menselijke gebruikspoorten van plannen 3, 4 en 6
blijven expliciet open; testtokens, bronmateriaal en technische autorisatie bevestigen
geen financiële feiten of bedoelingen. De bronvoorbereiding is geen gesimuleerde
menselijke gebruiksacceptatie. De externe oefencontext bleef ongemoeid.
Geen benodigde doelinleg, haalmaand, scenario's, gezamenlijke haalbaarheid, PDF,
hosting, opslagherontwerp, vervolgplan of release.
