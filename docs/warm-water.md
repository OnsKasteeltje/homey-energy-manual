# Warm water optimalisatie — PV boiler + CV advies

Deze pagina beschrijft niet alleen *wat* de flow doet, maar ook waarom de gekozen regeling zo is ingericht en welke wijzigingen nog gepland zijn.

## 1. Doel en uitgangspunt

De warmwaterregeling combineert twee bestaande warmtebronnen:

| Onderdeel | Uitgangspunt |
|---|---|
| Elektrische boiler | **Stiebel Eltron HSTP 200**, 200 liter |
| Gemeten boilervermogen | circa **1,95–2,0 kW** tijdens verwarmen |
| Typisch gemeten boilerverbruik | circa **7–8 kWh per dag** |
| CV-ketel | **Vaillant ecoTEC exclusive**; exacte VHR 25-35/5-7 of 35-45/5-7 nog te bevestigen |
| Gasprijs 2026 | **€ 1,19265/m³** incl. btw |
| Elektriciteit normaal | **€ 0,23790/kWh** incl. btw |
| Elektriciteit dal | **€ 0,23548/kWh** incl. btw |
| PV-meetbasis | netto P1-import/-export van de gehele woning |
| CV ↔ boiler omschakeling | **handmatig** |

Het doel is niet simpelweg *zomer = boiler* en *winter = CV*. De regeling probeert vast te stellen wanneer voldoende eigen PV beschikbaar is om de boiler economisch aantrekkelijk te gebruiken.

De elektrische boiler wordt automatisch aan/uit gestuurd. De Vaillant CV-ketel wordt **niet** automatisch omgeschakeld. Homey geeft alleen een seizoensadvies.

---

## 2. Dagelijkse regeling — huidige actieve implementatie

De Advanced Flow draait **iedere 5 minuten**.

### Beslislogica

```text
WW_Boilermodus = JA?
        │
        ├─ NEE → boiler UIT houden; CV is fysiek geselecteerd
        │
        └─ JA
             │
             ├─ tijd tussen 09:30 en 14:30?
             │
             └─ ≥ 2,1 kW netto P1-teruglevering
                 gedurende minimaal 5 minuten?
                       │
                       └─ JA → BOILER AAN
                                  │
                                  ├─ minimaal 30 minuten draaien
                                  │
                                  └─ daarna:
                                      > 0,5 kW netto netafname
                                      gedurende 10 minuten?
                                           │
                                           ├─ JA → BOILER UIT
                                           └─ NEE → doorverwarmen
```

### Starten op PV, niet op een vaste kloktijd

Een nieuwe verwarmingscyclus mag momenteel starten tussen **09:30 en 14:30**. De oude vaste starttijd is vervallen.

Homey wacht tot de P1-meter gedurende vijf minuten minimaal **2,1 kW netto export** meet. Omdat de P1-meter het saldo van de hele woning meet, is het normale huishoudelijke verbruik dan al van de PV-productie afgetrokken.

De boiler gebruikt daardoor primair energie die anders naar het elektriciteitsnet zou worden teruggeleverd.

### Minimumlooptijd van 30 minuten

Na inschakelen blijft de boiler minimaal **30 minuten** aan. Dit voorkomt pendelen bij:

- voorbijtrekkende bewolking;
- kortstondig hoger huishoudelijk verbruik;
- kleine schommelingen rond de PV-drempel.

### Stoppen bij structurele netafname

Na de minimumlooptijd mag de boiler worden uitgeschakeld wanneer gedurende **10 minuten meer dan 0,5 kW netto uit het net wordt afgenomen**.

Een korte dip in de PV-productie schakelt de boiler dus niet onmiddellijk uit.

### Herstart

Na uitschakelen kan een nieuwe cyclus beginnen wanneer opnieuw voldoende PV beschikbaar is, zolang het nog vóór **14:30** is.

### Hard einde

In de huidige actieve versie wordt de boiler uiterlijk om **15:30** uitgeschakeld.

---

## 3. Waarom het boilervenster waarschijnlijk langer moet worden

Uit de analyse kwam een belangrijk verschil tussen Tesla en boiler naar voren.

De boiler heeft ongeveer **2 kW** nodig. De Tesla heeft bij de minimale 3-fase laadstroom van 6 A ongeveer **4,14 kW** nodig.

Daardoor ontstaat later op de dag regelmatig deze situatie:

```text
PV beschikbaar: bijvoorbeeld 2,5–4,0 kW
                  │
                  ├─ te weinig voor zinvol Tesla-laden op 3×6 A
                  │
                  └─ wél voldoende voor de circa 2 kW boiler
```

Daarom is het huidige einde om 15:30 waarschijnlijk te vroeg.

### Huidig versus doelbeeld

| Regeling | Huidig actief | Doelbeeld na validatie |
|---|---:|---:|
| Eerste nieuwe start | 09:30 | 09:30 |
| Laatste nieuwe start | 14:30 | **16:30** |
| Lopende cyclus uiterlijk uit | 15:30 | **18:00** |

Het langere venster wordt nog niet blind ingevoerd. Eerst wordt met de centrale Energie Manager in **shadow mode** gecontroleerd of deze prioritering in de praktijk correct uitpakt.

---

## 4. Samenwerking met Tesla

De gewenste centrale PV-prioriteit is:

```text
1. Huishoudelijk verbruik
          ↓
2. Tesla
          ↓
3. Boiler
          ↓
4. Teruglevering
```

**Tesla krijgt dus voorrang boven de boiler**, maar alleen wanneer er voldoende vermogen beschikbaar is om de Tesla daadwerkelijk zinvol te laden.

De boiler vervult daarna twee functies:

1. resterend PV-overschot benutten wanneer Tesla al voldoende krijgt;
2. PV benutten dat **te klein is voor Tesla**, maar groot genoeg is voor de boiler.

Dit is precies waarom het geplande late boilervenster belangrijk is.

De flow **Energie Manager PV - Shadow Mode** simuleert deze centrale beslissing momenteel zonder Tesla of boiler daadwerkelijk vanuit de Energie Manager aan te sturen.

---

## 5. `WW_Boilermodus` — welke bron is werkelijk geselecteerd?

De fysieke omschakeling tussen CV en elektrische boiler blijft bewust handmatig.

Homey moet daarom weten welke bron de gebruiker heeft geselecteerd:

| `WW_Boilermodus` | Betekenis |
|---|---|
| **JA** | warm tapwater via elektrische boiler |
| **NEE** | warm tapwater via Vaillant CV |

In CV-modus houdt de warmwaterflow de elektrische boiler uit. Homey schakelt de CV zelf niet om.

Na een fysieke omschakeling moet dus ook `WW_Boilermodus` worden aangepast.

---

## 6. Seizoensadvies: wanneer van boiler naar CV en terug?

Eén slechte zomerdag mag niet betekenen dat we meteen naar gas overschakelen. Andersom mag één zonnige winterdag ook niet meteen tot boilerbedrijf leiden.

Daarom beoordeelt Homey steeds **zeven volledige meetdagen**.

Voor 2026 geldt een dag als een **goede PV-dag voor warm water** wanneer binnen het regelvenster ongeveer **5,8 kWh bruikbaar PV-potentieel** voor de boiler beschikbaar was.

### Omschakelregels

| Huidige modus | Laatste 7 dagen | Homey-advies |
|---|---|---|
| Boiler | **3 of minder** goede PV-dagen | handmatig naar **CV** |
| CV | **5 of meer** goede PV-dagen | handmatig naar **boiler** |
| Beide | tussen deze grenzen | huidige modus behouden |

Het verschil tussen 3 en 5 dagen is bewust. Deze **hysterese** voorkomt dat het systeem bij wisselvallig voor- of najaarsweer steeds heen en weer adviseert.

---

## 7. Wat gebeurt er bij een omschakeladvies?

Homey verandert de warmwaterbron niet zelf.

Bij een advies stuurt Homey een pushmelding expliciet naar **Mr Horizon**. De melding geeft aan:

- naar welke bron moet worden omgeschakeld;
- dat dit **handmatig** moet gebeuren;
- dat daarna `WW_Boilermodus` moet worden aangepast.

Wanneer de pushmelding technisch niet lukt, wordt een Homey Timeline-melding gebruikt als fallback.

---

## 8. Waarom de regels vanaf 2027 veranderen

Vanaf 2027 veranderen de opgegeven contractcondities. Een teruggeleverde PV-kWh heeft dan minder economische waarde. Het wordt daardoor aantrekkelijker om PV direct in warm water om te zetten, zelfs wanneer daarvoor tijdelijk een klein deel netstroom nodig is.

Het script voorziet daarom automatisch in soepelere drempels:

| Parameter | 2026 | Vanaf 1-1-2027 |
|---|---:|---:|
| Startdrempel netto export | **2,1 kW** | **1,4 kW** |
| Toegestane structurele netafname | **0,5 kW** | **0,8 kW** |
| Grens goede PV-dag | **ca. 5,8 kWh** | **4,5 kWh** |

Het uitgangspunt verschuift daarmee van *bijna uitsluitend eigen PV gebruiken* naar *PV zoveel mogelijk zelf benutten wanneer teruglevering weinig oplevert*.

---

## 9. Variabelen, tags en meetpunten

| Naam | Type | Functie |
|---|---|---|
| `WW_Boilermodus` | Logic boolean | JA = boiler; NEE = CV |
| WW PV-potentieel vandaag kWh | Flow-tag | geschatte bruikbare PV voor boiler |
| WW Boiler verbruik vandaag kWh | Flow-tag | gemeten boilerenergie |
| WW Boiler PV-aandeel vandaag % | Flow-tag | geschat direct PV-aandeel |
| WW Goede PV-dagen laatste 7 | Flow-tag | basis voor seizoensadvies |
| WW Advies | Flow-tag | GEEN / CV / BOILER |
| WW Modus | Flow-tag | geregistreerde warmwatermodus |
| P1-meter | apparaat | netto import/export woning |
| Boiler | apparaat | automatische aan/uit-sturing |

---

## 10. Fail-safe en veiligheid

De regeling is bewust conservatief:

- in CV-modus houdt Homey de elektrische boiler uit;
- Homey schakelt de Vaillant CV niet automatisch om;
- wanneer P1-meter of boiler niet kan worden gevonden, stopt het script met een fout in plaats van verder te regelen op aannames;
- minimumlooptijd en vertragingen voorkomen snel aan/uit schakelen;
- de oude flows **Boiler aan**, **Boiler uit** en **Boiler opwarmen** staan uit om dubbele aansturing te voorkomen;
- de nieuwe centrale Energie Manager blijft eerst in shadow mode totdat de beslissingen voldoende zijn gevalideerd.

---

## 11. Actuele status

| Onderdeel | Status |
|---|---|
| Warm water optimalisatie | 🟢 **Actief** |
| Oude `Boiler aan` flow | ⚫ Uit |
| Oude `Boiler uit` flow | ⚫ Uit |
| Oude `Boiler opwarmen` flow | ⚫ Uit |
| Nieuwe starts huidig | **09:30–14:30** |
| Hard einde huidig | **15:30** |
| Geplande nieuwe starts | **09:30–16:30** |
| Gepland hard einde | **18:00** |
| Tesla-prioritering | 🟡 Validatie via Energie Manager shadow mode |
| Seizoensadvies | na 7 volledige meetdagen |
| Fysieke CV ↔ boiler omschakeling | handmatig |
| Adviesmelding | naar **Mr Horizon** |

!!! note "Belangrijk"
    De tijden **09:30–16:30 / 18:00 zijn nog het doelbeeld**, niet de huidige actieve warmwaterregeling. De actieve flow gebruikt nog **09:30–14:30 / 15:30** totdat de shadow-validatie voldoende vertrouwen geeft.

## 12. Volgende optimalisatiestap

Na voldoende shadow-data beoordelen we of **Tesla eerst → boiler daarna** inderdaad meer eigen PV benut zonder onnodige netafname.

Bij een positief resultaat wordt de warmwaterflow aangepast naar het langere tijdvenster. Die wijziging wordt vervolgens zowel hier als in de Homey Flow Manual vastgelegd.
