# Welke vereisten en uitkomsten hebben de eerste analyses?

Type: grilling
Status: resolved
Blocked by: 02, 03, 05

## Question

Welke expliciete invoereisen, onzekerheidsstatussen, berekeningen, rekenstappen en uitvoerschema's gelden voor contextinventarisatie, inkomsten- en uitgavenpatronen, maandcashflow, nettovermogen en één eenvoudige scenariovergelijking?

## Answer

De eerste analyses delen één doelgebonden, herleidbaar contract. Zij rekenen alleen met beschikbare canonieke context en expliciete aannames; EngineCore kent geen universeel actualiteitsoordeel. Iedere analysemodule declareert zelf welke feiten, tijdsdekking, verificatiestatus en eventuele actualiteit zij per resultaatonderdeel vereist.

### Gemeenschappelijk verzoek en resultaat

Ieder analyseverzoek bevat minimaal:

- een stabiele analyse-identificatie en contractversie;
- een expliciet `analysis_scope` voor één persoon of huishouden;
- een expliciete `as_of_date`;
- voor transactiegebonden analyses een halfopen periode met inclusieve `start_date` en exclusieve `end_date`;
- optioneel een expliciete rapportagevaluta en de wisselkoersbeweringen of -aannames die daarvoor mogen worden gebruikt.

Een gemaks-CLI mag de huidige datum invullen, maar het genormaliseerde verzoek en resultaat leggen de gekozen datum altijd vast. Een huishoudanalyse gebruikt alleen expliciete huishoudelijke toerekeningen. Onbekende aandelen blijven onbekend en worden nooit stilzwijgend 50/50 verdeeld.

Ieder resultaat bevat minimaal:

- analyse-identificatie en versie, bereik, peildatum en eventuele periode;
- een deterministische resultaat-ID over contractversie, genormaliseerd verzoek en gebruikte canonieke generatie;
- de status van ieder afzonderlijk resultaatonderdeel;
- verwijzingen naar alle gebruikte beweringen, bronreferenties en eventuele voorstellen;
- aannames, benoemde rekenstappen, ongeronde tussenuitkomsten en presentatieafronding;
- ontbrekende, onvoldoende actuele, niet-toegerekende of conflicterende vereisten en hun lokale impact;
- waarschuwingen en de eerstvolgende doelgebonden vraag.

De drie resultaatstatussen zijn:

- `complete`: alle door het onderdeel gedeclareerde vereisten zijn geldig en bruikbaar;
- `provisional`: het onderdeel is berekenbaar, maar gebruikt of mist expliciet vermelde onzekere, onvoldoende actuele, aangenomen, niet-toegerekende of onvolledig gedekte invoer;
- `unavailable`: het onderdeel is niet verantwoord berekenbaar, bijvoorbeeld door een relevant echt conflict of een ontbrekende harde vereiste.

Een probleem blokkeert alleen de getroffen onderdelen. De engine verzint geen ontbrekende waarden. Kennistype, verificatiestatus, modulespecifieke detectiescore en resultaatstatus blijven afzonderlijke dimensies.

Bedragen blijven altijd per oorspronkelijke valuta beschikbaar. Een geconverteerd totaal vereist een expliciete rapportagevaluta plus koers, peildatum en herkomst. Ontbreekt een koers, dan blijven de subtotalen per valuta beschikbaar en is alleen het geconverteerde totaal `unavailable`. v0.1 haalt geen koersen op.

### Contextinventarisatie

De contextinventarisatie blijft altijd uitvoerbaar en haar eigen inventarisatie-uitkomst is `complete`, ook bij een vrijwel lege graph. Zij geeft geen algemeen volledigheidspercentage, maar retourneert per beschikbare analyse en resultaatonderdeel een vereistenmatrix met:

- aanwezig, ontbrekend, conflicterend of volgens de betreffende analysemodule onvoldoende actueel;
- kennistype en verificatiestatus;
- geldigheids- en registratietijd en vereiste tijdsdekking;
- onbekende huishoudelijke toerekening;
- impact op de resultaatstatus;
- de eerstvolgende doelgebonden vraag.

Daarnaast geeft zij uitsluitend beschrijvende aantallen per financieel domein. Volledigheid blijft altijd `sufficient_for(<analysis component>)` en wordt niet tot één score samengevoegd.

### Inkomsten- en uitgavenpatronen

De deterministische v0.1-herkenning ondersteunt `weekly`, `four_weekly`, `monthly`, `quarterly` en `annual`. Een patroonkandidaat vereist minimaal drie vergelijkbare transacties, behalve een jaarpatroon waarvoor minimaal twee waarnemingen nodig zijn. Vergelijkbaarheid gebruikt richting, tegenpartij of omschrijving, valuta, intervaltolerantie en een bedrag of bandbreedte.

Een kandidaat bevat frequentie, verwachte volgende periode, bedrag of bandbreedte, gebruikte transacties, afwijkingen, producent- en regelversie en een modulespecifieke detectiescore. Te weinig historie produceert geen automatisch voorstel; een gebruiker kan dezelfde terugkerende kasstroom wel rechtstreeks gestructureerd bevestigen.

Alleen bevestigde, op de peildatum geldige terugkerende kasstromen mogen in genormaliseerde cashflow meetellen. Kandidaten blijven apart zichtbaar. Een relevant open aandachtspunt maakt het getroffen resultaat voorlopig; een echt conflict maakt alleen het afhankelijke onderdeel niet beschikbaar.

De landneutrale basisclassificatie van transacties is beperkt tot `income`, `expense`, `internal_transfer` en `unclassified`. Fijnere bron-, domein- of jurisdictielabels blijven behouden maar zijn geen vereiste voor de basisanalyses.

Een Tally-adapter importeert de ruwe banktransactie als onveranderlijke waarneming en Tally-categorie, subcategorie, tags, regelversie en uitleg als herleidbaar classificatievoorstel. `income`/`Inkomen` mapt naar een inkomenskandidaat, `transfer`/`Overboekingen` naar een interne-overboekingskandidaat, een overige negatieve transactie naar een uitgavenkandidaat en een niet-eenduidige transactie naar `unclassified`. Een interne overboeking wordt waar mogelijk met de tegenboeking bewezen. De gebruiker kan voorstellen per mapping in een batch bevestigen; Tally wordt niet stilzwijgend bron van financiële waarheid.

### Gerealiseerde maandcashflow

De gerealiseerde maandcashflow sommeert werkelijk geboekte transacties binnen de gekozen kalendermaand en het analysebereik. Zij publiceert minimaal inkomsten, uitgaven, netto geldbeweging, interne overboekingen, ongeclassificeerde geldbeweging en uitsplitsingen per beschikbare categorie en rekening.

- Bevestigde interne overboekingen binnen hetzelfde bereik tellen niet als inkomen of uitgave.
- Een gekoppelde terugbetaling of stornering corrigeert de oorspronkelijke categorie; zonder koppeling blijft zij afzonderlijk en ongeclassificeerd.
- Ongeclassificeerde transacties tellen mee in de netto geldbeweging, maar niet in inkomsten- of uitgavencategorieën.
- Uitgesloten, gekoppelde en ongeclassificeerde transacties blijven zichtbaar voor reconciliatie.

Een gerealiseerde cashflow is alleen volledig wanneer alle expliciet opgenomen rekeningen de gehele halfopen analyseperiode aantoonbaar dekken en de huishoudelijke toerekening bekend is. Bij gedeeltelijke dekking toont de analyse wel de som van beschikbare transacties maar markeert getroffen totalen `provisional`. Aansluiting op begin- en eindsaldi is diagnostiek en geen harde volledigheidseis.

### Genormaliseerde maandcashflow

De genormaliseerde maandcashflow gebruikt uitsluitend bevestigde, geldige terugkerende kasstromen en houdt werkelijke boekingen, eenmalige posten en kandidaten apart. Frequenties worden deterministisch omgerekend:

- wekelijks: bedrag × 52 ÷ 12;
- vierwekelijks: bedrag × 13 ÷ 12;
- maandelijks: bedrag;
- per kwartaal: bedrag ÷ 3;
- jaarlijks: bedrag ÷ 12.

Vaste bedragen leveren exacte totalen. Bandbreedtes leveren minimum en maximum; alleen een expliciet bevestigd typisch bedrag mag daarnaast een verwacht totaal vormen. De engine kiest nooit zelf het midden van een bandbreedte. Vaste en variabele inkomsten en uitgaven blijven afzonderlijk zichtbaar. Geldberekeningen gebruiken decimale rekenkunde; alleen gepresenteerde eindbedragen worden volgens de valuta afgerond, terwijl factor en ongerond tussenresultaat herleidbaar blijven.

### Nettovermogen

Nettovermogen op de gekozen peildatum is:

`toegerekende rekeningsaldi + toegerekende bruikbare waarden van bezittingen - toegerekende schuldstanden`.

Iedere waarde bewaart haar eigen peildatum. EngineCore levert wat beschikbaar is en kent geen centrale `stale`-status; de nettovermogensmodule declareert eventueel per waarde- of producttype welke tijdsafstand voor haar doel bruikbaar is. Ontbrekende of volgens dat contract onvoldoende actuele waarden worden nooit geschat, maar apart vermeld en maken alleen getroffen totalen voorlopig of niet beschikbaar.

Objecten zonder bruikbare waardering blijven afzonderlijk zichtbaar. Pensioenaanspraken worden standaard niet opgeteld maar krijgen een eigen sectie. Contracten, verzekeringsdekkingen en toekomstige kasstromen tellen niet zelfstandig als vermogen. Meerdere valuta volgen het gedeelde rapportagevalutacontract.

### Eenvoudige scenariovergelijking

De scenarioanalyse vergelijkt een expliciete basislijn met een of meer benoemde scenario's op één gekozen toekomstige peildatum. Bekende wijzigingen behoren tot de basislijn; scenario's bevatten alleen expliciete aannames en mogelijke wijzigingen. v0.1 accepteert drie capability-limited aannamevormen:

- `recurring_cashflow_change`: een terugkerende kasstroom toevoegen, wijzigen of beëindigen vanaf een datum;
- `one_off_cashflow`: een eenmalige ontvangst of betaling op een datum;
- `value_override`: de waarde of stand van een specifieke rekening, bezitting of schuld op de scenariopeildatum vervangen.

Iedere aanname noemt doelobject, bedrag en valuta, geldigheidsdatum en reden. Vrije code, algemene formules en ongerichte procentuele mutaties zijn niet toegestaan.

Per scenario publiceert de analyse de genormaliseerde maandcashflow, afzonderlijke eenmalige kasstromen en waar expliciete waardeaannames dat toelaten het nettovermogen, steeds als absolute uitkomst en verschil met de basislijn. Een cashflowoverschot wordt niet automatisch als spaargeld toegevoegd en een tekort niet automatisch gefinancierd; zonder expliciete aanname verandert cashflow het geprojecteerde vermogen niet. De uitvoer meldt deze niet-gemodelleerde bestemming expliciet.

Scenario-uitkomsten zijn projecties en worden nooit canonieke feiten. Kansverdelingen, Monte Carlo, optimalisatie, productadvies, rente-op-rente-modellen en fiscale voorspellingen vallen buiten v0.1.
