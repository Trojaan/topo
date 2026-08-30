# 06 — Letterlijke transactiegegevens importeren

**Wat te bouwen:** Een expliciet geautoriseerde bronadapter kan genormaliseerde JSON- en CSV-transacties als onveranderlijke waarnemingen importeren, met blijvende bronidentiteit en zonder externe classificaties als bevestigde financiële betekenis over te nemen.

**Geblokkeerd door:** 03 — Financiële domeinmodules en Nederlandse betekenis veilig laden; 04 — Canonieke opslag beschermen tegen fouten en manipulatie.

**Status:** ready-for-agent

- [ ] Iedere geïmporteerde transactie bewaart de letterlijke rekening, boekingsdatum, money, omschrijving en stabiele bronreferentie als waarneming en bewijs.
- [ ] Een exacte herhaling van dezelfde operatie retourneert no_change met dezelfde referenties en maakt geen nieuwe generatie.
- [ ] Een broncorrectie overschrijft het eerdere record niet maar legt een herleidbare opvolger vast.
- [ ] Classificaties of uitleg uit de bron worden als voorstellen vastgelegd en nooit automatisch bevestigd.
