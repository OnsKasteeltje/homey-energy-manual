export const BC_VICTRON_CALIBRATION_SCHEMA="EMS_BC_VICTRON_CALIBRATION_V0.1";
const finite=v=>typeof v==="number"&&Number.isFinite(v);
const r=(v,n=5)=>Number(Number(v).toFixed(n));

/**
 * Analyze future Victron telemetry. Sign convention: batteryAcW +charge/-discharge,
 * batteryDcW +into battery/-out of battery. This module never reads or writes devices.
 */
export function calibrateVictronTelemetry({samples,usableCapacityKWh,minCoverage=0.95,minThroughputKWh=5,socClosurePct=3}={}){
  if(!Array.isArray(samples))throw new Error("VICTRON_CALIBRATION_SAMPLES_REQUIRED");
  if(!finite(usableCapacityKWh)||usableCapacityKWh<=0)throw new Error("INVALID_USABLE_CAPACITY");
  let valid=0,chargeAc=0,dischargeAc=0,chargeDc=0,dischargeDc=0,standbyWh=0,standbyHours=0;
  let firstSoc=null,lastSoc=null;
  for(let i=0;i<samples.length;i++){
    const x=samples[i]||{},next=samples[i+1];
    const t=Date.parse(String(x.ts||"")),tn=Date.parse(String(next?.ts||""));
    const h=Number.isFinite(t)&&Number.isFinite(tn)&&tn>t?(tn-t)/3600000:(finite(x.intervalMinutes)&&x.intervalMinutes>0?x.intervalMinutes/60:null);
    if(!finite(h)||h<=0||x.valid===false||!finite(x.batteryAcW)){continue;}
    valid++;
    if(finite(x.socPct)){if(firstSoc==null)firstSoc=x.socPct;lastSoc=x.socPct;}
    const ac=x.batteryAcW/1000*h;
    if(ac>0)chargeAc+=ac;else dischargeAc+=-ac;
    if(finite(x.batteryDcW)){
      const dc=x.batteryDcW/1000*h;
      if(dc>0)chargeDc+=dc;else dischargeDc+=-dc;
    }
    if(Math.abs(x.batteryAcW)<=50&&finite(x.systemLossW)&&x.systemLossW>=0){standbyWh+=x.systemLossW*h;standbyHours+=h;}
  }
  const coverage=samples.length?valid/samples.length:0;
  const throughput=(chargeDc+dischargeDc)>0?(chargeDc+dischargeDc)/2:(chargeAc+dischargeAc)/2;
  const chargeEfficiency=chargeAc>0&&chargeDc>0?chargeDc/chargeAc:null;
  const dischargeEfficiency=dischargeDc>0&&dischargeAc>0?dischargeAc/dischargeDc:null;
  const socClosure=finite(firstSoc)&&finite(lastSoc)?Math.abs(lastSoc-firstSoc):null;
  const roundTripEfficiency=chargeAc>0&&dischargeAc>0&&socClosure!=null&&socClosure<=socClosurePct?dischargeAc/chargeAc:null;
  const standbyW=standbyHours>0?standbyWh/standbyHours:null;
  const reasons=[];
  if(coverage<minCoverage)reasons.push("LOW_COVERAGE");
  if(throughput<minThroughputKWh)reasons.push("INSUFFICIENT_THROUGHPUT");
  if(chargeEfficiency==null||dischargeEfficiency==null)reasons.push("MISSING_DC_POWER_FOR_EFFICIENCY");
  if(roundTripEfficiency==null)reasons.push("SOC_NOT_CLOSED_FOR_ROUNDTRIP");
  const quality=reasons.length===0?"GOOD":coverage>=0.8?"PROVISIONAL":"LOW";
  return {schema:BC_VICTRON_CALIBRATION_SCHEMA,readOnly:true,controlImpact:false,evidence:{totalSamples:samples.length,validSamples:valid,coverage:r(coverage,4),quality,reasons},metrics:{chargeAcKWh:r(chargeAc),dischargeAcKWh:r(dischargeAc),chargeDcKWh:r(chargeDc),dischargeDcKWh:r(dischargeDc),throughputKWh:r(throughput),equivalentFullCycles:r(throughput/usableCapacityKWh,4),chargeEfficiency:chargeEfficiency==null?null:r(chargeEfficiency,4),dischargeEfficiency:dischargeEfficiency==null?null:r(dischargeEfficiency,4),roundTripEfficiency:roundTripEfficiency==null?null:r(roundTripEfficiency,4),standbyW:standbyW==null?null:r(standbyW,2),socClosurePct:socClosure==null?null:r(socClosure,2)}};
}

export function calibrationCandidateForScenario({scenario,calibration}){
  const good=calibration?.evidence?.quality==="GOOD";
  const m=calibration?.metrics||{};
  return {schema:BC_VICTRON_CALIBRATION_SCHEMA,scenarioId:scenario?.id??null,promotable:good&&finite(m.chargeEfficiency)&&finite(m.dischargeEfficiency),candidate:good?{chargeEfficiency:m.chargeEfficiency,dischargeEfficiency:m.dischargeEfficiency,standbyW:finite(m.standbyW)?m.standbyW:scenario?.standbyW}:null,provenance:{calibrationQuality:calibration?.evidence?.quality??"UNKNOWN",throughputKWh:m.throughputKWh??null,coverage:calibration?.evidence?.coverage??null},note:"Candidate only; promotion to scenario assumptions remains an explicit reviewed change."};
}
