#!/usr/bin/env python3
"""Build Homey EV Actuator v0.2.11 from the deployed v0.2.10 candidate.

No Homey calls are performed. Input may be either a single Advanced Flow JSON
or a full get-advanced-flows mapping. v0.2.11 makes a fresh PASS gate the
runtime safety authority for a validated active Tesla deadline, so stale
adapter/state timestamps alone cannot force 16 A -> 0 A.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

FLOW_ID_DEFAULT = "fea23193-a03f-49dd-9780-7e72ee48747d"
MAIN_CARD_ID = "10a00000-0000-4000-8000-000000000002"
SESSION_CARD_ID = "10a00000-0000-4000-8000-00000000000f"
EXPECTED_BASELINE_MARKER = "EM2_EV_ACTUATOR_V0.2.10"

MAIN_CODE = r'''// EV Actuator v0.2.11 SEMANTIC-TOKEN + DEADLINE GATE AUTHORITY
const VERSION='EM2_EV_ACTUATOR_V0.2.11',CHARGER_ID='4d0b6913-d940-474e-95d6-b43f194c4119',FRESH_MS=120000;
const IDS={live:'8d47e98d-e4bc-4f47-8c02-c2aca7f7a978',status:'ea1f8a44-2f6c-490e-9b86-bae761886cf9',intent:'04b57041-dd7f-41f7-a00a-f023afb1ccee',adapter:'f2118322-d59d-4aa8-b478-234effc3983c',gate:'4c66836b-77ae-43b5-b8e0-b32af15b57bc',state:'8e1efbb0-7999-494c-9429-7d274afacd79'};
const [liveVar,statusVar,intentVar,adapterVar,gateVar,stateVar]=await Promise.all([Homey.logic.getVariable({id:IDS.live}),Homey.logic.getVariable({id:IDS.status}),Homey.logic.getVariable({id:IDS.intent}),Homey.logic.getVariable({id:IDS.adapter}),Homey.logic.getVariable({id:IDS.gate}),Homey.logic.getVariable({id:IDS.state})]);
const parse=x=>{try{return JSON.parse(String(x??''));}catch{return null;}};
const num=x=>{if(x===null||x===undefined||x==='')return null;const n=Number(x);return Number.isFinite(n)?n:null;};
const age=x=>{const t=Date.parse(String(x||''));return Number.isFinite(t)?Date.now()-t:Infinity;};
const report=async(status,extra={})=>{const value=JSON.stringify({schema:VERSION,status,at:new Date().toISOString(),...extra});if(statusVar.value!==value){await Homey.logic.updateVariable({id:IDS.status,variable:{value}});statusVar.value=value;}};
const intent=parse(intentVar?.value),adapter=parse(adapterVar?.value),gate=parse(gateVar?.value),state=parse(stateVar?.value),ev=intent?.targets?.ev||{},pp=intent?.policyProjection||{};
const targetW=num(ev?.target_W),targetStatus=String(ev?.status??''),targetSource=String(ev?.source??'');
const cr=String(intent?.controlRevision||'')||JSON.stringify({policy:String(intent?.policyRevision||''),engine:String(intent?.engineVersion||''),valid:intent?.valid===true,status:String(intent?.status||''),evTargetW:targetW,evStatus:targetStatus,evSource:targetSource,wwTargetOn:intent?.targets?.ww?.target_on??null,wwStatus:String(intent?.targets?.ww?.status||''),authority:String(pp?.authoritySelector||pp?.plannerOwner||'')});
const acr=String(adapter?.controlRevision||''),gcr=String(gate?.controlRevision||''),requestedA=num(adapter?.command?.requested_A),coreR=num(state?.revision);
const deadlineAtMs=Date.parse(String(pp?.deadlineAt||'')),deadlineRemainingKWh=num(pp?.deadlineRemainingKWh),deadlineMaxA=num(pp?.deadlineMaxA);
const deadlineEligible=pp?.deadlineGuardApplied===true&&pp?.deadlineTeslaConnected===true&&targetStatus==='NUMERIC_DEADLINE_TARGET'&&targetSource==='REMAINING_KWH_OVER_TIME_TO_DEADLINE'&&Number.isInteger(targetW)&&targetW>0&&Number.isInteger(requestedA)&&requestedA>=6&&requestedA<=16&&Number.isInteger(deadlineMaxA)&&deadlineMaxA>=6&&deadlineMaxA<=16&&requestedA<=deadlineMaxA&&deadlineRemainingKWh!==null&&deadlineRemainingKWh>0&&Number.isFinite(deadlineAtMs)&&deadlineAtMs>Date.now();
if(liveVar.value!==true){await report('SHADOW_NO_WRITE',{targetW,requestedA,controlRevision:cr,live:false});return true;}
let charger=null;
const getCharger=async()=>{if(charger)return charger;const devices=await Homey.devices.getDevices();charger=devices[CHARGER_ID];if(!charger)throw new Error('CHARGER_MISSING');return charger;};
const writeA=async a=>{const c=await getCharger();const current=num(c.capabilitiesObj?.target_charger_current?.value);if(current===a)return {write:false,previousA:current};await c.setCapabilityValue('target_charger_current',a);return {write:true,previousA:current};};
const failClosed=async(reason,extra={})=>{const w=await writeA(0);await report('LIVE_FAIL_CLOSED',{reason,targetA:0,previousA:w.previousA,physicalWritePerformed:w.write,controlRevision:cr,coreRevision:coreR,live:true,...extra});return true;};
try{
  const intentFresh=age(intent?.generatedAt)<=FRESH_MS,adapterFresh=age(adapter?.generatedAt)<=FRESH_MS,gateFresh=age(gate?.updatedAt)<=FRESH_MS,stateFresh=age(state?.sampledAt)<=FRESH_MS;
  const normalControlFresh=intentFresh&&adapterFresh&&gateFresh;
  const cs=String(state?.tesla?.chargeState??'unknown').toLowerCase();
  const explicitUnsafe=['offline','error','fault','disconnected','unplugged'].some(x=>cs.includes(x));
  const connectedState=cs.includes('plugged_in')||cs.includes('charging');
  const schemaOK=intent?.schema==='EM2_POWER_INTENT_V0.2'&&adapter?.schema==='EM2_EV_POWER_ADAPTER_V0.1'&&gate?.schema==='EM2_EV_ADAPTER_GATE_V0.2';
  const tokenOK=!!cr&&acr===cr&&gcr===cr&&gate?.adapterControlRevision===cr;
  const adapterSafe=adapter?.valid===true&&adapter?.deviceWrites===false&&adapter?.readOnly===true&&adapter?.command?.physicalWrite===false&&adapter?.safety?.failClosed===true&&adapter?.safety?.semanticTokenGuard===true;
  const numericOK=Number.isInteger(targetW)&&targetW>=0&&Number.isInteger(requestedA)&&requestedA>=0&&requestedA<=16&&(requestedA===0||requestedA>=6);
  const gatePass=gate?.finalStatus==='PASS';
  const deadlineAuthority=deadlineEligible&&gateFresh&&gatePass&&tokenOK&&adapterSafe&&numericOK&&connectedState&&!explicitUnsafe;
  const coreSafeFresh=stateFresh&&!['','unknown'].includes(cs)&&!explicitUnsafe;
  if(!schemaOK)return await failClosed('SCHEMA_MISMATCH');
  if(!tokenOK)return await failClosed('SEMANTIC_TOKEN_MISMATCH',{adapterControlRevision:acr,gateControlRevision:gcr});
  if(!adapterSafe||!numericOK)return await failClosed('ADAPTER_CONTRACT_INVALID');
  if(!gateFresh)return await failClosed('STALE_GATE_AUTHORITY',{gateAgeMs:age(gate?.updatedAt)});
  if(!gatePass)return await failClosed('VALIDATION_GATE_NOT_PASS',{gateStatus:gate?.finalStatus});
  if(explicitUnsafe)return await failClosed('CORE_CHARGER_STATE_UNSAFE',{chargeState:cs});
  if(!normalControlFresh&&!deadlineAuthority)return await failClosed('STALE_CONTROL_INPUT_NO_DEADLINE_AUTHORITY',{intentFresh,adapterFresh,gateFresh,stateFresh,deadlineEligible});
  if(!coreSafeFresh&&!deadlineAuthority)return await failClosed(stateFresh?'CORE_CHARGER_STATE_UNSAFE':'STALE_STATE_NO_DEADLINE_AUTHORITY',{chargeState:cs,stateAgeMs:age(state?.sampledAt),deadlineEligible});
  if(requestedA===0){const w=await writeA(0);await report(w.write?'WRITE_ZERO_NORMALIZE':'NOOP_ALREADY_TARGET',{targetW,targetA:0,previousA:w.previousA,controlRevision:cr,coreRevision:coreR,physicalWritePerformed:w.write,live:true});return true;}
  const degraded=deadlineAuthority&&(!intentFresh||!adapterFresh||!stateFresh);
  await report(degraded?'READY_SESSION_CONTROL_DEGRADED_DEADLINE_AUTHORITY':'READY_SESSION_CONTROL',{targetW,targetA:requestedA,controlRevision:cr,coreRevision:coreR,gateStatus:'PASS',live:true,physicalWritePerformed:false,degraded,degradedReason:degraded?'STALE_UPSTREAM_ACCEPTED_BY_FRESH_GATE':null,intentAgeMs:age(intent?.generatedAt),adapterAgeMs:age(adapter?.generatedAt),stateAgeMs:age(state?.sampledAt),gateAgeMs:age(gate?.updatedAt),deadlineAt:pp?.deadlineAt??null});
  return true;
}catch(e){return await failClosed('RUNTIME_EXCEPTION',{error:String(e?.message||e)});}
'''

SESSION_CODE = r'''// EV Actuator v0.2.11 POST-SESSION + DEADLINE GATE AUTHORITY
const VERSION='EM2_EV_ACTUATOR_V0.2.11',CHARGER_ID='4d0b6913-d940-474e-95d6-b43f194c4119',FRESH_MS=120000;
const IDS={live:'8d47e98d-e4bc-4f47-8c02-c2aca7f7a978',status:'ea1f8a44-2f6c-490e-9b86-bae761886cf9',intent:'04b57041-dd7f-41f7-a00a-f023afb1ccee',adapter:'f2118322-d59d-4aa8-b478-234effc3983c',gate:'4c66836b-77ae-43b5-b8e0-b32af15b57bc',state:'8e1efbb0-7999-494c-9429-7d274afacd79'};
const parse=x=>{try{return JSON.parse(String(x??''));}catch{return null;}};
const num=x=>{if(x===null||x===undefined||x==='')return null;const n=Number(x);return Number.isFinite(n)?n:null;};
const age=x=>{const t=Date.parse(String(x||''));return Number.isFinite(t)?Date.now()-t:Infinity;};
const [liveVar,statusVar,intentVar,adapterVar,gateVar,stateVar]=await Promise.all([Homey.logic.getVariable({id:IDS.live}),Homey.logic.getVariable({id:IDS.status}),Homey.logic.getVariable({id:IDS.intent}),Homey.logic.getVariable({id:IDS.adapter}),Homey.logic.getVariable({id:IDS.gate}),Homey.logic.getVariable({id:IDS.state})]);
const intent=parse(intentVar?.value),adapter=parse(adapterVar?.value),gate=parse(gateVar?.value),state=parse(stateVar?.value),ev=intent?.targets?.ev||{},pp=intent?.policyProjection||{};
const targetW=num(ev?.target_W),targetStatus=String(ev?.status??''),targetSource=String(ev?.source??''),requestedA=num(adapter?.command?.requested_A),icr=String(intent?.controlRevision||''),cr=String(adapter?.controlRevision||''),gcr=String(gate?.controlRevision||'');
const effectiveIntentCr=icr||JSON.stringify({policy:String(intent?.policyRevision||''),engine:String(intent?.engineVersion||''),valid:intent?.valid===true,status:String(intent?.status||''),evTargetW:targetW,evStatus:targetStatus,evSource:targetSource,wwTargetOn:intent?.targets?.ww?.target_on??null,wwStatus:String(intent?.targets?.ww?.status||''),authority:String(pp?.authoritySelector||pp?.plannerOwner||'')});
const deadlineAtMs=Date.parse(String(pp?.deadlineAt||'')),deadlineRemainingKWh=num(pp?.deadlineRemainingKWh),deadlineMaxA=num(pp?.deadlineMaxA);
const deadlineEligible=pp?.deadlineGuardApplied===true&&pp?.deadlineTeslaConnected===true&&targetStatus==='NUMERIC_DEADLINE_TARGET'&&targetSource==='REMAINING_KWH_OVER_TIME_TO_DEADLINE'&&Number.isInteger(targetW)&&targetW>0&&Number.isInteger(requestedA)&&requestedA>=6&&requestedA<=16&&Number.isInteger(deadlineMaxA)&&deadlineMaxA>=6&&deadlineMaxA<=16&&requestedA<=deadlineMaxA&&deadlineRemainingKWh!==null&&deadlineRemainingKWh>0&&Number.isFinite(deadlineAtMs)&&deadlineAtMs>Date.now();
const devices=await Homey.devices.getDevices();const charger=devices[CHARGER_ID];if(!charger)throw new Error('CHARGER_MISSING');
const currentA=num(charger.capabilitiesObj?.target_charger_current?.value),cs=String(state?.tesla?.chargeState??'unknown').toLowerCase();
const stateFresh=age(state?.sampledAt)<=FRESH_MS,intentFresh=age(intent?.generatedAt)<=FRESH_MS,adapterFresh=age(adapter?.generatedAt)<=FRESH_MS,gateFresh=age(gate?.updatedAt)<=FRESH_MS;
const explicitUnsafe=['offline','error','fault','disconnected','unplugged'].some(x=>cs.includes(x));
const connectedState=cs.includes('plugged_in')||cs.includes('charging');
const tokenOK=!!effectiveIntentCr&&cr===effectiveIntentCr&&gcr===effectiveIntentCr&&gate?.adapterControlRevision===effectiveIntentCr;
const adapterSafe=adapter?.valid===true&&adapter?.deviceWrites===false&&adapter?.readOnly===true&&adapter?.command?.physicalWrite===false&&adapter?.safety?.failClosed===true&&adapter?.safety?.semanticTokenGuard===true;
const numericOK=Number.isInteger(requestedA)&&requestedA>=0&&requestedA<=16&&(requestedA===0||requestedA>=6);
const gatePass=gate?.finalStatus==='PASS';
const deadlineAuthority=deadlineEligible&&gateFresh&&gatePass&&tokenOK&&adapterSafe&&numericOK&&connectedState&&!explicitUnsafe;
const normalCoherent=liveVar.value===true&&intentFresh&&adapterFresh&&gateFresh&&gatePass&&tokenOK&&adapterSafe&&numericOK&&stateFresh&&!['','unknown'].includes(cs)&&!explicitUnsafe;
const coherent=normalCoherent||(liveVar.value===true&&deadlineAuthority);
const degraded=deadlineAuthority&&(!intentFresh||!adapterFresh||!stateFresh);
const report=async(status,extra={})=>{await Homey.logic.updateVariable({id:IDS.status,variable:{value:JSON.stringify({schema:VERSION,status,at:new Date().toISOString(),...extra})}});};
if(!coherent||requestedA===0){if(currentA!==0)await charger.setCapabilityValue('target_charger_current',0);await report('POST_SESSION_ABORT_ZERO',{requestedA,previousA:currentA,controlRevision:cr,physicalWritePerformed:currentA!==0,normalCoherent,deadlineAuthority,gateFresh,gateStatus:gate?.finalStatus,chargeState:cs});return true;}
if(!Number.isInteger(requestedA)||requestedA<6||requestedA>16){if(currentA!==0)await charger.setCapabilityValue('target_charger_current',0);await report('POST_SESSION_INVALID_ZERO',{requestedA,previousA:currentA,controlRevision:cr,physicalWritePerformed:currentA!==0});return true;}
if(currentA!==requestedA)await charger.setCapabilityValue('target_charger_current',requestedA);
await report(degraded?(currentA===requestedA?'NOOP_DEGRADED_DEADLINE_AUTHORITY':'WRITE_OK_DEGRADED_DEADLINE_AUTHORITY'):(currentA===requestedA?'NOOP_POST_SESSION_TARGET':'WRITE_OK_POST_SESSION'),{targetA:requestedA,previousA:currentA,controlRevision:cr,coreRevision:num(state?.revision),physicalWritePerformed:currentA!==requestedA,degraded,degradedReason:degraded?'STALE_UPSTREAM_ACCEPTED_BY_FRESH_GATE':null,intentAgeMs:age(intent?.generatedAt),adapterAgeMs:age(adapter?.generatedAt),stateAgeMs:age(state?.sampledAt),gateAgeMs:age(gate?.updatedAt),deadlineAt:pp?.deadlineAt??null});
return true;
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', default='/tmp/ev-actuator-v0.2.10-candidate.json')
    ap.add_argument('--output', default='/tmp/ev-actuator-v0.2.11-candidate.json')
    ap.add_argument('--flow-id', default=FLOW_ID_DEFAULT)
    args = ap.parse_args()

    raw = json.loads(Path(args.input).read_text(encoding='utf-8'))
    flow = raw.get(args.flow_id) if isinstance(raw, dict) and args.flow_id in raw else raw
    if not isinstance(flow, dict):
        raise SystemExit('invalid flow JSON')
    if flow.get('enabled') is not True:
        raise SystemExit('refusing: baseline flow is not enabled')
    if flow.get('broken') is True:
        raise SystemExit('refusing: baseline flow is broken')

    cards = flow.get('cards') or {}
    for cid in (MAIN_CARD_ID, SESSION_CARD_ID):
        if cid not in cards:
            raise SystemExit(f'required card missing: {cid}')
        if cards[cid].get('id') != 'homey:app:com.athom.homeyscript:runCode_v2':
            raise SystemExit(f'unexpected card type for {cid}')

    old_main = str((cards[MAIN_CARD_ID].get('args') or {}).get('code', ''))
    old_session = str((cards[SESSION_CARD_ID].get('args') or {}).get('code', ''))
    if EXPECTED_BASELINE_MARKER not in old_main or EXPECTED_BASELINE_MARKER not in old_session:
        raise SystemExit('refusing: expected deployed v0.2.10 marker not present in both cards')

    cards[MAIN_CARD_ID]['args']['code'] = MAIN_CODE
    cards[SESSION_CARD_ID]['args']['code'] = SESSION_CODE
    flow['name'] = 'EM v2 | 60 Actuator | EV Power v0.2.11 SEMANTIC-TOKEN LIVE + DEADLINE GATE AUTHORITY'

    out = Path(args.output)
    out.write_text(json.dumps(flow, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'candidate={out}')
    print(f'flow_id={args.flow_id}')
    print(f'name={flow.get("name")}')
    print(f'enabled={flow.get("enabled")} broken={flow.get("broken")}')
    print(f'main_card={MAIN_CARD_ID} -> v0.2.11')
    print(f'session_card={SESSION_CARD_ID} -> v0.2.11')
    print('policy=fresh PASS gate is deadline authority; stale adapter/state timestamps alone are degraded')
    print('homey_calls=0')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
