# Topo 2-performance

Deze metingen betreffen uitsluitend `src/topo_v2/`, op 17 oktober 2026 met
Python 3.13.11, PyInstaller 6.22.2 en macOS arm64. Alle contexten, transacties,
bronnen en rapporten zijn tijdelijk en synthetisch gegenereerd. Persoonlijke
financiële bestanden zijn niet geopend, gezocht of gebruikt.

## Bottleneck en keuze

De oude onefile-executable kost circa 2,1–2,3 seconden per start. De oorspronkelijke
Python-route kost ongeveer 0,16 seconden voor help/versie. Bij 10.000 transacties,
1.000 rekeningen en 100 doelen kost lezen plus volledige validatie ongeveer
0,054 seconden; de gewone Python-CLI kost circa 0,22 seconden voor een leesopdracht
en 0,32 seconden voor een bevestigde wijziging. Dit zijn lokale indicaties, geen
voorspelde bovengrenzen voor andere machines.

De nieuwe distributie is een programmamap: geen uitpakken per opdracht, geen daemon,
geen Python-installatie voor de gebruiker. Help en versie laden geen Pydantic of
financiële modules. `topo2` blijft dezelfde opdracht. De installer beheert de
executable en de bijbehorende `_topo2_runtime_*`-directory. De oorspronkelijke
`topo`-distributie blijft één executable. Oudere Topo 2-releases blijven installeerbaar.

Opslag blijft één leesbaar, volledig gevalideerd JSON-bestand met atomaire vervanging.
Een sectiefilter beperkt de uitvoer, niet validatie of bestand-I/O. Geen opslagmigratie,
transactielog, afgeleide cache, gewijzigde financiële berekening of apply-bypass.

## Opstartmetingen

De oorspronkelijke onefile-meting bevat drie afzonderlijke processen per opdracht;
de eerste nieuwe onedir-meting vijf. Geen samples zijn verwijderd.

| Opdracht | Onefile, mediaan | Onedir, mediaan |
| --- | ---: | ---: |
| `--help` | 2,2933 s | 0,1473 s |
| `--version` | 2,1233 s | 0,1225 s |

De daling is ongeveer 94%, ruim boven het doel van 70%. Eerste-startkosten blijven
bestaan: help had een eerste sample van 5,9699 s bij onefile en 4,6235 s bij onedir.
De meting is geen bewijs dat een koude eerste start onder één seconde blijft.
De nieuwe bronroute mat circa 0,08 s voor help/versie.

Ruwe opstartsamples in seconden:

- Onefile help: 5,9699; 2,2933; 2,2099. Versie: 2,1437; 2,1233; 2,1034.
- Onedir help: 4,6235; 0,1473; 0,1553; 0,1377; 0,1264.
  Versie: 0,1193; 0,1341; 0,1200; 0,1318; 0,1225.

## Volledig profiel na de controles

Een afsluitende run zonder gelijktijdige tests gebruikte dezelfde aantallen
(10.000 transacties, 1.000 rekeningen en 100 doelen), met vijf afzonderlijke
processen per leesopdracht. Alle operationele metingen en medianen bleven onder
één seconde. De mediane help-/versiestart was 0,128 / 0,121 seconden.

| Opdracht | Mediaan | Spreiding |
| --- | ---: | ---: |
| `show` | 0.288 s | 0.282–0.303 s |
| `show --sections cashflows,goals` | 0.267 s | 0.257–0.273 s |
| `context` | 0.350 s | 0.278–0.405 s |
| `summary` | 0.355 s | 0.285–0.410 s |
| `monthly-room` | 0.305 s | 0.300–0.324 s |

De volledige `show`-uitvoer is 3.629.670 bytes; `show --sections cashflows,goals`
is 38.057 bytes (circa 99% minder). Dit is selectie van inhoud, geen compressie.
De ene rekeningpatch kostte 0,266 s voor preview, 0,330 s voor toepassen en
0,318 s voor ongewijzigd herhalen; dit zijn afzonderlijke metingen, geen medianen.

Ruwe afsluitende samples in seconden:

- `--help`: 0.2689; 0.1277; 0.1236; 0.1278; 0.1409.
- `--version`: 0.1214; 0.1269; 0.1210; 0.1200; 0.1321.
- `show`: 0.3032; 0.2823; 0.2881; 0.2873; 0.2881.
- `show --sections cashflows,goals`: 0.2698; 0.2662; 0.2570; 0.2732; 0.2670.
- `context`: 0.2777; 0.3177; 0.3503; 0.3559; 0.4049.
- `summary`: 0.3600; 0.4097; 0.3555; 0.2851; 0.2960.
- `monthly-room`: 0.2996; 0.3054; 0.3243; 0.3021; 0.3124.

## Reproduceren

Vanuit een ontwikkelomgeving met de vastgelegde dependencies:

```sh
uv run python scripts/benchmark_topo2.py --transactions 10000 --runs 3
uv run python scripts/benchmark_topo2.py --transactions 100000 --runs 3
uv run pyinstaller --clean topo2.spec
uv run python scripts/benchmark_topo2.py --executable dist/topo2/topo2 --runs 5
uv run python scripts/benchmark_topo2.py --executable dist/topo2/topo2 --startup-only --runs 5
```

Op Windows heet de executable `dist/topo2/topo2.exe`; de volledige profileroute
gebruikt Unix `resource` voor geheugenmetingen. `--startup-only` gebruikt dat niet.
Een opgegeven executable wordt uitsluitend met de gegenereerde tijdelijke fixture
gebruikt; er is geen optie om een persoonlijke context als fixture op te geven.

Voer looptijdmetingen zonder andere zware controles uit. De JSON-uitvoer bewaart
alle opstart- en leessamples, medianen, uitvoerbytes, afzonderlijke preview/apply/no-op-
metingen, één-recordpatches en gerichte `show` naast het volledige overzicht.
Geheugen wordt alleen voor Python-subprocessen gemeten; bij een opgegeven executable
is `peak_rss_bytes` null. De 10.000-transactieroute controleert een grens van één
seconde voor de operationele metingen en de mediane opstart-/leesmetingen; 100.000
transacties zijn een schaalprofiel zonder tijdgrens. `--startup-only` is diagnostisch
en legt geen grens op, zodat ook oude executables vergelijkbaar blijven.

## Gebruik en verificatie

Begin met `context`. Gebruik `show --sections accounts,cashflows,goals` voor bepaalde
records; transactiedetails horen in gefilterde/gepagineerde `transactions`, totalen
in `aggregate-transactions`. Patches behouden weggelaten velden; `update` blijft een
volledig record vervangen. Beide behouden dezelfde gezamenlijke preview en expliciete
menselijke goedkeuring. Een no-op verandert geen bytes, mtime of opslagversie.

De gerichte tests dekken alle acht patchsecties, veldconstraints, null versus
weglaten, vervanging van lijsten/objectvelden, referenties, schema-overgangen,
verouderde tokens en ongewijzigde heraanlevering. CLI-tests bewijzen dat gefilterd
lezen corrupte transacties blijft weigeren en dat help/versie geen zware imports doen.
Installatietests dekken oude archieven, programmamappen, herinstallatie, upgrades en
behoud van bestaande executables bij mislukte voorbereiding. Een echt macOS-archief
is uitgepakt en geïnstalleerd in een tijdelijke map en doorloopt de volledige
synthetische standalone-smoke. Native Windows- en Linux-uitvoering blijft onderdeel
van de bestaande release-/installermatrix; die is lokaal niet uitgevoerd.

De algemene `scripts/verify.sh` stopt op zes reeds bestaande lintmeldingen in
ongerelateerde, ongetrackte `.scratch`-scripts. Deze zijn niet aangepast. Architectuur,
lint en formatting voor `src`, `tests`, `e2e`, `scripts`, mypy en de testlagen worden
afzonderlijk gecontroleerd. De volledige unit-/integratiesuite slaagde met
285 tests en twee skips; de laatste gerichte patchsuite met 22 tests en de
volledige CLI-suite met 101 tests slagen ook.

De [oudere performancepagina](performance.md) en `scripts/benchmark_reads.py`
betreffen de historische engine met generaties, niet Topo 2.
