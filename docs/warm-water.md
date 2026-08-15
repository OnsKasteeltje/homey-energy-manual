# Warm water optimalisatie

**Status:** 🟢 Actief  
**Flow:** `Warm water optimalisatie - PV boiler + CV advies`

## Huidige implementatie

- Nieuwe boilerstart: **09:30–14:30**
- Hard uit: **15:30**
- Startvoorwaarde 2026: minimaal **2,1 kW netto export gedurende 5 minuten**
- Minimumlooptijd: **30 minuten**
- Stopvoorwaarde: meer dan **0,5 kW netafname gedurende 10 minuten**
- `WW_Boilermodus = JA` betekent: elektrische boiler fysiek gekozen
- Omschakelmeldingen gaan naar **Mr Horizon**

## Gepland doelbeeld

Na succesvolle shadow-validatie:

- nieuwe starts **09:30–16:30**
- lopende cyclus uiterlijk uit **18:00**
- Tesla heeft binnen **09:30–17:30** prioriteit
- boiler gebruikt resterend overschot vanaf circa **2,1 kW**
