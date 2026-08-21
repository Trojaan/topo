# Financiële contextengine — begrippen

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

Een normatieve aanbeveling over wat iemand financieel behoort te doen of welk product diegene behoort te kiezen. Financieel advies valt buiten de financiële contextengine. Een agent mag engine-uitkomsten uitleggen en mogelijke vervolgvragen formuleren, maar maakt van een inzicht geen advies.

## Basiscontext

De minimale financiële context waarmee de engine een algemeen huishoudbeeld kan opbouwen en zinvolle vervolgstappen kan voorstellen. De basiscontext hoeft niet voldoende te zijn voor iedere analyse.

## Doelgebonden volledigheid

De mate waarin de beschikbare en voldoende actuele context voldoet aan de expliciete vereisten van één analyse. Volledigheid is niet absoluut: dezelfde graph kan voldoende zijn voor een nettovermogensberekening en onvoldoende voor een pensioenprojectie.

## Analysevereiste

Een expliciete beschrijving van welke feiten, tijdsdekking, zekerheid en aannames een analyse minimaal nodig heeft. De engine gebruikt analysevereisten om ontbrekende context te prioriteren en om aan te geven of een uitkomst volledig, voorlopig of niet verantwoord berekenbaar is.

## Analyse

Een deterministische bewerking die financiële inzichten uit de contextgraph produceert en vooraf haar analysevereisten declareert. De eerste analyseset bestaat uit contextinventarisatie, herkenning van inkomsten- en uitgavenpatronen, huishoudelijke maandcashflow, nettovermogen en een eenvoudige scenariovergelijking.

## EngineCore

De kleine, domeinoverschrijdende kern die identiteit, relaties, tijd, herkomst, zekerheid, contextvoorstellen, bevestiging en contextmutaties beheert. De EngineCore herkent zelf geen financiële patronen: agentoperators en deterministische regelmodules kunnen via hetzelfde voorstelcontract kandidaatpatronen aanleveren. Financiële verdieping hoort niet rechtstreeks in de EngineCore.

## Domeinmodule

Een uitbreidbare module voor een financieel domein, zoals hypotheken of pensioen. Zij voegt domeinspecifieke entiteiten en relaties toe zonder de EngineCore te verbreden.

## Analysemodule

Een uitbreidbare module die analysevereisten, deterministische berekeningen en herleidbare uitkomsten voor een of meer analyses bevat.

## Regelmodule

Een uitbreidbare module met regels voor validatie, afleiding of prioritering van ontbrekende context.

## Jurisdictiemodule

Een landspecifieke uitbreiding met financiële producttypen, regels en conventies die niet universeel zijn. Versie 0.1 richt zich op Nederland; de EngineCore blijft landneutraal zodat andere landen later als afzonderlijke jurisdictiemodule kunnen worden toegevoegd.

## Technische identifier

Een stabiele Engelstalige naam in schema's, bestanden en toolcontracten. Technische identifiers veranderen niet wanneer de presentatietaal verandert. Documentatie en agentgesprekken gebruiken in eerste instantie Nederlandse domeintermen; vertaalbare labels en uitleg vormen een afzonderlijke presentatielaag.

## Local-first

De eigenschap dat contextbestanden, regels, validatie, berekeningen en uitvoer lokaal en zonder netwerktoegang kunnen functioneren. Netwerktoegang is standaard niet nodig en kan later alleen via een expliciete adapter plaatsvinden.

## Agentoperator

Een optionele maar beoogde gesprekspartner die gebruikersintentie begrijpt, vragen stelt, voorstellen formuleert en engine-tools orkestreert. Vrije tekst die de agentoperator interpreteert wordt altijd eerst een expliciet, gestructureerd contextvoorstel; de interpretatie wordt nooit rechtstreeks een bevestigd financieel feit. De engine blijft zonder agent deterministisch bruikbaar voor import, validatie, mutatie en analyse. De agentoperator behoort niet tot de bron van financiële waarheid.

## CLI-contract

De primaire technische interface van versie 0.1. Commando's accepteren en produceren stabiele, schema-gevalideerde JSON naast mensleesbare uitvoer. Hierdoor kunnen mensen en uiteenlopende command-line-agents dezelfde engine gebruiken. Protocollen zoals MCP zijn optionele latere adapters en bepalen de EngineCore niet.

## Declaratieve regel

Een leesbare, niet-willekeurig-uitvoerbare regel voor herkenning, validatie, volledigheid of vraagprioritering. Een agent kan regelwijzigingen voorstellen, waarna de engine ze valideert en activeert.

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

Een door een domein- of jurisdictiemodule geleverde betekenisregel, zoals cardinaliteit, toegestane typen, overlappende geldigheidsperioden of een vereist totaal. De EngineCore begrijpt en handhaaft het generieke mechanisme; de module bepaalt op welke financiële begrippen het van toepassing is.

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

## Terugkerende kasstroom

Een herkenbare of verwachte reeks financiële ontvangsten of betalingen met een bedrag of bandbreedte, frequentie en geldigheidsperiode. Zij kan uit transacties zijn herkend of rechtstreeks zijn bevestigd, maar vervangt de onderliggende transacties niet.

## Bronadapter

Een afgebakende vertaler die gegevens uit een externe vorm omzet naar het canonieke invoerformaat van de engine, zonder dat het domeinmodel afhankelijk wordt van die bron. Een expliciet geautoriseerde bronadapter mag letterlijke bronvelden, zoals bedrag, valuta, boekingsdatum en bronreferentie, zonder bevestiging per record als waarneming importeren. Classificaties, identiteitskoppelingen en andere financiële betekenis die niet letterlijk uit de bron volgen blijven contextvoorstellen. Een broncorrectie overschrijft het eerdere record niet, maar wordt als herleidbare opvolger vastgelegd. Versie 0.1 ondersteunt handmatige invoer via het agentgesprek, een Tally-adapter en een generieke adapter voor genormaliseerde CSV- of JSON-transacties.

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

## Typeclassificatie

Een door een domein- of jurisdictiemodule geleverde verfijning van een financieel begrip die labels, toegestane eigenschappen en constraints kan activeren. Zij verandert de stabiele identiteit en gemeenschappelijke grondvorm van de geclassificeerde entiteit niet.

## Rekening

Een door een financiële instelling of andere administrateur bijgehouden financieel register waarop een saldo en transacties kunnen worden vastgelegd. Het saldo kan analytisch als bezit of verplichting meetellen zonder een tweede entiteit te creëren; afzonderlijk gehouden financiële objecten behouden wel hun eigen identiteit.

## Saldostand

Een tijdsgebonden bewering over het geldbedrag op een rekening op een peildatum. Een saldostand kan rechtstreeks zijn waargenomen, door de gebruiker zijn verstrekt of uit transacties zijn berekend; deze kennisvormen blijven onderscheiden en vereisen niet dat de volledige transactiehistorie bekend is.

## Bezitting

Een financieel of materieel object met een eigen identiteit en levensloop waarop een of meer personen een geheel of gedeeltelijk recht hebben. De waarde, verdeling en eventuele toerekening aan een huishouden zijn tijdsgebonden beweringen; een positief rekeningsaldo wordt niet als afzonderlijke bezitting gedupliceerd.

## Schuld

Een financiële verplichting met een eigen identiteit en levensloop waarvoor een of meer personen geheel of gedeeltelijk schuldenaar zijn. Het openstaande bedrag, de verdeling en eventuele toerekening aan een huishouden zijn tijdsgebonden beweringen; een negatief rekeningsaldo wordt niet als afzonderlijke schuld gedupliceerd.

## Contract

Een overeenkomst tussen partijen met een eigen identiteit, looptijd en status waaruit financiële rechten, verplichtingen of kasstromen kunnen voortkomen. Het contract blijft onderscheiden van de bezitting, schuld, dekking of aanspraak die eraan is gekoppeld.

## Dekking

Een afzonderlijk identificeerbaar onderdeel van een verzekeringscontract dat vastlegt welke persoon, bezitting of verplichting tegen welk soort financieel risico is verzekerd. Een contract kan meerdere dekkingen met verschillende geldigheidsperioden bevatten.

## Pensioenaanspraak

Een afzonderlijk identificeerbaar financieel recht van een begunstigde op een toekomstig pensioen, doorgaans gekoppeld aan een pensioencontract of regeling. De aanspraak is niet automatisch een vrij beschikbare bezitting of onderdeel van nettovermogen; een analyse bepaalt expliciet hoe zij wordt behandeld.

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

Een benoemde verzameling aannames en mogelijke wijzigingen waarmee de engine een alternatieve of toekomstige financiële situatie kan doorrekenen.

## Projectie

Een deterministisch berekende toekomstige waarde op basis van financiële feiten, bekende wijzigingen en aannames binnen een scenario. Een projectie is herleidbaar en reproduceerbaar, maar wordt nooit een financieel feit en overschrijft geen feiten.
