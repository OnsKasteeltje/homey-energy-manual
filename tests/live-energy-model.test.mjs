import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

async function loadBrowserScript(path, extra = {}) {
  const code = await readFile(path, 'utf8');
  const context = { console, window: {}, ...extra };
  context.window = context.window || {};
  vm.createContext(context);
  vm.runInContext(code, context, { filename: path });
  return context;
}

function baseState(overrides = {}) {
  return {
    meta: { schema_version: '2.11', state_revision: 1, decision_revision: 1, shadow_revision: 1 },
    grid: { power_w: 500 },
    pv: { total_w: 1000, solaredge_w: 1000, goodwe_4200_w: 0, goodwe_2000_w: 0 },
    battery: { power_w: 0 },
    energy_budget: { house_load_w: 1500 },
    tesla: { power_w: 0, connected: false },
    hot_water: { boiler_power_w: 0, boiler_on: false },
    quatt: { power_w: 0, thermostat_heating_on: false, cv_requested: false, cv_flame: false },
    loads: { washer: { active: false, power_w: 0 }, dryer: { active: false, power_w: 0 }, quooker: { active: false, switch_on: false, power_w: 0, status: 'OFF', source: 'HOMEY_SWITCH_PLUS_P1_L3', fresh: true } },
    manager: { decision: 'HOLD' },
    ...overrides,
  };
}

const modelContext = await loadBrowserScript('docs/javascripts/live-energy-model-v2.js');
const Model = modelContext.window.LiveEnergyModel;

test('20 W is standby; above 20 W is active', () => { assert.equal(Model.isActive(20), false); assert.equal(Model.activeW(20), 0); assert.equal(Model.isActive(21), true); assert.equal(Model.activeW(21), 21); });

test('grid sign produces import and export correctly', () => { const imported=Model.buildViewModel(baseState({grid:{power_w:750}}),true); assert.equal(imported.importW,750); assert.equal(imported.exportW,0); const exported=Model.buildViewModel(baseState({grid:{power_w:-425}}),true); assert.equal(exported.importW,0); assert.equal(exported.exportW,425); });

test('battery sign produces charge and discharge correctly', () => { const charging=Model.buildViewModel(baseState({battery:{power_w:600}}),true); assert.equal(charging.charge,600); assert.equal(charging.discharge,0); const discharging=Model.buildViewModel(baseState({battery:{power_w:-600}}),true); assert.equal(discharging.charge,0); assert.equal(discharging.discharge,600); });

test('house fallback prefers measured physical candidate before arithmetic fallback', () => { const candidate=baseState({grid:{power_w:300},pv:{total_w:700},battery:{power_w:-200},energy_budget:{},balance:{physical_house_candidate_w:987}}); const fromCandidate=Model.buildViewModel(candidate,true); assert.equal(fromCandidate.house,987); assert.equal(fromCandidate.houseSource,'BALANCE_PHYSICAL_HOUSE_CANDIDATE'); delete candidate.balance; const fromMath=Model.buildViewModel(candidate,true); assert.equal(fromMath.house,1200); assert.equal(fromMath.houseSource,'MEASURED_PV_GRID_BATTERY'); });

test('Overig contains only the residual after top-level consumers and decomposes secondary loads once', () => {
  const state=baseState({energy_budget:{house_load_w:2000},tesla:{power_w:500},hot_water:{boiler_power_w:400},quatt:{power_w:300},loads:{washer:{active:true,power_w:200},dryer:{active:true,power_w:100},dishwasher:{power_w:100},sonos:{power_w:25},quooker:{active:true,switch_on:true,status:'HEATING',power_w:50}}});
  const result=Model.buildViewModel(state,true);
  assert.equal(result.assigned,1550);
  assert.equal(result.other,450);
  assert.equal(result.detailKnownTotal,125);
  assert.equal(result.unattributedOther,325);
  assert.equal(result.assigned + result.other, result.house);
  state.energy_budget.house_load_w=100;
  assert.equal(Model.buildViewModel(state,true).other,0);
});

test('Quooker is first-class: switch status is separate from heating and residual', () => { const idle=baseState({energy_budget:{house_load_w:500},loads:{washer:{active:false,power_w:0},dryer:{active:false,power_w:0},quooker:{active:false,switch_on:true,status:'ON_IDLE',power_w:0,source:'HOMEY_SWITCH_PLUS_P1_L3',fresh:true}}}); const idleVm=Model.buildViewModel(idle,true); assert.equal(idleVm.consumers.length,7); assert.equal(idleVm.consumers[5].title,'Quooker'); assert.equal(idleVm.quooker.switchOn,true); assert.equal(idleVm.quooker.active,false); assert.equal(idleVm.quooker.sub,'aan · op temperatuur/idle'); assert.equal(idleVm.other,500); const heating=baseState({energy_budget:{house_load_w:2000},loads:{washer:{active:false,power_w:0},dryer:{active:false,power_w:0},quooker:{active:true,switch_on:true,status:'HEATING',power_w:1579,source:'HOMEY_SWITCH_PLUS_P1_L3',fresh:true}}}); const heatingVm=Model.buildViewModel(heating,true); assert.equal(heatingVm.quooker.active,true); assert.equal(heatingVm.quooker.power,1579); assert.equal(heatingVm.consumers[5].active,true); assert.equal(heatingVm.other,421); });

test('inactive appliance without measured power is normalized to 0 W in the model', () => { const state=baseState({loads:{washer:{active:false,power_w:null},dryer:{active:false,power_w:null}}}); const result=Model.buildViewModel(state,true); assert.equal(result.washer.value,'0 W'); assert.equal(result.dryer.value,'0 W'); });

test('active appliance without measured power remains explicit and unestimated', () => { const state=baseState({loads:{washer:{active:true,power_w:null},dryer:{active:false,power_w:0}}}); const result=Model.buildViewModel(state,true); assert.equal(result.washer.known,false); assert.equal(result.washer.power,0); assert.equal(result.washer.active,false); assert.equal(result.washer.stateActive,true); assert.equal(result.washer.value,'—'); assert.match(result.washer.sub,/vermogen niet apart gemeten/); });

test('Quatt and CV hybrid classification is preserved', () => { const state=baseState({quatt:{power_w:500,thermostat_heating_on:true,cv_requested:true,cv_flame:true}}); const result=Model.buildViewModel(state,true); assert.equal(result.quattFlowActive,true); assert.equal(result.heatSub,'Quatt + CV · hybride'); });

test('EnergyStore publishes state/error and supports unsubscribe', async () => { const context=await loadBrowserScript('docs/javascripts/energy-store-v1.js'); const Store=context.window.EnergyStore; const events=[]; const unsubscribe=Store.subscribe(event=>events.push(event.type)); Store.setSnapshot({id:1}); Store.setError('boom'); unsubscribe(); Store.setSnapshot({id:2}); assert.deepEqual(events,['state','error']); assert.deepEqual(Store.getState(),{id:2}); assert.equal(Store.getError(),null); });
