# Plan 2 — Levering en bewijs

## Actuele status na extern gebruiksbewijs

Techniek en de uitgevoerde synthetische basisjourney zijn geleverd. Zie
[extern gebruiksbewijs 0–2](gebruik-bewijs-00-02.md) voor de echte bevestigingen,
no-ops, herstelstappen en beperkingen. Onderstaande lokale sessieverslagen zijn
historisch: hun toen open bevestigingen beschrijven die eerdere sessies, niet de
actuele gecombineerde planstatus. Niet uitgevoerde optionele proeven blijven open.


Peildatum: 2026-10-14. Technisch geleverd; menselijke gebruikspoort nog open.
Uitsluitend synthetische bronnen. De open menselijke bevestigingen van plannen
0 en 1 zijn niet ontvangen, toegepast of als afgerond behandeld. Deze uitvoering
stopt bij plan 2.

## Onderzoek en geleverde functionaliteit

De kennisgraph meldde dat deze repository niet geïndexeerd is; codeverkenning
viel terug op rechtstreeks lezen. De bestaande wijzigingen voor plan 1 waren al
in de werkmap aanwezig, naast ongerelateerde onderzoeksmappen. Die zijn behouden.

Bestaande bronbinding, atomaire preview/bevestiging, Decimal-berekeningen,
importbehoud, identieke effectieve heraanlevering en compact lezen zijn hergebruikt.
Er is geen nieuwe importadapter, opslagarchitectuur of bevestigingsflow.

Nieuw zijn schuldrecords met onbekende of niet-negatieve stand, peildatum en valuta;
rente en einddatum zijn optioneel. Expliciete roodstandkoppelingen zijn gekozen
na één ontwerpvraag en een uitleg, gevolgd door instemming met die keuze. Dit
was een softwareontwerpkeuze, geen financiële bevestiging van oefengegevens.
Een gekoppelde schuld vereist bekende bedragen, dezelfde valuta/peildatum en exact
het tegengestelde van het niet-positieve saldo. Maximaal één koppeling per rekening;
rekening en schuld kunnen in één batch worden gecorrigeerd of verwijderd.
Het rekeningsaldo telt eenmaal; `linked_debt_ids` maakt de uitgesloten tweede
schuldafslag verklaarbaar. Niet-gekoppelde schulden zijn afzonderlijke verplichtingen.
Er is geen automatische herkenning van dubbele broninvoer.

`summary.net_wealth` toont per valuta het rekening-/bezittingentotaal, afzonderlijk
afgetrokken schulden, bekende nettosom, ontbrekende waarden en inventarisvolledigheid.
`complete` gaat uitsluitend over bedragen binnen bekende records;
`inventory_complete` vereist drie complete verklaringen. Verklaringen vullen nooit
een ontbrekend bedrag in. De inventarisstatus blijft bij een lege context zichtbaar,
zonder een verzonnen valuta of bekend nultotaal. Oude subtotalen en doelberekeningen
behouden hun betekenis. Transacties tellen nooit mee als saldo of vermogen.

Optionele actuele beschikbaarheid en toelichting worden bewaard op rekeningen en
bezittingen. Vrije en beperkte positieve bedragen staan apart, evenals onbekende
beschikbaarheid en ontbrekende waarden. Roodstand levert geen beschikbare middelen.
Een woning zonder verklaring wordt niet als vrij inzetbaar beschouwd; een waardering
is geen voorspelling van verkoopopbrengst. Er is geen bestedingsruimteberekening.

`context` toont schulden en hun waardepeildata, zonder transactierecords. Het bestaande
expliciete ouderdomsbeleid geldt ook voor schuldstanden. Vermogensinventarissen,
ontbrekende bedragen en ouderdom beperken nettovermogen; beschikbaarheid krijgt
eigen beperkingen. Schuldonzekerheid blokkeert geen doelen of transactieanalyse.
Alleen nettovermogen verliest `not_supported`; maandruimte blijft niet ondersteund.

CLI-contract `topo2.cli/3` is additief uitgebreid. Schulden en beschikbaarheidsvelden
vereisen opslag `topo2.context/4`. Versies 1–3 blijven leesbaar; lezen, preview en
no-op schrijven niets. De eerste effectieve bevestigde wijziging met nieuwe velden
schrijft versie 4. Deze versie blijft behouden na verwijderen van alle nieuwe data.
Zonder nieuwe velden blijven de bestaande versie-2/3-regels behouden.

## Technisch bewijs

`tests/test_topo_v2_wealth.py` en `e2e/test_topo_v2_wealth_journey.py` bewijzen:

- Woning EUR 300.000, hypotheek EUR 200.000, sparen EUR 10.000 en banksaldo EUR -500
  geven EUR 109.500. Een expliciet gekoppeld schuldrecord voor dezelfde roodstand
  verandert die uitkomst niet; USD blijft afzonderlijk.
- Bekende nul tegenover onbekende stand, lege en schuld-only context, ontbrekende
  bezittingswaarde, onbekende/gedeeltelijke/complete inventaris en expliciet complete
  verklaringen met nog ontbrekende bedragen. Een bekende deelsom blijft bruikbaar.
- Optionele vrije/beperkte beschikbaarheid, onbekende beschikbaarheid en ontbrekende
  waarde. Negatief saldo telt niet positief mee; bezitsoort geeft geen beschikbaarheid.
- Atomaire weigering van afwijkend bedrag/valuta/peildatum, onbekende rekening,
  onbekende gekoppelde bedragen, positieve gekoppelde saldi, dubbele koppeling,
  dubbele globale IDs, ongeldige schuldsoort en ongeldige verwijderingen.
- Gezamenlijke saldo-/schuldcorrecties, gezamenlijk verwijderen, bronbytes- en
  requesttokenbinding. Oude versies blijven bij lezen, preview en no-op byte- en
  mtime-identiek; opslagversie 4 blijft behouden na verwijderen van nieuwe velden.
- Een brongebonden gezamenlijke invoer vanaf de plan-0-bronnen plus expliciete
  synthetische vermogensbron; schema-overeenkomst, identieke heraanlevering zonder
  token of schrijven, bijgewerkte export met twee effectieve wijzigingen en behoud
  van categorieën, bronlabels, schuldrecords en beschikbaarheidsvelden.
- Werkelijk toegepaste standalone importcorrectie behoudt dezelfde verrijkingen;
  herhaling schrijft niets. Saldi, vermogen en doelen veranderen niet door transacties.

De oorspronkelijke invoerjourney en compacte leesjourney zijn opnieuw uitgevoerd.
Hun bestaande assertions blijven behouden; alleen een aanvullende mtime-assertion
is aan de invoerjourney toegevoegd. Gescripte tokens zijn mechanisch bewijs en
geen menselijke bevestiging.

## Werkelijk uitgevoerde agentsessie

De agent heeft de oorspronkelijke en bijgewerkte bankexport en doeltekst opnieuw
gelezen en beide PNG-saldoschermen visueel gecontroleerd. Een aanvullende tekstbron
`e2e/fixtures/topo2-wealth/vermogen.txt` bevat expliciet synthetische extra posten,
de roodstandoverlap en een lening met onbekende stand. De bron verklaart geen
complete inventaris of beschikbaarheid. De extra gegevens vervangen de oorspronkelijke
rekeningstanden niet.

Eén gezamenlijk request en één brongebonden preview staan lokaal in
`test-results/topo2-wealth/session/`, naast het ontdekte contract, geconverteerde
export, bronlijst, compacte leesuitkomst en een uitsluitend in geheugen berekende
samenvatting van de voorbereide invoer. De lege oefencontext is na init byte- en
mtime-identiek gebleven. Er is geen bevestigingstoken toegepast in deze agentsessie.

De voorbereide bronuitkomst is EUR 118.414,50 als **bekende deelsom**, inclusief
EUR 8.914,50 van de oorspronkelijke bankrekeningen; USD 900 blijft afzonderlijk.
De onbekende EUR-lening ontbreekt in de bekende bedragen en is zichtbaar als hiaat.
Bufferdekking blijft 64%; geen middelen zijn zonder verklaring vrij beschikbaar
genoemd. De beperkte inventaris en onbekende beschikbaarheid blijven zichtbaar.
Dit zijn voorbereide uitkomsten, geen menselijk bevestigd opgeslagen inzicht.

Voorbereiding kostte **0,619 s** vanaf contractontdekking tot preview, compacte
lezing en berekening van de kandidaat in geheugen. Afzonderlijke CLI-processen zijn
meegemeten; bronlezen, init en implementatie zijn uitgesloten. Dit is één lokale
voorbereidingsmeting, geen vergelijkbare gespreksbaseline of algemene snelheidsclaim.
Tijd tot menselijk bevestigd opgeslagen inzicht is niet vastgesteld.

Financiële verduidelijkingsbundels: **0**. Er is **één** gezamenlijke menselijke
bevestigingsvraag gesteld voor de concrete volledige preview. Ontvangen financiële
bevestigingen: **0**. Handmatig bronherstel: **0**. Identieke heraanlevering en
bijgewerkte export zijn technisch herhaald; hun menselijk bevestigde vervolg blijft
open. Ook de gebruikspoorten van plannen 0 en 1 blijven open.

## Controles en performance

De ongewijzigde `scripts/verify.sh` is uitgevoerd en stopt bij dezelfde zes
lintfouten in `.scratch/claude-code-security-research/` en `.scratch/research/`.
Die bestanden zijn niet gewijzigd. Dit is geen geslaagde volledige script-run.
Architectuurcontrole, lint en formattering (uitsluitend deze twee mappen uitgesloten),
mypy en `git diff --check` slagen afzonderlijk.

De volledige unit-/integratiesuite slaagt: **181 geslaagd, 2 bewust overgeslagen**
(CSV kent geen expliciete null). De gerichte vermogens-, invoer- en compacte
leescontrole slaagt: **24 geslaagd**.

De volledige black-box run slaagt: **62 geslaagd**. Een daarna toegevoegde
black-box inventaris-/nulstandcontrole is afzonderlijk geslaagd binnen de gerichte
run van 24 tests. Daarmee zijn alle 63 actuele black-box tests uitgevoerd en
geslaagd, waarvan de laatste niet in de eerder verzamelde volledige run zat.

Meetomgeving: macOS-27.0.1-arm64-arm-64bit-Mach-O, Python 3.13.11,
1.000 rekeningen, één ronde per schaal, afzonderlijke CLI-processen inclusief
inlezen, validatie, berekenen en serialiseren. De tests waren vóór deze metingen
beëindigd. De fixture bevat tevens een woning, bekende en onbekende schulden,
USD en expliciete vrije/beperkte beschikbaarheid. RSS komt van het eigen CLI-proces.

| Meting | 10.000 transacties | 100.000 transacties |
| --- | ---: | ---: |
| Uitgebreide `summary` | 0.199 s | 0.654 s |
| Compacte `context` | 0.210 s | 0.676 s |
| Samenvattingsuitvoer | 1,568 bytes | 1,568 bytes |
| Compacte uitvoer | 604,010 bytes | 604,010 bytes |
| Volledige `show`-uitvoer | 3,190,067 bytes | 29,640,167 bytes |
| Piek-RSS `summary` | 59.39 MiB | 259.55 MiB |
| Piek-RSS `context` | 61.47 MiB | 259.34 MiB |
| Langzaamste benoemde operatie | 0.362 s | 1.910 s |

Alle zestien benoemde operaties bij 10.000 transacties blijven onder één seconde;
het benchmarkscript eindigt succesvol. Het 100.000-profiel slaagt zonder nieuwe
harde grens. De uitvoergrootte van zowel summary als context is ook vóór toevoegen
van transacties gelijk aan de gemeten compacte uitvoer; dit wordt geasserteerd.
Geen transactiedetails worden geserialiseerd. Geheugen en latentie groeien nog wel
met het volledige JSON-bestand; dit is geen claim op constante leescomplexiteit.

Reproduceren: `uv run python scripts/benchmark_topo2.py` en dezelfde opdracht met
`--transactions 100000`. In deze sandbox is `UV_CACHE_DIR=/tmp/topo2-uv-cache`
gebruikt omdat de normale uv-cache buiten de schrijfrechten valt. Ruwe metingen,
controlelogs en de ongewijzigde scriptfout staan lokaal in
`test-results/topo2-wealth/`. Er is geen persoonlijke context gelezen.


## Beperkingen en stopgrens

Menselijke gebruiksbevestiging en het vervolg van de agentsessie ontbreken nog.
Er is geen automatische schuldherkenning, volledige inventarisatie, liquiditeits-
tijdlijn, verkoopopbrengstberekening, valutaomrekening, maandlastberekening of
rapportlaag. Beschikbaarheid is expliciet actuele input; onbekend blijft onbekend.
Compacte uitvoer leest en valideert intern nog het volledige JSON-bestand.
De uitvoering stopt na plan 2.
