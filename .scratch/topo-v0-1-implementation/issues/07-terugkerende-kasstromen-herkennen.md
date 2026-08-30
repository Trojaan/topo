# 07 — Kandidaten voor terugkerende kasstromen herkennen

**Wat te bouwen:** Topo kan Tally- en generieke transacties effectvrij onderzoeken op terugkerende inkomsten en uitgaven. De herkenning levert verklaarbare kandidaten op die een gebruiker afzonderlijk kan indienen en bevestigen, zonder de onderliggende transacties te vervangen.

**Geblokkeerd door:** 06 — Letterlijke transactiegegevens importeren.

**Status:** ready-for-agent

- [ ] De Tally-adapter bewaart letterlijke bronvelden en vertaalt Tally-classificaties uitsluitend naar voorstellen.
- [ ] Herkenning ondersteunt wekelijkse, vierwekelijkse, maandelijkse, kwartaal- en jaarpatronen met bewijs, verwachte periode, bedrag of bandbreedte, afwijkingen en detectiescore.
- [ ] Discovery is effectvrij en bewaart alleen een kandidaat wanneer die later expliciet via proposal submit wordt geselecteerd.
- [ ] Onvoldoende historie levert geen patroon maar een verklaarbaar INSUFFICIENT_PATTERN_HISTORY-aandachtspunt op.
