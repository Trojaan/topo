# Topo v0.1

Label: wayfinder:map

## Destination

Een implementatieklare technische specificatie voor Topo v0.1: een zelfstandige, local-first en Tally-geïnspireerde engine met een uitbreidbare financiële contextgraph, deterministische tools en een agentgestuurde invul- en analyseworkflow.

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
- [Hoe verloopt de keten van bronbewijs naar bevestigd financieel feit?](issues/05-evidence-proposal-confirmation.md) — Scheid letterlijke bronwaarnemingen van voorstellen door agent of regelmodule; laat EngineCore herleidbaarheid en bevestiging bewaken en wijzig afgeleide feiten alleen via bevestigde opvolgvoorstellen.
- [Welke declaratieve regels heeft de engine nodig en hoe blijven die veilig?](issues/06-declarative-rule-model.md) — Gebruik vier capability-limited YAML-regeltypen op begrensde input-views, met geregistreerde predicates, effectvrije preview, expliciete pakketactivatie en volledige uitleg van deterministische uitvoering.
- [Welke vereisten en uitkomsten hebben de eerste analyses?](issues/07-first-analysis-contracts.md) — Gebruik doelgebonden componentstatussen en herleidbare resultaatcontracten voor inventarisatie, patroonherkenning, gerealiseerde en genormaliseerde cashflow, nettovermogen en begrensde scenariovergelijking.
- [Welk CLI-contract laat mens, engine en agent betrouwbaar samenwerken?](issues/08-cli-and-agent-workflow.md) — Gebruik smalle JSON-commando's met uniforme envelopes, idempotente atomaire mutaties, effectvrije discovery en workflowacties, expliciete autorisatie en generieke uitleg via stabiele referenties.
- [Welke extensiecontracten houden domeinen, landen en talen uit de kern?](issues/09-modules-jurisdictions-and-locales.md) — Gebruik gepinde, vertrouwde capabilitymodules met scherpe grenzen voor domein, jurisdictie, analyse, regels, bronnen, opslag en betekenisvrije presentatie, plus veilige alleen-lezen degradatie en expliciete migraties.
- [Welke Nederlandse productclassificaties en constraints horen in v0.1?](issues/11-dutch-products-and-constraints.md) — Houd `jurisdiction.nl` als kleine semantische overlay op samengestelde universele domeinobjecten, met gangbare Nederlandse kwalificaties, waarderingen, pensioen-, kasstroom- en dekkingstypen en conservatieve constraints zonder diepe berekeningen.
- [Wanneer is de technische specificatie klaar voor implementatie?](issues/10-specification-readiness.md) — Lever één traceerbaar hoofddocument met technische bijlagen en drie compacte end-to-end-verhalen; alleen inhoudelijke, veiligheids- en consistentierisico's blokkeren de bouw, terwijl agentbegeleiding buiten de feitelijke engine blijft.
- [Welke naam krijgt de financiële contextengine?](issues/12-engine-name.md) — Noem de engine Topo: een korte, speelse en internationale naam voor het zelf in kaart brengen van de eigen financiële werkelijkheid.
- [Hoe wordt de implementatieklare specificatie samengesteld?](issues/13-assemble-implementation-specification.md) — Bundel alle besluiten in één normatieve Topo v0.1-handoff met JSON-contracten, acceptatievoorbeelden, drie end-to-end-verhalen en een geslaagde gereedheidscontrole.

## Not yet specified

<!-- De route naar de bestemming is volledig gespecificeerd en afgelegd. -->

## Out of scope

- Een SaaS-product, gebruikersinterface, dashboard, hostingarchitectuur, multi-tenancy of verdienmodel.
- Financieel advies door de engine, aanbevelingen van specifieke financiële producten door de agent en het vervangen van een bevoegde financiële of fiscale deskundige bij belangrijke beslissingen.
- Live bank-API's, documentextractie, pensioenportalen en automatische Nibud- of andere referentiedatakoppelingen in v0.1.
- MCP als vereiste interface; een eventuele latere adapter blijft mogelijk.
- Diepe Nederlandse pensioen-, fiscale, verzekerings- of hypotheekberekeningen in v0.1.
- Het bouwen van de productie-engine; deze kaart eindigt bij een implementatieklare specificatie.
