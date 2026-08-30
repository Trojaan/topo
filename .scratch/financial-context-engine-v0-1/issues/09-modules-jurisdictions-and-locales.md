# Welke extensiecontracten houden domeinen, landen en talen uit de kern?

Type: grilling
Status: resolved
Blocked by: 02, 03, 04

## Question

Welke verantwoordelijkheden en contracten gelden voor domeinmodules, analysemodules, regelmodules, bron- en opslagadapters, jurisdictiemodules en vertaalbare presentatielagen, zodat Nederland v0.1 kan zijn zonder toekomstige landen of talen te blokkeren?

## Answer

Gebruik expliciete, versiegebonden capabilitycontracten en houd financiële betekenis, uitvoering, opslag en presentatie van elkaar gescheiden. v0.1 laadt uitsluitend meegeleverde, vertrouwde codemodules uit een expliciete modulecatalogus. Willekeurige externe codeplug-ins, installatie op runtime en plug-insandboxing vallen buiten v0.1; declaratieve regelpakketten blijven wel veilig aanpasbaar.

Iedere codemodule heeft minimaal een stabiele `module_id`, eigen `module_version`, ondersteunde EngineCore-contractversies, expliciete dependencies en een opsomming van geleverde capabilities. Dependencies vormen een acyclische graph en worden vóór volledig openen gevalideerd. Modules mogen alleen publieke, versiegebonden capabilities van andere modules gebruiken en nooit hun interne schema's aanpassen.

### Verantwoordelijkheden per extensiepunt

- Een **domeinmodule** bezit de universele betekenis van één financieel domein: entiteits- en relatieclassificaties, toegestane beweringsvormen, generieke constraints en begrensde input-views. Domeinmodules composeren andere publieke domeincontracten. Zij bevatten geen landspecifieke regels, presentatie, fysieke opslag of analyses.
- Een **jurisdictiemodule** legt productclassificaties, betekenisregels en conventies van één rechtsgebied als namespaced overlay op universele domeinbegrippen. Zij mag classificaties, beweringsvormen en constraints toevoegen, maar verandert geen basisschema. Jurisdictie en taal zijn onafhankelijk: `jurisdiction.nl` kan met een Engelstalige presentatielaag worden gebruikt.
- Een **analysemodule** declareert haar analyse-ID, contract- en berekeningsversie, begrensde input-view, analysevereisten, uitvoerschema en ondersteunde jurisdicties. Zij is deterministisch en effectvrij, produceert uitsluitend herleidbare analyseresultaten en mag geen voorstellen indienen, feiten bevestigen, regels activeren of context muteren.
- Een vertrouwde **regelmodule** registreert de toegestane input-views, predicates, uitkomsttypen en schema's. Een afzonderlijk **regelpakket** bevat uitsluitend declaratieve YAML-regels binnen die capabilities; het kan geen code, vrije queries of predicates toevoegen. Activatie blijft gevalideerd, effectvrij vooraf bekeken en expliciet geautoriseerd.
- Een **bronadapter** vertaalt één externe bron naar genormaliseerde bronrecords en bewijs met stabiele bronidentiteit. Zij mag alleen letterlijke bronvelden als waarneming aanbieden, kent de canonieke opslag niet en muteert de context niet. Classificatie of afgeleide financiële betekenis wordt een voorstel; uitsluitend EngineCore valideert en importeert atomair.
- Een **opslagadapter** levert duurzame primitieve operaties voor lezen, staging, exclusieve locking, atomair publiceren en opruimen. EngineCore blijft eigenaar van generaties, checksums, validatie, optimistic concurrency, herstel en mutatiehistorie. Een adapter mag dus geen alternatieve financiële of historische semantiek introduceren.
- Een **presentatielaag** is betekenisvrije data voor labels, uitlegtemplates en locale-afhankelijke datum-, getal- en valutaopmaak. Zij bepaalt geen classificaties, constraints, standaardvaluta, berekeningen of vereisten. Canonieke en machineleesbare JSON blijft locale-onafhankelijk en valt bij ontbrekende vertaling terug op stabiele technische identifiers.

### Compatibiliteit en levenscyclus

Een canonieke generatie pint de exacte domein- en jurisdictiemodules en actieve regelpakketten met hun versies en checksums. Ontbreekt een vereiste module, dan blijven generieke entiteiten, ruwe beweringen en export leesbaar, maar worden afhankelijke validatie, mutaties en analyses geblokkeerd. Onbekende classificaties of constraints worden nooit stilzwijgend genegeerd.

Toevoegen, upgraden en verwijderen van een semantische module gebeurt uitsluitend via een expliciete, vooraf bekijkbare pakketmigratie die bij succes een nieuwe generatie publiceert. Een incompatibele upgrade laat de bestaande generatie intact. Verwijderen mag alleen wanneer geen canonieke data meer van de module afhankelijk is of wanneer een expliciete migratie die betekenis omzet. Een module wordt nooit automatisch geactiveerd omdat data haar identifier noemt.

Niet ieder extensiepunt bindt aan de contextgeneratie:

- domeinmodules, jurisdictiemodules en actieve regelpakketten worden per generatie gepind;
- bronadapter en versie worden per geïmporteerd bronrecord in de herkomst vastgelegd en hoeven later niet aanwezig te zijn om dat bewijs te lezen;
- opslagadapter en opslagcontract horen bij het contextpakket;
- analyse- en berekeningsversie horen bij het analyseresultaat en veranderen de context niet;
- locale en taalpakketversie horen uitsluitend bij mensleesbare uitvoer.

Deze grenzen maken Nederland de eerste meegeleverde jurisdictie zonder EngineCore, universele domeinen of canonieke identifiers aan Nederland of de Nederlandse taal te koppelen.
