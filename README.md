# Topo

Topo is een local-first CLI voor het opbouwen van een immutable, auditable
financiële context. Topo is een engine, geen financieel adviseur en geen
webapplicatie.

## Topo 2: eenvoudiger actueel overzicht

Naast de bestaande engine is er nu `topo2`: complete records voor rekeningen,
bezittingen en doelen, één bevestiging per groep wijzigingen en één lokaal
`context.json`, zonder historie. Begin met een nieuwe context.

```bash
uv sync --frozen
uv run topo2 init --context /pad/naar/context.json
uv run topo2 contract
uv run topo2 summary --context /pad/naar/context.json
```

Zie [Topo 2](docs/topo2.md) voor invoer, bevestiging en agentinstructies.
Vanaf release `v0.6.0` installeren de onderstaande installers zowel `topo` als
`topo2`. Topo 2 werkt zonder Python of `uv`; voer na installatie `topo2 contract`
uit. Heb je Topo al, voer de installer opnieuw uit om ook `topo2` te installeren.

## Installeren

macOS en Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/Trojaan/topo/main/install.sh | bash
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/Trojaan/topo/main/install.ps1 | iex
```

De installer downloadt de nieuwste standalone release. Python en `uv` zijn niet
nodig om de geïnstalleerde CLI te gebruiken. Voer de installer opnieuw uit om
beide commando’s bij te werken. `topo upgrade` werkt alleen de bestaande `topo` bij.
Een specifieke versie installeren kan met
`TOPO_VERSION=v0.3.0` op Unix of `-Version v0.3.0` in PowerShell.

## Agent-ready quickstart

```bash
topo init ./mijn-financien
cd ./mijn-financien
topo context status --package ./context.topo --json
```

`topo init` maakt een canonieke package onder `context.topo/`, een afgeschermde
`imports/`-map en beheerde Topo-secties in `AGENTS.md`, `CLAUDE.md` en
`.gitignore`. Bestaande instructies buiten de Topo-markers blijven behouden.

Open daarna de directory in Codex, Claude Code of een andere command-line agent.
De agent kan de beschikbare contracten ontdekken met:

```bash
topo contract describe --json
topo contract schema source.import --json
```

Agentinterpretaties worden uitsluitend als voorstellen ingediend. Alleen
expliciete menselijke autorisatie kan een voorstel promoveren tot een bevestigd
feit.

## Ontwikkelen

Voor werken aan Topo zelf zijn Python 3.12+, `uv` en de commando's in
[`docs/development.md`](docs/development.md) nodig. De volledige ship-gate is:

```bash
scripts/verify.sh
```
