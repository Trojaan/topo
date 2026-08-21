# Welke lessen uit Tally moeten normatief worden voor de engine?

Type: research
Status: resolved

## Question

Welke concrete architectuurmechanismen, CLI-patronen, bestandsconventies, workflowstappen en uitlegbaarheidsprincipes gebruikt Tally momenteel, en welke daarvan moeten we rechtstreeks overnemen, aanpassen of bewust niet overnemen voor Financial Context Engine v0.1?

## Answer

Neem Tally's samenwerkingsmodel normatief over: een local/file-first en deterministische engine die zonder agent werkt; een contextbewuste workflow; smalle CLI-commando's met stabiele JSON-uitvoer; een geprioriteerde discovery-loop; begrensde declaratieve regels; ingebouwde validatie, diagnostiek, diff en herleidbare uitleg; en versieerbare compatibiliteit.

Pas dit voor financiële context aan door discovery altijd voorstellen met bewijs en zekerheid te laten opleveren, canonieke mutaties uitsluitend via gevalideerde engine-commando's te laten verlopen, bevestiging te eisen waar een financieel feit ontstaat, ruwe observaties immutable te houden en volledigheid per analyse te bepalen.

Neem Tally's merchantgerichte model, directe agentwrites, universele `first_match`, concrete DSL/Python-opzet en rapport-UI niet over als kernarchitectuur.

Research asset: [Tally-lessen voor Financial Context Engine v0.1](../assets/tally-architecture-lessons.md)
