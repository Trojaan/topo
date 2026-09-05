# Topo

Topo is een local-first CLI voor het opbouwen van een immutable, auditable
financiële context. Topo is een engine, geen financieel adviseur en geen
webapplicatie.

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
nodig om de geïnstalleerde CLI te gebruiken. Voer dezelfde installer opnieuw uit
om Topo bij te werken. Een specifieke versie installeren kan met
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
