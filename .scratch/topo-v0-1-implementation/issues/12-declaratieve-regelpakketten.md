# 12 — Declaratieve regelpakketten valideren en activeren

**Wat te bouwen:** Een gebruiker kan een compleet, versiegebonden pakket met veilige declaratieve regels valideren, vooraf bekijken en expliciet activeren. Regels blijven binnen vaste capabilities en kunnen nooit vrije code, opslagtoegang of directe contextmutaties verkrijgen.

**Geblokkeerd door:** 05 — Ontbrekende context en de volgende nuttige vraag tonen; 07 — Kandidaten voor terugkerende kasstromen herkennen.

**Status:** ready-for-agent

- [ ] Alleen de regeltypen herkenning, validatie, volledigheid en vraagprioritering met geregistreerde input-views en predicates worden geaccepteerd.
- [ ] Vrije expressies, custom YAML-tags, onbekende predicates, cross-viewvelden en ongeldige uitkomsttypen worden semantisch geweigerd.
- [ ] Validatie en preview zijn effectvrij; activatie vereist expliciete autorisatie en een actuele verwachte manifestversie.
- [ ] Geldige activatie wisselt het volledige manifest atomair en iedere evaluatie bevat een uitlegtrace van pakket, regel, predicate, input-view en condities.
