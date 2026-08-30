# 14 — Context veilig migreren, herstellen, bewaren en verwijderen

**Wat te bouwen:** Een beheerder kan een Topo-context gecontroleerd laten evolueren, herstellen en verkleinen zonder historie stil te herschrijven of de actuele geldige generatie te verliezen. Privacyverwijdering kan geselecteerde gevoelige gegevens daadwerkelijk uit het pakket verwijderen.

**Geblokkeerd door:** 03 — Financiële domeinmodules en Nederlandse betekenis veilig laden; 04 — Canonieke opslag beschermen tegen fouten en manipulatie.

**Status:** ready-for-agent

- [ ] Schema- en modulemigraties worden vooraf gevalideerd en publiceren alleen bij volledig succes een nieuwe generatie; een incompatibele migratie laat de huidige generatie intact.
- [ ] Herstel valideert het gekozen herstelpunt en publiceert de herstelde toestand als een nieuwe generatie met eigen mutatiehistorie.
- [ ] Begrensde, configureerbare retentie bewaart actuele en noodzakelijke herstelgeneraties en verwijdert alleen aantoonbaar niet-benodigde generaties.
- [ ] Een privacy-scrub verwijdert geselecteerd bewijs en historie pakketbreed en markeert resterende beweringen expliciet als niet langer verifieerbaar.
