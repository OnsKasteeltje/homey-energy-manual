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
    meta: { schema_version: '2.10', state_revision: 1, decision_revision: 1, shadow_revision: 1 },
    grid: { power_w: 500 },
    pv: { total_w: 1000, solaredge_w: 1000, goodwe_4200_w: 0, goodwe_2000_w: 0 },
    battery: { power_w: 0 },
    energy_budget: { house_load_w: 1500 },
    tesla: { power_w: 0, connected: false },
    hot_water: { boiler_power_w: 0, boiler_on: false },
    quatt: { power_w: 0, thermostat_heating_on: false, cv_requested: false, cv_flame: false },
    loads: { washer: { active: false, power_w: 0 }, dryer: { active: false, power_w: 0 } },
    manager: { decision: 'HOLD' },
    ...overrides,
  };
}

const modelContext = await loadBrowserScript('docs/javascripts/live-energy-model-v1.js');
const Model = modelContext.window.LiveEnergyModel;

test('20 W is standby; above 20 W is active', () => {
  assert.equal(Model.isActive(20), false);
  assert.equal(Model.activeW(20), 0);
  assert.equal(Model.isActive(21), true);
  assert.equal(Model.activeW(21), 21);
});

test('grid sign produces import and export correctly', () => {
  const imported = Model.buildViewModel(baseState({ grid: { power_w: 750 } }), true);
  assert.equal(imported.importW, 750);
  assert.equal(imported.exportW, 0);

  const exported = Model.buildViewModel(baseState({ grid: { power_w: -425 } }), true);
  assert.equal(exported.importW, 0);
  assert.equal(exported.exportW, 425);
});

test('battery sign produces charge and discharge correctly', () => {
  const charging = Model.buildViewModel(baseState({ battery: { power_w: 600 } }), true);
  assert.equal(charging.charge, 600);
  assert.equal(charging.discharge, 0);

  const discharging = Model.buildViewModel(baseState({ battery: { power_w: -600 } }), true);
  assert.equal(discharging.charge, 0);
  assert.equal(discharging.discharge, 600);
});

test('house fallback is derived from PV, grid and battery when budget is missing', () => {
  const state = baseState({
    grid: { power_w: 300 },
    pv: { total_w: 700 },
    battery: { power_w: -200 },
    energy_budget: {},
  });
  assert.equal(Model.buildViewModel(state, true).house, 1200);
});

test('other is residual after measured/known loads and never negative', () => {
  const state = baseState({
    energy_budget: { house_load_w: 2000 },
    tesla: { power_w: 500 },
    hot_water: { boiler_power_w: 400 },
    quatt: { power_w: 300 },
    loads: {
      washer: { active: true, power_w: 200 },
      dryer: { active: true, power_w: 100 },
      dishwasher: { power_w: 100 },
      quooker: { power_w: 50 },
    },
  });
  assert.equal(Model.buildViewModel(state, true).other, 350);

  state.energy_budget.house_load_w = 100;
  assert.equal(Model.buildViewModel(state, true).other, 0);
});

test('active appliance without measured power remains explicit and unestimated', () => {
  const state = baseState({ loads: { washer: { active: true, power_w: null }, dryer: { active: false, power_w: 0 } } });
  const vm = Model.buildViewModel(state, true);
  assert.equal(vm.washer.known, false);
  assert.equal(vm.washer.power, 0);
  assert.equal(vm.washer.active, false);
  assert.equal(vm.washer.stateActive, true);
  assert.match(vm.washer.sub, /vermogen niet apart gemeten/);
});

test('Quatt and CV hybrid classification is preserved', () => {
  const state = baseState({ quatt: { power_w: 500, thermostat_heating_on: true, cv_requested: true, cv_flame: true } });
  const vm = Model.buildViewModel(state, true);
  assert.equal(vm.quattFlowActive, true);
  assert.equal(vm.heatSub, 'Quatt + CV · hybride');
});

test('EnergyStore publishes state/error and supports unsubscribe', async () => {
  const context = await loadBrowserScript('docs/javascripts/energy-store-v1.js');
  const Store = context.window.EnergyStore;
  const events = [];
  const unsubscribe = Store.subscribe(event => events.push(event.type));
  Store.setSnapshot({ id: 1 });
  Store.setError('boom');
  unsubscribe();
  Store.setSnapshot({ id: 2 });
  assert.deepEqual(events, ['state', 'error']);
  assert.deepEqual(Store.getState(), { id: 2 });
  assert.equal(Store.getError(), null);
});
