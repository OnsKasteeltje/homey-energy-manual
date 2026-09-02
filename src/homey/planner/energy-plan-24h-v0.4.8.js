// EM v2 | 45 Planner | 24h Energy Plan v0.4.8 SHADOW LOW-LOAD
// Weather-aware PV forecast + conservative clean base-load learning. NO physical writes.
// Tesla opportunity: 7 A start (~4.83 kW), 6 A continue (~4.14 kW), min 30 min.
// Warm water planning is Europe/Amsterdam day-boundary aware: current-day state never suppresses tomorrow's daily fallback.
const VERSION='EM2_ENERGY_PLAN_24H_V0.4.8',STEP_MS=15*60000,MAX_SLOTS=96;
const EV_OPPORTUNITY_START_MIN_W=4830,EV_OPPORTUNITY_CONTINUE_MIN_W=4140,EV_OPPORTUNITY_MIN_RUN_SLOTS=2;
const PLANNER_INPUT_VAR_ID='39c7c169-34d7-4e14-a27b-520aca255032';
const PLANNER_SNAPSHOT_VAR_ID='b9f1232c-ac01-45fa-9453-ef95d998b138';
const HAUWERT={lat:52.70808,lon:5.10003};
const PV_NOMINAL_W=8000,PV_FALLBACK_SCALE_W_PER_WM2=PV_NOMINAL_W/1000,BASE_HIGH_LOAD_W=1500;
const BOILER_W=1900,WW_DAILY_FALLBACK_MIN=240,WW_DEADLINE_HOUR=19;
const SCENARIO={id:'VICTRON_3X_US5000_SHADOW_V0.1',simulationOnly:true,multiplus:'MultiPlus-II 48/5000/70-50',battery:'3x Pylontech US5000',nominalCapacityKWh:14.4,acChargeLimitW:3300,acDischargeLimitW:3300,minSocPct:20,maxSocPct:90,chargeEfficiency:0.95,dischargeEfficiency:0.95,roundTripEfficiency:0.9025,usableWindowKWh:10.08};
const parse=v=>{try{return JSON.parse(String(v??'null'));}catch{return null;}},bool=v=>v===true||String(v).toLowerCase()==='true',finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v)),num=v=>finite(v)?Number(v):null;
const median=a=>{const x=a.filter(finite).map(Number).sort((p,q)=>p-q);if(!x.length)return null;const m=Math.floor(x.length/2);return x.length%2?x[m]:(x[m-1]+x[m])/2;};
const round=(v,d=0)=>finite(v)?Number(Number(v).toFixed(d)):null;
const inputVar=await Homey.logic.getVariable({id:PLANNER_INPUT_VAR_ID});
const input=parse(inputVar?.value);
if(!input||input.schema!=='EM2_PLANNER_INPUT_V0.1')throw new Error('PLANNER_INPUT_MISSING_OR_INVALID');
const state=input.state??null,ww=input.warmWater??null,priceCtx=input.contractPriceContext??null,dayHist=input.dayHistory??null;

const localParts=d=>Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Amsterdam',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(d).filter(x=>x.type!=='literal').map(x=>[x.type,x.value]));
const localDateKey=d=>{const p=localParts(d);return `${p.year}-${p.month}-${p.day}`;};
const quarterIndex=d=>{const p=localParts(d);return Number(p.hour)*4+Math.floor(Number(p.minute)/15);};
const localOffsetMs=d=>{const p=localParts(d);return Date.UTC(+p.year,+p.month-1,+p.day,+p.hour,+p.minute,+p.second)-d.getTime();};
const localDeadlineMs=dateKey=>{const [y,m,d]=dateKey.split('-').map(Number),guess=Date.UTC(y,m-1,d,WW_DEADLINE_HOUR,0,0);return guess-localOffsetMs(new Date(guess));};

const now=new Date(),nowMs=now.getTime(),slotStart=Math.floor(nowMs/STEP_MS)*STEP_MS,currentDateKey=localDateKey(now);
const contractRaw=String(input.contractType||priceCtx?.contractType||'UNKNOWN').toUpperCase();
const contract=contractRaw==='VAST'?'FIXED':contractRaw;
const allPrices=Array.isArray(input.priceBuffer)?input.priceBuffer.map(Number):[];let contiguous=0;for(const p of allPrices){if(!Number.isFinite(p)||p<=-2||p>=5)break;contiguous++;}
const dynamicPrices=contract==='DYNAMIC'?allPrices.slice(0,Math.min(contiguous,MAX_SLOTS)):[];
const pct=(a,p)=>{if(!a.length)return null;const s=[...a].sort((x,y)=>x-y),i=(s.length-1)*p,lo=Math.floor(i),hi=Math.ceil(i);return lo===hi?s[lo]:s[lo]+(s[hi]-s[lo])*(i-lo);};
const p25=pct(dynamicPrices,.25),p75=pct(dynamicPrices,.75);

const samples=Array.isArray(dayHist?.samples)?dayHist.samples:[],baseBuckets=Array.from({length:96},()=>[]),baseTraceBuckets=Array.from({length:96},()=>[]),cleanBaseAll=[];let usableHistory=0,cleanHistory=0,rejectedHighLoad=0,rejectedKnownAppliance=0;
for(const s of samples){
  if(s?.p1Valid!==true||!finite(s.p1W)||!s.ts)continue;
  const pv=Math.max(0,num(s.solarEdgeW)||0)+Math.max(0,num(s.goodWe4200W)||0)+Math.max(0,num(s.goodWe2000W)||0),tesla=Math.max(0,num(s.teslaW)||0),boiler=Math.max(0,num(s.boilerW)||0),house=Number(s.p1W)+pv,base=Math.max(0,house-tesla-boiler);
  if(!Number.isFinite(base)||base>20000)continue;
  usableHistory++;
  if(s.washerActive===true||s.dryerActive===true){rejectedKnownAppliance++;continue;}
  if(base>=BASE_HIGH_LOAD_W){rejectedHighLoad++;continue;}
  const qi=quarterIndex(new Date(s.ts));baseBuckets[qi].push(base);baseTraceBuckets[qi].push({ts:s.ts,baseW:base,washerActive:false,dryerActive:false});cleanBaseAll.push(base);cleanHistory++;
}
const cleanGlobalBase=median(cleanBaseAll),observedBaseBins=baseBuckets.filter(x=>x.length>=2).length,cleanFallbackUsable=cleanHistory>=3&&finite(cleanGlobalBase)&&cleanGlobalBase<BASE_HIGH_LOAD_W;
const baseQuality=observedBaseBins>=32?'CLEAN_QUARTER_PROFILE':cleanFallbackUsable?'CLEAN_GLOBAL_MEDIAN_FALLBACK':'INSUFFICIENT_CLEAN_BASE_HISTORY';

let weatherMap=new Map(),weatherStatus='UNAVAILABLE',weatherGeneratedAt=null,calibrationScale=null,calibrationPoints=0;
try{
  const url=`https://api.open-meteo.com/v1/forecast?latitude=${HAUWERT.lat}&longitude=${HAUWERT.lon}&minutely_15=shortwave_radiation&past_minutely_15=96&forecast_minutely_15=104&timezone=UTC`;
  const r=await fetch(url,{headers:{'User-Agent':'Homey-EMS-Planner-v0.4.8'}});if(!r.ok)throw new Error(`HTTP ${r.status}`);
  const w=await r.json(),q=w?.minutely_15,times=Array.isArray(q?.time)?q.time:[],rad=Array.isArray(q?.shortwave_radiation)?q.shortwave_radiation:[];
  for(let i=0;i<Math.min(times.length,rad.length);i++){const ms=Date.parse(`${times[i]}Z`),v=Number(rad[i]);if(Number.isFinite(ms)&&Number.isFinite(v))weatherMap.set(Math.floor(ms/STEP_MS),Math.max(0,v));}
  weatherGeneratedAt=new Date().toISOString();if(weatherMap.size<96)throw new Error(`insufficient 15-min weather slots:${weatherMap.size}`);
  const ratios=[];for(const s of samples){if(!s?.ts)continue;const pv=Math.max(0,num(s.solarEdgeW)||0)+Math.max(0,num(s.goodWe4200W)||0)+Math.max(0,num(s.goodWe2000W)||0),ms=Date.parse(s.ts),irr=weatherMap.get(Math.floor(ms/STEP_MS));if(!Number.isFinite(ms)||!finite(irr)||irr<80||pv<50)continue;const ratio=pv/irr;if(Number.isFinite(ratio)&&ratio>0&&ratio<20)ratios.push(ratio);}
  calibrationScale=median(ratios);calibrationPoints=ratios.length;weatherStatus=finite(calibrationScale)&&calibrationPoints>=6?'WEATHER_HAUWERT_CALIBRATED':'WEATHER_HAUWERT_THEORETICAL_SCALE';
}catch(e){weatherStatus=`WEATHER_UNAVAILABLE:${String(e.message||e).slice(0,80)}`;}
const pvScale=finite(calibrationScale)&&calibrationPoints>=6?Number(calibrationScale):PV_FALLBACK_SCALE_W_PER_WM2;

const forecastSlots=[];
for(let i=0;i<MAX_SLOTS;i++){
  const start=new Date(slotStart+i*STEP_MS),end=new Date(slotStart+(i+1)*STEP_MS),qi=quarterIndex(start),price=finite(dynamicPrices[i])?Number(dynamicPrices[i]):null,baseBin=baseBuckets[qi],trace=baseTraceBuckets[qi],useQuarter=baseBin.length>=2,baseW=useQuarter?median(baseBin):(cleanFallbackUsable?cleanGlobalBase:null),baseBasis=useQuarter?'CLEAN_QUARTER_MEDIAN':cleanFallbackUsable?'CLEAN_GLOBAL_MEDIAN':'UNAVAILABLE_INSUFFICIENT_CLEAN_HISTORY',irr=weatherMap.get(Math.floor(start.getTime()/STEP_MS)),pvW=finite(irr)?Math.min(PV_NOMINAL_W,Math.max(0,Number(irr)*pvScale)):null,net=finite(baseW)&&finite(pvW)?Number(baseW)-Number(pvW):null;
  forecastSlots.push({i,start:start.toISOString(),end:end.toISOString(),localDate:localDateKey(start),localQuarter:qi,price_eur_kwh:price,priceClass:contract==='FIXED'?'FIXED':price===null?'UNKNOWN':price<0?'NEGATIVE':price<=p25?'CHEAP':price>=p75?'EXPENSIVE':'NORMAL',baseLoadForecastW:round(baseW),baseForecastTrace:{basis:baseBasis,sampleCount:baseBin.length,sampleValuesW:baseBin.slice(-8).map(x=>round(x)),sampleTimestamps:trace.slice(-8).map(x=>x.ts),likelyContributor:finite(baseW)?'STRUCTURAL_CLEAN_BASE':'INSUFFICIENT_CLEAN_BASE_HISTORY',washerActiveSamples:0,dryerActiveSamples:0,globalCleanSampleCount:cleanHistory,rejectedHighLoadSamples:rejectedHighLoad,rejectedKnownApplianceSamples:rejectedKnownAppliance},pvForecastW:round(pvW),netBeforeFlexW:round(net),importBeforeFlexW:finite(net)?round(Math.max(0,net)):null,pvSurplusBeforeFlexW:finite(net)?round(Math.max(0,-net)):null,gridHeadroomW:null,forecastQuality:{baseLoad:baseBasis,pv:finite(irr)?weatherStatus:'UNAVAILABLE'}});
}
const priceFreshAt=Date.parse(String(priceCtx?.updatedAt||'')),priceFresh=Number.isFinite(priceFreshAt)&&nowMs-priceFreshAt>=0&&nowMs-priceFreshAt<=35*60000,priceQuality=String(priceCtx?.quality||'MISSING');
const priceUsable=contract==='FIXED'||(priceFresh&&priceQuality==='GOOD'&&dynamicPrices.length>=4),horizonQuality='FULL_24H_ENERGY_AXIS';

const deadlineActive=bool(state?.goals?.teslaDeadlineActive),remainingKWh=Math.max(0,num(state?.goals?.teslaRemainingKWh)||0),deadlineAt=state?.goals?.teslaDeadline??null,latestStart=state?.goals?.teslaLatestStart??null;
const wwGoal=ww?.goalReachedToday===true||ww?.goalReached===true,wwRemainingMin=Math.max(0,num(ww?.remainingFallbackMin)??0),wwCatchup=ww?.catchupRequired===true;
const dlMs=Date.parse(String(deadlineAt||'')),before=(s,ms)=>Number.isFinite(ms)?Date.parse(s.start)<ms:true;

const rankGeneric=c=>[...c].sort((a,z)=>{if(contract==='DYNAMIC'&&finite(a.price_eur_kwh)&&finite(z.price_eur_kwh)){const d=a.price_eur_kwh-z.price_eur_kwh;if(Math.abs(d)>1e-9)return d;}const sd=(z.pvSurplusBeforeFlexW||0)-(a.pvSurplusBeforeFlexW||0);return sd||Date.parse(a.start)-Date.parse(z.start);});
const rankTeslaDeadline=c=>[...c].sort((a,z)=>{const ap=(a.pvSurplusBeforeFlexW||0)>=EV_OPPORTUNITY_START_MIN_W,zp=(z.pvSurplusBeforeFlexW||0)>=EV_OPPORTUNITY_START_MIN_W;if(ap!==zp)return ap?-1:1;if(ap&&zp){const d=(z.pvSurplusBeforeFlexW||0)-(a.pvSurplusBeforeFlexW||0);if(d)return d;}if(contract==='DYNAMIC'&&finite(a.price_eur_kwh)&&finite(z.price_eur_kwh)){const d=a.price_eur_kwh-z.price_eur_kwh;if(Math.abs(d)>1e-9)return d;}return Date.parse(a.start)-Date.parse(z.start);});
const buildTeslaOpportunityRuns=c=>{const runs=[];let run=[];const flush=()=>{if(run.length>=EV_OPPORTUNITY_MIN_RUN_SLOTS)runs.push(run);run=[];};for(const s of c){const surplus=Math.max(0,Number(s.pvSurplusBeforeFlexW)||0),adjacent=!run.length||Date.parse(run[run.length-1].end)===Date.parse(s.start);if(!adjacent)flush();if(!run.length){if(surplus>=EV_OPPORTUNITY_START_MIN_W)run=[s];}else if(surplus>=EV_OPPORTUNITY_CONTINUE_MIN_W)run.push(s);else{flush();if(surplus>=EV_OPPORTUNITY_START_MIN_W)run=[s];}}flush();return runs;};
const rankWW=c=>[...c].sort((a,z)=>{const ac=Math.min(BOILER_W,Math.max(0,a.pvSurplusBeforeFlexW||0)),zc=Math.min(BOILER_W,Math.max(0,z.pvSurplusBeforeFlexW||0));if(zc!==ac)return zc-ac;if(contract==='DYNAMIC'){const ap=finite(a.price_eur_kwh)?Number(a.price_eur_kwh):999,zp=finite(z.price_eur_kwh)?Number(z.price_eur_kwh):999;if(ap!==zp)return ap-zp;}return Date.parse(a.start)-Date.parse(z.start);});
const reserveWW=(candidateSlots,needKWh,meta)=>{let remain=needKWh;const chosen=[];for(const s of rankWW(candidateSlots)){if(remain<=1e-6)break;const e=Math.min(BOILER_W/1000*.25,remain),surplus=Math.max(0,s.pvSurplusBeforeFlexW||0),pvCoverageW=Math.min(BOILER_W,surplus),gridRequiredW=Math.max(0,BOILER_W-pvCoverageW);chosen.push({...s,...meta,allocatedKWh:Number(e.toFixed(3)),pvCoverageW:round(pvCoverageW),gridRequiredW:round(gridRequiredW),allocationReason:pvCoverageW>=BOILER_W?'PV_FULL':pvCoverageW>0?'PV_PARTIAL':(contract==='DYNAMIC'?'DEADLINE_REQUIRED_CHEAPEST':'DEADLINE_REQUIRED')});remain-=e;}chosen.sort((a,z)=>Date.parse(a.start)-Date.parse(z.start));return{chosen,unallocatedKWh:Number(Math.max(0,remain).toFixed(3))};};

const teslaCandidates=forecastSlots.filter(s=>before(s,dlMs));
const teslaDeadlineRanked=deadlineActive&&remainingKWh>0?rankTeslaDeadline(teslaCandidates).slice(0,Math.min(12,teslaCandidates.length)):[];
const teslaOpportunityRuns=!deadlineActive?buildTeslaOpportunityRuns(forecastSlots):[],teslaOpportunitySlots=teslaOpportunityRuns.flat();

const horizonDates=[...new Set(forecastSlots.map(s=>s.localDate))];
const wwDailyPlans=[];
for(const dateKey of horizonDates){
  const isCurrentDay=dateKey===currentDateKey;
  const goalReached=isCurrentDay?wwGoal:false;
  const remainingMin=isCurrentDay?(goalReached?0:wwRemainingMin):WW_DAILY_FALLBACK_MIN;
  const catchupRequired=isCurrentDay?wwCatchup:false;
  const deadlineMs=localDeadlineMs(dateKey);
  const needKWh=Number((remainingMin/60*BOILER_W/1000).toFixed(3));
  const candidates=forecastSlots.filter(s=>s.localDate===dateKey&&Date.parse(s.start)<deadlineMs);
  const alloc=!goalReached&&remainingMin>0?reserveWW(candidates,needKWh,{planningDate:dateKey,dayRelation:isCurrentDay?'CURRENT_DAY':'FUTURE_DAY',catchupRequired}):{chosen:[],unallocatedKWh:0};
  wwDailyPlans.push({date:dateKey,dayRelation:isCurrentDay?'CURRENT_DAY':'FUTURE_DAY',goalReached,remainingFallbackMin:remainingMin,derivedEnergyKWh:needKWh,catchupRequired,deadlineLocal:'19:00',deadlineAt:new Date(deadlineMs).toISOString(),allocatedSlots:alloc.chosen,unallocatedKWh:alloc.unallocatedKWh});
}
const wwChosen=wwDailyPlans.flatMap(x=>x.allocatedSlots);

const priceKnown=forecastSlots.filter(s=>finite(s.price_eur_kwh)),chargeSlots=rankGeneric(priceKnown.length?priceKnown:forecastSlots).slice(0,8),dischargeSlots=[...priceKnown].sort((a,z)=>z.price_eur_kwh-a.price_eur_kwh).slice(0,8),pairs=[];
if(contract==='DYNAMIC')for(let i=0;i<Math.min(chargeSlots.length,dischargeSlots.length);i++){const c=chargeSlots[i],d=dischargeSlots[i];if(c.i>=d.i||!finite(c.price_eur_kwh)||!finite(d.price_eur_kwh))continue;const value=d.price_eur_kwh*SCENARIO.roundTripEfficiency-c.price_eur_kwh;if(value>0)pairs.push({chargeStart:c.start,dischargeStart:d.start,chargePrice:c.price_eur_kwh,dischargePrice:d.price_eur_kwh,netValuePerGridKWh:Number(value.toFixed(4))});}

const actions=forecastSlots.map(s=>({...s,battery:'HOLD',tesla:'HOLD',warmWater:'HOLD'})),byStart=Object.fromEntries(actions.map(a=>[a.start,a]));
for(const x of teslaDeadlineRanked)if(byStart[x.start])byStart[x.start].tesla='PREFERRED_BEFORE_DEADLINE';
for(const x of teslaOpportunitySlots)if(byStart[x.start])byStart[x.start].tesla='OPPORTUNITY_PV_MIN_RUN';
for(const x of wwChosen)if(byStart[x.start]){byStart[x.start].warmWater=x.catchupRequired?'MUST_CATCHUP':(x.pvCoverageW>0?'PV_PREFERRED':'DEADLINE_REQUIRED');byStart[x.start].warmWaterReason=x.allocationReason;byStart[x.start].warmWaterPvCoverageW=x.pvCoverageW;byStart[x.start].warmWaterGridRequiredW=x.gridRequiredW;byStart[x.start].warmWaterPlanningDate=x.planningDate;byStart[x.start].warmWaterDayRelation=x.dayRelation;}

const balanceReady=forecastSlots.some(x=>finite(x.baseLoadForecastW)&&finite(x.pvForecastW)),teslaAllocationPolicy=deadlineActive&&remainingKWh>0?'PV_SURPLUS_THEN_CHEAPEST_REQUIRED_GRID_SLOTS':'PV_START_4830W_CONTINUE_4140W_MIN_30MIN_NO_PRICE_TRIGGER';
const wwAllocationPolicy=contract==='DYNAMIC'?'DAY_BOUNDARY_AWARE_MAXIMIZE_PV_COVERAGE_THEN_PRICE_TIEBREAK_BEFORE_19':'DAY_BOUNDARY_AWARE_MAXIMIZE_PV_COVERAGE_THEN_TIME_BEFORE_19';
const currentWWPlan=wwDailyPlans.find(x=>x.date===currentDateKey)||null;
const futureWWPlans=wwDailyPlans.filter(x=>x.date!==currentDateKey);

const plan={schema:VERSION,generatedAt:now.toISOString(),controlMode:'SHADOW',readOnly:true,physicalWritePerformed:false,purpose:'24H_ENERGY_BALANCE_AND_COST_PLANNING',scenario:SCENARIO,inputs:{sourceRevision:Number(state?.revision)||null,contract,price:{quality:priceQuality,fresh:priceFresh,usable:priceUsable,dynamicSlots:dynamicPrices.length},history:{schema:dayHist?.schema_version||null,source:dayHist?.source||null,samples:samples.length,usableSamples:usableHistory,cleanBaseSamples:cleanHistory,rejectedHighLoadSamples:rejectedHighLoad,rejectedKnownApplianceSamples:rejectedKnownAppliance,observedBaseQuarterBins:observedBaseBins,measurementControlIndependent:dayHist?.measurement_control_independent===true},forecastQuality:{baseLoad:baseQuality,pv:weatherStatus,pvNote:`PV forecast uses Hauwert weather shortwave radiation; scale=${round(pvScale,3)} W per W/m2, calibrationPoints=${calibrationPoints}. No day-persistence PV forecast.`,baseLoadNote:`Known Tesla/boiler are subtracted. Washer/dryer-active and residual >= ${BASE_HIGH_LOAD_W} W samples are excluded from base learning. Global fallback is unavailable until >=3 clean samples exist.`,pvSource:{provider:'Open-Meteo',location:'Hauwert',latitude:HAUWERT.lat,longitude:HAUWERT.lon,variable:'shortwave_radiation',resolutionMinutes:15,retrievedAt:weatherGeneratedAt},gridHeadroom:'NOT_MODELED_PHASE_AWARE'},tesla:{deadlineActive,remainingKWh,deadlineAt,latestStart,throughputModel:'NOT_ASSUMED',opportunityPolicy:'PV_SURPLUS_START_CONTINUE_MIN_RUN',opportunityStartMinW:EV_OPPORTUNITY_START_MIN_W,opportunityContinueMinW:EV_OPPORTUNITY_CONTINUE_MIN_W,opportunityMinRunSlots:EV_OPPORTUNITY_MIN_RUN_SLOTS,opportunityMinRunMinutes:EV_OPPORTUNITY_MIN_RUN_SLOTS*15,pricePolicy:'DEADLINE_OPTIMIZATION_ONLY'},warmWater:{goalReachedToday:wwGoal,remainingFallbackMin:wwRemainingMin,catchupRequired:wwCatchup,modeledPowerW:BOILER_W,derivedEnergyKWh:Number((wwRemainingMin/60*BOILER_W/1000).toFixed(3)),deadlineLocal:'19:00',dayBoundaryAware:true,timeZone:'Europe/Amsterdam',futureDayFallbackMin:WW_DAILY_FALLBACK_MIN,horizonDates}},plan:{slotMinutes:15,horizonQuality,slotsAvailable:MAX_SLOTS,actions,energyBalance:{baseLoadGlobalMedianW:round(cleanGlobalBase),baseLoadFallbackUsable:cleanFallbackUsable,balanceReady,slotsWithPvForecast:forecastSlots.filter(x=>finite(x.pvForecastW)).length,slotsWithBaseForecast:forecastSlots.filter(x=>finite(x.baseLoadForecastW)).length,slotsWithNetForecast:forecastSlots.filter(x=>finite(x.netBeforeFlexW)).length,note:'netBeforeFlexW = clean uncontrollable base-load - weather-aware Hauwert PV forecast. Missing clean base history stays null instead of inventing a high global fallback.'},tesla:{preferredSlots:deadlineActive?teslaDeadlineRanked:teslaOpportunitySlots,deadlinePreferredSlots:teslaDeadlineRanked,pvOpportunitySlots:teslaOpportunitySlots,pvOpportunityRuns:teslaOpportunityRuns.map(r=>({start:r[0].start,end:r[r.length-1].end,slots:r.length,minSurplusW:Math.min(...r.map(x=>x.pvSurplusBeforeFlexW||0)),maxSurplusW:Math.max(...r.map(x=>x.pvSurplusBeforeFlexW||0))})),obligationKWh:deadlineActive?remainingKWh:0,deadlineAt,allocationPolicy:teslaAllocationPolicy},warmWater:{allocatedSlots:wwChosen,unallocatedKWh:Number(wwDailyPlans.reduce((n,x)=>n+x.unallocatedKWh,0).toFixed(3)),allocationPolicy:wwAllocationPolicy,currentDay:currentWWPlan,futureDays:futureWWPlans,dailyPlans:wwDailyPlans},battery:{mode:'THEORETICAL_ONLY_NO_SOC',economicPairs:pairs.slice(0,12),note:'No physical battery dispatch until actual SOC and commissioning constraints are integrated.'}},plannerStatus:!state?'BLOCKED_STATE_MISSING':baseQuality==='INSUFFICIENT_CLEAN_BASE_HISTORY'?'DEGRADED_BASE_LOAD_HISTORY':contract==='DYNAMIC'&&!priceUsable?'DEGRADED_PRICE_CONTEXT':!balanceReady?'DEGRADED_PV_WEATHER_FORECAST':'READY_SHADOW_V0.4.7',nextPhase:'VALIDATE_DAY_BOUNDARY_WW_AND_LEARN_CLEAN_QUARTER_PROFILE',safety:{noDeviceWrites:true,noVictronWrites:true,noEaseeWrites:true,noBoilerWrites:true,existingWritersUnchanged:true,p1ControlPolicyUnchanged:true,simulationOnly:true}};
const wwObligation=wwDailyPlans.some(x=>!x.goalReached&&x.remainingFallbackMin>0);
const status={status:plan.plannerStatus,at:plan.generatedAt,version:VERSION,contract,slots:MAX_SLOTS,baseQuality,pvQuality:weatherStatus,pvSource:'OPEN_METEO_HAUWERT',pvCalibrationPoints:calibrationPoints,pvScaleWPerWm2:round(pvScale,3),usableHistory,cleanHistory,rejectedHighLoad,rejectedKnownAppliance,observedBaseBins,slotsWithNetForecast:plan.plan.energyBalance.slotsWithNetForecast,traceableBaseLoad:true,teslaObligation:deadlineActive&&remainingKWh>0,teslaOpportunitySlots:teslaOpportunitySlots.length,teslaOpportunityRuns:teslaOpportunityRuns.length,teslaAllocationPolicy,wwObligation,wwDayBoundaryAware:true,wwPlanningDates:wwDailyPlans.map(x=>x.date),wwAllocatedSlots:wwChosen.length,wwAllocationPolicy,noActuatorWrites:true};
const snapshot={schema:'EM2_ENERGY_PLANNER_SNAPSHOT_V0.1',generatedAt:plan.generatedAt,sourceRevision:Number(input.sourceRevision??state?.revision)||null,plan,status};
await Homey.logic.updateVariable({id:PLANNER_SNAPSHOT_VAR_ID,variable:{value:JSON.stringify(snapshot)}});
return true;
