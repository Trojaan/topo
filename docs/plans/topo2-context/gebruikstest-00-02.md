# Externe gebruikstest — plannen 0 tot en met 2

Dit is een testhandleiding voor een andere agentsessie, geen implementatie van
plan 3. Gebruik uitsluitend de synthetische bronnen hieronder. Publicatie van
v0.8.0 of geslaagde technische tests sluit de menselijke gebruikspoorten niet.

## 1. Installeer de testversie en zet een losse werkmap klaar

Gebruik een terminalagent die bestanden en PNG's kan lezen en shellcommando's
kan uitvoeren, bijvoorbeeld Claude Code. Python is niet nodig voor de standalone CLI.
Op macOS/Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/Trojaan/topo/v0.8.0/install.sh -o /tmp/topo-install-v0.8.0.sh
TOPO_VERSION=v0.8.0 bash /tmp/topo-install-v0.8.0.sh
topo2 --version
```

Op Windows PowerShell:

```powershell
Invoke-WebRequest https://raw.githubusercontent.com/Trojaan/topo/v0.8.0/install.ps1 -OutFile "$env:TEMP\topo-install-v0.8.0.ps1"
& "$env:TEMP\topo-install-v0.8.0.ps1" -Version v0.8.0
topo2 --version
```

Verwacht `topo2 0.8.0`. Als een oudere versie verschijnt, controleer welk programma
je PATH vindt (`command -v topo2` of `Get-Command topo2`); gebruik het zojuist
geïnstalleerde absolute pad. De versie is pas downloadbaar nadat de releasebuilds
zijn afgerond. Kies voor elke proef een nieuwe lege werkmap buiten een Git-repository.

Haal de bronnen uit de gepubliceerde tag, bijvoorbeeld:

```bash
git clone --depth 1 --branch v0.8.0 https://github.com/Trojaan/topo.git topo-testbronnen
mkdir topo-gebruikstest
```

Open de agent in `topo-gebruikstest`, niet in de ontwikkelrepository. Geef hem
alleen de bronmappen `e2e/fixtures/topo2-input/` en `e2e/fixtures/topo2-wealth/`
van de clone, plus `docs/topo2.md` als handleiding. Laat de agent geen testhelpers
of vooraf ingevulde requests gebruiken voor de gebruiksproef. Zonder Git kun je
de [broncodezip van v0.8.0](https://github.com/Trojaan/topo/archive/refs/tags/v0.8.0.zip)
uitpakken. De actuele release is vindbaar bij de
[GitHub-releases](https://github.com/Trojaan/topo/releases).

## 2. Start een schone agentsessie met deze opdracht

Vervang de bron- en documentatiepaden door absolute paden op jouw computer:

```text
Test Topo 2 met mij als gebruiker. Werk alleen in deze lege oefenmap en gebruik
uitsluitend topo2 en de synthetische bronnen die ik hieronder opgeef.
Lees eerst /ABSOLUUT/PAD/topo-testbronnen/docs/topo2.md en ontdek topo2 contract.

Mijn bronnen:
- /ABSOLUUT/PAD/topo-testbronnen/e2e/fixtures/topo2-input/bank.csv
- dezelfde map: saldo-betaal.png, saldo-spaar.png en doel.txt
- /ABSOLUUT/PAD/topo-testbronnen/e2e/fixtures/topo2-wealth/vermogen.txt

Geef een eerste beeld van mijn bekende nettovermogen per valuta, de onzekerheden
en mijn bufferdoel. Lees de screenshots zelf en converteer de export; gebruik geen
kant-en-klare testhelper, request of verwacht resultaat uit de testcode.
De vermogensbron bevat extra posten en vervangt de screenshotstanden niet.

Maak met topo2 init één nieuwe context in deze oefenmap. Lees compact met context;
haal transacties alleen gericht op. Combineer alle samenhangende invoer en eventuele
interpretaties in één change-preview. Bind de oorspronkelijke bronnen en de
geconverteerde export met --source. Scheid bronwaarden, interpretaties en onbekenden.
Stel maximaal drie korte vraagbundels, alleen over wezenlijke ambiguïteiten.
Vraag geen beschikbaarheidsadministratie of complete inventaris om te kunnen beginnen.
Toon de preview leesbaar en wacht op mijn expliciete bevestiging voordat je de token
gebruikt. Ontwikkeltoestemming of deze testopdracht is geen financiële bevestiging.

Houd bij: vragen, bevestigingen, tijd tot eerste bruikbare bespreking, tijd tot
bevestigd opgeslagen inzicht, onzekerheden, handmatig herstel en uitgevoerde
commando's. Wijzig context.json nooit rechtstreeks. Stop na de hier gevraagde proef;
voer geen vervolgplan uit en bevestig nooit namens mij.
```

Bekijk de preview zelf. Controleer of bronnen en interpretaties kloppen. Antwoord
pas dan expliciet, bijvoorbeeld: “Ik bevestig deze volledige preview.” Bij een
fout vraag je een correctie en beoordeel je de nieuwe preview. Zonder bevestiging
moet de context leeg blijven. Noteer de eerste bruikbare bespreking ook als die
vóór opslaan plaatsvindt. Als de agent geen beelden kan lezen, registreer dat als
beperking en geef geen verzonnen beeldwaarden door als agentbewijs.

## 3. Controleer de eerste uitkomst

Laat de agent `context`, `summary` en een gerichte transactiequery uitvoeren.
Gebruik deze controlewaarden pas nadat de agent de bronnen zelf heeft verwerkt:

| Controle | Verwachting |
| --- | --- |
| Oorspronkelijke bankrekeningen | EUR 2.514,50 en EUR 6.400,00, peildatum 2026-10-04 |
| Alle bekende rekeningen en bezittingen | EUR 318.414,50; USD 1.000 |
| Afzonderlijk afgetrokken bekende schulden | EUR 200.000; USD 100 |
| Bekende nettodeelsom | EUR 118.414,50; USD 900 |
| Roodstand | EUR -500 in rekening; gekoppelde EUR 500 niet nogmaals afgetrokken |
| Onbekende persoonlijke lening | Ontbrekend EUR-bedrag, geen bekend nul |
| Inventaris | Geen complete inventaris verklaren; ontbrekende verklaring blijft onbekend |
| Beschikbaarheid | Onbekend; geen woning of spaargeld automatisch vrij verklaren |
| Bufferdoel | EUR 6.400 gekoppeld, 64% van EUR 10.000 |
| Transacties | Vier records; eigen overboekingen zijn geen externe uitgaven |
| Compacte uitvoer | Schuldrecords en peildata zichtbaar; geen transactierecordlijst |

Laat vervolgens lezen met `--reference-date 2026-10-14 --max-age-days 10` en met
`--max-age-days 9`. Tien dagen oude bekende waarden zijn bij grens 10 niet verouderd,
bij grens 9 wel. Zonder beide opties mag er geen impliciet ouderdomsoordeel ontstaan.
De exportdata bewijzen geen complete transactiedekking. Ontbrekende schulden
mogen gerichte transactieanalyse of bestaande doelvoortgang niet blokkeren.

## 4. Herhaal dezelfde aanlevering

Zeg: “Hier zijn exact dezelfde bronnen nogmaals. Verwerk ze opnieuw met behoud
van alles wat al bekend is.” Geef dezelfde bestanden.

Verwacht: geen herhaalde inventarisatie, geen nieuwe bevestiging, `unchanged`,
geen token en geen schrijven. Laat de agent vóór en na bytes/hash én wijzigingstijd
van context.json vergelijken. Het technische lockbestand is geen contextmutatie.
Volledige change-updates moeten bestaande optionele velden meenemen.

## 5. Geef de bijgewerkte export

Lever nu `e2e/fixtures/topo2-input/bank-updated.csv` en zeg:

```text
Dit is de bijgewerkte export. Verwerk de verschillen; behoud bekende categorieën,
bronlabels, rekeningkoppelingen, doelen en schulden. De saldoscreenshots blijven
leidend voor de rekeningstanden. Toon één gezamenlijke preview en wacht op mijn
bevestiging. Gebruik bankreferenties als vaste transactie-identiteit.
```

Verwacht één gecorrigeerde transactie (SYN004 naar EUR -86,50) en één nieuwe
(SYN005, EUR -24), met drie ongewijzigde records. Rijvolgorde mag geen nieuwe IDs
opleveren. De bestaande categorie Boodschappen en het bronlabel blijven behouden.
Vraag geen nieuwe categorie voor de lunch als dit niet wezenlijk is voor de vraag;
ontbrekende verrijking mag onbekend blijven. Bevestig de concrete wijziging zelf.

Herhaal daarna dezelfde bijgewerkte export. Verwacht opnieuw geen schrijven of
bevestiging. Vermogen, rekeningstanden en bufferdekking blijven ongewijzigd.

## 6. Verdiep alleen op jouw verzoek

Voer deze onderdelen als afzonderlijke, bewust gevraagde testwijzigingen uit;
elk samenhangend request krijgt maximaal één gezamenlijke bevestiging.

- Vraag: “Welke bekende middelen kan ik nu inzetten? Neem voor deze synthetische
  proef aan dat de extra spaarrekening van EUR 10.000 vrij is en de woning beperkt
  beschikbaar; voor de rest weet ik het niet.” Laat dit in één preview vastleggen.
  Na jouw bevestiging: vrij EUR 10.000, beperkt EUR 300.000, overige beschikbaarheid
  onbekend. Dit is geen bestedingsruimte na schulden of verkoopopbrengstgarantie.
- Vraag daarna: “De eerder onbekende lening bedraagt EUR 1.250 op 2026-10-04.”
  Na preview en jouw bevestiging wordt de bekende EUR-nettosom EUR 117.164,50.
  Dat maakt de inventaris nog niet compleet. USD blijft 900.
- Laat alleen een ongeldige **preview** voorbereiden voor een roodstandschuld van
  EUR 600 met rekening EUR -500. Verwacht weigering zonder schrijven. Laat daarna
  rekening -600 en gekoppelde schuld 600 samen voorbereiden: één geldige preview.
  Pas die alleen toe als je deze extra testwijziging ook zelf wilt bevestigen.
- Herhaal de bijgewerkte export na de beschikbaarheidswijziging: beschikbaarheid,
  toelichting en schuldcorrectie moeten behouden blijven, zonder schrijven bij
  identieke effectieve transacties.

Een technische nulstand-/inventaristest staat in de black-box suite. Declareer
geen volledige financiële inventaris alleen om de gebruiksproef groen te krijgen.

## 7. Laat de agent het gebruiksbewijs opleveren

Vraag een kort verslag met bronbestanden, CLI-versie, vragen en echte antwoorden,
preview(s), jouw ontvangen bevestiging(en), byte-/mtime-controles, gemeten tijden,
herstelwerk en resterende beperkingen. Eén bevestiging geldt per samenhangende
wijziging, niet voor alle verschillende teststappen bij elkaar. Een no-op vraagt nul.

Plannen 0–2 zijn pas ook in gebruik bewezen als jij de broninterpretatie en de
journey werkelijk hebt beoordeeld en bevestigd. Bewaar het verslag in de losse
synthetische werkmap en deel het hier om de planstatus op basis van dat bewijs bij
te werken. Een externe agent mag niet uit zichzelf claimen dat de open poorten
in deze repository zijn gesloten.

Als extra technische controle vanuit de broncodeclone, met uv geïnstalleerd:

```bash
uv sync --frozen
uv run pytest tests/test_topo_v2_wealth.py e2e/test_topo_v2_input_journey.py e2e/test_topo_v2_context_journey.py e2e/test_topo_v2_wealth_journey.py
scripts/verify.sh
uv run python scripts/benchmark_topo2.py
uv run python scripts/benchmark_topo2.py --transactions 100000
```

In een schone clone staan de lokale ongetrackte onderzoeksmappen niet. Die
veroorzaakten in de ontwikkelwerkmap zes bestaande lintfouten; dat is geen reden
om tests in de clone over te slaan. De technische controles vervangen de
menselijke agentsessie hierboven niet.
