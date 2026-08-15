# M7 – Opportunity Shadow

**Status:** 🟡 Actief in shadow mode  
**Actieve Homey-flow:** `M7 Opportunity Shadow v1.2`  
**Frequentie:** iedere 5 minuten  
**Aansturing:** geen — volledig read-only

## Doel

M7 meet of er momenten zijn waarop de boiler op basis van de actuele energiesituatie zinvol met beschikbaar PV-vermogen had kunnen worden verwarmd. De flow observeert alleen en grijpt niet in. Daarmee kunnen we eerst aantonen of de opportuniteitslogica voldoende waarde toevoegt voordat deze ooit onderdeel wordt van actieve aansturing.

M7 is nu aangesloten op de gevalideerde statusinformatie uit de Energy Manager en op de Easee/Equalizer-safetycontext.

## Stap 2 – huidige implementatie

De actieve implementatie is `M7 Opportunity Shadow v1.2`. Deze draait iedere 5 minuten en maakt per run een read-only beoordeling.

Een **M7-kans** wordt alleen geregistreerd wanneer tegelijkertijd aan alle volgende voorwaarden wordt voldaan:

- het tijdstip ligt tussen **09:30 en 18:00**;
- de boiler staat elektrisch **uit**;
- de semantische boilerstatus is niet `OP_TEMPERATUUR` en er is dus nog een potentiële warmtevraag;
- het berekende beschikbare PV-vermogen is minimaal **2,1 kW**;
- de Easee/Equalizer-context is stabiel en staat niet op `LIMITED`, `PAUSED_OR_BLOCKED` of `ONBEKEND`.

Hiermee voorkomt M7 dat een theoretisch PV-overschot als kans wordt geregistreerd terwijl de boiler al warm is of de laad-/netcontext onzeker of begrensd is.

## Inputs

M7 gebruikt rechtstreeks actuele Homey-informatie:

- P1 totaalvermogen;
- P1 vermogen per fase L1/L2/L3;
- Tesla/Easee laadvermogen;
- gevraagde laadstroom;
- actuele boilerstand en boilervermogen;
- `EM Shadow Boiler status` uit de Energy Manager;
- `EM Shadow Equalizer status` uit de Energy Manager.

De boilerstatus wordt daarmee niet opnieuw door M7 afgeleid. De Energy Manager blijft eigenaar van de boiler-state-machine.

## Boilerstatus

De belangrijkste semantische toestand is `OP_TEMPERATUUR`. Zodra de Energy Manager deze status rapporteert, kan M7 geen boilerkans registreren, ongeacht de elektrische schakelstand.

Andere toestanden kunnen aangeven dat nog warmte nodig kan zijn. M7 combineert dat altijd met de actuele elektrische boilerstand, het beschikbare PV-vermogen, het tijdvenster en de Equalizer-safetycontext.

## Easee / Equalizer safety

M7 gebruikt de door de Energy Manager gepubliceerde Equalizer-status. Bij:

- `LIMITED`;
- `PAUSED_OR_BLOCKED`;
- `ONBEKEND`;

wordt geen M7-kans geregistreerd. De reden wordt dan vastgelegd als `EQUALIZER_STABILISATIE`.

Dit is bewust conservatief: M7 mag een onzekere of begrensde EV/nettoestand niet interpreteren als vrij beschikbaar vermogen.

## Beschikbaar PV-vermogen

Voor de opportunity-beoordeling wordt een actuele benadering gebruikt op basis van P1, Tesla-laadvermogen en boilervermogen. De drempel voor een boilerkans is momenteel **2.100 W**.

Deze waarde is een shadow-parameter: de verzamelde resultaten moeten aantonen of deze grens in de praktijk goed gekozen is voordat actieve boilersturing wordt overwogen.

## Redencodes

Iedere beoordeling krijgt een leesbare reden. De huidige codes zijn:

- `BUITEN_VENSTER`;
- `BOILER_OP_TEMPERATUUR`;
- `BOILER_REEDS_AAN`;
- `EQUALIZER_STABILISATIE`;
- `ONVOLDOENDE_PV`;
- `M7_KANS`.

Daardoor kunnen we achteraf niet alleen tellen hoeveel kansen zijn gevonden, maar ook analyseren waarom op andere momenten bewust géén kans is geregistreerd.

## Logging

De runtimehistorie wordt in Homey bijgehouden in `M7 Opportunity Runtime v1.2`.

Per sample worden onder andere opgeslagen:

- tijdstip;
- wel/geen opportunity;
- reden;
- berekend beschikbaar PV-vermogen;
- P1 totaal en L1/L2/L3;
- Tesla-laadvermogen en gevraagde ampères;
- Equalizer-status;
- boilervermogen;
- elektrische boilerstand;
- semantische boilerstatus.

Er worden maximaal **576 samples** bewaard, overeenkomend met circa 48 uur bij een interval van 5 minuten.

Daarnaast publiceert de flow tags voor de actuele opportunity, reden en het beschikbare PV-vermogen.

## Aangestuurde apparaten

**Geen.** `M7 Opportunity Shadow v1.2` is volledig read-only. De flow schakelt de boiler, Tesla/Easee of andere apparaten niet.

## Architectuur

De verantwoordelijkheden zijn bewust gescheiden:

**Energy Manager** → bepaalt en publiceert betrouwbare apparaat- en safety-statussen.  
**M7 Opportunity Shadow** → beoordeelt met die statusinformatie of er een gemiste PV/boilerkans bestaat.  
**Toekomstige actieve optimalisatie** → pas na voldoende shadow-validatie en expliciete besluitvorming.

Deze scheiding past bij de doelarchitectuur richting Victron: betrouwbare metingen en statusbepaling onderin, optimalisatielogica daarboven en daadwerkelijke actuatorsturing pas nadat de beslislogica aantoonbaar veilig en nuttig is.

## Huidige status

Stap 2 is uitgevoerd: `M7 Opportunity Shadow v1.2` is actief in Homey en is niet broken. De flow verzamelt vanaf nu iedere 5 minuten data waarmee we de opportunity-logica kunnen beoordelen en later kunnen fine-tunen.
