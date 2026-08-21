# Tally-lessen voor Financial Context Engine v0.1

Onderzocht op 20 augustus 2026 tegen de actuele officiële documentatie en Tally-broncommit [`2dc309c`](https://github.com/davidfowl/tally/tree/2dc309c6aeb61e992cc264cf57c786de74fa63ce). De lokale Tally-budgetmap is alleen gebruikt om te controleren of de gedocumenteerde conventies ook in werkelijk gebruik terugkomen; zij is geen bron voor algemene Tally-claims.

## Kort antwoord

Neem Tally's **samenwerkingsmodel** normatief over, niet zijn transactiespecifieke domeinmodel of concrete Python/DSL-implementatie. De kernformule is: lokale bestanden als controleerbare input, een deterministische engine die waarneemt en rekent, een optionele agent die voorstellen doet, een contextbewuste CLI die steeds de volgende stap benoemt, en uitleg die iedere uitkomst naar bron en regel terugleidt.

Voor de Financial Context Engine moet die formule strenger worden gemaakt: de agent schrijft nooit canonieke context, ontdekkingen worden voorstellen, financiële feiten vereisen bevestiging, bronobservaties blijven onveranderlijk, en “klaar” betekent voldoende context voor een gekozen analyse in plaats van alles geclassificeerd.

## Wat Tally concreet doet

- **Local/file-first en agent-onafhankelijk.** Tally noemt zichzelf een lokale rule engine; de agent is de operator die regels schrijft. De projectmap bevat gewone configuratie-, regel- en databestanden en vereist geen database of cloudservice. Iedere command-line-agent kan dezelfde CLI bedienen. Bronnen: [README](https://github.com/davidfowl/tally/blob/main/README.md), [productpagina](https://tallyai.money/), [Guide](https://tallyai.money/guide.html).
- **Een gesloten feedbacklus.** `workflow` detecteert de toestand van de projectmap en stuurt naar inspecteren, onbekenden ontdekken of output genereren. `discover --format json` groepeert onbekenden, ordent ze op uitgavenimpact en geeft voorbeelden plus regelvoorstellen terug; de agent vult regels aan en herhaalt de lus. Bronnen: [Guide — workflow](https://tallyai.money/guide.html#the-workflow-command), [`workflow.py`](https://github.com/davidfowl/tally/blob/2dc309c6aeb61e992cc264cf57c786de74fa63ce/src/tally/commands/workflow.py), [`discover.py`](https://github.com/davidfowl/tally/blob/2dc309c6aeb61e992cc264cf57c786de74fa63ce/src/tally/commands/discover.py).
- **Smalle commando's met menselijke én machineleesbare uitvoer.** `inspect`, `discover`, `explain`, `diag`, `up` en `reference` hebben ieder één herkenbare taak. JSON is beschikbaar voor agents; HTML, CSV, Markdown, summary en oplopende verbosity bedienen mensen en diagnostiek. `--diff` toont wijzigingen sinds een vorige run. Bronnen: [Formats — CLI commands](https://tallyai.money/formats.html#cli-commands), [Guide — key commands](https://tallyai.money/guide.html#key-commands-for-ai-agents).
- **Bronnormalisatie is declaratief.** `settings.yaml` beschrijft databronnen, kolommen, datum- en bedragconventies en custom velden; `inspect` helpt de gebruiker een formaat te vinden. Daarmee blijft bankspecifieke invoer aan de rand van de analyse. Bron: [Formats](https://tallyai.money/formats.html).
- **Regels zijn leesbaar, begrensd en deterministisch.** `merchants.rules` gebruikt een kleine expressietaal voor matches, categorieën, tags en transforms. De parser valideert eigenschappen en expressies en rapporteert regelnummers. De standaardconflictafhandeling is “first matching categorization rule wins”; tag-only rules vormen een afzonderlijke tweede pass. Bronnen: [Reference](https://tallyai.money/reference.html), [`merchant_engine.py`](https://github.com/davidfowl/tally/blob/2dc309c6aeb61e992cc264cf57c786de74fa63ce/src/tally/merchant_engine.py).
- **Uitleg is een eersteklas bediening.** `explain -vv` toont waarom iets geclassificeerd is en welke regel won; verbose JSON bevat classification reasoning. Transforms bewaren bovendien oorspronkelijke waarden als `_raw_<field>`. Bronnen: [Guide — explain](https://tallyai.money/guide.html#explain-a-classification), [Reference — field transforms](https://tallyai.money/reference.html#field-transforms).
- **Afgeleide output is opnieuw te bouwen.** De invoer en regels zijn de blijvende projectinhoud; rapporten en exports volgen deterministisch uit een nieuwe run. Tally houdt categorieën bewust door de gebruiker definieerbaar en levert meerdere views op dezelfde transacties. Bronnen: [Quick Start](https://tallyai.money/quickstart.html), [Guide — customizing categories](https://tallyai.money/guide.html#customizing-categories), [Reference — views rules](https://tallyai.money/reference.html#views-rules).

## Rechtstreeks normatief overnemen

1. **Engine en agent zijn los gekoppeld.** De engine moet volledig via de CLI bruikbaar en testbaar zijn; een agent is een optionele operator, niet de runtime.
2. **Canonical-input/derived-output.** Canonieke context, gevalideerde regels en bronregistraties staan in lokale, leesbare, schema-gevalideerde bestanden. Indexen, analyses, projecties en rapporten zijn reproduceerbare afgeleiden.
3. **Één contextbewuste workflow-ingang.** Een `workflow`-achtig commando inspecteert de lokale toestand en retourneert gestructureerd: huidige fase, blockers, eerstvolgende toegestane acties en waarom die relevant zijn.
4. **Smalle CLI-capabilities met JSON-contracten.** Houd ten minste de concepten `inspect`, `import`, `discover`, `validate`, `explain`, `analyze` en `workflow` apart. Menselijke uitvoer mag rijk zijn; JSON moet stabiel, versieerbaar en zonder decoratieve terminaltekst zijn.
5. **De discovery-loop.** Laat de engine onvolledigheid en patronen vinden, bundelen en prioriteren; laat een mens of agent vervolgens voorstellen uitwerken; valideer en herbereken daarna deterministisch.
6. **Explainability by construction.** Iedere afleiding of analyse kan minimaal haar bronobservaties, toegepaste regels en versies, gekozen pad, uitgesloten alternatieven, aannames en rekenstappen tonen. “Explain” is geen achteraf gegenereerde tekstsamenvatting.
7. **Een veilige declaratieve regellaag.** Een kleine, parseerbare taal/configuratie met bekende operators, expliciete prioriteit, schema- en semantische validatie, precieze foutlocaties en geen willekeurige code-uitvoering.
8. **Diagnostiek en self-documentation.** Fouten zeggen wat ontbreekt en welke actie dit oplost; de CLI kan haar actuele schema's, regelreferentie en voorbeelden zelf tonen, zodat een agent niet op verouderde externe kennis hoeft te vertrouwen.
9. **Ongewijzigd bronbewijs.** Bewaar de ruwe observatie naast elke normalisatie of afleiding. Nieuwe imports en regelwijzigingen moeten via een dry-run/diff controleerbaar zijn.
10. **Versieerbare compatibiliteit.** Gepersonaliseerde context en regels leven langer dan een enginerelease. Schema- en rule-contracten krijgen daarom expliciete versies, gecontroleerde migraties en regressietests; nieuwe semantiek verandert bestaand gedrag niet stilzwijgend. Tally hanteert dezelfde onderhoudsdiscipline voor settings en rule matching in zijn [maintainer-instructies](https://github.com/davidfowl/tally/blob/2dc309c6aeb61e992cc264cf57c786de74fa63ce/CLAUDE.md).

## Aangepast overnemen

| Tally-patroon | Aanpassing voor de contextengine |
|---|---|
| Agent schrijft direct in `merchants.rules` | Een agent mag regel- en contextmutaties alleen **voorstellen**. De engine parseert, valideert, toont impact en activeert via een expliciet commando. Alleen bevestigde voorstellen mogen canonieke financiële feiten maken. |
| `discover` retourneert onbekende merchants, op totale uitgaven gesorteerd | `discover` retourneert typed contextvoorstellen en ontbrekende context, geprioriteerd op waarde voor het actieve doel, risico, onzekerheid en inspanning; elk voorstel bevat bewijs en een voorgestelde vervolgvraag. |
| Alles gecategoriseerd = workflow klaar | “Klaar” is altijd `sufficient_for(<analysis>)`; de minimale basiscontext kan bruikbaar zijn terwijl andere analyses expliciete blockers houden. |
| Eén regel classificeert een transactie | Een afleidingsregel produceert een **claim/proposal met provenance en confidence**, geen feit. Regels mogen meerdere compatibele claims leveren; conflicten worden zichtbaar en niet stil overschreven. |
| Brontransforms muteren genormaliseerde transactievelden en bewaren `_raw_*` | Bronrecords zijn immutable observations. Normalisaties worden nieuwe, herleidbare representaties/assertions; de oorspronkelijke waarde blijft altijd adresseerbaar. |
| Door gebruiker gekozen categorieën en views | Houd vrije labels/views mogelijk, maar leg identiteit, tijd, ownership, provenance, certainty en voorstelstatus vast in een stabiel EngineCore-meta-model. Land- of producttypen horen in modules, niet in vrije categorievelden van de kern. |
| `--diff` op rapportuitvoer | Maak impact preview verplicht vóór mutaties die feiten, relaties of actieve regels veranderen; toon zowel graph-diff als gevolgen voor relevante analyses. |

## Bewust niet overnemen

- **Geen directe canonical-file writes door de agent.** Tally kan dit verdragen omdat regels classificatieconfiguratie zijn; in deze engine kunnen wijzigingen financiële waarheid creëren.
- **Geen universele `first_match`-semantiek.** Die is eenvoudig voor merchantcategorisatie, maar te impliciet voor meerdere bewijsbronnen, eigendom, tijd, tegenstrijdige claims en zekerheid. Gebruik expliciete rule priority plus conflict policies per afleidingstype.
- **Niet Tally's concrete DSL kopiëren.** De goede les is een kleine declaratieve taal; de precieze syntax, Python-parser en experimentele `most_specific`-heuristiek zijn geen architectuurcontract voor v0.1.
- **Geen vlak transaction/category-model als contextmodel.** Tally-output is een waardevolle adapterbron, maar de contextengine modelleert entiteiten, relaties, perioden, bronnen, claims, bevestigingen, scenario's en aannames.
- **Geen HTML-report of specifieke implementatietaal in EngineCore.** Presentatie en programmeertaal zijn verwisselbare keuzes; alleen de CLI/JSON- en modulecontracten worden normatief.
- **Geen onbeperkte transforms of verrijkingscode in agentgeschreven regels.** Financiële berekeningen blijven geteste code; regels selecteren, valideren, prioriteren of stellen afleidingen voor.

## Normatieve ontwerpzin

> Financial Context Engine v0.1 is een local-first, file-first en deterministische CLI-engine waarin adapters onveranderlijke observaties normaliseren, declaratieve regels herleidbare voorstellen produceren, alleen gevalideerde en waar nodig bevestigde mutaties canonieke context wijzigen, en iedere workflowstap of analyse als versieerbare JSON inclusief bewijs, aannames, blockers en uitleg beschikbaar is—met of zonder agent en met of zonder Tally.

## Lokale plausibiliteitscontrole

De read-only Tally-budgetmap onder `/Users/arjenvanputten/dev/prive/finance-analyse/my-budget/tally` volgt dezelfde conventies: `settings.yaml` verwijst naar databronnen en losse `merchants.rules`/`views.rules`; merchantregels zijn geordend en declaratief; views gebruiken statistieken zoals `months` en `cv`; JSON-output is afgeleid. De lokaal genoemde CLI was in deze omgeving niet uitvoerbaar omdat het `tally`-programma niet in de actieve `uv`-omgeving aanwezig was, dus CLI-gedrag is uitsluitend op actuele officiële bronnen gebaseerd.
