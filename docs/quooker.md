# Quooker-regeling

**Status:** 🟢 Actief via bestaande Quooker-flows  
**Flow:** `Quooker`-flowfolder (meerdere flows)

De Quooker-flows reageren op de bestaande tijdvensters en sturen de Quooker aan; de shadowintegratie leest alleen mee en stuurt niets extra aan.

## Doel
De bestaande Quooker-flows bepalen wanneer de Quooker beschikbaar mag zijn. Binnen de energiearchitectuur wordt deze regeling als comfortconstraint meegenomen, zodat toekomstige optimalisatie de bestaande gebruiksvensters respecteert.

## Trigger
De bestaande flows in de Homey-flowfolder **Quooker** zijn leidend. Het gaat dus niet om slechts drie veronderstelde flows, maar om de volledige set flows in die folder.

## Inputs
- Tijd/dag van de week.
- Bestaande Quooker-flowlogica en tijdvensters.
- Quooker aan/uit-status voor shadowanalyse.

## Logica
De huidige shadowintegratie verandert de Quooker-regeling niet. Shadow v0.2 leest de Quookerstatus en gebruikt de bestaande tijdvensters als context. Daarmee kunnen we later onderzoeken of coördinatie met Tesla, boiler en Victron zinvol is zonder het huidige comfortgedrag te verstoren.

## Outputs
- Bestaande Quooker aan/uit-regeling blijft actief via de bestaande flows.
- Shadow v0.2 registreert Quookerstatus en venstercontext apart.

## Aangestuurde apparaten
De bestaande Quooker-flows sturen de Quooker aan. De shadowlaag zelf stuurt **niets**.

## Status
Bestaande Quooker-regeling actief. De Quooker-aware shadowversie v0.2 staat gereed voor de geplande overgang na de baselineperiode.

## Afhankelijkheden
Quooker-apparaat in Homey, bestaande flows in de Quooker-folder en de Energy Manager shadowarchitectuur.
