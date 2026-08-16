# Live energiestroom

Deze pagina maakt de energiearchitectuur **live zichtbaar**. De bovenste energiebalans toont de meest recente P1- en PV-metingen; de apparaatverdeling daaronder wordt alleen aan diezelfde balans gekoppeld wanneer de meetmomenten voldoende dicht bij elkaar liggen.

<div id="live-energy-flow">
  <p><em>Live energiestroom wordt geladen…</em></p>
</div>

!!! info "Tijdconsistentie is leidend"
    P1/PV wordt ongeveer iedere 2 minuten gepubliceerd, terwijl Tesla-, boiler- en andere Energy Manager-shadowwaarden op een ander publicatiemoment kunnen binnenkomen. De website combineert deze bronnen daarom **alleen wanneer de timestamps maximaal 90 seconden verschillen**. Is dat niet zo, dan toont de apparaatverdeling bewust `—` in plaats van een stale Tesla- of boilerwaarde als **Overig verbruik** te boeken.

## Gemeten versus toegewezen

P1, PV-productie, Tesla- en boilervermogen zijn gemeten waarden uit de bestaande Homey/GitHub-datasets. De energiebalans geldt boekhoudkundig als:

```text
woningverbruik = PV-productie + netimport - netexport ± batterij
```

De batterij is momenteel niet actief. Een negatieve P1-waarde betekent export; een positieve P1-waarde import.

De verdeling van het totale woningverbruik over Tesla, boiler, wasmachine, droger en Overig is alleen betrouwbaar wanneer die apparaatmetingen uit hetzelfde tijdvenster komen als de P1/PV-balans. **Overig verbruik is uitsluitend een sluitpost van een geldige, tijd-consistente meetset.**

## Live balans versus apparaatuitsplitsing

Boven het diagram worden voortaan twee meetmomenten getoond:

- **Live balans** — nieuwste P1/PV-meetmoment;
- **Apparaten** — laatste Energy Manager-shadowmeting.

Wanneer deze maximaal **90 seconden** verschillen, wordt de apparaatuitsplitsing als **synchroon** gemarkeerd en mogen Tesla, boiler en Overig worden berekend. Bij een groter verschil wordt de uitsplitsing als **vertraagd** gemarkeerd.

Dit voorkomt specifiek het probleem dat een Tesla die tussen twee shadowpublicaties start of stopt meerdere kilowatts ten onrechte onder **Overig verbruik** laat verschijnen.

## Interpretatie

Een dikke actieve lijn betekent een grotere vermogensstroom. Een dunne/grijze lijn betekent dat het pad op dat moment niet of nauwelijks actief is. Bij netafname loopt vermogen vanaf **Net** naar de woning; bij teruglevering loopt de richting naar **Net**.

De verbindingen van **Huis** naar de onderliggende verbruikers zijn afzonderlijke connectoren. De lijnsterkte van Tesla, boiler, wasmachine, droger en Overig wordt uitsluitend bepaald door die specifieke belasting wanneer daarvoor een geldige synchrone meetset beschikbaar is.

De centrale Energy Manager blijft momenteel grotendeels in **shadow mode**. De kaart onderscheidt daarom de actuele fysieke energiebalans van beslis-/statusinformatie.

## Grootverbruikers onder Huishouden

Onder **Huishouden** worden bekende grote verbruikers apart zichtbaar gemaakt:

- **Tesla / Easee** — werkelijk laadvermogen indien tijd-consistent beschikbaar;
- **Boiler** — werkelijk vermogen indien tijd-consistent beschikbaar;
- **Wasmachine — L2, groep 1, aardlek 1** — Homey-status, geen individueel live wattage;
- **Droger — L3, groep 2, aardlek 1** — Homey-status, geen individueel live wattage;
- **Overig huishouden** — uitsluitend de rekenkundige rest van een synchrone meetset.

Voor wasmachine en droger wordt bewust geen wattage geschat zolang hun Homey-integraties geen individueel `measure_power` leveren.

## Tesla gevraagd versus werkelijk

Het aparte Tesla-paneel toont de **laatste Energy Manager-shadowmeting** met gevraagde laadstroom, geschatte werkelijk geleverde laadstroom en Tesla-vermogen. Dit paneel vermeldt expliciet het shadow-meetmoment. Een oudere shadowmeting wordt niet meer voorgesteld als onderdeel van de nieuwste P1/PV-balans.

De Easee Equalizer blijft de harde veiligheidslaag voor de hoofdaansluiting.

## Huidige toewijzingsvolgorde

1. actuele P1/PV-balans bepalen;
2. alleen bij een synchrone apparaatmeting bekende verbruikers aftrekken;
3. resterend woningverbruik als **Overig** tonen;
4. bij ontbrekende synchronisatie geen restpost berekenen.

Het dashboard controleert in de browser iedere **5 minuten** op nieuw gepubliceerde GitHub-data. Dit veroorzaakt geen extra polling richting Homey.

Later kan dezelfde kaart worden uitgebreid met de Victron-laag: batterij laden/ontladen, netladen, eilandbedrijf en vermogensgrenzen per fase.
