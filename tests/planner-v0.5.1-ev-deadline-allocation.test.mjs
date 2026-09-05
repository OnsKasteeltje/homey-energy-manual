import assert from 'node:assert/strict';

const STEP_MIN=15;
const EV_W_PER_A=690;
const EV_MIN_A=6;
const EV_MAX_A=16;

function allocateDeadline({nowMs,deadlineMs,latestStartMs,remainingKWh,maxA,slots,rankedStarts}){
  const a=Math.max(EV_MIN_A,Math.min(EV_MAX_A,Math.round(Number(maxA)||EV_MAX_A)));
  const maxPowerW=a*EV_W_PER_A;
  const slotEnergyKWh=maxPowerW/1000*(STEP_MIN/60);
  const requiredSlots=remainingKWh>0?Math.ceil(remainingKWh/slotEnergyKWh-1e-12):0;
  const catchUp=Number.isFinite(latestStartMs)&&nowMs>=latestStartMs;
  const candidates=slots.filter(s=>s<deadlineMs);
  const ranked=catchUp
    ? [...candidates].sort((x,y)=>x-y)
    : rankedStarts.map(x=>candidates.find(y=>y===x)).filter(Number.isFinite);
  const chosen=ranked.slice(0,Math.min(requiredSlots,ranked.length));
  const allocatedKWh=chosen.length*slotEnergyKWh;
  const unallocatedKWh=Math.max(0,remainingKWh-allocatedKWh);
  return {a,maxPowerW,slotEnergyKWh,requiredSlots,catchUp,chosen,allocatedKWh,unallocatedKWh};
}

const t=s=>Date.parse(`2026-09-05T${s}:00+02:00`);

{
  const r=allocateDeadline({
    nowMs:t('10:27'),
    deadlineMs:t('10:45'),
    latestStartMs:t('10:13'),
    remainingKWh:3.3,
    maxA:9,
    slots:[t('10:15'),t('10:30'),t('10:45'),t('11:00')],
    rankedStarts:[t('10:30'),t('10:15')]
  });
  assert.equal(r.a,9);
  assert.equal(r.maxPowerW,6210);
  assert.equal(Number(r.slotEnergyKWh.toFixed(4)),1.5525);
  assert.equal(r.requiredSlots,3);
  assert.equal(r.catchUp,true);
  assert.deepEqual(r.chosen,[t('10:15'),t('10:30')]);
  assert.equal(Number(r.unallocatedKWh.toFixed(3)),0.195);
}

{
  const r=allocateDeadline({
    nowMs:t('09:30'),
    deadlineMs:t('12:00'),
    latestStartMs:t('11:00'),
    remainingKWh:3.0,
    maxA:9,
    slots:[t('09:30'),t('09:45'),t('10:00'),t('10:15'),t('10:30'),t('10:45'),t('11:00'),t('11:15'),t('11:30'),t('11:45')],
    rankedStarts:[t('10:30'),t('10:45'),t('09:45'),t('11:00')]
  });
  assert.equal(r.requiredSlots,2);
  assert.equal(r.catchUp,false);
  assert.deepEqual(r.chosen,[t('10:30'),t('10:45')]);
  assert.equal(r.unallocatedKWh,0);
}

{
  const r=allocateDeadline({
    nowMs:t('10:00'),
    deadlineMs:t('13:00'),
    latestStartMs:t('12:00'),
    remainingKWh:1.0,
    maxA:99,
    slots:[t('10:00'),t('10:15'),t('10:30')],
    rankedStarts:[t('10:15'),t('10:00'),t('10:30')]
  });
  assert.equal(r.a,16);
  assert.equal(r.maxPowerW,11040);
  assert.equal(r.requiredSlots,1);
  assert.deepEqual(r.chosen,[t('10:15')]);
}

{
  const r=allocateDeadline({
    nowMs:t('10:00'),
    deadlineMs:t('13:00'),
    latestStartMs:t('12:00'),
    remainingKWh:0,
    maxA:9,
    slots:[t('10:00'),t('10:15')],
    rankedStarts:[t('10:00'),t('10:15')]
  });
  assert.equal(r.requiredSlots,0);
  assert.deepEqual(r.chosen,[]);
  assert.equal(r.allocatedKWh,0);
  assert.equal(r.unallocatedKWh,0);
}

console.log('PASS planner-v0.5.1 EV deadline allocation');
