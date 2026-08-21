# Wat behoort tot de EngineCore en welke graph-invarianten bewaakt die?

Type: grilling
Status: resolved

## Question

Wat is het minimale, land- en domeinonafhankelijke meta-model voor identiteit, entiteiten, relaties, tijd, herkomst, zekerheid, voorstellen, bevestiging en mutaties, en welke invarianten moet de EngineCore altijd afdwingen?

## Answer

De EngineCore beheert een klein, land- en domeinonafhankelijk meta-model:

- **Entity** — een stabiele identifier en een technisch type; veranderlijke financiële betekenis staat niet als stil overschrijfbaar profielveld op de entiteit.
- **Assertion** — een bewering over een eigenschap of relatie, met dezelfde grondvorm voor beide.
- **Source reference / evidence** — de herleidbare oorsprong in een bronrecord, gebruikersuitspraak of eerdere beweringen plus de toegepaste regel- of berekeningsversie.
- **Identity proposal** — een expliciet voorstel dat bronreferenties of entiteiten dezelfde werkelijkheid vertegenwoordigen.
- **Mutation** — de atomaire, gevalideerde wijzigingsset met actor, reden en unieke mutatie-ID.

Iedere bewering bevat verplicht:

- geldigheidstijd en registratietijd;
- kennistype: `observed`, `user_provided`, `inferred`, `calculated`, `assumed` of `projected`;
- verificatiestatus: `proposed`, `confirmed`, `disputed`, `rejected` of `superseded`;
- een herkomstketen;
- verwijzingen naar bestaande entiteiten en, waar relevant, de bewering die zij vervangt.

De EngineCore handhaaft de volgende invarianten:

1. Identifiers zijn stabiel en beweringen mogen niet naar ontbrekende entiteiten verwijzen.
2. Een bewering zonder geldige tijdsdimensies, kennistype, verificatiestatus of herkomst wordt geweigerd.
3. Tegenstrijdig bronbewijs mag naast elkaar bestaan, maar exclusieve beweringen met overlappende geldigheid mogen niet gelijktijdig actieve waarheid zijn. Relevante analyses worden bij een onopgelost conflict geblokkeerd.
4. De EngineCore voert generieke constraints uit; domein- en jurisdictiemodules declareren waar cardinaliteit, typebeperkingen, tijdsoverlap of vereiste totalen gelden.
5. Entiteiten worden conservatief samengevoegd: bevestiging is vereist, behalve bij een door een module aantoonbaar uniek en betrouwbaar verklaarde sleutel.
6. Een contextvoorstel wordt nooit zonder geldige bevestiging of expliciete deterministische regel een bevestigd financieel feit.
7. Kennistype, verificatiestatus en eventuele modulespecifieke detectiescore blijven gescheiden; er bestaat geen universele confidence-score.
8. Berekende, aangenomen en geprojecteerde kennis wordt nooit als waargenomen financieel feit voorgesteld of gebruikt om feiten te overschrijven.
9. Privacybewuste bewijsverwijdering markeert resterende beweringen als niet langer verifieerbaar.
10. Contextmutaties zijn logisch atomair. v0.1 gebruikt één lokale schrijver, valideert de gehele wijziging vooraf en gebruikt een mutatie-ID om retries idempotent te maken. Multi-usertransacties vallen buiten deze kern.

Buiten de EngineCore blijven concrete financiële entiteiten, Nederlandse producttypen, opslagindeling, regel-DSL, berekeningen, CLI-workflow en presentatie. Die worden door volgende tickets bepaald.
