# Welke declaratieve regels heeft de engine nodig en hoe blijven die veilig?

Type: prototype
Status: resolved
Blocked by: 01, 02, 05

## Question

Welke leesbare regelvorm ondersteunt herkenning, validatie, doelgebonden volledigheid en vraagprioritering zonder willekeurige code-uitvoering, en hoe worden regels gevalideerd, geordend, uitgelegd en veilig geactiveerd?

## Answer

Gebruik YAML als menselijk auteursformaat voor vier afzonderlijke, capability-limited regeltypen. De engine parseert YAML zonder custom tags of uitvoerbare constructies naar één getypeerd intern model; stabiele CLI-invoer en -uitvoer blijven JSON.

De vier regeltypen delen alleen de conditievorm en hebben ieder precies één toegestane uitkomst:

- `recognition` leest een herkenningsview en produceert uitsluitend een herleidbaar contextvoorstel of aandachtspunt;
- `validation` leest een validatieview en produceert uitsluitend fouten of waarschuwingen;
- `completeness` leest analysevereisten en produceert uitsluitend een doelgebonden volledigheidsoordeel;
- `question_priority` leest open vragen en analysevereisten en produceert uitsluitend een rangschikking.

Een herkenningsregel kan nooit zelf een voorstel bevestigen, een feit vervangen of een conflict oplossen. Financiële berekeningen blijven gewone, geteste programmacode en worden niet expressief gemaakt in YAML.

Een regel declareert een benoemde, versiegebonden input-view. Die view begrenst beschikbare velden, groeperingen, omvang en toegestane bewerkingen; YAML krijgt geen vrije graphquery of toegang tot de opslagindeling. De gedeelde conditietaal bevat een kleine vaste verzameling logische en vergelijkingsoperatoren. Vertrouwde modules mogen daarnaast pure, deterministische en versiegebonden predicates in code registreren. YAML kan zo'n predicate alleen via haar stabiele identifier en gevalideerde argumenten aanroepen; zij kan geen code definiëren.

Alle toepasselijke regels worden deterministisch uitgevoerd. Er is geen algemene `first_match` en bestandsvolgorde heeft geen betekenis. Uitkomsten worden per type gecombineerd: herkenningen blijven afzonderlijke voorstellen of worden op een expliciete semantische sleutel gededupliceerd, alle validatiediagnoses blijven zichtbaar en alle volledigheidsvereisten tellen mee. Vragen worden eerst gerangschikt op `blocking`, `required`, `helpful` of `optional`, daarna op een modulespecifieke score van 0–100 en ten slotte deterministisch op ouderdom en regel-ID. Alleen een expliciete analysevereiste kan een vraag `blocking` maken.

Regels worden als complete, versiegebonden modulepakketten beheerd. Een agent mag een pakket voorstellen, maar activatie vereist achtereenvolgens syntactische en semantische validatie, compatibiliteitscontrole met de volledige actieve regelset, een effectvrije preview en expliciete gebruikersactivatie. De engine wisselt daarna atomair één manifest met moduleversies en checksums om; losse regels worden niet afzonderlijk geactiveerd. De verwachte actieve manifestversie voorkomt het overschrijven van een gelijktijdige wijziging en een eerder manifest kan via dezelfde gecontroleerde procedure worden hersteld.

Iedere evaluatie levert een uitlegtrace met pakket-, regel- en predicateversie, gebruikte input-view en per conditie het resultaat. Evaluatie is effectvrij en begrensd. Een falende regel wordt nooit stilzwijgend overgeslagen: validatiefalen blokkeert de betreffende mutatie, volledigheidsfalen verhindert een definitief analyseoordeel en herkenning of vraagprioritering mag alleen overige resultaten met de expliciete status `incomplete` retourneren. Een regelfout veroorzaakt nooit een gedeeltelijke contextmutatie.

Prototype primary source: branch `prototype/declarative-rule-model`, commit `95c83b6`, path `.scratch/financial-context-engine-v0-1/assets/declarative-rule-model-prototype/`.
