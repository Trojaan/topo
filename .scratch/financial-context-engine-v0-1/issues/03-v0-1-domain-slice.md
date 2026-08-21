# Welke minimale financiële domeinsnede hoort in v0.1?

Type: grilling
Status: resolved
Blocked by: 02

## Question

Welke minimale entiteiten en relaties zijn per kerndomein nodig om huishoudens, gezamenlijke rekeningen, inkomsten, uitgaven, bezittingen, schulden, contracten, pensioen, verzekeringen, doelen en gebeurtenissen coherent maar uitbreidbaar te modelleren?

## Answer

v0.1 modelleert de financiële domeinen door een kleine verzameling eersteklas entiteiten te **componeren**. Productsoorten worden geen losstaande modeleilanden: modules verfijnen de gemeenschappelijke grondvorm met uitbreidbare typeclassificaties, labels en constraints. Een onbekende classificatie blijft geldige, nog niet verfijnde context.

De minimale domeinentiteiten zijn:

- **Betrokkenen:** persoon, huishouden en organisatie. Een huishouden is een tijdsgebonden context- en toerekeningseenheid, geen juridische persoon. Banken, werkgevers, verzekeraars, pensioenuitvoerders en andere externe partijen zijn organisaties met afzonderlijke rollen.
- **Geldverkeer:** rekening, transactie en terugkerende kasstroom. Een transactie is een stabiel identificeerbare geldbeweging op precies één rekening. Inkomen en uitgave zijn corrigeerbare classificaties; twee rekeningtransacties kunnen als zijden van een interne overboeking worden gekoppeld. Een terugkerende kasstroom kan rechtstreeks zijn bevestigd of uit transacties zijn voorgesteld en vervangt haar bewijs niet.
- **Vermogen:** bezitting en schuld wanneer het financiële belang een eigen identiteit en levensloop heeft. Een positief of negatief rekeningsaldo wordt niet als tweede bezitting of schuld gedupliceerd. Afzonderlijke effecten binnen een beleggingsrekening en een lening met een eigen contract blijven wel zelfstandige entiteiten.
- **Overeenkomsten:** contract als gedeelde ruggengraat met partijen, looptijd en status. Een hypotheek composeert bijvoorbeeld een contract, schuld en onderpand zonder die objecten te vereenzelvigen.
- **Verzekering:** dekking als zelfstandig onderdeel van een verzekeringscontract, gekoppeld aan de verzekerde persoon, bezitting of verplichting; premie is een terugkerende kasstroom.
- **Pensioen:** pensioenaanspraak als zelfstandig financieel recht van een begunstigde, doorgaans gekoppeld aan een pensioencontract of regeling. De entiteit impliceert niet dat zij vrij beschikbaar is of in nettovermogen meetelt.
- **Intentie en verandering:** financieel doel en financiële gebeurtenis. Een doel legt een gewenste toestand vast zonder handelwijze of advies. Een gebeurtenis verbindt alleen betekenisvolle causale gevolgen; gewone tijdsgebonden wijzigingen blijven beweringen en onzekere toekomstige gebeurtenissen bestaan alleen binnen een scenario.
- **Scenario:** de reeds vastgelegde benoemde verzameling van aannames en mogelijke wijzigingen. Zekere toekomstige veranderingen blijven bekende wijzigingen en geen aannames.

De minimale relaties onderscheiden expliciet:

- `lid van huishouden` en `betreft persoon/huishouden`;
- contractpartij, tegenpartij, rekeningbeheerder en begunstigde;
- rekeninghouder, rechthebbende en schuldenaar als juridische of contractuele posities;
- praktisch gebruik en huishoudelijke toerekening als daarvan onafhankelijke relaties;
- geboekt op rekening, tegenzijde van overboeking en bewijs voor terugkerende kasstroom;
- hoort bij contract, veroorzaakt kasstroom, gehouden op rekening, gedekt door onderpand en dekt verzekerd onderwerp;
- betreft of beïnvloedt als verbinding van doelen en gebeurtenissen met andere financiële objecten.

Een **verdelingsaandeel** wordt alleen gebruikt voor werkelijk deelbare rechten, verplichtingen of toerekeningen. Rekeninghouderschap, gebruik en hoofdelijke aansprakelijkheid zijn geen impliciete percentages. Ontbrekende verdelingen blijven onbekend; de engine neemt nooit stilzwijgend 50/50 aan. Alleen een expliciet volledige verdeling moet tot 100% optellen.

Iedere geldwaarde bestaat uit hoeveelheid plus expliciete valuta. EUR kan door de Nederlandse presentatielaag worden voorgesteld, maar wordt niet door de EngineCore aangenomen. Omrekening is een herleidbare berekening met koers en peildatum.

Een rekening kan rechtstreeks een **saldostand op peildatum** krijgen zonder volledige transactiehistorie. Waargenomen, door de gebruiker verstrekte en uit transacties berekende saldostanden blijven onderscheiden. Een verschil signaleert ontbrekende context of een conflict; de engine verzint geen correctietransactie. Daardoor ondersteunen handmatige inventarisatie, gedeeltelijke historie en transactie-import elkaar zonder wederzijdse afhankelijkheid.

v0.1 bouwt geen dubbelboekhoudjournaal en bevat geen diepe product-, fiscale, hypotheek-, verzekerings- of pensioenberekeningen. Juridisch belang, praktisch gebruik, huishoudelijke toerekening, kennisstatus en analytische behandeling blijven expliciet gescheiden.
