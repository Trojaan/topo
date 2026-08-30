# 03 — Financiële domeinmodules en Nederlandse betekenis veilig laden

**Wat te bouwen:** Topo laadt gepinde financiële domeinmodules en de Nederlandse jurisdictie-overlay als expliciete, versiegebonden capabilities. Daardoor kan de engine universele financiële betekenis en Nederlandse constraints toepassen zonder EngineCore of de presentatielaag ermee te vermengen.

**Geblokkeerd door:** 02 — Een voorstel omzetten in een bevestigd financieel feit.

**Status:** ready-for-agent

- [ ] De modulecatalogus valideert identifiers, versies, checksums, capabilities, compatibiliteit en een acyclische afhankelijkhedengraph.
- [ ] Universele domeinclassificaties en jurisdiction.nl-kwalificaties worden alleen via hun publieke contracten toegepast.
- [ ] Nederlandse constraints, waaronder een verplichte WOZ-waardepeildatum en geldige volledige verdelingen, weigeren ongeldige mutaties zonder partieel effect.
- [ ] Bij een ontbrekende gepinde semantische module blijven generieke reads en export beschikbaar, terwijl afhankelijke mutaties en analyses veilig worden geblokkeerd.
