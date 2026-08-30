# 08 — Gerealiseerde maandcashflow berekenen

**Wat te bouwen:** Een huishouden kan over een expliciete kalendermaand de werkelijk geboekte ontvangsten, betalingen en netto geldbeweging laten berekenen, met afzonderlijke zichtbaarheid van transfers, ongeclassificeerde transacties en onvolledige dekking.

**Geblokkeerd door:** 03 — Financiële domeinmodules en Nederlandse betekenis veilig laden; 06 — Letterlijke transactiegegevens importeren.

**Status:** ready-for-agent

- [ ] De analyse gebruikt een expliciet bereik en een halfopen periode en verwijst naar alle gebruikte transacties en toerekeningen.
- [ ] Bevestigde gekoppelde interne overboekingen tellen niet als inkomen of uitgave en worden niet dubbel geteld.
- [ ] Ongeclassificeerde transacties blijven onderdeel van de netto geldbeweging maar maken alleen de categorie-uitsplitsing voorlopig.
- [ ] Volledigheid vereist aantoonbare transactiedekking en bekende huishoudelijke toerekening per opgenomen rekening.
