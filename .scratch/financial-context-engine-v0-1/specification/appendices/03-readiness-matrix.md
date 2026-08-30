# Bijlage 3 — traceerbaarheid en gereedheidscontrole

Deze compacte matrix koppelt eisen aan hun beslisbron en voorbeelddekking. `A`, `B` en `C` verwijzen naar de drie verhalen in [bijlage 2](02-examples-and-stories.md). Namen linken naar de detailbeslissing; issue-nummers worden niet als naam gebruikt.

## 1. Controletabel

| Eis/capability | Beslisbron | Voorbeeld | Status |
|---|---|---|---|
| Local/file-first, deterministisch, agent- en Tally-onafhankelijk | [Welke lessen uit Tally moeten normatief worden voor de engine?](../../issues/01-tally-architecture-lessons.md) | A, B | ready |
| Alleen EngineCore muteert canonieke context | [Welke lessen uit Tally moeten normatief worden voor de engine?](../../issues/01-tally-architecture-lessons.md), [Hoe verloopt de keten van bronbewijs naar bevestigd financieel feit?](../../issues/05-evidence-proposal-confirmation.md) | B | ready |
| Entity/assertion/evidence/proposal/mutation-meta-model | [Wat behoort tot de EngineCore en welke graph-invarianten bewaakt die?](../../issues/02-enginecore-graph-invariants.md) | A–C | ready |
| Tijd, herkomst, kennis- en verificatiestatus verplicht | [Wat behoort tot de EngineCore en welke graph-invarianten bewaakt die?](../../issues/02-enginecore-graph-invariants.md) | B, C | ready |
| Conservatieve identiteit en zichtbare conflicten | [Wat behoort tot de EngineCore en welke graph-invarianten bewaakt die?](../../issues/02-enginecore-graph-invariants.md) | capability 1.8 | ready |
| Minimale samengestelde financiële domeinsnede | [Welke minimale financiële domeinsnede hoort in v0.1?](../../issues/03-v0-1-domain-slice.md) | A–C | ready |
| Juridische positie, gebruik en huishoudtoerekening gescheiden | [Welke minimale financiële domeinsnede hoort in v0.1?](../../issues/03-v0-1-domain-slice.md) | B, C | ready |
| Expliciete valuta, geen impliciete 50/50 of correctietransactie | [Welke minimale financiële domeinsnede hoort in v0.1?](../../issues/03-v0-1-domain-slice.md) | A, C | ready |
| Complete generatie, atomische `CURRENT`-wissel en checksums | [Hoe worden context en mutatiehistorie canoniek opgeslagen?](../../issues/04-canonical-files-and-history.md) | capability 1.12 | ready |
| Idempotentie, optimistic concurrency en crash recovery | [Hoe worden context en mutatiehistorie canoniek opgeslagen?](../../issues/04-canonical-files-and-history.md) | capabilities 1.2, 1.7, 1.12 | ready |
| Begrensde retentie, nieuwe-generatieherstel en privacy-scrub | [Hoe worden context en mutatiehistorie canoniek opgeslagen?](../../issues/04-canonical-files-and-history.md) | contract + storage fixture | ready |
| Letterlijke observation → proposal → expliciete bevestiging | [Hoe verloopt de keten van bronbewijs naar bevestigd financieel feit?](../../issues/05-evidence-proposal-confirmation.md) | B | ready |
| Correctie als nieuw bewijs; opvolging wijzigt niet stil | [Hoe verloopt de keten van bronbewijs naar bevestigd financieel feit?](../../issues/05-evidence-proposal-confirmation.md) | capabilities 1.5, fixture | ready |
| Vier capability-limited YAML-regeltypen | [Welke declaratieve regels heeft de engine nodig en hoe blijven die veilig?](../../issues/06-declarative-rule-model.md) | capability 1.11 | ready |
| Effectvrije rule preview en atomaire pakketactivatie | [Welke declaratieve regels heeft de engine nodig en hoe blijven die veilig?](../../issues/06-declarative-rule-model.md) | capability 1.11 | ready |
| Componentstatussen en herleidbaar analysecontract | [Welke vereisten en uitkomsten hebben de eerste analyses?](../../issues/07-first-analysis-contracts.md) | A–C | ready |
| Altijd beschikbare context inventory zonder totaalscore | [Welke vereisten en uitkomsten hebben de eerste analyses?](../../issues/07-first-analysis-contracts.md) | A | ready |
| Patroonherkenning en bevestigde recurring cashflows | [Welke vereisten en uitkomsten hebben de eerste analyses?](../../issues/07-first-analysis-contracts.md) | B | ready |
| Realized en normalized monthly cashflow | [Welke vereisten en uitkomsten hebben de eerste analyses?](../../issues/07-first-analysis-contracts.md) | B | ready |
| Net worth zonder dubbeltelling of schatting | [Welke vereisten en uitkomsten hebben de eerste analyses?](../../issues/07-first-analysis-contracts.md) | C | ready |
| Begrensde scenariovergelijking zonder impliciet sparen | [Welke vereisten en uitkomsten hebben de eerste analyses?](../../issues/07-first-analysis-contracts.md) | C | ready |
| Smalle CLI, uniforme envelope en exitcodebeleid | [Welk CLI-contract laat mens, engine en agent betrouwbaar samenwerken?](../../issues/08-cli-and-agent-workflow.md) | capabilities 1.1–1.10 | ready |
| Getypept `workflow next` en generiek `explain` | [Welk CLI-contract laat mens, engine en agent betrouwbaar samenwerken?](../../issues/08-cli-and-agent-workflow.md) | A, B | ready |
| Capabilitymodules houden domein, land, analyse en taal gescheiden | [Welke extensiecontracten houden domeinen, landen en talen uit de kern?](../../issues/09-modules-jurisdictions-and-locales.md) | contract + C | ready |
| Veilige read-only degradatie bij ontbrekende module | [Welke extensiecontracten houden domeinen, landen en talen uit de kern?](../../issues/09-modules-jurisdictions-and-locales.md) | failure fixture | ready |
| Kleine `jurisdiction.nl` overlay en conservatieve constraints | [Welke Nederlandse productclassificaties en constraints horen in v0.1?](../../issues/11-dutch-products-and-constraints.md) | C, capability 1.6 | ready |
| Eén hoofddocument, bijlagen en drie verhalen | [Wanneer is de technische specificatie klaar voor implementatie?](../../issues/10-specification-readiness.md) | dit pakket | ready |
| Engine blijft feitelijk; agentbegeleiding blijft erbuiten | [Wanneer is de technische specificatie klaar voor implementatie?](../../issues/10-specification-readiness.md) | A–C | ready |
| Productnaam Topo en technische categorienaam | [Welke naam krijgt de financiële contextengine?](../../issues/12-engine-name.md) | hoofddocument | ready |
| SaaS/UI/hosting/multi-tenancy | [Wanneer is de technische specificatie klaar voor implementatie?](../../issues/10-specification-readiness.md) | n.v.t. | out_of_scope |
| Live bank-, document-, pensioen- en referentiedatakoppelingen | [Welke Nederlandse productclassificaties en constraints horen in v0.1?](../../issues/11-dutch-products-and-constraints.md) | n.v.t. | out_of_scope |
| Diepe fiscale, pensioen-, verzekerings- en hypotheekberekeningen | [Welke Nederlandse productclassificaties en constraints horen in v0.1?](../../issues/11-dutch-products-and-constraints.md) | n.v.t. | out_of_scope |
| MCP als verplichte interface | [Welk CLI-contract laat mens, engine en agent betrouwbaar samenwerken?](../../issues/08-cli-and-agent-workflow.md) | n.v.t. | deferred |
| Runtime-installatie van externe plug-ins en sandboxing | [Welke extensiecontracten houden domeinen, landen en talen uit de kern?](../../issues/09-modules-jurisdictions-and-locales.md) | n.v.t. | deferred |
| Applicatielaagversleuteling | [Hoe worden context en mutatiehistorie canoniek opgeslagen?](../../issues/04-canonical-files-and-history.md) | n.v.t. | deferred |

## 2. Gereedheidscriteria

| Controle | Uitkomst |
|---|---|
| Kan een ontwikkelaar financieel gedrag implementeren zonder nieuwe domeinkeuzes? | Ja; domein, tijd, status, toerekening, valuta en formules zijn normatief vastgelegd. |
| Zijn mutatie- en autorisatiegrenzen expliciet? | Ja; muterende requests, previewgrenzen, idempotentie en optimistic concurrency zijn vastgelegd. |
| Zijn storage-integriteit en crashgedrag expliciet? | Ja; complete generaties, checksums, publishvolgorde, recovery en write blocking zijn vastgelegd. |
| Is iedere beloofde capability concreet geïllustreerd? | Ja; capabilityvoorbeelden 1.1–1.12 plus de drie verhalen. |
| Zijn veiligheidskritische weigeringen geïllustreerd? | Ja; incompatibele versie, ontbrekende autorisatie, invalid constraint, stale generatie, ontbrekende koers, checksumtampering en onvoldoende historie. |
| Sluiten drie verhalen end-to-end? | Ja; lege context, transactie-import/confirmatie/cashflow en vermogen/scenario. |
| Zijn open technische keuzes als implementatievrijheid gemarkeerd? | Ja; zie hoofdstuk 11 van het hoofddocument. |
| Blijft advies buiten engine-output? | Ja; productgrens en alle verhalen handhaven dit. |

## 3. Open-risicocontrole

### Blokkerende risico's

Geen bekende blokkerende specificatierisico's resteren. De volgende voorheen risicovolle gebieden hebben een normatieve grens en weigervoorbeeld:

- partiële of ongewenste writes: complete generatie + `effect: none` bij falen;
- verloren updates: `expected_generation` en stale-generationconflict;
- agent maakt financiële waarheid: proposal- en autorisatiegrens;
- ontbrekende context wordt een schijnzeker getal: componentstatussen en geen nuldefault;
- dubbeltelling: rekening/saldo, portefeuille/posities en kredietrekening/debt-invarianten;
- verborgen scenario-aannames: capability-limited assumptiontypes en geen impliciet sparen;
- onbetrouwbare regels: gesloten YAML-capabilities, preview en pakketactivatie;
- onleesbare of gemanipuleerde opslag: manifests, checksums en conservatieve write blocking.

### Niet-blokkerende implementatierisico's

Deze vragen mogen tijdens implementatie worden opgelost zonder financieel gedrag te veranderen:

- keuze van taal, JSON Schema-validator en YAML-parser;
- bestandslocking per ondersteund besturingssysteem;
- interne indexen en performancebudgetten, mits input-views begrensd blijven;
- precieze default-retentielimiet, zolang die expliciet, begrensd en configureerbaar is vóór release;
- concrete doelgebonden actualiteitsdrempels per analysis/module, mits als modulecontract en niet als EngineCore-default geleverd;
- locale-copy en terminalpresentatie.

De laatste twee vragen vereisen vóór publieke v0.1-release concrete moduleconfiguratie en fixtures, maar blokkeren de start van EngineCore-, opslag-, CLI- en contractimplementatie niet omdat hun semantische eigenaarschap en fail-safe gedrag vaststaan.

## 4. Handoffbesluit

Het specificatiepakket voldoet aan de afgesproken overdrachtsvorm en minimale bewijsvoering. De implementatie kan starten. Een deskundigenreview blijft vereist voordat agentbegeleiding wordt gebruikt voor belangrijke, complexe of mogelijk gereguleerde financiële beslissingen; die review blokkeert de technische implementatie en tests van v0.1 niet.
