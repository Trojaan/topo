# Welke Nederlandse productclassificaties en constraints horen in v0.1?

Type: grilling
Status: resolved
Blocked by: 09

## Question

Welke minimale, namespaced Nederlandse productclassificaties, betekenisregels en validatieconstraints moet `jurisdiction.nl` meeleveren voor de reeds gekozen domeinsnede, zodat v0.1 bruikbare Nederlandse context kan vastleggen zonder de uitgesloten diepe fiscale, pensioen-, verzekerings- of hypotheekberekeningen binnen te halen?

## Answer

`jurisdiction.nl` blijft een kleine semantische overlay en wordt geen catalogus van Nederlandse commerciële producten. Een classificatie hoort alleen in deze module wanneer zij ten minste één landspecifieke betekenisregel, toegestane relatie of constraint activeert. Merk-, aanbieder- en productnamen blijven bronmetadata. Alle technische identifiers zijn stabiel en Engelstalig; een lokale identifier `x` krijgt als volledige vorm `jurisdiction.nl/x`.

### Compositie en module-eigenaarschap

Financiële producten blijven composities van universele domeinobjecten. Een hypotheek bestaat uit een contract, een of meer schulden en een onderpandrelatie; een verzekering uit een contract en afzonderlijke dekkingen; een pensioenproduct kan zowel een rekening als een aanspraak omvatten. Eigendom, rekeninghouderschap, aansprakelijkheid, praktisch gebruik, bestemming, verdeling en huishoudelijke toerekening zijn tijdsgebonden relaties of beweringen en worden niet in gecombineerde producttypen gecodeerd.

De universele domeinmodules bezitten de basisclassificaties:

- rekeningen: `payment_account`, `savings_account` en `investment_account`;
- bezittingen: vastgoed, voertuig, belegging, contant geld, waardevol object en overig bezit; ETF verfijnt een belegging;
- schulden: `mortgage_loan`, `student_loan`, `personal_loan`, `informal_loan` en `other_debt`;
- contracten: arbeids-, huur-, lening- of hypotheek-, verzekerings-, pensioen-, dienst- of abonnementcontract en overig contract;
- de kleine universele inkomsten- en uitgavengroepen die in `CONTEXT.md` staan.

Een onbekende classificatie blijft geldige, onvolledige context. De engine bewaart altijd de oorspronkelijke bronnaam en dwingt de gebruiker nooit tot gokken.

### Nederlandse overlay

De minimale meegeleverde Nederlandse identifiers zijn:

- kwalificaties: `jurisdiction.nl/qualification/retirement_restriction`, `jurisdiction.nl/qualification/annuity_restriction` en `jurisdiction.nl/qualification/owner_occupied_home_debt`;
- waardering: `jurisdiction.nl/valuation/woz`;
- pensioenoorsprong: `jurisdiction.nl/pension_origin/aow`, `jurisdiction.nl/pension_origin/employer` en `jurisdiction.nl/pension_origin/individual`;
- inkomsten: `jurisdiction.nl/income/aow` en `jurisdiction.nl/income/allowance`;
- uitgaven: `jurisdiction.nl/expense/health_insurance_premium`, `jurisdiction.nl/expense/municipal_tax` en `jurisdiction.nl/expense/water_authority_tax`;
- dekkingen: `basic_health`, `supplementary_health`, `dental`, `building`, `contents`, `glass`, `personal_liability`, `motor_third_party`, `motor_limited_casco`, `motor_full_casco`, `travel`, `cancellation`, `term_life`, `disability`, `accident`, `funeral` en `legal_assistance`, elk onder `jurisdiction.nl/coverage/`; daarnaast bestaat `jurisdiction.nl/coverage/other` met verplichte oorspronkelijke bronnaam.

Doelen en gebeurtenissen krijgen in v0.1 geen Nederlandse subtypen. Nederlandse gevolgen van een levensgebeurtenis worden nooit verondersteld, maar ontstaan alleen als afzonderlijk bevestigd feit of voorstel.

### Betekenisregels

- Een fiscale of juridische kwalificatie is altijd expliciet bevestigd, tijdsgebonden en herleidbaar. De engine mag haar gebruiken om conservatieve aannames te doen, bijvoorbeeld pensioenvermogen niet als vrij beschikbaar behandelen, maar stelt de wettelijke geldigheid niet zelf vast en berekent geen fiscale gevolgen.
- Een pensioen- of lijfrenterekening blijft een spaar- of beleggingsrekening met een afzonderlijke beperking. Een aanbieder zoals Brand New Day is een organisatie, geen rekeningsoort.
- ETF's zijn afzonderlijke bezittingen op een beleggingsrekening. Wanneer posities onbekend of onvolledig zijn, mag een tijdsgebonden totale portefeuillewaardering worden gebruikt. Voor hetzelfde belang gebruikt een analyse de portefeuillewaardering of de volledige som van cash en posities, nooit beide.
- Een WOZ-waardering blijft onderscheiden van een marktwaardering en bewaart haar eigen waardepeildatum en herkomst.
- Ieder hypotheekleningdeel is een afzonderlijke schuld met eigen openstaand bedrag, renteafspraak, aflosvorm en looptijd, gekoppeld aan hetzelfde contract en eventueel onderpand.
- Iedere rentedragende schuld of kredietrekening kan een tijdsgebonden vaste of variabele renteafspraak hebben. Een schuldbetaling bewaart het totale kasbedrag en, alleen wanneer bekend, de verdeling in rente, aflossing en kosten. Alleen aflossing verlaagt de schuld.
- Roodstand, creditcards en opnieuw opneembare kredieten blijven kredietrekeningen met een mogelijk negatief saldo; hetzelfde bedrag wordt niet daarnaast als schuld vastgelegd.
- Een verzekeringscontract bevat alleen werkelijk aanwezige dekkingen. Iedere dekking verwijst naar een type-correct verzekerd persoon, bezit, verplichting of aansprakelijkheid. Premies zijn afzonderlijke terugkerende kasstromen.
- AOW, werkgeverspensioen en individueel pensioen blijven onderscheiden. Een pensioenrekening en de ermee samenhangende pensioenaanspraak worden niet vereenzelvigd en een ontbrekende prognose wordt niet verzonnen.

### Validatiegrens

Structureel onmogelijke of tegenstrijdige combinaties blokkeren een mutatie: een dekking op een verboden doeltype, overlappende exclusieve classificaties, ontbrekende geldigheid of herkomst voor een jurisdictiekwalificatie, een WOZ-waarde zonder waardepeildatum, ongeldige verdelingsaandelen en iedere aantoonbare dubbeltelling. Ontbrekende optionele context — zoals onbekende rente, onderliggende fondsposities, verzekerde bedragen of een uitsplitsing van een schuldbetaling — blijft toegestaan en levert een zichtbaar, doelgebonden aandachtspunt op. Alleen analyses die het ontbrekende gegeven nodig hebben worden `provisional` of `unavailable`.

Daarmee ondersteunt v0.1 een gangbaar Nederlands huishouden op overzichtsniveau zonder recht op toeslagen, fiscale aftrek, pensioenuitkomsten, verzekeringsgeschiktheid of hypotheekscenario's zelfstandig vast te stellen of door te rekenen.
