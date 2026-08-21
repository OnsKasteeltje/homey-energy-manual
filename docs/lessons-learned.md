# Lessons learned

## Tesla-deadline UI – 21 augustus 2026

Tijdens het herstellen van de zichtbaarheid en bediening van de Tesla-deadline op de Live Energy-pagina zijn in korte tijd meerdere implementatievormen gebruikt. De uiteindelijke oplossing is een native component in de Live Energy-renderer met één bijbehorende controller. Uit dit traject volgen onderstaande ontwerp- en werkwijzeregels voor het Home Energy Management System.

### Ontwerpregels

1. **Eén UI-feature = één renderer + één controller + één stylesheet.** Aanvullende migration-, postsave-, status- of DOM-patchscripts horen alleen in productie wanneer ze aantoonbaar nog nodig zijn.
2. **Bij vervanging wordt de oude route in dezelfde wijziging uitgefaseerd.** Een nieuwe implementatie toevoegen is niet voldoende: oude bundle-entries, listeners, selectors en styles moeten worden verwijderd zodra ze niet meer worden gebruikt.
3. **Leg eerst het DOM-contract vast.** Voor een component wordt één canonieke selector/interface gekozen. Renderer, controller, CSS en tests gebruiken uitsluitend dat contract.
4. **MutationObservers zijn geen standaard reparatiemechanisme.** Meerdere scripts die achteraf dezelfde DOM proberen te corrigeren wijzen op onduidelijk componentownership. Waar mogelijk moet de eigenaar van de component zelf de juiste toestand renderen.
5. **Source of truth en presentatie blijven gescheiden.** Command/config/snapshot vormen de data. Eén controller vertaalt die data naar de UI. Andere scripts mogen dezelfde zichtbare status niet vervolgens opnieuw overschrijven.
6. **Deploymentvalidatie test gedrag, niet alleen aanwezigheid.** Naast controleren of bestanden/selectors in de bundle zitten, moeten functionele contracttests relevante toestanden afdekken, bijvoorbeeld: deadline uit → velden verborgen; deadline aan → velden zichtbaar; oude datum → geldige actuele datum; doel-SOC ≤ huidige SOC → opslaan geblokkeerd.
7. **Een fix is pas klaar na cleanup.** Zodra de functie weer werkt volgt altijd een korte dead-code-, CSS- en bundle-audit. 'Het werkt weer' is niet het technische eindpunt.

### Debuggingregel

Bij een vergelijkbare storing wordt eerst vastgesteld in welke laag het probleem zit voordat code wordt gewijzigd:

1. **Data:** is de benodigde state correct gepubliceerd?
2. **Rendering:** wordt de bedoelde component daadwerkelijk opgebouwd?
3. **Binding/controller:** is de component aan precies één controller gekoppeld?
4. **Build/bundle:** zit de bedoelde broncode in het gegenereerde frontend-artifact?
5. **Deployment/cache:** draait de browser/PWA daadwerkelijk die versie?

Wijzig vervolgens in beginsel alleen de laag waarin het defect is aangetoond. Hiermee voorkomen we dat een lokale UI-storing leidt tot gelijktijdige wijzigingen in renderer, runtime, bundling en backendcontracten.

### Definition of Done voor frontend-fixes

Een frontend-fix is voortaan pas afgerond wanneer:

- de gewenste functie end-to-end werkt;
- er één aantoonbare actieve implementatieroute is;
- vervangen runtime-code en CSS niet meer actief worden meegebundeld;
- selectors en componentversies consistent zijn;
- automatische tests het relevante gedrag controleren;
- de gebouwde/deployed versie aantoonbaar de geteste implementatie bevat;
- relevante projectdocumentatie is bijgewerkt.

Deze regels gelden projectbreed en niet alleen voor de Tesla-deadline.