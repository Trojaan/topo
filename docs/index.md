# Topo documentation

This directory is the maintainer system of record. `AGENTS.md` is the short map;
these pages hold the detail.

| Topic | Document |
| --- | --- |
| Eenvoudige actuele toestand, topo2 en bevestiging | [Topo 2](topo2.md) |
| Contextuitbreidingen, geleverde rapportage en vervolgplannen | [Topo 2-deelplannen](plans/topo2-context/README.md) |
| Beschikbare functies en uitvoerbare workflows | [Capabilities](capabilities.md) |
| Runtime structure, data flow, dependency boundaries | [Architecture](architecture.md) |
| Begeleide technische rondleiding door de architectuur | [Architecture tour](architecture-tour.md) |
| Domain language, invariants, and safety boundary | [Domain](domain.md) |
| Environment setup and common commands | [Development](development.md) |
| Test layers, e2e evidence, and ship gate | [Testing](testing.md) |
| CLI-verbeteringen en voortgang per sessie | [CLI-roadmap](cli-usability-roadmap.md) |

`CONTEXT.md` is the canonical Dutch glossary. The material under `.scratch/` is
design history: useful for rationale, but it does not override code, tests, or
the documents above.

- [Topo 2-performance](performance-topo2.md): opstarttijd, gerichte uitvoer en synthetische CLI-metingen.
- [Historische Topo-performance](performance.md): generaties en kosten van integriteitscontrole.
