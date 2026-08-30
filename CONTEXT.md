# Topo — begrippen

## Topo

De productnaam van de financiële contextengine. Topo helpt een gebruiker diens eigen financiële werkelijkheid in kaart te brengen en presenteert zich niet als financieel adviseur.

## Financiële contextengine

Een zelfstandige engine die samen met een gebruiker diens financiële werkelijkheid gestructureerd vastlegt, controleert, aanvult en bevraagbaar maakt. De engine kan zonder Tally functioneren en is geen SaaS-product, dashboard of adviesdienst.

## Financiële contextgraph

Het samenhangende model van financiële feiten, relaties, aannames, afleidingen, doelen en gebeurtenissen van een persoon of huishouden. Graph duidt hier de vorm van het domein aan, niet een verplichte graphdatabase.

## Canonieke contextbestanden

De leesbare, lokale en schema-gevalideerde bestanden die de bron van waarheid voor de financiële contextgraph vormen. Entiteiten en relaties hebben stabiele identifiers. Indexen, caches en graphweergaven worden hieruit afgeleid en zijn zelf niet canoniek. Een database kan later via een opslagadapter worden toegevoegd.

## Contextmutatie

Een gevalideerde wijziging aan de canonieke contextbestanden. Alleen de financiële contextengine mag een contextmutatie uitvoeren. Een agent kan gegevens lezen, contextvoorstellen formuleren en engine-tools aanroepen, maar schrijft nooit rechtstreeks financiële feiten of relaties weg. Regels worden eveneens gevalideerd voordat de engine ze activeert.

## Financieel inzicht

Een herleidbare uitkomst zoals een berekening, totaal, trend, afwijking, ontbrekend of verouderd gegeven, risico-indicator of scenariovergelijking. Het inzicht verwijst naar de gebruikte feiten, aannames en rekenstappen. Het schrijft geen productkeuze of handeling voor.

## Financieel advies

Een normatieve aanbeveling over wat iemand financieel behoort te doen of welk product diegene behoort te kiezen. Financieel advies valt buiten de financiële contextengine: de engine levert uitsluitend herleidbare feiten, berekeningen, onzekerheden en scenario's. Een agentoperator mag daarvan wel afzonderlijke agentbegeleiding maken, maar die begeleiding wordt nooit een engine-uitkomst of financieel feit.

## Agentbegeleiding

Een niet-bindende interpretatie, vergelijking of voorzichtige aanbeveling die een agentoperator baseert op expliciete doelen, herleidbare engine-uitkomsten en zichtbaar gemaakte aannames en onzekerheden. De agent houdt feiten, berekeningen en zijn aanbeveling herkenbaar gescheiden. In versie 0.1 mag hij opties of productcategorieën bespreken, maar geen specifiek financieel product aanbevelen. Bij een belangrijke, ingewikkelde of mogelijk gereguleerde keuze markeert hij zijn begeleiding als voorlopig en verwijst hij voor besluitvorming naar een bevoegde financiële of fiscale deskundige.

## Basiscontext

De minimale financiële context waarmee de engine een algemeen huishoudbeeld kan opbouwen en zinvolle vervolgstappen kan voorstellen. De basiscontext hoeft niet voldoende te zijn voor iedere analyse.

## Doelgebonden volledigheid

De mate waarin de beschikbare en voldoende actuele context voldoet aan de expliciete vereisten van één analyse. Volledigheid is niet absoluut: dezelfde graph kan voldoende zijn voor een nettovermogensberekening en onvoldoende voor een pensioenprojectie.

## Analysevereiste

Een expliciete beschrijving van welke feiten, tijdsdekking, zekerheid en aannames een analyse minimaal nodig heeft. De engine gebruikt analysevereisten om ontbrekende context te prioriteren en om aan te geven of een uitkomst volledig, voorlopig of niet verantwoord berekenbaar is.

## Doelgebonden actualiteit

Het oordeel van een analysemodule of de beschikbare geldigheids- en registratietijd voor één analysevereiste bruikbaar is. EngineCore bewaart tijd maar kent geen universele status `stale`; dezelfde bewering kan voor de ene analyse bruikbaar en voor een andere onvoldoende actueel zijn.

## Analyseresultaatstatus

De doelgebonden bruikbaarheid van één resultaatonderdeel: `complete` wanneer alle vereiste context geldig en actueel is, `provisional` wanneer het resultaat berekenbaar is met expliciete ontbrekende, verouderde of aangenomen invoer, en `unavailable` wanneer het niet verantwoord berekenbaar is. Een probleem blokkeert alleen de getroffen resultaatonderdelen; de engine verzint nooit ontbrekende waarden en de contextinventarisatie blijft altijd beschikbaar.

## Analysebereik

De expliciet gekozen persoon of het expliciet gekozen huishouden waarop een analyse betrekking heeft. Een huishoudanalyse gebruikt uitsluitend expliciete huishoudelijke toerekeningen; onbekende of niet-toegerekende posten blijven afzonderlijk zichtbaar en maken getroffen totalen voorlopig zonder een verdeling te veronderstellen.

## Analysepeildatum

De expliciete datum waarvoor een analyse de context beoordeelt of een toestand berekent. Transactiegebonden analyses gebruiken daarnaast een expliciete halfopen analyseperiode met een inclusieve begindatum en exclusieve einddatum; een eventueel door de CLI ingevulde datum wordt altijd in verzoek en resultaat vastgelegd.

## Analyseresultaat

De versiegebonden en deterministisch identificeerbare uitkomst van één analyseverzoek, met bereik, tijdsafbakening, status per onderdeel, gebruikte beweringen en bronreferenties, aannames, rekenstappen en tussenuitkomsten. Ontbrekende, verouderde of conflicterende vereisten en een mogelijke vervolgvraag blijven onderdeel van het resultaat, ook wanneer de mensleesbare weergave ze samenvat.

## Analyse

Een deterministische bewerking die financiële inzichten uit de contextgraph produceert en vooraf haar analysevereisten declareert. De eerste analyseset bestaat uit contextinventarisatie, herkenning van inkomsten- en uitgavenpatronen, huishoudelijke maandcashflow, nettovermogen en een eenvoudige scenariovergelijking.

## Contextinventarisatie

Een altijd beschikbare analyse die per beoogde analyse toont welke vereiste context aanwezig, ontbrekend, verouderd, conflicterend of niet toegerekend is en wat daarvan de impact en eerstvolgende doelgebonden vraag is. Zij geeft beschrijvende aantallen per financieel domein, maar geen algemeen volledigheidspercentage.

## EngineCore

De kleine, domeinoverschrijdende kern die identiteit, relaties, tijd, herkomst, zekerheid, contextvoorstellen, bevestiging en contextmutaties beheert. De EngineCore herkent zelf geen financiële patronen: agentoperators en deterministische regelmodules kunnen via hetzelfde voorstelcontract kandidaatpatronen aanleveren. Financiële verdieping hoort niet rechtstreeks in de EngineCore.

## Domeinmodule

Een uitbreidbare module die de universele betekenis van één financieel domein bezit, zoals rekeningen, hypotheken of pensioen. Zij declareert classificaties, toegestane beweringsvormen, generieke constraints en begrensde input-views zonder de EngineCore te verbreden. Domeinmodules composeren uitsluitend elkaars publieke, versiegebonden begrippen en bevatten geen landspecifieke betekenis.

## Analysemodule

Een uitbreidbare, effectvrije module die analysevereisten, begrensde input-views, deterministische berekeningen en herleidbare uitkomsten voor een of meer analyses bevat. Zij leest context maar dient geen voorstellen in en muteert geen financiële context.

## Regelmodule

Een vertrouwde uitbreiding die de toegestane input-views, predicates, uitkomsttypen en schema's voor validatie, afleiding of prioritering registreert. Aanpasbare declaratieve regels leven in afzonderlijke regelpakketten en kunnen geen code, vrije queries of nieuwe predicates toevoegen.

## Jurisdictiemodule

Een uitbreiding voor één rechtsgebied met financiële productclassificaties, betekenisregels en conventies die niet universeel zijn. Zij legt landspecifieke betekenis als overlay op universele domeinbegrippen en verandert hun basisschema's niet. Een jurisdictieclassificatie hoort alleen in de module wanneer zij minimaal één landspecifieke betekenisregel, toegestane relatie of validatieconstraint activeert; een herkenbare productnaam zonder semantisch verschil blijft bronmetadata of presentatietekst. De jurisdictie staat los van de presentatietaal: Nederlandse financiële context kan bijvoorbeeld met Engelstalige labels worden weergegeven. Versie 0.1 richt zich op Nederland; de EngineCore blijft jurisdictieneutraal zodat andere rechtsgebieden later als afzonderlijke jurisdictiemodule kunnen worden toegevoegd.

## Jurisdictiekwalificatie

Een expliciet bevestigde, tijdsgebonden aanduiding dat een financieel object binnen één rechtsgebied een bijzondere juridische, fiscale of gebruiksgebonden status heeft. De engine bewaart deze aanduiding om conservatieve aannames te doen, zoals vermogen niet automatisch als vrij beschikbaar behandelen. Versie 0.1 stelt de wettelijke geldigheid niet zelfstandig vast, berekent de verdere fiscale of juridische gevolgen niet en geeft daarover geen advies.

## Opslagadapter

Een afgebakende leverancier van duurzame opslagoperaties zoals lezen, staging, exclusieve vergrendeling en atomair publiceren. De opslagadapter bepaalt niet de betekenis van generaties, validatie, herstel of mutatiehistorie; die blijft bij de EngineCore. Versie 0.1 gebruikt lokale bestanden, terwijl een latere versleutelde of databaseadapter hetzelfde logische opslagcontract kan uitvoeren.

## Presentatielaag

Een betekenisvrije verzameling labels, uitlegtemplates en locale-afhankelijke opmaak voor mensleesbare uitvoer. Zij verandert geen financiële classificaties, constraints, standaardvaluta, berekeningen of analysevereisten. Presentatietaal staat los van jurisdictie en machineleesbare contracten blijven locale-onafhankelijk.

## Technische identifier

Een stabiele Engelstalige naam in schema's, bestanden en toolcontracten. Technische identifiers veranderen niet wanneer de presentatietaal verandert. Documentatie en agentgesprekken gebruiken in eerste instantie Nederlandse domeintermen; vertaalbare labels en uitleg vormen een afzonderlijke presentatielaag.

## Local-first

De eigenschap dat contextbestanden, regels, validatie, berekeningen en uitvoer lokaal en zonder netwerktoegang kunnen functioneren. Netwerktoegang is standaard niet nodig en kan later alleen via een expliciete adapter plaatsvinden.

## Agentoperator

Een optionele maar beoogde gesprekspartner die gebruikersintentie begrijpt, vragen stelt, voorstellen formuleert, agentbegeleiding geeft en engine-tools orkestreert. Vrije tekst die de agentoperator interpreteert wordt altijd eerst een expliciet, gestructureerd contextvoorstel; de interpretatie of begeleiding wordt nooit rechtstreeks een bevestigd financieel feit. De engine blijft zonder agent deterministisch bruikbaar voor import, validatie, mutatie en analyse. De agentoperator behoort niet tot de bron van financiële waarheid.

## CLI-contract

De primaire technische interface van versie 0.1. Commando's accepteren en produceren stabiele, schema-gevalideerde JSON naast mensleesbare uitvoer. Hierdoor kunnen mensen en uiteenlopende command-line-agents dezelfde engine gebruiken. Protocollen zoals MCP zijn optionele latere adapters en bepalen de EngineCore niet.

## Declaratieve regel

Een leesbare, niet-willekeurig-uitvoerbare regel voor herkenning, validatie, volledigheid of vraagprioritering. Een agent kan regelwijzigingen voorstellen, waarna de engine ze valideert en activeert.

## Regeltype

De vaste capabilitygrens van een declaratieve regel: herkenning produceert contextvoorstellen of aandachtspunten, validatie produceert diagnoses, volledigheid produceert doelgebonden volledigheidsoordelen en vraagprioritering produceert een rangschikking van open vragen. Een regeltype mag geen uitkomst van een ander type produceren.

## Regelpakket

Een complete, versiegebonden verzameling declaratieve regels van één module die als geheel wordt gevalideerd, vooraf bekeken en expliciet geactiveerd. Losse regels worden niet onafhankelijk actief, zodat onderlinge aannames binnen het pakket intact blijven.

## Input-view

Een benoemde en versiegebonden begrenzing van de financiële context die een declaratieve regel mag lezen. Een input-view maakt beschikbare begrippen en omvang expliciet zonder regels toegang te geven tot de interne opslagindeling of een vrije graphquery.

## Predicate

Een benoemde, deterministische en effectvrije toets die een declaratieve regel in haar conditie mag aanroepen. Een predicate levert uitsluitend een toetsresultaat en kan geen context muteren of regeluitkomsten produceren.

## Regelactivatie

De expliciet door de gebruiker geautoriseerde overgang waarbij een volledig gevalideerd en vooraf bekeken regelpakket onderdeel wordt van de actieve regelset. Een technisch geldige regelwijziging wordt nooit uitsluitend op initiatief van een agent actief.

## Financiële berekening

Een deterministische en geteste bewerking die in gewone programmacode is geïmplementeerd. Berekeningen worden niet in door agents wijzigbare regelbestanden ondergebracht en publiceren hun invoer en rekenstappen voor herleidbaarheid.

## Mutatiehistorie

De lokale, controleerbare geschiedenis van contextmutaties met tijdstip, actor, reden, bron en wijziging. Zij ondersteunt uitleg en herstel, maar is niet onverwijderbaar: gevoelige gegevens moeten expliciet volledig verwijderd of privacybewust gecompacteerd kunnen worden. Git is hiervoor geen vereiste.

## Entiteit

Een stabiel identificeerbaar onderdeel van de financiële contextgraph, zoals een persoon, huishouden of rekening. Een entiteit draagt identiteit en type; veranderlijke financiële betekenis wordt er via beweringen aan gekoppeld en niet stilzwijgend als mutable profielveld overschreven.

## Bewering

Een tijdsgebonden uitspraak over een eigenschap van een entiteit of een relatie tussen entiteiten. Iedere bewering bewaart minimaal haar geldigheid, herkomst, zekerheid en status. Eigenschappen en relaties gebruiken dezelfde grondvorm, zodat historie, gezamenlijke eigendom, onzekerheid en correcties op dezelfde manier worden behandeld.

## Beweringsconflict

De toestand waarin beweringen voor dezelfde exclusieve betekenis en overlappende geldigheidsperiode elkaar tegenspreken. De beweringen en hun bewijs blijven bewaard, maar mogen niet gelijktijdig als actieve waarheid gelden. Een afwijkende waarneming bij een bevestigd patroon is niet vanzelf een beweringsconflict: zij blijft een afzonderlijk aandachtspunt zolang zij het exclusieve feit niet rechtstreeks tegenspreekt. De engine markeert echte conflicten en blokkeert alleen analyses waarvoor het conflict relevant is, totdat een gebruiker of geldige regel het oplost.

## Constraintdeclaratie

Een door een domein- of jurisdictiemodule geleverde betekenisregel, zoals cardinaliteit, toegestane typen, overlappende geldigheidsperioden of een vereist totaal. De EngineCore begrijpt en handhaaft het generieke mechanisme; de module bepaalt op welke financiële begrippen het van toepassing is. Een structureel onmogelijke of tegenstrijdige combinatie blokkeert de contextmutatie. Ontbrekende optionele informatie maakt bestaande context niet ongeldig, maar levert een zichtbaar, doelgebonden aandachtspunt op en beperkt alleen analyses die dat gegeven vereisen.

## Bronreferentie

De blijvende identificatie van een record binnen een bronadapter. Bronreferenties worden aan interne entiteiten gekoppeld maar niet met die entiteiten vereenzelvigd, zodat meerdere bronnen naar hetzelfde object kunnen verwijzen en hun eigen herkomst behouden.

## Identiteitsvoorstel

Een voorstel dat twee bronreferenties of bestaande entiteiten dezelfde financiële werkelijkheid vertegenwoordigen. Samenvoegen vereist bevestiging, tenzij een module een aantoonbaar unieke en betrouwbare sleutel declareert. Een vermoedelijke overeenkomst is nooit voldoende voor automatische samenvoeging.

## Herkomstketen

De verplichte, navolgbare verbinding van een bewering met een bronrecord, een expliciete gebruikersuitspraak of eerdere beweringen plus de versie van de toegepaste regel of berekening. Na privacybewuste verwijdering van bewijs wordt een resterende bewering expliciet als niet langer verifieerbaar gemarkeerd.

## Kennistype

De aard van de kennis in een bewering: waargenomen, door een gebruiker verstrekt, afgeleid, berekend, aangenomen of geprojecteerd. Kennistype staat los van verificatie.

## Verificatiestatus

De workflowtoestand van een bewering: voorgesteld, bevestigd, betwist, verworpen of vervangen. De EngineCore gebruikt geen algemene confidence-score. Een module mag een detectiescore toevoegen, maar die score heeft uitsluitend betekenis binnen die module.

## Geldigheidstijd

De periode waarin een bewering volgens de beschikbare context in de financiële werkelijkheid geldt of gold.

## Registratietijd

Het moment waarop de engine een bewering ontving of vastlegde. Iedere bewering bevat zowel geldigheidstijd als registratietijd, zodat de engine historische situaties en later ontvangen correcties afzonderlijk kan reconstrueren.

## Atomaire contextmutatie

Een wijzigingsset die de engine eerst volledig op een tijdelijk model toepast en valideert en daarna geheel of niet opslaat. Versie 0.1 gebruikt één lokale schrijver en een unieke mutatie-ID om dubbele agentcommando's veilig te herkennen; complexe gelijktijdige multi-usertransacties behoren niet tot de EngineCore.

## Transactiebron

Een optionele bron van geclassificeerde transacties. Tally kan zo'n bron leveren via een adapter, maar is geen interne runtime of verplichte afhankelijkheid van de financiële contextengine.

## Transactie

Een stabiel identificeerbare financiële gebeurtenis die één geldbeweging op precies één rekening vastlegt. Inkomen en uitgave zijn corrigeerbare classificaties; twee transacties kunnen als zijden van dezelfde interne overboeking aan elkaar worden gekoppeld.

## Transactieclassificatie

De minimale analytische betekenis van een transactie: `income`, `expense`, `internal_transfer` of `unclassified`. Bronlabels, categorieën en subcategorieën blijven als verfijning behouden; afgeleide classificaties van een bron zoals Tally worden herleidbare contextvoorstellen die per mapping in een batch kunnen worden bevestigd.

## Terugkerende kasstroom

Een herkenbare of verwachte reeks financiële ontvangsten of betalingen met een bedrag of bandbreedte, frequentie en geldigheidsperiode. Zij kan uit transacties zijn herkend of rechtstreeks zijn bevestigd, maar vervangt de onderliggende transacties niet.

## Inkomstenclassificatie

De corrigeerbare betekenis van een ontvangen transactie of terugkerende kasstroom. Versie 0.1 herkent salaris, vakantiegeld, inkomsten als zelfstandige, pensioenuitkering, sociale uitkering, toeslag, alimentatie, rente en dividend; `jurisdiction.nl` verfijnt AOW en Nederlandse toeslagen terwijl universele inkomsten bij hun domeinmodule blijven. De classificatie ondersteunt het inkomstenoverzicht maar stelt geen recht op een uitkering of toeslag vast en berekent geen belasting.

## Uitgavenclassificatie

De corrigeerbare betekenis van een uitgaande transactie of terugkerende kasstroom. Versie 0.1 gebruikt de kleine universele groepen wonen, boodschappen en huishouden, vervoer, zorg, verzekering, belastingen, kinderopvang en onderwijs, abonnementen, vrije tijd, schuldbetaling en overig. `jurisdiction.nl` kan betekenisvolle Nederlandse vormen zoals zorgverzekeringspremie, gemeentelijke belasting en waterschapsbelasting verfijnen en een hypotheekbetaling aan haar schuld koppelen. De oorspronkelijke broncategorie blijft behouden en een classificatie bepaalt niet of de uitgave wenselijk of fiscaal aftrekbaar is.

## Patroonkandidaat

Een onbevestigd voorstel voor een terugkerende kasstroom, gebaseerd op minimaal drie vergelijkbare transacties of twee bij een jaarlijks patroon. Versie 0.1 herkent wekelijkse, vierwekelijkse, maandelijkse, kwartaal- en jaarfrequenties en bewaart frequentie, verwachte volgende periode, bedrag of bandbreedte, bewijs, afwijkingen en een modulespecifieke detectiescore.

## Gerealiseerde maandcashflow

De herleidbare som van werkelijk geboekte ontvangsten en betalingen binnen één kalendermaand en een expliciete huishoudelijke toerekening. Interne overboekingen tellen niet als inkomen of uitgave; ongeclassificeerde transacties blijven wel in de netto geldbeweging, waardoor het totaal volledig kan zijn terwijl de categorieverdeling voorlopig is.

## Transactiedekking

De aantoonbare beschikbaarheid van transacties voor iedere in een analyse opgenomen rekening gedurende de volledige analyseperiode. Alleen volledige transactiedekking en bekende huishoudelijke toerekening maken een gerealiseerde cashflow volledig; saldoreconciliatie blijft diagnostiek en is geen harde voorwaarde.

## Genormaliseerde maandcashflow

Het actuele structurele maandbeeld waarin bevestigde, geldige terugkerende kasstromen naar maandbasis zijn omgerekend. Vaste bedragen leveren exacte totalen; bandbreedtes leveren minimum en maximum en alleen een expliciet bevestigd typisch bedrag mag een verwacht totaal vormen.

## Maandnormalisatie

De deterministische omrekening van een terugkerende kasstroom naar maandbasis: wekelijks × 52 ÷ 12, vierwekelijks × 13 ÷ 12, maandelijks × 1, per kwartaal ÷ 3 en jaarlijks ÷ 12. Geldberekeningen blijven decimaal en afronding vindt alleen plaats voor gepresenteerde eindbedragen volgens de valuta.

## Bronadapter

Een afgebakende vertaler die gegevens uit een externe vorm omzet naar genormaliseerde bronrecords en bewijs, zonder dat het domeinmodel afhankelijk wordt van die bron. Een expliciet geautoriseerde bronadapter mag letterlijke bronvelden, zoals bedrag, valuta, boekingsdatum en bronreferentie, zonder bevestiging per record als waarneming aanbieden; uitsluitend de EngineCore valideert en importeert die atomair. Classificaties, identiteitskoppelingen en andere financiële betekenis die niet letterlijk uit de bron volgen blijven contextvoorstellen. Een broncorrectie overschrijft het eerdere record niet, maar wordt als herleidbare opvolger vastgelegd. Versie 0.1 ondersteunt handmatige invoer via het agentgesprek, een Tally-adapter en een generieke adapter voor genormaliseerde CSV- of JSON-transacties.

## Contextvoorstel

Een mogelijke toevoeging aan de financiële contextgraph die een agentoperator of deterministische regelmodule uit brongegevens afleidt en via een gedeeld voorstelcontract bij de EngineCore indient. Terugkerende transacties kunnen bijvoorbeeld leiden tot voorstellen voor vaste inkomsten, vaste uitgaven, variabele kosten of andere financiële patronen. Het voorstel benoemt zijn producent en bewaart zijn bewijs, periode, bedrag of bandbreedte en producent-specifieke zekerheid. De EngineCore valideert de vorm en herleidbaarheid, maar voert de patroonherkenning niet zelf uit. Een contextvoorstel is nog geen bevestigd financieel feit. Bij een expliciete gebruikerscorrectie blijft het oorspronkelijke voorstel onveranderd als gecorrigeerd spoor bewaard; de correctie vormt nieuw gebruikersbewijs voor de bevestigde bewering.

## Bevestigd financieel feit

Een contextvoorstel dat de gebruiker expliciet heeft bevestigd, of bewust gestructureerde informatie die de gebruiker rechtstreeks als feit bij de EngineCore heeft ingediend. Vrije tekst die een agentoperator heeft geïnterpreteerd blijft eerst een contextvoorstel en vereist bevestiging van de gestructureerde betekenis. De engine promoveert afgeleide patronen nooit zelfstandig tot bevestigde financiële feiten. In versie 0.1 actualiseren nieuwe brongegevens een afgeleid bevestigd feit nooit automatisch: een agentoperator of regelmodule dient een herleidbaar opvolgvoorstel in, waarna bevestiging de oude bewering in de tijd afsluit en de nieuwe activeert.

## Persoon

Een mens over wie de financiële contextgraph feiten kan bevatten en aan wie financiële objecten, verplichtingen, gebeurtenissen en doelen geheel of gedeeltelijk kunnen worden toegerekend.

## Organisatie

Een externe rechtspersoon of instelling met een stabiele identiteit die als financiële tegenpartij of contractpartij kan optreden. Rollen zoals werkgever, bank, kredietverstrekker, verzekeraar en pensioenuitvoerder worden afzonderlijk vastgelegd en behoren niet tot haar identiteit.

## Huishouden

Een tijdsgebonden samenwerkingsverband van een of meer personen waarvoor gezamenlijke financiële context wordt vastgelegd en toegerekend. Het huishouden is geen juridische persoon: eigendom, rekeninghouderschap en schuldenaarschap blijven aan personen gekoppeld.

## Gezamenlijke rekening

Een rekening met meer dan één rechthebbende. De graph legt eigendom, gebruik en financiële toerekening afzonderlijk vast, zodat een gezamenlijke rekening en haar transacties niet impliciet aan slechts één persoon worden toegeschreven.

## Huishoudelijke toerekening

Een tijdsgebonden analytische relatie die vastlegt welk deel van een financieel object, belang, verplichting of kasstroom voor een huishouden relevant is. Toerekening creëert geen juridisch recht, rekeninghouderschap of praktisch gebruik en wordt daar niet automatisch uit afgeleid.

## Verdelingsaandeel

Een expliciet deel van een werkelijk deelbaar recht, een deelbare verplichting of een huishoudelijke toerekening. Het staat los van rekeninghouderschap, gebruik en hoofdelijke aansprakelijkheid; een ontbrekend aandeel blijft onbekend en wordt nooit automatisch gelijk verdeeld.

## Geldbedrag

Een hoeveelheid geld in één expliciet vermelde valuta. Valuta wordt nooit uit land, taal of rekening impliciet afgeleid; omrekening levert een berekend resultaat met koers, peildatum en herkomst.

## Rapportagevaluta

De expliciet gekozen valuta waarin een analyse bedragen uit meerdere valuta optioneel samenvoegt. Oorspronkelijke bedragen en subtotalen blijven zichtbaar; zonder vereiste wisselkoers, peildatum en herkomst is alleen het geconverteerde totaal niet beschikbaar.

## Typeclassificatie

Een door een domein- of jurisdictiemodule geleverde verfijning van de intrinsieke soort van een financieel object die toegestane eigenschappen en constraints kan activeren. Zij verandert de stabiele identiteit en gemeenschappelijke grondvorm van de geclassificeerde entiteit niet. Samengestelde producten blijven composities van afzonderlijke entiteiten: partijen, eigendom, rekeninghouderschap, aansprakelijkheid, gebruik, bestemming, verdeling en huishoudelijke toerekening zijn tijdsgebonden beweringen of relaties en worden niet in een gecombineerd producttype gecodeerd.

## Rekening

Een door een financiële instelling of andere administrateur bijgehouden financieel register waarop een saldo en transacties kunnen worden vastgelegd. Het saldo kan analytisch als bezit of verplichting meetellen zonder een tweede entiteit te creëren; afzonderlijk gehouden financiële objecten behouden wel hun eigen identiteit.

## Rekeningsoort

De intrinsieke gebruikssoort van een rekening. Versie 0.1 onderscheidt `payment_account` voor betalen en ontvangen, `savings_account` voor sparen en `investment_account` voor het aanhouden van geld en beleggingen bij een beleggingsplatform. Een pensioen- of lijfrentebeperking is een afzonderlijke jurisdictiekwalificatie op een spaar- of beleggingsrekening en geen vierde rekeningsoort. Een nog niet geclassificeerde rekening blijft geldig.

## Saldostand

Een tijdsgebonden bewering over het geldbedrag op een rekening op een peildatum. Een saldostand kan rechtstreeks zijn waargenomen, door de gebruiker zijn verstrekt of uit transacties zijn berekend; deze kennisvormen blijven onderscheiden en vereisen niet dat de volledige transactiehistorie bekend is.

## Bezitting

Een financieel of materieel object met een eigen identiteit en levensloop waarop een of meer personen een geheel of gedeeltelijk recht hebben. De waarde, verdeling en eventuele toerekening aan een huishouden zijn tijdsgebonden beweringen; een positief rekeningsaldo wordt niet als afzonderlijke bezitting gedupliceerd.

## Bezittingsoort

De intrinsieke soort van een bezitting. Versie 0.1 onderscheidt vastgoed, voertuig, belegging, contant geld, waardevol object en overig bezit; ETF verfijnt een belegging. Een rekening blijft een rekening en wordt niet daarnaast als bezitting gedupliceerd. Eigen bewoning, verhuur, gebruik, eigendom, verdeling en huishoudelijke toerekening blijven afzonderlijke tijdsgebonden beweringen of relaties. Nederlandse WOZ-waardering en jurisdictiekwalificaties veranderen de bezittingsoort niet.

## WOZ-waardering

Een Nederlandse, tijdsgebonden waardering van een onroerende zaak met een eigen waardepeildatum, geldigheidsperiode en herkomst. Zij blijft onderscheiden van een geschatte of waargenomen marktwaarde. Een analyse mag een WOZ-waardering als expliciet benoemde vervangende grondslag gebruiken wanneer een marktwaarde ontbreekt, maar presenteert haar nooit alsof zij dezelfde betekenis of peildatum heeft.

## ETF

Een verhandelbare fondspositie die als afzonderlijke bezitting op een beleggingsrekening wordt aangehouden. De beleggingsrekening legt de administratieve houder vast; de ETF-positie bewaart het instrument, het aantal eenheden en tijdsgebonden waarderingen. Geldsaldo en aangehouden posities blijven onderscheiden en worden bij vermogensanalyses niet dubbel geteld. ETF is een universele classificatie van een bezitting en geen Nederlandse jurisdictieclassificatie.

## Portefeuillewaardering

Een tijdsgebonden totaalwaarde van een beleggingsrekening wanneer de losse aangehouden posities niet of niet volledig bekend zijn. Zij maakt een beleggingsrekening bruikbaar voor een vermogensoverzicht zonder instrumenten te verzinnen. Een analyse gebruikt voor hetzelfde belang de portefeuillewaardering of de volledige som van geldsaldo en posities, maar nooit beide; bij onvolledige posities blijft de gekozen grondslag expliciet zichtbaar.

## Nettovermogen

De peildatumgebonden som van toegerekende rekeningsaldi en bruikbare actuele waarden van bezittingen minus toegerekende schuldstanden binnen één analysebereik. Ongewaardeerde posten en pensioenaanspraken blijven afzonderlijk zichtbaar; contracten, verzekeringsdekkingen en toekomstige kasstromen tellen niet zelfstandig mee.

## Schuld

Een financiële verplichting met een eigen identiteit en levensloop waarvoor een of meer personen geheel of gedeeltelijk schuldenaar zijn. Het openstaande bedrag, de verdeling en eventuele toerekening aan een huishouden zijn tijdsgebonden beweringen; een negatief rekeningsaldo wordt niet als afzonderlijke schuld gedupliceerd.

## Schuldsoort

De intrinsieke soort van een afzonderlijke schuld. Versie 0.1 onderscheidt `mortgage_loan`, `student_loan`, `personal_loan`, `informal_loan` en `other_debt`. Een roodstand, creditcard of doorlopend krediet met een opnieuw opneembare kredietruimte blijft een kredietrekening met een mogelijk negatief saldo en wordt niet daarnaast als schuld gedupliceerd. De oorspronkelijke productnaam blijft als bronmetadata behouden.

## Hypotheekleningdeel

Een afzonderlijke schuld die samen met eventuele andere leningdelen bij hetzelfde hypotheekcontract en onderpand hoort. Ieder leningdeel bewaart zijn eigen openstaande bedrag, renteafspraak, aflosvorm en looptijd, zodat verschillen tussen bijvoorbeeld annuïtaire en aflossingsvrije delen niet in één gecombineerd hypotheekprofiel verloren gaan. De classificatie zegt op zichzelf niets over fiscale behandeling.

## Renteafspraak

Een tijdsgebonden bewering over het rentepercentage, het vaste of variabele karakter en, indien bekend, de rente- of rentevaste periode van een rentedragende schuld of kredietrekening. Ieder hypotheekleningdeel heeft zijn eigen renteafspraak. Een gewijzigde rente vervangt de eerdere bewering in de tijd en verandert het producttype of de identiteit van de schuld niet.

## Schuldbetaling

Een uitgaande transactie of terugkerende kasstroom waarmee een schuld wordt bediend. Het volledige bedrag telt mee in de gerealiseerde cashflow. Wanneer de bron de verdeling geeft, worden rente, aflossing en eventuele kosten afzonderlijk vastgelegd en verlaagt alleen het aflossingsdeel de schuld; bij een onbekende verdeling blijft deze onbekend en verzint de engine geen componenten.

## Contract

Een overeenkomst tussen partijen met een eigen identiteit, looptijd en status waaruit financiële rechten, verplichtingen of kasstromen kunnen voortkomen. Versie 0.1 onderscheidt arbeidscontract, huurcontract, lening- of hypotheekcontract, verzekeringscontract, pensioenregeling, algemeen dienst- of abonnementcontract en overig contract. Het contract blijft onderscheiden van salaris of andere kasstromen en van de bezitting, schuld, dekking of aanspraak die eraan is gekoppeld.

## Dekking

Een afzonderlijk identificeerbaar onderdeel van een verzekeringscontract dat vastlegt welke persoon, bezitting of verplichting tegen welk soort financieel risico is verzekerd. Een contract kan meerdere dekkingen met verschillende geldigheidsperioden bevatten en krijgt alleen de dekkingen die werkelijk zijn overeengekomen. `jurisdiction.nl` kent in versie 0.1 de gangbare dekkingstypen basiszorg, aanvullende zorg, tandzorg, opstal, inboedel, glas, privéaansprakelijkheid, voertuig-WA, beperkt casco, volledig casco, reis, annulering, overlijdensrisico, arbeidsongeschiktheid, ongevallen, uitvaart en rechtsbijstand. Een andere dekking blijft geldig als `other_coverage` met behoud van haar oorspronkelijke bronnaam.

## Pensioenaanspraak

Een afzonderlijk identificeerbaar financieel recht van een begunstigde op een toekomstig pensioen, doorgaans gekoppeld aan een pensioencontract of regeling. `jurisdiction.nl` onderscheidt in versie 0.1 een wettelijke AOW-aanspraak, een via een werkgever opgebouwde pensioenaanspraak en een individuele pensioen- of lijfrenteaanspraak. Een pensioenrekening kan daarnaast als spaar- of beleggingsrekening met een pensioenbeperking in de graph staan. De aanspraak en rekening worden niet vereenzelvigd en zijn niet automatisch vrij beschikbaar of onderdeel van nettovermogen; een analyse bepaalt expliciet hoe bekende opgebouwde waarde, verwachte uitkering en ingangsdatum worden behandeld en verzint geen prognose.

## Financieel doel

Een door een persoon of huishouden gewenste financiële toestand met een streefdatum of periode. Een doel legt intentie vast, maar bevat geen voorgeschreven handelwijze of productkeuze en is daarmee geen financieel advies.

## Financiële gebeurtenis

Een betekenisvol voorval dat meerdere financiële gevolgen of objecten causaal kan verbinden voor een persoon of huishouden. Een gewone tijdsgebonden waardewijziging vereist geen afzonderlijke gebeurtenis; een onzekere toekomstige gebeurtenis bestaat alleen binnen een scenario.

## Financieel domein

Een samenhangend deel van de financiële context, zoals inkomsten, uitgaven, rekeningen, bezittingen, schulden, contracten, pensioen, verzekeringen, doelen of gebeurtenissen. Versie 0.1 bevat van ieder kerndomein een minimale gemeenschappelijke basis. Ieder domein moet later onafhankelijk in breedte en diepte kunnen worden uitgebreid zonder de kernbegrippen te veranderen.

## Financieel feit

Een uitspraak over de financiële werkelijkheid met een geldigheidsperiode en een moment waarop de engine haar heeft waargenomen. Een nieuwe versie vervangt een oudere versie zonder de historie ervan te wissen.

## Bekende wijziging

Een toekomstige verandering die al voldoende vaststaat, bijvoorbeeld een contractueel vastgelegde salariswijziging. Een bekende wijziging is geen schatting.

## Aanname

Een expliciete, wijzigbare veronderstelling die nodig is voor een berekening of scenario. Een aanname vermeldt haar herkomst en peildatum en kan later worden gebaseerd op een externe referentiebron, zoals een publicatie van het Nibud. Automatische koppelingen met zulke bronnen behoren niet tot versie 0.1.

## Scenario

Een benoemde verzameling expliciete aannames en mogelijke wijzigingen waarmee de engine een alternatieve financiële situatie op één gekozen toekomstige peildatum vergelijkt met een basislijn. Bekende wijzigingen behoren tot de basislijn en een scenario bevat in versie 0.1 geen kansverdeling, optimalisatie of advies.

## Scenarioaanname

Een expliciete, gedateerde en gemotiveerde wijziging binnen een scenario: een terugkerende kasstroom toevoegen, wijzigen of beëindigen, een eenmalige kasstroom opnemen, of een waarde of stand op de scenariopeildatum vervangen. Versie 0.1 ondersteunt geen vrije formules of ongerichte procentuele mutaties.

## Projectie

Een deterministisch berekende toekomstige maandcashflow of, waar mogelijk, nettovermogenswaarde op basis van financiële feiten, bekende wijzigingen en aannames binnen een scenario. Cashflowoverschotten of -tekorten veranderen vermogen alleen via een expliciete aanname over bestemming of financiering; een projectie wordt nooit een financieel feit.
