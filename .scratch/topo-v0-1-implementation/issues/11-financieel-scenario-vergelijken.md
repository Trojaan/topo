# 11 — Eén expliciet financieel scenario vergelijken

**Wat te bouwen:** Een gebruiker kan een baseline vergelijken met één of meer expliciete, begrensde wijzigingen in terugkerende kasstromen of objectwaarden. Het scenario blijft effectvrij en maakt iedere aanname, uitkomst en delta herleidbaar.

**Geblokkeerd door:** 09 — Genormaliseerde maandcashflow berekenen; 10 — Nettovermogen conservatief berekenen.

**Status:** ready-for-agent

- [ ] Het scenario accepteert uitsluitend toegestane, getypepte aannames met doelobject, datum, reden, valuta en herkomst.
- [ ] Baseline, scenario en delta worden afzonderlijk berekend en rapporteren projected kennis met dezelfde componentstatussen als gewone analyses.
- [ ] Een lagere uitgave verandert de cashflow maar niet automatisch het vermogen; zonder gemodelleerde bestemming verschijnt CASHFLOW_DESTINATION_NOT_MODELED.
- [ ] De vergelijking muteert geen canonieke context en verzint geen rendement, belasting, rente-op-rente of productadvies.
