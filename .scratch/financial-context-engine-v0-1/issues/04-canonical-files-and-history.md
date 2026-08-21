# Hoe worden context en mutatiehistorie canoniek opgeslagen?

Type: prototype
Status: resolved
Blocked by: 01, 02

## Question

Welke file-first mappenstructuur, bestandsgrenzen, schema's, identifiers en historie-opzet maken de context mensleesbaar, atomair valideerbaar, veilig wijzigbaar, migreerbaar en privacybewust verwijderbaar?

## Answer

Gebruik per zelfstandige financiële contextgraph één lokaal **contextpakket**. Een pakket mag meerdere personen en huishoudens door de tijd heen bevatten en heeft één stabiele `context_id`. Splits een pakket niet per persoon of huishouden: gezamenlijke objecten en veranderende huishoudrelaties moeten binnen één graph atomair kunnen veranderen.

De actuele, schema-gevalideerde context is canoniek. De mutatiehistorie ondersteunt uitleg en begrensd herstel, maar is geen event source waaruit de actuele toestand moet worden opgebouwd.

### Pakketvorm

```text
<context-package>/
├── CURRENT
├── generations/
│   └── <generation_uuidv7>/
│       ├── manifest.json
│       ├── entities.json
│       ├── assertions.json
│       ├── evidence.json
│       └── proposals.json
├── evidence/
│   └── records/
│       └── <evidence_uuidv7>.json
├── history/
│   └── journal.json
└── staging/
```

- `CURRENT` bevat uitsluitend de UUIDv7 van de gepubliceerde generatie en wordt via een atomaire bestandsvervanging omgeschakeld.
- `manifest.json` bevat minimaal `context_id`, generatie-ID, voorgaande generatie-ID, pakket- en schemaversies, mutatie-ID, registratietijd en checksums van alle collectie­bestanden.
- De getypeerde collecties zijn gewone JSON-documenten met een `schema_version` en een `records`-array. Records zijn deterministisch op ID gesorteerd en worden stabiel geformatteerd. JSONL is geen canonieke vorm in v0.1.
- `evidence.json` bevat de herkomststructuur en verwijzingen; gebruikte genormaliseerde bronrecords staan zelfvoorzienend onder `evidence/records/`. Een externe locatie en checksum mogen als extra bronmetadata worden bewaard, maar zijn niet de enige kopie van het gebruikte bewijs.
- `history/journal.json` bevat structurele mutatiemetadata, geen gekopieerde oude of nieuwe financiële waarden. Als de journalupdate na publicatie wordt onderbroken, kan de engine de ontbrekende waardevrije entry uit het generatiemanifest reconstrueren.
- `staging/` bevat uitsluitend nog niet gepubliceerde werkbestanden en is nooit canoniek.

Alle eersteklas identifiers — context, entiteit, bewering, bewijs, voorstel, mutatie en generatie — zijn wereldwijd unieke UUIDv7's. Een identifier codeert geen veranderlijk domeintype. Identifiers van externe bronnen blijven afzonderlijke bronreferenties.

### Atomaire mutatie

v0.1 gebruikt één lokale schrijver, een exclusieve package-lock, een door de aanroeper opgegeven unieke mutatie-ID en optimistic concurrency op de verwachte `CURRENT`-generatie.

1. Open het pakket en voer startup recovery uit.
2. Controleer de checksums en valideer de actuele generatie volledig tegen JSON Schema, referentiële integriteit, moduleconstraints en de verwachte basisgeneratie.
3. Pas de volledige wijzigingsset in `staging/` toe op een nieuwe generatie.
4. Schrijf benodigd bewijs vóór publicatie, maar beschouw het nog niet als bereikbaar vanuit de canonieke graph.
5. Valideer de nieuwe generatie volledig en synchroniseer bestanden en mappen naar duurzame opslag.
6. Verplaats de complete generatie naar `generations/` en vervang daarna `CURRENT` atomair.
7. Werk het waardevrije journaal bij. Een herhaalde mutatie-ID retourneert hetzelfde resultaat en maakt geen tweede generatie.

Een crash vóór stap 6 laat `CURRENT` intact. Bij openen verwijdert de engine deterministisch onvolledige staging en complete maar ongepubliceerde orphan-generaties; zij publiceert nooit zelf een orphan. Onbereikbaar bewijs wordt eveneens opgeruimd. Kan de engine niet ondubbelzinnig vaststellen of deze cleanup veilig is, dan blijven reads mogelijk maar worden writes geblokkeerd.

### Validatie, manipulatie en herstel

De engine valideert niet alleen `CURRENT`, maar alle bewaarde generaties, manifests, checksums, collectie­schema's, bewijsverwijzingen, lineage en journalconsistentie. Directe bestandswijzigingen zijn leesbaar maar niet toegestaan: een checksumverschil blokkeert mutaties en migraties. Checksums worden nooit stilzwijgend opnieuw berekend om manipulatie te accepteren.

Normaal herstel of rollback zet de pointer niet terug. De engine kopieert een gekozen, vertrouwde oude toestand naar een nieuwe generatie, valideert die en publiceert haar met een expliciete herstelmutatie. Daardoor blijft duidelijk wat er gebeurde.

`based_on` is een historische generatie-ID en geen harde foreign key naar een nog bewaard pakket. Als de parent aanwezig is, moet zij valide zijn. Als zij door retentie is verdwenen, moet een waardevrije compactieregistratie haar verwijdering verklaren. Ontbreken zowel parent als compactieregistratie, dan faalt validatie.

### Retentie, privacy en migratie

Oude generaties worden volgens een expliciete, begrensde lokale retentiepolicy bewaard. De huidige generatie wordt nooit door gewone compactie verwijderd. De policy en standaardlimiet worden via het latere CLI- en configuratiecontract vastgelegd.

Normale generaties en bronrecords zijn immutable. Privacyverwijdering is de enige pakketbrede uitzondering: zij verwijdert het doel uit de actuele generatie, alle bewaarde herstelgeneraties, staging, orphans, genormaliseerd bewijs en eventuele mutatievelden, en herschrijft bijbehorende manifests en checksums. Alleen waardevrije metadata dat een privacyactie plaatsvond mag blijven. De engine verifieert daarna dat de doel-ID's en doelvelden nergens in het door haar beheerde pakket voorkomen.

Privacyverwijdering mag ook op een beschadigd pakket gegevens scrubben, maar publiceert dan geen nieuwe geldige generatie op basis van de onbetrouwbare `CURRENT`; het pakket blijft geblokkeerd tot expliciet herstel. Een herhaalde verwijdering die niets vindt is idempotent: zij maakt geen generatie en registreert alleen een waardevrije no-op.

Deze garantie geldt uitsluitend binnen het beheerde contextpakket. Forensisch wissen van SSD-restdata, besturingssysteemsnapshots, cloudsynchronisatie en externe back-ups valt erbuiten.

Schema-evolutie gebeurt uitsluitend met benoemde, versiegebonden migraties. Een migratie leest een oude generatie, produceert een nieuwe generatie, valideert die volledig en schakelt pas daarna `CURRENT` om. Zij verandert nooit een bestaande generatie ter plekke. Een onbekende nieuwere hoofdversie wordt geweigerd in plaats van gedeeltelijk geïnterpreteerd.

v0.1 voegt geen eigen applicatieversleuteling toe. JSON blijft lokaal leesbaar, bestanden krijgen uitsluitend eigenaarstoegang en de documentatie verlangt passende schijf- of mapversleuteling van het besturingssysteem. Een versleutelde opslagadapter kan later worden toegevoegd.

Primary-source prototype: branch `prototype/canonical-storage-generations`, path `.scratch/financial-context-engine-v0-1/assets/canonical-storage-prototype/`.
