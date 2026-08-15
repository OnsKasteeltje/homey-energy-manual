# Live energiestroom

Deze pagina maakt de energiearchitectuur **live zichtbaar**. De lijnen tonen de actuele vermogensrichting en een boekhoudkundige toewijzing volgens de huidige Energy Manager-prioriteiten.

<div id="live-energy-flow">
  <p><em>Live energiestroom wordt geladen…</em></p>
</div>

!!! info "Gemeten versus toegewezen"
    P1, PV-productie, Tesla- en boilervermogen zijn gemeten waarden uit de bestaande Homey/GitHub-datasets. De verdeling **PV → huishouden → Tesla → boiler → net** is een boekhoudkundige toewijzing volgens de architectuur en is geen fysieke meting van afzonderlijke elektronenstromen.

## Interpretatie

Een dikke actieve lijn betekent een grotere vermogensstroom. Een dunne/grijze lijn betekent dat het pad op dat moment niet of nauwelijks actief is. Bij netafname loopt vermogen vanaf **Net** naar de woning; bij teruglevering loopt de richting naar **Net**.

De centrale Energy Manager blijft momenteel grotendeels in **shadow mode**. De kaart onderscheidt daarom de actuele fysieke energiebalans van de actuele beslis-/statusinformatie.

## Huidige toewijzingsvolgorde

1. normaal huishoudelijk verbruik;
2. Tesla wanneer zinvol beschikbaar vermogen aanwezig is;
3. elektrische boiler;
4. resterend vermogen naar het net.

Later kan dezelfde kaart worden uitgebreid met de Victron-laag: batterij laden/ontladen, netladen, eilandbedrijf en vermogensgrenzen per fase.
