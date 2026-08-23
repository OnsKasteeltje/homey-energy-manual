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
    return {known,power,active,stateActive,value:known?fmt(power):(stateActive?'—':'0 W'),sub:active?'actief':stateActive?(known?'stand-by / laag verbruik':'actief · vermogen niet apart gemeten'):'niet actief'};
  }

  function derivedHouseGate(raw){
    const gate=raw?.balance?.control_gate?.derived_house_balance_valid;
    if(typeof gate==='boolean')return gate;
    const budgetGate=raw?.energy_budget?.derived_house_balance_valid;
    return typeof budgetGate==='boolean'?budgetGate:null;
  }

  function resolveHouse(raw,pv,grid,charge,discharge){
    const gate=derivedHouseGate(raw);
    if(gate===false)return {power:0,source:'DERIVED_BALANCE_UNAVAILABLE',valid:false};
    const budget=raw.energy_budget||{};
    if(finite(budget.house_load_w)) return {power:pos(budget.house_load_w),source:'ENERGY_BUDGET',valid:true};
    const candidate=raw.balance?.physical_house_candidate_w;
    if(finite(candidate)&&Number(candidate)>=0) return {power:pos(candidate),source:'BALANCE_PHYSICAL_HOUSE_CANDIDATE',valid:true};
    return {power:Math.max(0,pv+grid+discharge-charge),source:'MEASURED_PV_GRID_BATTERY',valid:gate!==false};
  }

  function detailLoad(load){return load&&finite(load.power_w)?pos(load.power_w):0;}

  function buildViewModel(raw,freshness){
    if(!raw) return null;
    const gridRaw=raw.grid||{},pvRaw=raw.pv||{},teslaRaw=raw.tesla||{},hotWaterRaw=raw.hot_water||{},heatingRaw=raw.quatt||raw.heating||{},batteryRaw=raw.battery||{},loadsRaw=raw.loads||{},quookerRaw=loadsRaw.quooker||{},metaRaw=raw.meta||{};
    const solaredge=pos(pvRaw.solaredge_w),goodwe4200=pos(pvRaw.goodwe_4200_w),goodwe2000=pos(pvRaw.goodwe_2000_w),pv=pos(pvRaw.total_w)||solaredge+goodwe4200+goodwe2000;
    const grid=n(gridRaw.power_w),importW=Math.max(0,grid),exportW=Math.max(0,-grid);
    const battery=n(batteryRaw.power_w),charge=battery>0?battery:0,discharge=battery<0?Math.abs(battery):0;
    const resolvedHouse=resolveHouse(raw,pv,grid,charge,discharge),house=resolvedHouse.power,houseValid=resolvedHouse.valid!==false;

    // Direct device measurements are authoritative for their own cards. They are never
    // invalidated by P1/PV source skew. The Core field hot_water.boiler_power_w is the
    // direct Homey Boiler measure_power publication, analogous to tesla.power_w from Easee.
    const teslaKnown=finite(teslaRaw.power_w),tesla=teslaKnown?pos(teslaRaw.power_w):0;
    const boilerKnown=finite(hotWaterRaw.boiler_power_w),boiler=boilerKnown?pos(hotWaterRaw.boiler_power_w):0;
    const quatt=pos(heatingRaw.power_w??heatingRaw.quatt_power_w),washer=appliance(loadsRaw.washer),dryer=appliance(loadsRaw.dryer);
    const quookerPower=finite(quookerRaw.power_w)?pos(quookerRaw.power_w):0,quookerSwitchOn=quookerRaw.switch_on===true,quookerStatus=String(quookerRaw.status||'UNKNOWN').toUpperCase(),quookerHeating=quookerRaw.active===true&&quookerStatus==='HEATING'&&isActive(quookerPower);
    const quooker={known:finite(quookerRaw.power_w),power:quookerPower,active:quookerHeating,switchOn:quookerSwitchOn,status:quookerStatus,value:fmt(quookerPower),sub:quookerHeating?'verwarmt':quookerSwitchOn?'aan · op temperatuur/idle':'uit',source:quookerRaw.source||null,fresh:quookerRaw.fresh!==false};

    // Overig is a derived residual and therefore only exists when Core explicitly permits
    // the P1+PV house reconstruction. Direct device cards above remain valid independently.
    const topLevelAssigned=tesla+boiler+quatt+washer.power+dryer.power+quooker.power;
    const other=houseValid?Math.max(0,house-topLevelAssigned):0;
    const detailKnown={
      dishwasher:detailLoad(loadsRaw.dishwasher),
      sonos:detailLoad(loadsRaw.sonos||loadsRaw.sonos_kitchen||loadsRaw.kitchen_sonos),
      kitchen:detailLoad(loadsRaw.kitchen||loadsRaw.kitchen_appliances||loadsRaw.keukenapparaten)
    };
    const detailKnownTotal=detailKnown.dishwasher+detailKnown.sonos+detailKnown.kitchen;
    const unattributedOther=houseValid?Math.max(0,other-detailKnownTotal):0;

    const thermal=pos(heatingRaw.thermal_power_w),thermostatHeating=heatingRaw.thermostat_heating_on===true,cvRequested=heatingRaw.cv_requested===true,cvKnown=typeof heatingRaw.cv_flame==='boolean',cvFlame=heatingRaw.cv_flame===true;
    const working=[heatingRaw.working_mode_1,heatingRaw.working_mode_2].some(v=>String(v??'0')!=='0'&&String(v??'').toLowerCase()!=='unknown');
    const quattDemand=thermal>100||working||(quatt>100&&thermostatHeating),quattFlowActive=isActive(quatt);
    let heatSub='geen warmtevraag'; if(quattFlowActive&&cvFlame)heatSub='Quatt + CV · hybride'; else if(quattFlowActive&&cvRequested&&!cvKnown)heatSub='Quatt · CV gevraagd'; else if(quattFlowActive)heatSub='Quatt actief'; else if(cvFlame)heatSub='CV verwarmt'; else if(cvRequested)heatSub='CV ondersteuning gevraagd'; else if(thermostatHeating||quattDemand)heatSub='warmtevraag · laag elektrisch verbruik';
    const uncertain=[!washer.known&&washer.stateActive?'wasmachine':'',!dryer.known&&dryer.stateActive?'droger':''].filter(Boolean);
    const otherSub=uncertain.length?`incl. ${uncertain.join(' + ')}`:(detailKnownTotal>0?'incl. bekende kleine verbruikers':'rest na bekende top-level vermogens');
    const boilerValue=boilerKnown?fmt(boiler):'—';
    const boilerSub=!boilerKnown?'directe Homey-meting niet beschikbaar':isActive(boiler)?'verwarmt · direct Homey':(hotWaterRaw.boiler_on?'aan · 0 W direct Homey':'uit · direct Homey');
    const consumers=[
      {x:25,title:'Tesla',value:teslaKnown?fmt(tesla):'—',sub:isActive(tesla)?'laden':(teslaRaw.connected?'aangesloten · geen actief verbruik':'niet aangesloten'),w:tesla,active:teslaKnown&&isActive(tesla),ico:'car'},
      {x:230,title:'Boiler',value:boilerValue,sub:boilerSub,w:boiler,active:boilerKnown&&isActive(boiler),ico:'boiler'},
      {x:435,title:'Ruimteverwarming',value:fmt(quatt),sub:heatSub,w:quatt,active:quattFlowActive,ico:'heat'},
      {x:640,title:'Wasmachine',value:washer.value,sub:washer.sub,w:washer.power,active:washer.active,ico:'washer'},
      {x:845,title:'Droger',value:dryer.value,sub:dryer.sub,w:dryer.power,active:dryer.active,ico:'dryer'},
      {x:1050,title:'Quooker',value:quooker.value,sub:quooker.sub,w:quooker.power,active:quooker.active,ico:'quooker'},
      {x:1255,title:'Overig',value:houseValid?fmt(other):'—',sub:houseValid?(isActive(other)?otherSub:'laag/stand-by restverbruik'):'P1/PV niet tijdgelijk',w:houseValid?other:0,active:houseValid&&isActive(other),ico:'more'}
    ];
    const bus={total:consumers.reduce((sum,c)=>sum+activeW(c.w),0)};
    const cvState=cvRequested?'CV ondersteuning gevraagd':'CV niet gevraagd',cvDiag=cvKnown?(cvFlame?'OpenTherm · brander actief':'OpenTherm · brander niet actief'):'OpenTherm · branderfeedback niet beschikbaar',quattState=quattFlowActive?'verwarmt':thermostatHeating?'warmtevraag':'geen warmtevraag';
    return {thresholdW:ACTIVE_THRESHOLD_W,fresh:freshness!==false,meta:metaRaw,raw:{tesla:teslaRaw,hotWater:hotWaterRaw,manager:raw.manager||{},quooker:quookerRaw},pv,grid,importW,exportW,charge,discharge,house,houseValid,houseSource:resolvedHouse.source,tesla,teslaKnown,boiler,boilerKnown,boilerSource:'HOMEY_DIRECT_MEASURE_POWER',quatt,washer,dryer,quooker,other,detailKnown,detailKnownTotal,unattributedOther,heatSub,quattFlowActive,cvRequested,cvKnown,cvFlame,thermostatHeating,cvState,cvDiag,quattState,assigned:topLevelAssigned,consumers,bus};
  }

  window.LiveEnergyModel={ACTIVE_THRESHOLD_W,n,pos,fmt,activeW,isActive,appliance,derivedHouseGate,resolveHouse,buildViewModel};
})();
