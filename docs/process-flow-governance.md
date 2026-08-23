# Procesflow-governance

## Basisregel: procesflows zijn altijd as-coded

Procesflowdiagrammen zijn geen ontwerpvoornemen en geen historische illustratie. Zij geven **altijd de actuele, werkelijk gecodeerde en actieve softwarestand** weer.

Daarom geldt vanaf nu als harde projectregel:

- Iedere inhoudelijke code- of flowwijziging die de beslisvolgorde, guards, prioriteiten, statusovergangen, triggers, writers, fail-safe-logica of gegevensbron beïnvloedt, vereist **in dezelfde wijziging** een controle van het bijbehorende procesflowdiagram.
- Als de runtime-/productiecode afwijkt van een procesdiagram, is het diagram direct **verouderd** en mag de wijziging niet als afgerond worden beschouwd totdat het diagram is aangepast.
- Een procesdiagram mag geen geplande of gewenste logica als huidige werkelijkheid tonen. Toekomstige logica wordt apart gemarkeerd als `PLANNED`, `SHADOW` of `OPEN` en nooit vermengd met de as-coded productiestroom.
- Versienummers, flow-/scriptnamen en controlstatus in een diagram moeten overeenkomen met de actieve implementatie waarop het diagram betrekking heeft.
- Bij cut-over naar een nieuwe productieflow moet het procesdiagram tegelijk worden bijgewerkt; de oude procesflow wordt expliciet `SUPERSEDED` of als historische referentie aangeduid.
- Bij een code-review, architectuurreview of documentupdate wordt een procesflow standaard tegen de actuele Homey/GitHub-implementatie gecontroleerd en niet alleen tegen oudere documentatie.

## Definition of Done

Een wijziging die procesgedrag raakt is pas **DONE** wanneer:

1. de nieuwe code/flow actief of volgens de bedoelde status gepubliceerd is;
2. de actuele runtime-/controlstatus is gecontroleerd;
3. het bijbehorende procesflowdiagram dezelfde beslislogica en status toont;
4. verouderde procesdiagrammen zijn vervangen of expliciet als historisch/SUPERSEDED gemarkeerd;
5. softwarebaseline en relevante projectdocumentatie hiermee in sync zijn.

Kort: **code is de operationele waarheid; het procesflowdiagram is de actuele visuele representatie daarvan.**
