# 04 — Canonieke opslag beschermen tegen fouten en manipulatie

**Wat te bouwen:** Een Topo-context blijft betrouwbaar bij een afgebroken write, verweesde stagingdata of gemanipuleerde bestanden. De engine opent alleen aantoonbaar geldige generaties en blokkeert risicovolle writes zonder beschikbare diagnostiek weg te nemen.

**Geblokkeerd door:** 02 — Een voorstel omzetten in een bevestigd financieel feit.

**Status:** ready-for-agent

- [ ] Publicatie gebruikt exclusieve vergrendeling, volledige staging, validatie en een atomaire wissel van de actuele generatie.
- [ ] Na een crash met complete of incomplete staging opent Topo de laatste geldige actuele generatie en publiceert het verweesde materiaal nooit automatisch.
- [ ] Aantoonbaar veilige staging- en orphan-data kan worden opgeruimd zonder geldige context te verwijderen.
- [ ] Checksum- of manifestmanipulatie levert PACKAGE_INTEGRITY_FAILED, behoudt veilige reads en diagnostiek en blokkeert mutaties en migraties met effect: none.
