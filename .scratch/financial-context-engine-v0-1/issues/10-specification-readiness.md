# Wanneer is de technische specificatie klaar voor implementatie?

Type: grilling
Status: resolved
Blocked by: 03, 04, 05, 06, 07, 08, 09, 11

## Question

Welke traceerbare acceptatiecriteria, voorbeeldscenario's en open-risicocontroles tonen aan dat de verzamelde beslissingen samen één coherente, implementeerbare Financial Context Engine v0.1 specificeren zonder verborgen product- of domeinkeuzes?

## Answer

De technische specificatie is implementatieklaar wanneer een ontwikkelaar de engine kan bouwen zonder zelf financieel gedrag, productgedrag, gebruikersgedrag of veiligheidsgrenzen te verzinnen. Interne code-indeling, bibliotheken en andere omkeerbare programmeerkeuzes blijven vrij voor de implementatie.

### Overdrachtsvorm

De overdracht bestaat uit één leesbaar hoofddocument met gekoppelde technische bijlagen voor grotere JSON-schema's en voorbeelden. Een compacte controletabel koppelt iedere belangrijke eis aan:

- het besluit waaruit de eis voortkomt;
- het voorbeeldverhaal waarin de eis zichtbaar is;
- de status `ready`, `deferred` of `out_of_scope`.

De gesloten Wayfinder-tickets blijven de detailbron, maar een ontwikkelaar hoeft ze niet zelf tot een specificatie samen te puzzelen.

### Minimale bewijsvoering

Iedere beloofde capability heeft minimaal één concreet voorbeeld met invoer en verwachte uitvoer. Voor veiligheidskritische grenzen bevat de specificatie ook een weigering of waarschuwing, in het bijzonder bij ontbrekende gegevens, conflicterende informatie, onbevestigde wijzigingen, verouderde generaties en ongeldige mutaties. Dit zijn specificatievoorbeelden en nog geen volledige testsuite.

Drie kleine end-to-end-verhalen geven samen voldoende dekking:

1. Een nieuwe gebruiker begint met weinig gegevens; de engine toont doelgebonden ontbrekende context en verzint niets.
2. Een huishouden importeert banktransacties, beoordeelt en bevestigt terugkerende inkomsten en uitgaven en krijgt een herleidbaar maandbeeld.
3. Een huishouden legt spaargeld en schulden vast en vergelijkt één eenvoudige toekomstige verandering, met zichtbare aannames, onzekerheden en beperkingen.

### Blokkerende risico's

Een open risico blokkeert de overdracht alleen wanneer het kan leiden tot verkeerde financiële uitkomsten, verloren of ongewenst gewijzigde gegevens, tegenstrijdige contracten of gedrag dat de ontwikkelaar zelf inhoudelijk zou moeten uitvinden. Kleine technische keuzes mogen openblijven wanneer zij expliciet als implementatievrijheid zijn vermeld.

De specificatie is dus klaar wanneer het hoofddocument en de bijlagen onderling consistent zijn, iedere belangrijke eis traceerbaar en door de minimale voorbeelden gedekt is, de drie verhalen van begin tot eind sluiten en geen blokkerend risico resteert.

### Adviesgrens

De engine blijft feitelijk en deterministisch: zij levert herleidbare feiten, berekeningen, onzekerheden en scenario's, maar geen aanbeveling. Een agentoperator mag hiervan afzonderlijke, niet-bindende agentbegeleiding maken op basis van expliciete doelen en zichtbare aannames. Hij mag opties en productcategorieën bespreken, maar beveelt in v0.1 geen specifiek financieel product aan. Bij belangrijke, ingewikkelde of mogelijk gereguleerde keuzes markeert hij zijn begeleiding als voorlopig en verwijst hij voor de uiteindelijke beslissing naar een bevoegde financiële of fiscale deskundige.

Een deskundigenreview blokkeert de eerste implementatie en technische tests niet, omdat v0.1 geen diepe fiscale, pensioen-, verzekerings- of hypotheekberekeningen uitvoert. Zo'n review is wel een noodzakelijke veiligheidsstap voordat belangrijke financiële beslissingen op agentbegeleiding worden gebaseerd.
