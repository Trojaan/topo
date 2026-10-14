# Plan 0 — Levering en bewijs

Peildatum: 2026-10-14. Uitsluitend synthetische bronnen. Geen functionaliteit uit
vervolgplannen geleverd.

## Geleverde contracten

- `topo2.cli/3`, met leesbare weigering van expliciete versie-2-change-requests.
  Opslag blijft `topo2.context/2`; bestaande versie-1- en versie-2-contexten blijven
  leesbaar. Preview en identieke effectieve invoer herschrijven niets.
- Import behoudt ontbrekende categorieën en bronlabels. Lege CSV-cellen behouden
  ook; JSON `null` wist, een label vervangt. Bij nieuwe transacties is ontbrekend
  onbekend (`null`). `change.update` blijft volledige records vervangen.
- `change --source PATH` bindt opgeloste paden en exacte bronbytes, naast request,
  contextpad en contextbytes. Bronbestanden worden niet opgeslagen. Identieke
  updates geven `unchanged`, geen token en geen schrijfactie; lege requests blijven
  ongeldig. Ook vóór een no-op wordt een aangeleverde token gecontroleerd.

## Reproduceerbaar technisch bewijs

De vaste bronnen staan in `e2e/fixtures/topo2-input/`: een puntkomma-export met
Nederlandse bedragen en eigen overboekingen, twee visueel leesbare PNG-saldoschermen,
een doelbericht en een bijgewerkte export. De PNG's zijn getekende fictieve
bankschermen. De bijgewerkte export verandert rijvolgorde en omschrijving, corrigeert
SYN004 en voegt SYN005 toe. IDs komen uit vaste bankreferenties; geen hash van
veranderlijke omschrijvingen of rijnummers.

`e2e/topo2_input_fixture.py` zet uitsluitend deze bronlayout om. De helper is geen
engineadapter en leest geen screenshots automatisch. Bij het voorbereiden van
volledige updates kopieert hij expliciet bestaande verrijkingen vóór toepassing
van de exportvelden. De engine gebruikt één gedeelde importvoorbereiding voor
omissies, duplicaten en effectieve wijzigingen.

`e2e/test_topo_v2_input_journey.py` bewijst vanaf die bronnen:

- Eén gezamenlijke rekening/doel/transactie-preview met zeven wijzigingen;
  schema-overeenkomst, effectvrije preview en weigering na gewijzigde bronbytes.
- Een identieke heraanlevering zonder schrijven of token; bijgewerkte export met
  twee effectieve wijzigingen en behoud van categorie en bronlabel.
- Dezelfde wijzigingen via gecombineerde `change` en standalone import; daarnaast
  bevestigde standalone correctie met behoud, expliciet wissen en vervangen.
- Atomische weigering bij ongeldige rekeningverwijzing, onveranderde saldi en
  doelvoortgang, en versie-2-requestweigering.

Unit-tests bewijzen daarnaast JSON/CSV-omissie, lege cellen, expliciet null,
vervanging, nieuwe records, volledige-recordvervanging bij change.update, lege
requests, verouderde tokens vóór no-op en exacte bronbinding aan bytes, pad en
bronlijst. Bestaande tests behouden de garantie voor gewijzigde importbytes,
request/contextwijzigingen, gelijktijdige schrijvers en falende opslag.

Gescripte bevestigingen in deze tests zijn mechanisch bewijs, geen menselijke
bevestiging van een agentsessie.

## Werkelijk uitgevoerde agentsessie

De agent heeft de twee PNG's visueel gelezen, de oorspronkelijke export en het
doelbericht gelezen, het actuele CLI-contract ontdekt en de conversie en gezamenlijke
preview gemaakt. Werkbestanden en de ongewijzigde oefencontext staan buiten Git in
`test-results/topo2-input/session/`; de CLI-preview staat in `preview.json`.

Bronwaarden: betaalrekening EUR 2.514,50 en spaarrekening EUR 6.400,00, beide op
2026-10-04. Het doelbericht noemt EUR 10.000 op 2027-12-31, gekoppeld aan de
spaarrekening, en bevestigt de eigen overboekingen. Voorbereide interpretaties:
salaris → Inkomen, overboekingen → Eigen overboeking, supermarkt → Boodschappen;
bronlabel Synthetische bankexport. De agent heeft deze interpretaties in de
gezamenlijke bevestigingsvraag zichtbaar gemaakt.

Eerste bruikbare bespreking: beschikbaar vermogen EUR 8.914,50; de gekoppelde
spaarrekening dekt 64% van het bufferdoel. Eigen overboekingen zijn geen uitgaven.
Losse schulden en structurele maandruimte blijven onbekend; deze zijn niet eerst
uitgevraagd en worden niet als nul voorgesteld. Na herimport blijven screenshots
leidend voor de opgeslagen saldi; transacties wijzigen ze niet.

Gemeten baseline vanaf start contractontdekking/voorbereiding van deze oefensessie
tot de brongebonden preview: **13,512 seconden**. Fixtureaanmaak en implementatietijd
zijn uitgesloten. Dit is één voorbereide sessie met leesbare synthetische bronnen,
geen algemene snelheidsclaim. De agent las de beelden binnen dit meetvenster
opnieuw. De tijd tot bevestigd opgeslagen inzicht is nog niet vastgesteld.

Financiële verduidelijkingsbundels: **0**. Er is één gezamenlijke menselijke
bevestigingsvraag gesteld voor de concreet beschreven eerste invoer en de twee
latere exportwijzigingen samen. Menselijke bevestigingen ontvangen: **0**.
De agent heeft de oefencontext daarom niet gewijzigd. Identieke heraanlevering en
bijgewerkte export zijn technisch bewezen, maar nog niet uitgevoerd in deze
menselijk bevestigde agentsessie. Handmatig herstel aan brongegevens: **0**.

De eerdere ontwerpkeuze voor lege CSV-cellen was één contractvraag tijdens de
planning; die is geen financiële inventarisatievraag aan de fictieve gebruiker.

## Controles en schaalprofiel

- Architectuurcontrole, mypy, `git diff --check`, lint en formattering slagen.
- Volledige unit-/integratiesuite: **162 geslaagd, 2 bewust overgeslagen**
  (CSV kent geen expliciete null; wissen wordt via JSON getest).
- Volledige black-box suite: **56 geslaagd**. Gerichte eindcontrole: **66 geslaagd,
  2 bewust overgeslagen**.
- `scripts/verify.sh` is uitgevoerd, maar stopt bij zes bestaande lintfouten in
  twee ongetrackte onderzoeksmappen: `.scratch/claude-code-security-research/` en
  `.scratch/research/`. Die zijn niet gewijzigd. De lint- en formatteringspoorten
  zijn afzonderlijk herhaald met uitsluitend die twee mappen uitgesloten;
  alle overige scriptpoorten zijn afzonderlijk volledig uitgevoerd. Dit is geen
  geslaagde ongewijzigde script-run.

Meetomgeving: macOS-27.0.1-arm64-arm-64bit-Mach-O, Python 3.13.11,
1.000 rekeningen, één afzonderlijk CLI-proces per meting, één meetronde per schaal.
Gerichte tests liepen tijdens een deel van de metingen; dit is een lokale baseline,
geen geïsoleerde performancevergelijking. De CLI-wrapper leest alleen de eigen
piek-RSS na afloop; inlezen, valideren, tokencontrole, serialiseren en schrijven
zitten in de gemeten procesduur.

| Operatie | 10.000 transacties | 100.000 transacties |
| --- | ---: | ---: |
| Volledige importpreview | 0.216 s | 1.064 s |
| Volledige import bevestigen | 0.348 s | 1.794 s |
| Gericht zoeken | 0.199 s | 0.644 s |
| Herimportpreview (1.000 wijzigingen) | 0.228 s | 0.844 s |
| Herimport bevestigen (1.000 wijzigingen) | 0.266 s | 1.520 s |
| Brongebonden change-preview (1.000 wijzigingen) | 0.209 s | 0.780 s |
| Brongebonden change bevestigen (1.000 wijzigingen) | 0.275 s | 1.437 s |
| Brongebonden identieke change | 0.214 s | 0.767 s |

Alle 15 benoemde operaties bij 10.000 transacties blijven onder één seconde;
het maximum is **0.348 s**. Het 100.000-profiel heeft geen
nieuwe harde grens. Maximale gemeten piek-RSS over alle CLI-processen: respectievelijk
**89.48 MiB** en
**500.72 MiB**.
De grootste JSON-uitvoer (`show`) is respectievelijk
**3,118,835 bytes** en
**29,568,935 bytes**.
De opslag is ongewijzigd; deze metingen onderbouwen geen nieuwe opslagarchitectuur.

Reproduceren: `uv run python scripts/benchmark_topo2.py` en dezelfde opdracht met
`--transactions 100000`. Ruwe uitvoer, uitvoergrootte en piek-RSS per afzonderlijke
operatie staan lokaal in `test-results/topo2-input/benchmark-10000.json` en
`benchmark-100000.json`; verificatie-uitvoer staat naast deze bestanden.

## Beperkingen

De gebruikspoort is nog niet volledig afgerond zolang de menselijke bevestiging
en het vervolg van de agentsessie ontbreken. De synthetische bronlayout bevat
stabiele bankreferenties en ondubbelzinnige rekeningidentifiers. Exports zonder
zulke referenties of onleesbare/tegenstrijdige beelden vragen gerichte verduidelijking;
het frictiebudget geeft nooit toestemming om te gokken. Er is geen OCR,
bankherkenning, automatische transferherkenning, bronarchief of enginecategorisatie.
