import test from 'node:test';
import assert from 'node:assert/strict';
import {buildControlEvidence,CONTROL_EVIDENCE_SCHEMA} from '../src/homey/publisher/control-evidence-contract-v0.1.mjs';

test('publishes raw aligned runtime contracts without deriving values',()=>{
  const intent={schema:'EM2_POWER_INTENT_V0.2',sourceRevision:42,valid:true,deviceWrites:false,targets:{ev:{target_W:6200},ww:{target_on:true}}};
  const ev={schema:'EM2_EV_POWER_ADAPTER_V0.1',sourceRevision:42,deviceWrites:false,electrical:{executable_W:5520},command:{requested_A:8,commanded_A:null,physicalWrite:false}};
  const ww={schema:'EM2_WW_POWER_ADAPTER_V0.1',sourceRevision:42,deviceWrites:false,command:{value:true,physicalWrite:false}};
  const out=buildControlEvidence({powerIntent:intent,evAdapter:ev,wwAdapter:ww});
  assert.equal(out.schema,CONTROL_EVIDENCE_SCHEMA);
  assert.equal(out.complete,true);
  assert.equal(out.revisions.aligned,true);
  assert.equal(out.power_intent,intent);
  assert.equal(out.adapter.ev,ev);
  assert.equal(out.adapter.warm_water,ww);
  assert.equal(out.safety.derivedValues,false);
  assert.equal(out.safety.deviceWritesIntroduced,false);
});

test('incomplete or revision-mismatched evidence never reports aligned',()=>{
  const out=buildControlEvidence({powerIntent:{sourceRevision:7},evAdapter:{sourceRevision:8},wwAdapter:null});
  assert.equal(out.complete,false);
  assert.equal(out.revisions.aligned,false);
  assert.equal(out.adapter.warm_water,null);
});
