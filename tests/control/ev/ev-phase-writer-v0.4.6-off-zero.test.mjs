import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const src=fs.readFileSync('apps/homey/control/ev/ev-power-v0.4.6.off-zero-idempotent.js','utf8');
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;

const helperStart=src.indexOf('const offZeroConfirmed=hw=>');
const helperEnd=src.indexOf(';\n',helperStart)+2;
assert.ok(helperStart>=0 && helperEnd>helperStart);
const offZeroConfirmed=vm.runInNewContext(
  src.slice(helperStart,helperEnd)+'\noffZeroConfirmed'
);

const offStart=src.indexOf("if(control.mode==='OFF'){");
const offEnd=src.indexOf('// If the EV is already safely paused on the requested confirmed phase',offStart);
assert.ok(offStart>=0 && offEnd>offStart);
const offBlock=src.slice(offStart,offEnd);
const runOff=new AsyncFunction('ctx',`
  const control={mode:'OFF'};
  let hw=ctx.initial;
  const offZeroConfirmed=ctx.offZeroConfirmed;
  const setCurrentA=ctx.setCurrentA;
  const waitHardware=ctx.waitHardware;
  const readHardware=ctx.readHardware;
  const saveStatus=ctx.saveStatus;
  const safeAbort=ctx.safeAbort;
  const liveEnabled=true;
  const CURRENT_CONFIRM_TIMEOUT_MS=6000;
  ${offBlock}
`);

const safe=(changes={})=>({
  charging:false,chargeState:'plugged_in_paused',
  chargerTargetA:0,offeredA:0,powerW:0,
  ...changes
});

function fixture(initial,{waitResult,waitError,finalRead}={}){
  const calls=[];
  let abortDetails=null;
  const ctx={
    initial,offZeroConfirmed,
    setCurrentA:async a=>{calls.push(['setCurrentA',a]);},
    waitHardware:async(predicate)=>{
      calls.push(['waitHardware']);
      if(waitError)throw waitError;
      assert.equal(predicate(waitResult),true);
      return waitResult;
    },
    readHardware:async()=>{
      calls.push(['readHardware']);
      return finalRead;
    },
    saveStatus:async(...args)=>{calls.push(['saveStatus',args[0],args[1],args[6]]);},
    safeAbort:async(...args)=>{
      abortDetails=args;
      calls.push(['safeAbort',args[0]]);
      return true;
    }
  };
  return {calls,ctx,getAbort:()=>abortDetails};
}

test('v0.4.6 HomeyScript syntax is valid and single-writer boundary unchanged',()=>{
  assert.doesNotThrow(()=>new AsyncFunction(src));
  assert.match(src,/VERSION='EM2_EV_ACTUATOR_V0\.4\.6_PHASE_WRITER'/);
  assert.match(src,/PREVIOUS_COMPAT_VERSION='EM2_EV_ACTUATOR_V0\.4\.5_PHASE_WRITER'/);
  assert.match(src,/OLDER_COMPAT_VERSION='EM2_EV_ACTUATOR_V0\.4\.4_PHASE_WRITER'/);
  assert.match(src,/SUPPORTED_VERSIONS\.includes\(previous\?\.schema\)/);
  assert.doesNotMatch(src,/setCapabilityValue\(/);
  assert.doesNotMatch(src,/triggerAdvancedFlow/);
  assert.match(src,/const withEasee401RefreshRetry=async/);
  assert.match(src,/const safeAbort=async/);
  assert.match(src,/hw=await restoreCircuit\(originalCircuitA\)/);
  assert.match(src,/await sleep\(DEADTIME_MS\)/);
});

test('confirmed zero current means zero actions even after previously FAILED status',async()=>{
  const f=fixture(safe());
  await runOff(f.ctx);
  assert.deepEqual(f.calls.map(x=>x[0]),['saveStatus']);
  assert.equal(f.calls[0][1],'STABLE');
  assert.equal(f.calls[0][2],'OFF_ZERO_A_HOLD');
  assert.equal(f.calls[0][3].physicalWritePerformed,false);
});

test('zero readback is not accepted with charging, missing offeredA or residual power',()=>{
  assert.equal(offZeroConfirmed(safe()),true);
  assert.equal(offZeroConfirmed(safe({charging:true})),false);
  assert.equal(offZeroConfirmed(safe({chargerTargetA:6})),false);
  assert.equal(offZeroConfirmed(safe({offeredA:null})),false);
  assert.equal(offZeroConfirmed(safe({offeredA:2})),false);
  assert.equal(offZeroConfirmed(safe({powerW:null})),false);
  assert.equal(offZeroConfirmed(safe({powerW:500})),false);
});

test('unconfirmed OFF issues only native current-zero and requires fresh confirmation',async()=>{
  const f=fixture(safe({chargerTargetA:8,powerW:1800}),{waitResult:safe()});
  await runOff(f.ctx);
  assert.deepEqual(f.calls.map(x=>x[0]),['setCurrentA','waitHardware','saveStatus']);
  assert.equal(f.calls[0][1],0);
  assert.equal(f.calls[2][1],'STABLE');
  assert.equal(f.calls[2][3].physicalWritePerformed,true);
  assert.doesNotMatch(offBlock,/resumeSession\(/);
  assert.doesNotMatch(offBlock,/pauseSession\(/);
  assert.doesNotMatch(offBlock,/pauseAndConfirm\(/);
});

test('late but safe final read after timeout becomes STABLE without recovery cycle',async()=>{
  const timeout=new Error('OFF_ZERO_CURRENT_CONFIRM_TIMEOUT');
  timeout.lastHardware=safe({offeredA:8,powerW:1200});
  const f=fixture(safe({chargerTargetA:8}),{waitError:timeout,finalRead:safe()});
  await runOff(f.ctx);
  assert.deepEqual(f.calls.map(x=>x[0]),[
    'setCurrentA','waitHardware','readHardware','saveStatus'
  ]);
  assert.equal(f.calls[3][2],'OFF_ZERO_A_HOLD_LATE_CONFIRMED');
});

test('unsafe final read fails closed and records original timeout evidence',async()=>{
  const timeout=new Error('OFF_ZERO_CURRENT_CONFIRM_TIMEOUT');
  const unsafe=safe({offeredA:8,powerW:2000});
  timeout.lastHardware=unsafe;
  const f=fixture(safe({chargerTargetA:8}),{
    waitError:timeout,
    finalRead:safe({powerW:900})
  });
  await runOff(f.ctx);
  assert.deepEqual(f.calls.map(x=>x[0]),[
    'setCurrentA','waitHardware','readHardware','safeAbort'
  ]);
  assert.match(f.calls[3][1],/OFF_ZERO_CURRENT_CONFIRM_TIMEOUT/);
  assert.deepEqual(f.getAbort()[5].offZeroLastReadback,unsafe);
  assert.match(src,/statusExtra:\{authAlert,\.\.\.diagnostics\}/);
});

test('no positive write and no weakened fail-closed or AUTH handling',()=>{
  assert.match(src,/const offZeroConfirmed=hw=>/);
  assert.match(src,/hw\?\.charging===false/);
  assert.match(src,/Number\.isFinite\(hw\?\.offeredA\)/);
  assert.match(src,/Number\.isFinite\(hw\?\.powerW\)/);
  assert.match(src,/EASEE_REFRESH_HTTP_\(400\|401\|403\)/);
  assert.match(src,/PAUSE_AND_RESTORE/);
  assert.match(src,/CURRENT_CONFIRM_TIMEOUT_MS/);
});
