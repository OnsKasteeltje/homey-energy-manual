# EM v2 | 80 Validation | EV Power Adapter Gate v0.2.1 TARGETED-READ

- Homey flow ID: `ec5e5d34-8205-4cf0-a661-7bf744feb6e0`
- Runtime state at capture: `enabled=true`, `broken=false`, `triggerable=true`
- Trigger: `EM2_Power_Intent` changed + manual start
- Settle delay: 2 seconds
- Capture date: 2026-09-03
- Status: exact current runtime captured from Homey; no runtime mutation performed

## Runtime HomeyScript

```js
// EM v2 | 80 Validation | EV Power Adapter Gate v0.2.1 TARGETED-READ
// Logic-only. Four targeted reads; same settle/revision/safety/electrical/translation checks.
const IDS={intent:'04b57041-dd7f-41f7-a00a-f023afb1ccee',adapter:'f2118322-d59d-4aa8-b478-234effc3983c',state:'8e1efbb0-7999-494c-9429-7d274afacd79',gate:'4c66836b-77ae-43b5-b8e0-b32af15b57bc'};
const [intentVar,adapterVar,stateVar,gateVar]=await Promise.all([Homey.logic.getVariable({id:IDS.intent}),Homey.logic.getVariable({id:IDS.adapter}),Homey.logic.getVariable({id:IDS.state}),Homey.logic.getVariable({id:IDS.gate})]);
const parse=x=>{try{return JSON.parse(String(x??''));}catch{return null;}};
const num=x=>{if(x===null||x===undefined||x==='')return null;const n=Number(x);return Number.isFinite(n)?n:null;};
const intent=parse(intentVar?.value),adapter=parse(adapterVar?.value),state=parse(stateVar?.value),prev=parse(gateVar?.value);
const r=num(intent?.sourceRevision),ar=num(adapter?.sourceRevision),sr=num(adapter?.stateRevision),coreR=num(state?.revision),ag=String(adapter?.generatedAt??'');
const targetW=num(intent?.targets?.ev?.target_W),a=num(adapter?.command?.requested_A),ph=num(adapter?.electrical?.phase_count),v=num(adapter?.electrical?.voltage_V),wpa=num(adapter?.electrical?.w_per_A),minA=num(adapter?.electrical?.min_A),maxA=num(adapter?.electrical?.max_A),minW=num(adapter?.electrical?.min_charge_W),maxW=num(adapter?.electrical?.max_charge_W),execW=num(adapter?.electrical?.executable_W),status=String(adapter?.status||'');
const electricalOK=ph===3&&v===230&&wpa===690&&minA===6&&maxA!==null&&maxA>=6&&maxA<=16&&Number.isInteger(maxA)&&minW===wpa*minA&&maxW===wpa*maxA;
let expectedA=null,allowedStatus=[];
if(targetW!==null&&Number.isInteger(targetW)&&targetW>=0&&electricalOK){if(targetW===0){expectedA=0;allowedStatus=['ZERO_INTENT'];}else if(targetW<minW){expectedA=0;allowedStatus=['BELOW_MINIMUM_EXECUTABLE_POWER'];}else{expectedA=Math.min(maxA,Math.floor(targetW/wpa+Number.EPSILON));if(expectedA<minA)expectedA=0;allowedStatus=(expectedA===maxA&&targetW/wpa>maxA)?['CLAMPED_TO_MAX_CURRENT']:(expectedA*wpa<targetW?['QUANTIZED_DOWN']:['EXECUTABLE']);}}
const mappingPowerOK=a!==null&&execW===a*wpa&&(targetW===0||a===0||execW<=targetW||a===maxA);
const checks={schema:adapter?.schema==='EM2_EV_POWER_ADAPTER_V0.1'&&adapter?.inputSchema==='EM2_POWER_INTENT_V0.2',revisionsAligned:r!==null&&ar===r&&sr===r&&coreR===r,safety:adapter?.readOnly===true&&adapter?.controlMode==='SHADOW'&&adapter?.deviceWrites===false&&adapter?.command?.physicalWrite===false&&adapter?.command?.capability==='setDynamicChargerCurrent'&&adapter?.command?.commanded_A===null&&adapter?.ownership?.physicalWriter==='DISABLED'&&adapter?.ownership?.policy==='ENERGY_CORE_P1'&&adapter?.ownership?.translation==='EV_POWER_ADAPTER'&&adapter?.safety?.logicOnly===true&&adapter?.safety?.noDeviceWrites===true&&adapter?.safety?.noInsights===true&&adapter?.safety?.noNetworkCalls===true&&adapter?.safety?.noPoller===true&&adapter?.safety?.policyDecisionMadeHere===false&&adapter?.safety?.failClosed===true&&adapter?.safety?.mappingRevision==='FLOOR_3P230_FAIL_CLOSED'&&adapter?.safety?.neverIncreaseUpstreamPower===true,electrical:electricalOK,translation:targetW!==null&&num(adapter?.input?.target_W)===targetW&&adapter?.valid===true&&a===expectedA&&allowedStatus.includes(status)&&mappingPowerOK};
const errors=Object.entries(checks).filter(([,ok])=>!ok).map(([k])=>k.toUpperCase());
const semantic=JSON.stringify({r:ar,inputSchema:adapter?.inputSchema,targetW:adapter?.input?.target_W,status:adapter?.status,a:adapter?.command?.requested_A,ph,v,wpa,minA,maxA,minW,maxW,execW,pw:adapter?.command?.physicalWrite,dw:adapter?.deviceWrites,mapping:adapter?.safety?.mappingRevision,ag});
let duplicateMutation=false;
if(prev?.schema==='EM2_EV_ADAPTER_GATE_V0.2'&&prev.mode==='RUNTIME_HEALTH'&&prev.sourceRevision===ar){if(prev.semantic===semantic)return prev.finalStatus!=='FAIL';duplicateMutation=true;errors.push('DUPLICATE_ADAPTER_MUTATION');}
const gate={schema:'EM2_EV_ADAPTER_GATE_V0.2',mode:'RUNTIME_HEALTH',contract:'EM2_EV_POWER_ADAPTER_V0.1',mapping:'FLOOR_3P230_FAIL_CLOSED',sourceRevision:ar,intentRevision:r,stateRevision:sr,coreRevision:coreR,adapterGeneratedAt:ag,requested_A:a,target_W:targetW,updatedAt:new Date().toISOString(),checks,errors,duplicateMutation,semantic,finalStatus:errors.length?'FAIL':'PASS'};
const out=JSON.stringify(gate);if(gateVar.value!==out)await Homey.logic.updateVariable({id:IDS.gate,variable:{value:out}});return gate.finalStatus==='PASS';
```

## Reconciliation note

The flow was read directly from Homey on 2026-09-03. It is enabled and logic-only. No physical device write path exists in this gate.
