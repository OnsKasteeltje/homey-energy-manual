# EM v2 | 60 Adapter | WW Power v0.1 SHADOW

- Homey flow ID: `472d0355-3bb9-4a42-be43-114b57822136`
- Runtime state at capture: `enabled=false`, `broken=false`, `triggerable=true`
- Trigger: `EM2_Power_Intent` changed + manual start
- Capture date: 2026-08-28
- Status: exact runtime baseline captured; no runtime promotion performed

## Runtime HomeyScript

```js
// EM v2 | 60 Adapter | WW Power v0.1 SHADOW
// Translation boundary only. NO device reads/writes, Insights, network or policy decisions.
const vars=await Homey.logic.getVariables();
const by=Object.fromEntries(Object.values(vars).map(v=>[v.name,v]));
const parse=x=>{try{return JSON.parse(String(x??''));}catch{return null;}};
const num=x=>{if(x===null||x===undefined||x==='')return null;const n=Number(x);return Number.isFinite(n)?n:null;};
const set=async(name,value)=>{const v=by[name];if(v){if(v.value!==value){await Homey.logic.updateVariable({id:v.id,variable:{value}});v.value=value;}return;}const nv=await Homey.logic.createVariable({variable:{name,type:'string',value}});by[name]=nv;};
const intent=parse(by.EM2_Power_Intent?.value),prev=parse(by.EM2_WW_Power_Adapter?.value);
const r=num(intent?.sourceRevision),ww=intent?.targets?.ww||null;
const targetPresent=!!ww&&Object.prototype.hasOwnProperty.call(ww,'target_on');
const targetOn=targetPresent?ww.target_on:undefined;
const typeOk=targetPresent&&(targetOn===null||typeof targetOn==='boolean');
const inputValid=intent?.schema==='EM2_POWER_INTENT_V0.2'&&intent?.valid===true&&intent?.deviceWrites===false&&r!==null&&typeOk;
let status='INVALID_POWER_INTENT',value=null;
if(inputValid){if(targetOn===true){status='OK_ON';value=true;}else if(targetOn===false){status='OK_OFF';value=false;}else{status='OK_HOLD';value=null;}}
const semantic=JSON.stringify({r,targetPresent,targetOn,status,value});
const prevSemantic=JSON.stringify({r:num(prev?.sourceRevision),targetPresent:prev?.input?.targetPresent===true,targetOn:prev?.input?.target_on,status:prev?.status,value:prev?.command?.value});
if(prev?.schema==='EM2_WW_POWER_ADAPTER_V0.1'&&prev?.inputSchema==='EM2_POWER_INTENT_V0.2'&&semantic===prevSemantic)return true;
const out={schema:'EM2_WW_POWER_ADAPTER_V0.1',inputSchema:'EM2_POWER_INTENT_V0.2',generatedAt:new Date().toISOString(),sourceRevision:r,valid:inputValid,status,readOnly:true,controlMode:'SHADOW',deviceWrites:false,input:{targetPresent,target_on:targetPresent?targetOn:null,sourceAction:ww?.sourceAction??null},command:{capability:'onoff',value,physicalWrite:false},ownership:{physicalWriter:'DISABLED',policy:'ENERGY_CORE_P1',translation:'WW_POWER_ADAPTER'},safety:{logicOnly:true,noDeviceReads:true,noDeviceWrites:true,noInsights:true,noNetworkCalls:true,noPoller:true,policyDecisionMadeHere:false,failClosed:true,idempotentBySourceRevision:true}};
await set('EM2_WW_Power_Adapter',JSON.stringify(out));
return inputValid;
```
