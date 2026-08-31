export const CONTROL_EVIDENCE_SCHEMA='EM2_CONTROL_EVIDENCE_V0.1';

const n=v=>Number.isFinite(Number(v))?Number(v):null;

export function buildControlEvidence({powerIntent,evAdapter,wwAdapter}){
  const intentRev=n(powerIntent?.sourceRevision);
  const evRev=n(evAdapter?.sourceRevision);
  const wwRev=n(wwAdapter?.sourceRevision);
  const revisions=[intentRev,evRev,wwRev].filter(v=>v!==null);
  const revisionAligned=revisions.length===3&&revisions.every(v=>v===revisions[0]);
  return {
    schema:CONTROL_EVIDENCE_SCHEMA,
    generatedAt:new Date().toISOString(),
    readOnly:true,
    observabilityOnly:true,
    controlImpact:'NONE',
    power_intent:powerIntent??null,
    adapter:{ev:evAdapter??null,warm_water:wwAdapter??null},
    revisions:{powerIntent:intentRev,evAdapter:evRev,wwAdapter:wwRev,aligned:revisionAligned},
    complete:!!powerIntent&&!!evAdapter&&!!wwAdapter,
    safety:{deviceWritesIntroduced:false,derivedValues:false,rawRuntimeContracts:true}
  };
}
