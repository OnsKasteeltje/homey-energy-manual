# Live energiestroom

Deze pagina maakt de energiearchitectuur **live zichtbaar**. De lijnen tonen de actuele vermogensrichting en een boekhoudkundige toewijzing volgens de huidige Energy Manager-prioriteiten.

<div id="live-energy-flow">
  <p><em>Live energiestroom wordt geladen…</em></p>
</div>

!!! info "Gemeten versus toegewezen"
    P1, PV-productie, Tesla- en boilervermogen zijn gemeten waarden uit de bestaande Homey/GitHub-datasets. De verdeling **PV → huishouden → Tesla → boiler → net** is een boekhoudkundige toewijzing volgens de architectuur en is geen fysieke meting van afzonderlijke elektronenstromen.

## Interpretatie

Een dikke actieve lijn betekent een grotere vermogensstroom. Een dunne/grijze lijn betekent dat het pad op dat moment niet of nauwelijks actief is. Bij netafname loopt vermogen vanaf **Net** naar de woning; bij teruglevering loopt de richting naar **Net**.

De verbindingen van **Huis** naar de onderliggende verbruikers zijn bewust als **afzonderlijke rechte connectoren** opgebouwd. Er is geen gedeelde horizontale vermogensbus meer: de lijnsterkte van Tesla, boiler, wasmachine, droger en overig verbruik wordt uitsluitend bepaald door die specifieke belasting. Daardoor wordt bijvoorbeeld alleen de verbinding naar **Overig verbruik** dik wanneer daar op dat moment het gemeten/toegewezen vermogen zit.

De centrale Energy Manager blijft momenteel grotendeels in **shadow mode**. De kaart onderscheidt daarom de actuele fysieke energiebalans van de actuele beslis-/statusinformatie.

## Grootverbruikers onder Huishouden

Onder **Huishouden** worden bekende grote verbruikers apart zichtbaar gemaakt:

- **Wasmachine — L2**;
- **Droger — L3**;
- **Vaatwasser**;
- **Overig huishouden**.

Vanaf `Energie Manager PV - Shadow Mode v1.6.6` publiceert de bestaande baseline-run ook `washerActive` en `dryerActive`. De website kan daardoor voor wasmachine en droger **ACTIEF** of **idle** tonen op basis van de Homey `measure_applianceState`, zonder een extra Homey-meetflow toe te voegen.

De wasmachine- en drogerintegraties leveren geen individueel live wattage. Daarom wordt voor deze apparaten bewust geen vermogen geschat. Hun verbruik blijft onderdeel van de totale huishoudelijke energiebalans en **Overig huishouden** blijft de sluitpost zolang geen afzonderlijke vermogensmeting beschikbaar is.

De vaatwasser is visueel voorbereid, maar wordt pas als actief getoond zodra een betrouwbare statusbron in de bestaande publicatiedata is opgenomen.

## Huidige toewijzingsvolgorde

1. normaal huishoudelijk verbruik;
2. Tesla wanneer zinvol beschikbaar vermogen aanwezig is;
3. elektrische boiler;
4. resterend vermogen naar het net.

Het dashboard controleert in de browser iedere **5 minuten** op nieuw gepubliceerde GitHub-data. Dit veroorzaakt geen extra polling richting Homey.

Later kan dezelfde kaart worden uitgebreid met de Victron-laag: batterij laden/ontladen, netladen, eilandbedrijf en vermogensgrenzen per fase.
