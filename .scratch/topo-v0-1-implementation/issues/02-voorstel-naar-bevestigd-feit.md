# 02 — Een voorstel omzetten in een bevestigd financieel feit

**Wat te bouwen:** Een gebruiker kan een gestructureerd financieel voorstel indienen, vooraf bekijken, autoriseren, bevestigen, corrigeren of afwijzen. De volledige route bewaart bewijs, beslissingen en mutatiehistorie zonder een voorstel stilzwijgend tot waarheid te promoveren.

**Geblokkeerd door:** 01 — Een lege Topo-context aanmaken en inspecteren.

**Status:** ready-for-agent

- [ ] Indienen bewaart een onveranderlijk voorstel met producent, bewijs en voorgestelde bewering in een nieuwe generatie.
- [ ] Bevestigen zonder autorisatie retourneert een effectvrije preview; geldige autorisatie creëert atomair een afzonderlijke bevestigde bewering.
- [ ] Corrigeren bewaart het oorspronkelijke voorstel en voegt gebruikersbewijs en de gecorrigeerde bevestigde bewering toe; afwijzen creëert geen bewering.
- [ ] Herhaling van dezelfde operatie is idempotent en een verouderde verwachte generatie wordt zonder effect geweigerd.
