# Financial Context Engine v0.1

Label: wayfinder:map

## Destination

Een implementatieklare technische specificatie voor Financial Context Engine v0.1: een zelfstandige, local-first en Tally-geïnspireerde engine met een uitbreidbare financiële contextgraph, deterministische tools en een agentgestuurde invul- en analyseworkflow.

## Notes

- Gebruik bij besluitvorming de skills `grilling` en `domain-modeling`; werk één beslissing per sessie af.
- Gebruik voor extern onderzoek de skill `research` en baseer technische Tally-claims op primaire bronnen.
- De glossary in [`CONTEXT.md`](../../CONTEXT.md) bevat de reeds bevestigde domeintaal.
- Ontwerpprincipes: file-first, CLI + JSON, local-first/offline-capable, agent schrijft nooit canonieke context, feiten zijn tijdsbewust en herleidbaar.
- v0.1 is Nederlandstalig voor mensen, gebruikt stabiele Engelstalige technische identifiers en houdt EngineCore, jurisdictie en presentatietaal gescheiden.
- De engine kan zonder agent en zonder Tally functioneren; beide zijn belangrijke maar optionele samenwerkingspartners.
- De kaart plant en beslist; zij implementeert de engine niet.

## Decisions so far

<!-- Besluiten leven in opgeloste tickets; hier komen alleen korte contextpointers. -->

- [Welke lessen uit Tally moeten normatief worden voor de engine?](issues/01-tally-architecture-lessons.md) — Neem de lokale deterministische CLI-loop, veilige regels, JSON-contracten en ingebouwde uitleg over, maar maak financiële feiten bevestigde, herleidbare enginemutaties en kopieer Tally's merchantmodel niet.
- [Wat behoort tot de EngineCore en welke graph-invarianten bewaakt die?](issues/02-enginecore-graph-invariants.md) — Gebruik stabiele entiteiten en tijdsgebonden beweringen met verplichte herkomst, expliciete kennis- en verificatiestatus, conservatieve identiteit, declaratieve constraints en lichte atomaire single-writermutaties.
- [Welke minimale financiële domeinsnede hoort in v0.1?](issues/03-v0-1-domain-slice.md) — Composeer een kleine set financiële entiteiten met expliciete juridische, gebruiks- en toerekeningsrelaties; laat modules typen verfijnen en houd rekeningtransacties, zelfstandige saldostanden en objecten met een eigen levensloop onderscheiden.
- [Hoe worden context en mutatiehistorie canoniek opgeslagen?](issues/04-canonical-files-and-history.md) — Publiceer gevalideerde, getypeerde JSON-collecties als complete UUIDv7-generaties via een atomaire `CURRENT`-wissel, met waardevrije historie, conservatief herstel, begrensde retentie en pakketbrede privacy-scrubs.

## Not yet specified

- De concrete Nederlandse producttypen en landspecifieke validaties worden zichtbaar nadat de domeinmodulegrenzen zijn vastgesteld.
- De precieze vraagprioritering en workflowtoestanden hangen af van het voorstelmodel en de analysevereisten.
- De extensiecontracten voor nieuwe domeinen, landen en talen hangen af van de EngineCore en de eerste Nederlandse modules.
- De vorm van de uiteindelijke implementatiehandoff kan pas worden vastgesteld wanneer de technische beslissingen samen een coherent geheel vormen.

## Out of scope

- Een SaaS-product, gebruikersinterface, dashboard, hostingarchitectuur, multi-tenancy of verdienmodel.
- Financieel advies en productaanbevelingen.
- Live bank-API's, documentextractie, pensioenportalen en automatische Nibud- of andere referentiedatakoppelingen in v0.1.
- MCP als vereiste interface; een eventuele latere adapter blijft mogelijk.
- Diepe Nederlandse pensioen-, fiscale, verzekerings- of hypotheekberekeningen in v0.1.
- Het bouwen van de productie-engine; deze kaart eindigt bij een implementatieklare specificatie.
