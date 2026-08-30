# 10 — Nettovermogen conservatief berekenen

**Wat te bouwen:** Een persoon of huishouden kan het nettovermogen op een expliciete peildatum laten berekenen zonder dubbeltelling of stilzwijgende schattingen. Onbekende waarderingen, beperkte beschikbaarheid en ontbrekende wisselkoersen blijven lokaal zichtbaar.

**Geblokkeerd door:** 03 — Financiële domeinmodules en Nederlandse betekenis veilig laden; 04 — Canonieke opslag beschermen tegen fouten en manipulatie.

**Status:** ready-for-agent

- [ ] Geldige rekeningstanden, bezittingen en schulden worden volgens expliciete scope en toerekening opgeteld zonder rekening-, positie- of schuldduplicatie.
- [ ] Beperkt beschikbaar pensioen wordt afzonderlijk gerapporteerd en niet automatisch als vrij nettovermogen meegeteld.
- [ ] Per-valutasubtotalen kunnen complete blijven wanneer een geconverteerd totaal door een ontbrekende koers unavailable is.
- [ ] Ontbrekende of conflicterende waarderingen treffen alleen afhankelijke componenten en worden nooit als nul of geschatte waarde ingevuld.
