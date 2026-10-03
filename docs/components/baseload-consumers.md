# Baselineverbruikers — vaste en cyclische nachtlast

_Status: 3 oktober 2026_

## Doel

Dit document legt de bekende structurele nachtverbruikers vast die samen de P1-baseload van de woning verklaren. Deze lasten worden niet als flexload behandeld zolang daar geen expliciet besluit voor is genomen.

P1 blijft de autoritatieve bron voor het totale woningvermogen. Vermogens op typeplaatjes zijn nominale apparaatvermogens en **geen** gemiddeld continu verbruik.

## 1. Gemeten nacht-baseline

`VERIFIED` — Homey Insights, P1 per fase, nacht 2 oktober 2026, venster 01:00–05:00 Europe/Amsterdam:

- minimum gemeten totaal: circa **247 W**;
- rustige/typische belasting: circa **300–340 W**;
- rustige faseverdeling typisch:
  - L1 circa **90–110 W**;
  - L2 circa **140–175 W**;
  - L3 circa **42–55 W**;
- afzonderlijke nachtelijke pieken tot circa 1,8–2,2 kW zijn geen baseload en worden voor baseline-attributie apart behandeld.

De huidige werkhypothese is dat een deel van de variatie boven de vaste bodem afkomstig is van compressorcycli van de koelapparatuur. Een definitieve mapping van elk koelapparaat naar fase/signatuur is nog niet vastgesteld.

## 2. Koelapparatuur

Deze drie apparaten gelden als bekende cyclische baselineverbruikers:

| Apparaat | Type | Typeplaatje | Status |
|---|---|---:|---|
| Siemens KI18RA50/02 | koelkast | **90 W** | bekend / cyclisch |
| Siemens KI87VVF30/03 | koel-vriescombinatie | **90 W** | bekend / cyclisch |
| Liebherr KGT 3046 Index 26C/001 | koel-vriescombinatie | **170 W** | bekend / cyclisch |

Aanvullende identificatie:

- Siemens KI18RA50/02: FD `8710`;
- Siemens KI87VVF30/03: FD `9806`;
- Liebherr: Service-Nr. `9996514-03`.

`OPEN` — fase-attributie per apparaat. De in P1 zichtbare stapveranderingen passen bij thermostatisch geschakelde lasten, maar er wordt nog geen apparaat→fase-mapping als feit vastgelegd zonder gecontroleerde meting.

## 3. Netwerk- en infrastructuurlast

De netwerkstack wordt als **vaste, niet-flexibele baseline** behandeld. Nachtelijk uitschakelen is niet de huidige optimalisatieroute omdat de infrastructuur noodzakelijk is voor netwerk, IoT en EMS-connectiviteit.

### 3.1 Kern

- UDM Pro;
- Switch Meterkast;
- Switch Inbouwkast;
- Switch CV Ruimte.

### 3.2 Access points

| Access point | Uplink / voeding | Waargenomen PoE-vermogen | Opmerking |
|---|---|---:|---|
| U6-Lite Meterkast | Switch Meterkast, poort 1 | circa **4,33 W** | o.a. P1/Easee/IoT-connectiviteit |
| U6-LR CV-Ruimte | Switch CV Ruimte, poort 2 | circa **7,20 W** | mesh-parent van U6-Lite Schuur |
| UAP-IW-HD Spellenkast | Switch Inbouwkast, poort 4 | circa **5,10 W** | heeft downstream Ethernet-clients |
| U6-Lite Schuur | wireless mesh via U6-LR CV-Ruimte | nog niet afzonderlijk gemeten | afhankelijk van mesh-parent |

De drie bedrade AP's gebruikten tijdens de inventarisatie samen circa **16,6 W** PoE. Dit verklaart slechts een beperkt deel van de totale nacht-baseload.

## 4. EMS-classificatie

Voor de huidige energiebalans worden de bovenstaande apparaten als volgt behandeld:

- koelapparatuur: **niet-flexibel, cyclisch basisverbruik**;
- UDM/switches/AP's: **niet-flexibel, structureel basisverbruik**;
- P1 blijft leidend voor de totale werkelijk gemeten baseload;
- nog niet toegeschreven restvermogen blijft `unknown/residual baseload` en wordt niet kunstmatig aan een apparaat toegewezen.

## 5. Open validatie

1. `OPEN` — bepaal welke koelcompressorsignatuur bij welk apparaat/fase hoort met een gecontroleerde korte meting.
2. `OPEN` — kwantificeer zo nodig overige always-on verbruikers alleen wanneer de residual baseload groot genoeg is om relevant te zijn.
3. Geen automatische nachtelijke uitschakeling van netwerkcomponenten toevoegen zonder afzonderlijk ontwerpbesluit.
