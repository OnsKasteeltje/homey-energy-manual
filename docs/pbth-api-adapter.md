# PBTH API Adapter v0.1 — SHADOW

_Status: ontwerp + read-only probe voorbereid op 25 augustus 2026. Geen productiecut-over en geen actuatorwrites._

## Doel

De huidige DYNAMIC-prijsroute gebruikt PBTH via Flow-cards en `prices_json(next_hours)`. Die route werkt, maar bevat extra koppelpunten: Advanced Flow card-token, token-interpolatie, buffering en JSON-parsing. De eerder gevalideerde horizonprobe liet zien dat juist de interne tokenreferentie fragiel kan zijn.

PBTH biedt inmiddels een lokale API die vanuit HomeyScript rechtstreeks alle bekende toekomstige DAP/DAP15-prijssloten kan leveren:

`GET /api/app/com.gruijter.powerhour/dap-prices`

De nieuwe kandidaatroute is daarom:

`PBTH DAP15 device -> lokale PBTH API -> EM2 Price Adapter -> uniforme PriceContext -> Energy Core`

De bestaande productieroute blijft ongewijzigd totdat shadow-agreement aantoonbaar voldoende is.

## Architectuurstatus

- `FIXED`: ongewijzigd, geen PBTH-afhankelijkheid.
- `DYNAMIC`: productie blijft voorlopig de bestaande PBTH/Flow-route.
- `DYNAMIC_PBTH_API`: nieuwe read-only kandidaatbron in SHADOW.
- Downstream Tesla-, warmwater-, Power Intent- en toekomstige Victron-logica blijven bron-onafhankelijk en lezen alleen de uniforme prijscontext.

## API-contract

De PBTH API retourneert per geconfigureerd prijsdevice onder meer:

- `deviceId`
- `deviceName`
- `driverType`
- `biddingZone`
- `currency`
- `priceInterval`
- `slots[]`

Per slot:

- `time`
- `importPrice`
- `exportPrice`
- `isForecast`

Voor deze woning accepteert de adapter uitsluitend een elektriciteitsdevice met:

- `driverType === "dap15"`
- `priceInterval === 15`
- Nederlandse bidding zone `10YNL----------L`

Wanneer meerdere devices tegelijk matchen, faalt de kandidaatadapter bewust met `AMBIGUOUS_DAP15_DEVICE`; er wordt niet stilzwijgend een eerste device gekozen.

## Prijssemantiek

`importPrice` en `exportPrice` worden rechtstreeks overgenomen. De PBTH API documenteert deze als consumentenprijzen na de in PBTH geconfigureerde markups en exchange rate. De adapter voegt daarom **geen** belastingen, opslag, btw of wisselkoerscorrectie nogmaals toe.

`isForecast` blijft per slot behouden. Confirmed marktprijzen en forecastprijzen worden niet samengevoegd tot één impliciet kwaliteitsniveau.

## Validatie en fail-safe

De kandidaatadapter publiceert alleen een geldige shadowcontext wanneer alle onderstaande checks slagen:

1. API-response bevat `prices` als array.
2. Exact één passend NL DAP15-device is gevonden.
3. `slots` is niet leeg.
4. Ieder slot heeft een valide ISO-timestamp.
5. `importPrice` en `exportPrice` zijn finite numbers.
6. Slots zijn strikt oplopend.
7. Opeenvolgende timestamps liggen exact 15 minuten uit elkaar.
8. Het eerste slot is het huidige of eerstvolgende geldige kwartier; ontbrekende historische slots worden niet gereconstrueerd.
9. Ontbrekende toekomstige slots worden nooit verzonnen.

Bij een fout publiceert de probe alleen diagnostiek; bestaande productiecontext blijft onaangeraakt.

## Shadow-output

De read-only probe produceert één JSON-resultaat met minimaal:

- `schema = EM2_PBTH_API_SHADOW_V0.1`
- `status = OK | ERROR`
- `generatedAt`
- `deviceId`
- `deviceName`
- `biddingZone`
- `currency`
- `priceInterval`
- `slotCount`
- `confirmedSlotCount`
- `forecastSlotCount`
- `firstSlot`
- `lastSlot`
- `horizonHours`
- `currentImportPrice`
- `currentExportPrice`
- `slots`
- `errors[]`

De probe schrijft geen Homey Logic-variabelen en voert geen devicewrite uit. Output gaat uitsluitend naar HomeyScript-log/return zodat de eerste runtime-validatie volledig read-only blijft.

## A/B-validatie tegen bestaande route

Na een succesvolle API-probe wordt de volgende stap een parallelle vergelijking met de bestaande `prices_json(next_hours)`-route. Per overlappend kwartier vergelijken we:

| Veld | Vergelijking |
|---|---|
| timestamp | exact gelijk |
| importprijs | verschil binnen floating-point tolerantie |
| exportprijs | verschil binnen floating-point tolerantie |
| slotduur | exact 15 minuten |
| horizon | verklaren uit beschikbare PBTH-data |
| forecast | expliciet markeren; niet mengen met confirmed |

Cut-overcriterium: minimaal één volledige overgang waarbij morgenprijzen beschikbaar komen, zonder ontbrekende of verschoven kwartieren en zonder onverklaard prijsverschil.

## Niet doen in v0.1

- Geen productieflow uitschakelen.
- Geen `EM2_Price_*` of `EM2_ContractPrice_*` overschrijven.
- Geen realtime `dap-prices-updated` listener activeren.
- Geen Tesla-, boiler-, Quatt-, Victron- of andere actuatorwrite.
- Geen ontbrekende horizon aanvullen met aannames.

De realtime PBTH-eventroute kan later eventueel uitsluitend als refresh-trigger worden onderzocht nadat polling/read-consistency eerst bewezen is.

## Uitvoerbare probe

De bijbehorende HomeyScript-bron staat in:

`docs/snippets/pbth-api-shadow-v0.1.js`

Deze kan handmatig in HomeyScript worden uitgevoerd. Een succesvolle run moet `status: "OK"` teruggeven en diagnostische aantallen/horizon tonen. De eerste runtime-run is expliciet een read-only verificatie en vormt nog geen productiecut-over.
