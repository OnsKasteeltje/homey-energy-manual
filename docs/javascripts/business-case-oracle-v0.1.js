import { BC_STRATEGIES, replayBusinessCase } from "./business-case-engine-v2.js";

export const BC_ORACLE_SCHEMA = "EMS_BC_PERFECT_INFORMATION_ORACLE_V0.1";
const finite=v=>typeof v==="number"&&Number.isFinite(v);
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));

/**
 * Dynamic-programming perfect-information optimizer.
 * It sees the entire supplied horizon, unlike the EMS. The optimizer uses the
 * same battery constraints as the replay kernel and returns EMS_REPLAY targets
 * that are replayed by the canonical kernel for final accounting.
 *
 * Initial SOC is real starting energy, not free charging opportunity; tests
 * that specifically validate cheap-to-expensive shifting therefore start empty.
 * Energy state is discretized; this remains an auditable numerical upper
 * benchmark, not a claim of continuous mathematical exactness.
 */
export function optimizePerfectInformation({samples,scenario,energyStepKWh=0.1,terminalEnergyValueEuroPerKWh=null}){
  if(!Array.isArray(samples)||!samples.length)throw new Error("ORACLE_SAMPLES_REQUIRED");
  if(!finite(energyStepKWh)||energyStepKWh<=0)throw new Error("INVALID_ORACLE_ENERGY_STEP");
  const minE=scenario.capacityKWh*scenario.minSocPct/100,maxE=scenario.capacityKWh*scenario.maxSocPct/100;
  const states=[];for(let e=minE;e<=maxE+1e-9;e+=energyStepKWh)states.push(Math.min(maxE,e));
  if(states[states.length-1]<maxE-1e-6)states.push(maxE);
  const initialE=scenario.capacityKWh*scenario.initialSocPct/100;
  const nearest=e=>states.reduce((best,x)=>Math.abs(x-e)<Math.abs(best-e)?x:best,states[0]);
  const key=e=>String(states.indexOf(nearest(e)));
  const usable=samples.map((x,i)=>{
    const h=(finite(x.intervalMinutes)&&x.intervalMinutes>0?x.intervalMinutes:5)/60;
    const gridW=finite(x.gridW)?x.gridW:finite(x.p1W)?x.p1W:NaN;
    if(!finite(gridW)||x.measurementValid===false||x.p1Valid===false||!finite(x.importPriceEuroPerKWh)||!finite(x.exportPriceEuroPerKWh))throw new Error(`ORACLE_INVALID_SAMPLE_${i}`);
    return {...x,h,gridW};
  });
  const defaultTerminal=usable[usable.length-1].importPriceEuroPerKWh*scenario.dischargeEfficiency;
  const terminalValue=finite(terminalEnergyValueEuroPerKWh)?terminalEnergyValueEuroPerKWh:defaultTerminal;
  let future=new Map(states.map(e=>[key(e),-(e-minE)*terminalValue]));
  const policy=new Array(usable.length);
  for(let i=usable.length-1;i>=0;i--){
    const s=usable[i],next=new Map(),decisions=new Map();
    const maxChargeDc=scenario.maxChargeKW*s.h*scenario.chargeEfficiency;
    const maxDischargeDc=scenario.maxDischargeKW*s.h/scenario.dischargeEfficiency;
    for(const e of states){
      let best=Infinity,bestTarget=0;
      const low=Math.max(minE,e-maxDischargeDc),high=Math.min(maxE,e+maxChargeDc);
      for(const e2 of states){
        if(e2<low-1e-9||e2>high+1e-9)continue;
        let batteryAcKWh=0,throughputDc=0;
        if(e2>e){throughputDc=e2-e;batteryAcKWh=(e2-e)/scenario.chargeEfficiency;}
        else if(e2<e){throughputDc=e-e2;batteryAcKWh=-(e-e2)*scenario.dischargeEfficiency;}
        const gridKWh=s.gridW/1000*s.h+batteryAcKWh+scenario.standbyW/1000*s.h;
        const energyCost=gridKWh>=0?gridKWh*s.importPriceEuroPerKWh:gridKWh*s.exportPriceEuroPerKWh;
        const deg=throughputDc*scenario.degradationEuroPerThroughputKWh;
        const total=energyCost+deg+(future.get(key(e2))??Infinity);
        if(total<best){best=total;bestTarget=batteryAcKWh/s.h*1000;}
      }
      next.set(key(e),best);decisions.set(key(e),bestTarget);
    }
    policy[i]=decisions;future=next;
  }
  let e=nearest(initialE);const targets=[];
  for(let i=0;i<usable.length;i++){
    const target=policy[i].get(key(e))??0;targets.push(target);
    const h=usable[i].h;
    if(target>0)e=clamp(e+target/1000*h*scenario.chargeEfficiency,minE,maxE);
    else if(target<0)e=clamp(e-(-target/1000*h)/scenario.dischargeEfficiency,minE,maxE);
    e=nearest(e);
  }
  const replaySamples=samples.map((s,i)=>({...s,emsBatteryTargetW:targets[i]}));
  const replay=replayBusinessCase({samples:replaySamples,scenario,strategy:BC_STRATEGIES.EMS_REPLAY});
  return {schema:BC_ORACLE_SCHEMA,perfectInformation:true,readOnly:true,controlImpact:false,energyStepKWh,terminalEnergyValueEuroPerKWh:terminalValue,replay,targetsW:targets};
}
