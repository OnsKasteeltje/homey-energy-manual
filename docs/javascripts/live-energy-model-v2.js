(function(){
  'use strict';

  const ACTIVE_THRESHOLD_W=20;
  const n=v=>Number.isFinite(Number(v))?Number(v):0;
  const pos=v=>Math.max(0,n(v));
  const fmt=v=>`${Math.round(Number(v)||0).toLocaleString('nl-NL')} W`;
  const activeW=v=>pos(v)>ACTIVE_THRESHOLD_W?pos(v):0;
  const isActive=v=>pos(v)>ACTIVE_THRESHOLD_W;
  const finite=v=>v!==null&&v!==undefined&&Number.isFinite(Number(v));

  function appliance(load){
    const known=!!(load&&finite(load.power_w));
    const power=known?pos(load.power_w):0;
    const active=known&&isActive(power);
    const stateActive=load?.active===true;
    return {
      known,
      power,
      active,
      stateActive,
      value:known?fmt(power):(stateActive?'—':'0 W'),
      sub:active?'actief':stateActive?(known?'stand-by / laag verbruik':'actief · vermogen niet apart gemeten'):'niet actief'
    };
  }

  function resolveHouse(raw,pv,grid,charge,discharge){
    const budget=raw.energy_budget||{};
    if(finite(budget.house_load_w)){
      return {power:pos(budget.house_load_w),source:'ENERGY_BUDGET'};
    }
    const candidate=raw.balance?.physical_house_candidate_w;
    if(finite(candidate)&&Number(candidate)>=0){
      return {power:pos(candidate),source:'BALANCE_PHYSICAL_HOUSE_CANDIDATE'};
    }
    return {power:Math.max(0,pv+grid+discharge-charge),source:'MEASURED_PV_GRID_BATTERY'};
  }

  function buildViewModel(raw,freshness){
    if(!raw) return null;

    const gridRaw=raw.grid||{};
    const pvRaw=raw.pv||{};
    const teslaRaw=raw.tesla||{};
    const hotWaterRaw=raw.hot_water||{};
    const heatingRaw=raw.quatt||raw.heating||{};
    const batteryRaw=raw.battery||{};
    const loadsRaw=raw.loads||{};
    const metaRaw=raw.meta||{};

    const solaredge=pos(pvRaw.solaredge_w);
    const goodwe4200=pos(pvRaw.goodwe_4200_w);
    const goodwe2000=pos(pvRaw.goodwe_2000_w);
    const pv=pos(pvRaw.total_w)||solaredge+goodwe4200+goodwe2000;

    const grid=n(gridRaw.power_w);
    const importW=Math.max(0,grid);
    const exportW=Math.max(0,-grid);

    const battery=n(batteryRaw.power_w);
    const charge=battery>0?battery:0;
    const discharge=battery<0?Math.abs(battery):0;
    const resolvedHouse=resolveHouse(raw,pv,grid,charge,discharge);
    const house=resolvedHouse.power;

    const tesla=pos(teslaRaw.power_w);
    const boiler=pos(hotWaterRaw.boiler_power_w);
    const quatt=pos(heatingRaw.power_w??heatingRaw.quatt_power_w);
    const washer=appliance(loadsRaw.washer);
    const dryer=appliance(loadsRaw.dryer);

    const otherKnownExtras=['dishwasher','quooker'].reduce((sum,key)=>{
      const load=loadsRaw[key];
      return sum+(load&&finite(load.power_w)?pos(load.power_w):0);
    },0);

    const other=Math.max(0,house-tesla-boiler-quatt-washer.power-dryer.power-otherKnownExtras);

    const thermal=pos(heatingRaw.thermal_power_w);
    const thermostatHeating=heatingRaw.thermostat_heating_on===true;
    const cvRequested=heatingRaw.cv_requested===true;
    const cvKnown=typeof heatingRaw.cv_flame==='boolean';
    const cvFlame=heatingRaw.cv_flame===true;
    const working=[heatingRaw.working_mode_1,heatingRaw.working_mode_2]
      .some(v=>String(v??'0')!=='0'&&String(v??'').toLowerCase()!=='unknown');
    const quattDemand=thermal>100||working||(quatt>100&&thermostatHeating);
    const quattFlowActive=isActive(quatt);

    let heatSub='geen warmtevraag';
    if(quattFlowActive&&cvFlame) heatSub='Quatt + CV · hybride';
    else if(quattFlowActive&&cvRequested&&!cvKnown) heatSub='Quatt · CV gevraagd';
    else if(quattFlowActive) heatSub='Quatt actief';
    else if(cvFlame) heatSub='CV verwarmt';
    else if(cvRequested) heatSub='CV ondersteuning gevraagd';
    else if(thermostatHeating||quattDemand) heatSub='warmtevraag · laag elektrisch verbruik';

    const uncertain=[
      !washer.known&&washer.stateActive?'wasmachine':'',
      !dryer.known&&dryer.stateActive?'droger':''
    ].filter(Boolean);
    const otherSub=uncertain.length?`incl. ${uncertain.join(' + ')}`:'rest na bekende vermogens';

    const consumers=[
      {x:55,title:'Tesla',value:fmt(tesla),sub:isActive(tesla)?'laden':(teslaRaw.connected?'aangesloten · geen actief verbruik':'niet aangesloten'),w:tesla,active:isActive(tesla),ico:'car'},
      {x:295,title:'Boiler',value:fmt(boiler),sub:isActive(boiler)?'verwarmt':(hotWaterRaw.boiler_on?'aan · geen actief verbruik':'uit'),w:boiler,active:isActive(boiler),ico:'boiler'},
      {x:535,title:'Ruimteverwarming',value:fmt(quatt),sub:heatSub,w:quatt,active:quattFlowActive,ico:'heat'},
      {x:775,title:'Wasmachine',value:washer.value,sub:washer.sub,w:washer.power,active:washer.active,ico:'washer'},
      {x:1015,title:'Droger',value:dryer.value,sub:dryer.sub,w:dryer.power,active:dryer.active,ico:'dryer'},
      {x:1255,title:'Overig',value:fmt(other),sub:isActive(other)?otherSub:'laag/stand-by restverbruik',w:other,active:isActive(other),ico:'more'}
    ];

    const bus={
      leftHeat:activeW(tesla)+activeW(boiler)+activeW(quatt),
      leftBoiler:activeW(tesla)+activeW(boiler),
      leftTesla:activeW(tesla),
      rightWasher:activeW(washer.power)+activeW(dryer.power)+activeW(other),
      rightDryer:activeW(dryer.power)+activeW(other),
      rightOther:activeW(other)
    };
    bus.total=bus.leftHeat+bus.rightWasher;

    const cvState=cvRequested?'CV ondersteuning gevraagd':'CV niet gevraagd';
    const cvDiag=cvKnown?(cvFlame?'OpenTherm · brander actief':'OpenTherm · brander niet actief'):'OpenTherm · branderfeedback niet beschikbaar';
    const quattState=quattFlowActive?'verwarmt':thermostatHeating?'warmtevraag':'geen warmtevraag';
    const assigned=tesla+boiler+quatt+washer.power+dryer.power+otherKnownExtras;

    return {
      thresholdW:ACTIVE_THRESHOLD_W,
      fresh:freshness!==false,
      meta:metaRaw,
      raw:{tesla:teslaRaw,hotWater:hotWaterRaw,manager:raw.manager||{}},
      pv,
      grid,
      importW,
      exportW,
      charge,
      discharge,
      house,
      houseSource:resolvedHouse.source,
      tesla,
      boiler,
      quatt,
      washer,
      dryer,
      other,
      otherKnownExtras,
      heatSub,
      quattFlowActive,
      cvRequested,
      cvKnown,
      cvFlame,
      thermostatHeating,
      cvState,
      cvDiag,
      quattState,
      assigned,
      consumers,
      bus
    };
  }

  window.LiveEnergyModel={
    ACTIVE_THRESHOLD_W,
    n,
    pos,
    fmt,
    activeW,
    isActive,
    appliance,
    resolveHouse,
    buildViewModel
  };
})();
