# Hoe verloopt de keten van bronbewijs naar bevestigd financieel feit?

Type: prototype
Status: resolved
Blocked by: 01, 02, 03

## Question

Hoe importeren bronadapters transacties en handmatige antwoorden, hoe worden patronen met bewijs en zekerheid contextvoorstellen, hoe bevestigt of corrigeert de gebruiker die, en wanneer mag nieuwe brondata een bestaand feit actualiseren of als afwijkend markeren?

## Answer

Gebruik één herleidbare keten waarin bronwaarneming, patroonherkenning, voorstelvalidatie en canonieke mutatie afzonderlijke verantwoordelijkheden zijn.

### Import en handmatige invoer

Een expliciet geautoriseerde bronadapter mag uitsluitend letterlijke bronvelden — zoals bedrag, valuta, boekingsdatum en stabiele bronreferentie — zonder bevestiging per record als waarneming importeren. De adapter bewaart bronidentiteit en herkomst; een broncorrectie overschrijft het oude record niet maar wordt een herleidbare opvolger.

Een gebruiker kan bewust gestructureerde, schema-gevalideerde invoer direct als bevestigd feit indienen. Vrije tekst die een LLM interpreteert wordt daarentegen altijd eerst een expliciet contextvoorstel, zodat de gebruiker de gestructureerde betekenis kan controleren.

### Voorstelproductie en EngineCore

De EngineCore herkent zelf geen financiële patronen. De LLM-agentoperator is in v0.1 de voornaamste voorstelproducent; deterministische regelmodules mogen via precies hetzelfde voorstelcontract werken. Een voorstel bevat minimaal:

- de voorgestelde bewering met geldigheidsperiode;
- de producerende agent of regelmodule en diens versie;
- alle gebruikte bronreferenties of eerdere beweringen;
- een begrijpelijke redeneer- of regelreferentie;
- eventuele producent-specifieke detectiezekerheid.

EngineCore kent geen universele confidence-score. Zij valideert schema, typen, bestaande referenties, herkomst, constraints en toegestane statusovergangen, maar beoordeelt niet zelf of het patroon inhoudelijk waarschijnlijk is.

### Bevestiging en correctie

Een voorstel wordt nooit stilzwijgend een financieel feit. Expliciete bevestiging maakt in een atomaire contextmutatie een afzonderlijke bevestigde bewering die naar voorstel, bewijs en bevestiging verwijst. Het voorstel blijft als historisch beslisspoor bewaard.

Bij een ondubbelzinnige gebruikerscorrectie blijft het oorspronkelijke voorstel onveranderd met de uitkomst `corrected`. De gestructureerde correctie is nieuw gebruikersbewijs en mag direct de bevestigde bewering vormen; een tweede bevestigingsronde is niet nodig. De bewering verwijst zowel naar het oorspronkelijke bewijs als naar de correctie.

### Nieuwe brondata, opvolging en afwijkingen

Nieuwe letterlijke bronwaarnemingen mogen automatisch worden toegevoegd, maar een afgeleid bevestigd feit wordt in v0.1 nooit automatisch geactualiseerd. Wanneer nieuwe data een ander patroon suggereert, dient de agentoperator of regelmodule een herleidbaar opvolgvoorstel in. Na bevestiging sluit EngineCore de geldigheidsperiode van de oude bewering af en activeert zij de nieuwe; beide blijven in de historie bestaan.

Een afwijkende waarneming is standaard een afzonderlijk aandachtspunt en maakt het bestaande bevestigde patroon niet meteen `disputed`: een uitzonderlijke salarisbetaling kan bijvoorbeeld vakantiegeld of een bonus zijn. De agent of regelmodule kan een verduidelijkingsvraag of opvolgvoorstel produceren. Alleen bewijs dat dezelfde exclusieve betekenis binnen een overlappende geldigheidsperiode rechtstreeks tegenspreekt veroorzaakt een beweringsconflict. Relevante analyses tonen bij een open aandachtspunt een waarschuwing; alleen een relevant echt conflict blokkeert de analyse.

Prototype asset: branch `prototype/evidence-proposal-confirmation`, map `.scratch/financial-context-engine-v0-1/assets/evidence-proposal-confirmation-prototype/`.
