# Plan 1 — Levering en bewijs

Peildatum: 2026-10-14. Technisch geleverd; menselijke gebruikspoort staat nog open.
Uitsluitend synthetische bronnen. Geen functionaliteit uit plannen 2–9 geleverd.
De open bevestiging van [plan 0](00-bewijs.md) is niet als afgerond behandeld.

## Onderzoek en keuzes

Bestaand: `show` levert alle records, `summary` berekent Decimal-totalen en
gekoppelde doelvoortgang met ontbrekende waarden, `transactions` zoekt gericht.
De bestaande change-flow biedt al één atomische preview/bevestiging, bronbinding
en no-ops. Plan 0 bewaakt behoud van verrijkingen bij herimport. Deze onderdelen
zijn hergebruikt; er is geen nieuwe berekening, opslagarchitectuur of vragenlijst.

De kennisgraph meldde dat deze repository niet geïndexeerd is. Codeverkenning
viel daarom terug op rechtstreeks lezen. De reeds aanwezige plan-0-wijzigingen en
onderzoeksmappen zijn niet teruggedraaid of opgeschoond.

Nieuw: `topo2 context`, met rekeningen, bezittingen, doelen, bestaande samenvatting,
waardepeildata, optioneel ouderdomsbeleid, inventarisstatus en transactiedekking.
Geen transactielijst. De route leest en valideert intern nog het volledige
JSON-bestand; compact serialiseren is geen constant geheugen of constante latentie.

Klein domeinenregister: `accounts`, `assets`, `debts`, `goals`, `cashflows`.
Verklaringen zijn optionele records in `inventories` met domein-ID, status
`unknown`/`partial`/`complete` en `checked_on`. Afwezig is onbekend; een expliciet
lege complete inventaris blijft onderscheiden. `transaction_coverage` bewaart
expliciet bevestigde inclusieve intervallen per bestaande rekening, ook één dag.
Overlappingen blijven letterlijk; gaten blijven onbekend. Transactiedata leiden
geen dekking af. Beide recordsoorten ondersteunen add/update/delete in dezelfde
preview als bronrecords; import behoudt ze.

`limitations` richt onzekerheid op de betreffende uitkomst. Onbekende schulden
beperken nettovermogen, geen saldi of transactieanalyse. Ontbrekende/verouderde
waarden beperken alleen gekoppelde doelen. `summary.complete` blijft uitsluitend
waardebeschikbaarheid binnen bekende records/koppelingen. Er is geen algemeen
volledigheidspercentage. Nettovermogen en maandruimte blijven expliciet nog niet
ondersteund, ook met complete verklaringen. Een verklaring is geen berekening.

CLI-contract `topo2.cli/3` is additief uitgebreid; bestaande requests behouden hun
betekenis. Nieuwe verklaringen vereisen opslag `topo2.context/3`. Oude versies 1/2
blijven zonder herschrijven leesbaar. Gewone mutaties zonder verklaringen blijven
versie 2 schrijven; eenmaal versie 3 blijft versie 3. Lezen, preview en no-op
schrijven geen migratie. Oude programma's kunnen versie 3 niet lezen.

## Technisch bewijs

`e2e/test_topo_v2_context_journey.py` bewijst via afzonderlijke CLI-processen:

- Oude, gedeeltelijke context zonder herschrijven, schema-overeenkomst, ontbrekend
  saldo als ontbrekend en onbekende inventaris zonder verplichte invoer.
- Eén gezamenlijke preview en gescripte bevestiging voor bronrecords, optionele
  inventarisverklaringen en dekking; opslagversie 3 ontstaat pas bij toepassen.
- Bekende EUR 8.914,50 en 64% doelvoortgang blijven leesbaar. Bevestigd lege
  schuldeninventaris verschilt van afwezig; beiden laten bekende totalen toe.
- Referentiedatum en grens zijn gezamenlijk verplicht; precies tien dagen oud is
  bij grens tien niet verouderd, bij grens negen wel. Gekoppelde doelbeperking is
  zichtbaar, onbekende saldi krijgen geen verborgen ouderdomsoordeel.
- Dekking blijft exact de opgegeven septemberperiode, ondanks transacties in
  oktober; de andere rekening blijft onbekend. Geen impliciete volle periode.
- No-op schrijft niets; ongeldige datums, domeinen en rekeningverwijzingen worden
  atomair geweigerd. Import behoudt verklaringen; verwijderen herstelt onbekend.

`tests/test_topo_v2_reading.py` bewijst tevens een lege complete inventaris,
versievalidatie, unieke domeinen, afzonderlijke valuta, bekend nul tegenover onbekend,
doelonzekerheid uitsluitend via koppelingen, één-dagdekking en gaten, tokenbinding
van verklaringen, behoud bij gewone updates en verwijderen van de laatste verklaring.

De invoerjourney `e2e/test_topo_v2_input_journey.py` is ongewijzigd opnieuw uitgevoerd:
brongebonden eerste invoer, identieke heraanlevering zonder token of schrijven,
bijgewerkte export met twee effectieve wijzigingen en behoud van categorieën en
bronlabels. Saldi en doelvoortgang veranderen niet door transacties. De journey
werkt zonder volledigheidsverklaringen. Gescripte tokens zijn technisch bewijs,
geen menselijke gebruiksbevestiging.

## Gebruiksbewijs en open poort

De agent heeft de oorspronkelijke bankexport, bijgewerkte export en het doelbericht
opnieuw gelezen en beide PNG-saldoschermen visueel gecontroleerd. Bronwaarden:
betaalrekening EUR 2.514,50 en spaarrekening EUR 6.400,00 op 2026-10-04;
bufferdoel EUR 10.000 op 2027-12-31, gekoppeld aan sparen. Bekende uitkomst:
EUR 8.914,50 en 64% doeldekking. De bronnen verklaren geen volledige exportperiode,
geen complete schuldeninventaris en geen structurele maandruimte; die blijven
onbekend. Er zijn geen extra verklaringen voorbereid om de nieuwe functie te vullen.

Een nieuwe brongebonden preview staat lokaal in
`test-results/topo2-context/session/preview.json`, met request, geconverteerde export,
ontdekt contract en compacte leesuitkomst ernaast. De oefencontext is na init
byte-identiek gebleven. De compacte leesuitkomst van die nog lege context toont
onbekende inventarissen en geen verzonnen totalen. De hierboven genoemde saldi zijn
een bespreking van de voorbereide broninvoer, nog geen bevestigd opgeslagen inzicht.

Voorbereiding via CLI en helper kostte **0,053 s**, na het lezen van de bronnen.
Dit omvat contractontdekking, conversie, preview en compact lezen binnen hetzelfde
Python-proces; het sluit beeldlezen en implementatie uit. Dit is geen vergelijkbare
hermeting van de 13,512 s baseline van plan 0 en geen snelheidsclaim voor een gesprek.
Tijd tot menselijk bevestigd opgeslagen inzicht is nog niet vastgesteld.

Financiële verduidelijkingsbundels: **0**. Eén gezamenlijke menselijke bevestigingsvraag
is gesteld voor de eerste invoer en de concreet beschreven latere exportupdate;
geen aparte domeinvragen. Ontvangen bevestigingen: **0**. Handmatig bronherstel: **0**.
Zonder die bevestiging zijn identieke heraanlevering en latere export alleen in de
mechanische journey herhaald. De menselijke gebruikspoorten van plannen 0 en 1
blijven open; er wordt geen bevestiging gesimuleerd als gebruiksbewijs.

## Controles en performance

`scripts/verify.sh` is opnieuw uitgevoerd en stopt bij dezelfde zes bestaande
lintfouten in `.scratch/claude-code-security-research/` en `.scratch/research/`.
Die mappen zijn ongemoeid gelaten. Dit is geen geslaagde volledige script-run.
Architectuurcontrole, lint en formattering (uitsluitend die twee onderzoeksmappen
uitgesloten), mypy en `git diff --check` slagen afzonderlijk.
De volledige unit-/integratiesuite slaagt: **165 geslaagd, 2 bewust overgeslagen**
(CSV kent geen expliciete null). De volledige black-box suite slaagt: **57 geslaagd**, inclusief plan 0 en de
nieuwe compacte leesjourney.

Meetomgeving: macOS-27.0.1-arm64-arm-64bit-Mach-O, Python 3.13.11, 1.000 rekeningen,
één ronde per schaal en afzonderlijke CLI-processen inclusief lezen, validatie en
serialisatie. De testsuites liepen deels gelijktijdig: lokale baseline, geen
geïsoleerde performancevergelijking. RSS wordt gemeten met `resource` van het eigen
CLI-proces. Geen persoonlijke context gelezen.

| Meting | 10.000 transacties | 100.000 transacties |
| --- | ---: | ---: |
| `context`, met expliciet ouderdomsbeleid | 0,229 s | 0,681 s |
| Compacte uitvoer | 530.478 bytes | 530.478 bytes |
| Volledige `show`-uitvoer | 3.118.890 bytes | 29.568.990 bytes |
| Piek-RSS `context` | 61,02 MiB | 258,91 MiB |
| Langzaamste benoemde operatie | 0,342 s | 1,758 s |

De compacte uitvoer is ook vóór toevoeging van transacties exact 530.478 bytes.
Alle zestien benoemde operaties bij 10.000 transacties blijven onder één seconde;
het benchmarkscript eindigt succesvol. Het 100.000-profiel slaagt zonder nieuwe
harde grens. De groei van geheugen en latentie blijft zichtbaar: de opslag is
ongewijzigd en volledige validatie blijft nodig.

Reproduceren: `uv run python scripts/benchmark_topo2.py` en dezelfde opdracht met
`--transactions 100000`. Ruwe metingen (alle operaties, uitvoergrootte en piek-RSS)
en controlelogs staan lokaal in `test-results/topo2-context/`.

## Beperkingen en stopgrens

Menselijke bevestiging en vervolg van de agentsessie ontbreken nog; technische
journeys vervangen die poort niet. Verklaringen zijn gedateerde menselijke input,
geen bewijs dat bronnen alles bevatten. Er is geen automatische verouderingsgrens,
OCR, bronarchief, categorisatie, schuldrecord, maandanalyse of nieuw rapport.
De uitvoering stopt bij plan 1; vervolgplannen zijn niet gestart.
