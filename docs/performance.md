# Performance: 7.500 bronrecords en 21 generaties

Gemeten op 4 oktober 2026, met Python 3.13.11 op macOS arm64. Alle pakketten
zijn synthetisch en tijdelijk; er is geen persoonlijk financieel pakket gebruikt.
De nulmeting is een expliciete referentieroute met volledige recordvalidatie,
volledige collectieserialisatie, adapter-diffs en de eerdere metadata-traversal.
Deze route behoudt de nieuwe berekening van de wijzigingsset. Het is dus geen
ongewijzigde executable van vóór deze verbetering. De eerdere indicatieve
8,4 s / 13,3 s uit de opdracht zijn geen opnieuw gemeten nulmeting.

## Reproduceren

```sh
uv run python scripts/benchmark_mutations.py --submit-round --output /tmp/topo-performance.json
```

De fixture importeert 7.500 records over twintig mutaties, naast de initiële
generatie. Beide meetroutes starten met dezelfde 21 generaties en dezelfde bytes.
Er zijn tien opeenvolgende imports van één nieuw bronrecord, met telkens een
preview en menselijke autorisatie. Hun generatie-id wordt aan de volgende aanvraag
doorgegeven. De aparte voorstelronde vergelijkt tien gewone indieningen met één
geautoriseerde batch van dezelfde tien voorstellen.

Met `--no-profile` worden alleen gewone looptijden gemeten. `--package` hergebruikt
een reeds gemaakte synthetische fixture; de opgegeven record- en generatieaantallen
moeten daarmee overeenkomen. Draai zonder andere zware controles. Koude caches en
belasting van de desktop geven uitschieters; de ruwe reeksen blijven bewaard.

## Looptijden

| Meting | Volledige referentie | Geoptimaliseerd |
| --- | ---: | ---: |
| Eén bronmutatie, mediaan van tien | 9,84 s | 6,36 s |
| Spreiding bronmutaties | 8,59–32,69 s | 5,92–13,83 s |
| Tien bronmutaties, zonder previews | 128,50 s | 71,52 s |
| Werkronde inclusief tien previews | 167,18 s | 98,08 s |
| `context verify`, één run | 24,62 s | 7,15 s |
| `context status` | 4,22 s | 2,09 s |
| `workflow next` | 2,25 s | 1,42 s |
| `analyze run` | 1,37 s | 1,25 s |

De onveranderlijke canonieke opslag blijft 58,14 MiB. Met het materialiseerde
`derived/current`-beeld en verklaringen is het pakket tijdens de leesmeting
85,46 MiB. De volledige fixture vóór delta-migratie is circa 295,4 MiB. Grootte
betekent bestandbytes, niet door het bestandssysteem toegewezen blokken.

Tien afzonderlijke voorstelindieningen kosten 81,82 s, waarvan de eerste een
uitschieter van 30,45 s is. De batch kost 5,15 s voor publicatie en 24,05 s voor
de preview: samen 29,21 s. De bulkroute voegt één generatie toe; individuele
indieningen voegen tien generaties toe. Ook hier blijven alle uitschieters zichtbaar
in [de meetgegevens](performance-results.json).

De richtwaarden zijn niet allemaal gehaald: de mediane bronmutatie ligt ongeveer
2,16 s boven 4,2 s; verificatie ligt 0,45 s boven 6,7 s. De eerste status-read ligt
0,09 s boven de leesgrens van 2 s. De overige twee reads blijven eronder. Deze
metingen zijn geen garantie voor een bovengrens op deze desktop.

## Integriteit en resterende kosten

De verificatie hergebruikt alleen binnen dezelfde aanroep exact gelijke getypeerde
records en bronprojecties met exact dezelfde afhankelijkheden. JSON-getaltypen
worden onderscheiden: `1`, `1.0` en `true` zijn geen uitwisselbare cachewaarden.
Alle canonieke bestanden, checksums, journal, bewijsinventarissen, verwijzingen en
opvolgingsinvarianten blijven gecontroleerd voor iedere bewaarde generatie.

Ongewijzigde collectiebytes en recordfragmenten worden bij gewone mutaties
hergebruikt. EngineCore geeft de recordwijzigingen expliciet door. De complete
opvolgertoestand wordt semantisch gevalideerd; de adapter controleert vóór publicatie
of de fysieke delta exact die toestand reconstrueert. Restore, schemamigratie en
privacy-scrub behouden de volledige serialisatie- en diffroute.

De historie moet nog steeds worden gereconstrueerd, alle logische checksums moeten
worden berekend, en globale invarianten worden voor iedere generatie opnieuw
nagelopen. Een mutatie controleert bovendien de canonieke bytes voor de
historieverklaring, leest het huidige volledige beeld en valideert het volledige
nieuwe beeld. De metadata-traversal gebruikt nu directory-entry-informatie om
herhaalde stat-aanroepen te vermijden; iedere bestandsbyte wordt opnieuw gehasht.
Statistieken zoals grootte of mtime vervangen geen integriteitscontrole.

SQLite is niet ingevoerd. Een andere opslagbackend is een afzonderlijk ontwerpbesluit
met migratie-, recovery- en auditconsequenties. Deze meting bewijst niet dat SQLite
de resterende volledige semantische controles wegneemt. Verdere verbetering vraagt
een afzonderlijke onderbouwde wijziging van reconstructie, afhankelijkheidscontrole
of het aantal veilige opslagpassages.

## Verificatie

Alle 143 unit- en black-box CLI-tests slagen. De vergelijking met de volledige
validator omvat geldige bronketens en corrupte oude generaties met bijgewerkte
checksums: afwijkende bronwaarden, onopgeloste verwijzingen, dubbele ids,
schemaversies en gewijzigd raw evidence. Aanvullende tests bewijzen exacte
collectieserialisatie, JSON-typeverschillen, afwijzing van foutieve wijzigingssets,
digestgelijkwaardigheid en autorisatie die aan alle batchitems is gebonden.

`scripts/verify.sh` is uitgevoerd en stopt op zes niet-gerelateerde lintmeldingen in
`.scratch/claude-code-security-research/build_report.py` en
`.scratch/research/okf-memory-race-test.py`. Het tweede script is tijdens deze
werkronde verschenen. Beide bestanden zijn niet aangepast. Architectuurcontrole, lint en formatting van
`src`, `tests`, `e2e`, `scripts`, mypy en alle tests zijn afzonderlijk uitgevoerd.

## Geheugen en uitsplitsing

De laatste afzonderlijke profilerun meet 920,5 MiB piek-RSS voor verificatie en
623,2 MiB voor een bronmutatie. Dit is inclusief de profiler; het geheugen is dus
niet gelijk aan de kale applicatie-RSS. De eerste volledige referentieprofielrun
mat 871,2 MiB en 594,9 MiB. Er is geen aangetoonde geheugenwinst: het bewaren van
getypeerde records, JSON-waarden en bronprojecties heeft zelf een prijs.

| Exclusieve profilerbijdrage | Verify | Bronmutatie |
| --- | ---: | ---: |
| Openen/lezen/sluiten van bestanden | 1,38 s | 3,40 s |
| Parsen en getypeerde JSON-validatie | 1,50 s | 1,02 s |
| Semantische controles en vergelijking | 3,28 s | 0,53 s |
| JSON-serialisatie | 0,37 s | 0,12 s |
| Opslagcoördinatie/synchronisatie | 0,19 s | 0,14 s |
| Overige functies en native aanroepen | 4,15 s | 1,43 s |

Dit zijn gedeeltelijke fase-indicaties op basis van exclusieve functietijd, geen
exacte stopwatchgrenzen tussen enginefasen. Native bestandsopeningen zijn aan lezen
toegerekend; de profiler volgt de parallelle evidence-readerthreads niet apart.
Imports, checksums en niet-toegerekende native kosten blijven deels in overige
functies. De profiler voegt overhead toe: tel deze kolommen niet op als vervanging
van de gewone looptijden. [De profielgegevens](performance-profile.json) bewaren
ook de twintig grootste individuele bijdragen. Bestanden opnieuw openen voor de
canonieke digest is de grootste losse bijdrage aan de mutatie. Bij verificatie
blijven JSON-parsing, exacte typevergelijking en globale semantische controles
zichtbare kosten. Die controles zijn behouden.
