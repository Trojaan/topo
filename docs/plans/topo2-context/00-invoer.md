# Plan 0 — Van bronnen naar een bruikbare eerste context

Status: technisch en voor de uitgevoerde synthetische basisjourney in gebruik
geleverd. Zie [extern gebruiksbewijs 0–2](gebruik-bewijs-00-02.md), inclusief
herstelstappen, beperkte tijdmeting en niet uitgevoerde optionele proeven.


Levering: `topo2.cli/3`, behoud van verrijkingen bij import, expliciet wissen via
JSON null, brongebonden gezamenlijke wijzigingen en identieke updates zonder
schrijven. Opslag blijft `topo2.context/2`. Zie [geleverd bewijs en beperkingen](00-bewijs.md)
voor tests, bronnen, agentsessie, frictiebudget en meetresultaten. Vervolgplannen
zijn niet uitgevoerd.

## Resultaat

De gebruiker levert een export, saldoscreenshots en een korte vraag of doel aan.
De agent bereidt een gedeeltelijke context voor, vraagt weinig bij en levert na
één gezamenlijke bevestiging een eerste bruikbaar overzicht. Dit plan begint met
de bestaande records; toekomstige schulden en geldstromen zijn geen voorwaarde.

## Scope

- Beschrijf en beproef de agentworkflow: actuele contracten en bestaande context
  gericht lezen, bronnen verwerken, relevante onzekerheden selecteren, één preview
  presenteren, na goedkeuring opslaan en inzicht teruggeven.
- De agent zet exports om naar het vaste importformaat en leest screenshots waar
  mogelijk. Geen ingebouwde OCR-, bankadapter- of herkenningsinfrastructuur.
- Gebruik bekende rekeningen, stabiele transactie-IDs, categorieën en eerdere input
  opnieuw. Ambigue rekeningkoppelingen en onleesbare waarden worden niet geraden.
- Scheid aangeleverde waarden, voorbereide interpretaties en onbekende informatie
  in de leesbare preview. Interpretaties mogen mee in dezelfde bevestigde batch.
- Bundel nieuwe rekeningen, waarden, doelen en transacties waar nodig via `change`.
  Voorkom een verplichte reeks import-bevestiging-classificatie-bevestiging.
- Maak herimport veilig voor verrijkingen: ontbrekende optionele importvelden
  behouden bestaande categorieën, bronlabels en later classificaties. Expliciet
  wissen of vervangen blijft mogelijk en zichtbaar in de preview.
- Een bronlabel of korte toelichting volstaat waar nuttig; geen bewijsregister,
  bronarchief, herkomstgraph of aparte voorstelstatussen.

## Voor implementatie beslissen

Leg vast hoe afwezige velden, expliciet lege waarden en expliciete vervanging bij
import worden onderscheiden. De huidige import vervangt volledige records; deze
wijziging vereist bewuste contractversiekeuze en compatibiliteitsdocumentatie.
Behoud de bestaande volledige-recordsemantiek van `change.update`; documenteer hoe
de agent daarbij verrijkingen meeneemt. Identieke effectieve invoer schrijft niets.

Kies een reproduceerbare omzetting voor de synthetische export en stabiele IDs.
Leg vast hoe de agent contextverrijkingen behoudt bij het voorbereiden van een
gecombineerd `change`-request. Bouw alleen een klein gedeeld voorbereidingspad als
de journey aantoont dat dit nodig is; geen nieuw importframework.

## Acceptatie en bewijs

- Gebruik een synthetische bankexport met eigen overboekingen, enkele leesbare
  saldoscreenshots en een kort doelbericht. Bewaar geen persoonlijke bronnen.
- De gebruiker krijgt een vermogensbeeld en een eerste bespreking op basis van
  beschikbare gegevens; ontbrekende schulden en kasstroominformatie worden lokaal
  benoemd, niet eerst verplicht uitgevraagd. Latere plannen verrijken dit resultaat.
- Maximaal drie korte gebundelde verduidelijkingsvragen en één menselijke
  bevestiging voor de samenhangende wijziging. Geen extra toestemming voor lezen,
  analyseren, bronconversie of het voorbereiden van wijzigingen.
- De agent vraagt geen gegevens die al bekend zijn en geen beschikbaarheid,
  compleetverklaring of doelverdeling zonder concrete noodzaak voor de gebruikersvraag.
- Een identieke heraanlevering schrijft niets en vraagt geen bevestiging. Een
  bijgewerkte export behoudt eerdere verrijkingen en vraagt alleen over nieuwe
  wezenlijke ambiguïteiten. Expliciet wissen/vervangen is afzonderlijk bewezen.
- Een black-box journey bewijst gezamenlijk wijzigen, importbehoud, expliciete
  vervanging, validatie en tokenbinding op de effectieve wijziging en relevante
  broninput. Behoud ook de bestaande garanties tegen gewijzigde importbytes.
- Een vastgelegde agentsessie bewijst de route vanaf bronnen en het frictiebudget.
  Meet tijd tot eerste inzicht en herstelwerk; leg de eerste baseline vast.

## Buiten scope

Alle banken ondersteunen, enginecategorisatie, opgeslagen voorstellen, workflow-
regels, verplichte volledige inventarisatie en automatische bevestiging.
