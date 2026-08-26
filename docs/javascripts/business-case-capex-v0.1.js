export const BC_CAPEX_SCHEMA="EMS_BC_CAPEX_V0.1";
const finite=v=>typeof v==="number"&&Number.isFinite(v);

/**
 * Applies evidence-based CAPEX without fabricating missing BOS/install costs.
 * financialReady only becomes true when a completeCapexEuro is explicit.
 */
export function resolveScenarioCapex({capexEvidence,scenarioId}){
  const row=capexEvidence?.scenarios?.[scenarioId];
  if(!row)return {schema:BC_CAPEX_SCHEMA,scenarioId,knownIncrementalHardwareEuro:null,completeCapexEuro:null,financialReady:false,completeness:"UNKNOWN_SCENARIO"};
  const complete=finite(row.completeCapexEuro)?row.completeCapexEuro:null;
  return {schema:BC_CAPEX_SCHEMA,scenarioId,knownIncrementalHardwareEuro:finite(row.knownIncrementalHardwareEuro)?row.knownIncrementalHardwareEuro:null,completeCapexEuro:complete,financialReady:complete!=null,completeness:String(row.completeness||"UNKNOWN")};
}

export function applyCompleteCapex(scenario,resolved){
  if(!scenario||!resolved)throw new Error("CAPEX_SCENARIO_REQUIRED");
  return {...scenario,capexEuro:resolved.financialReady?resolved.completeCapexEuro:null,capexStatus:resolved.completeness,knownIncrementalHardwareEuro:resolved.knownIncrementalHardwareEuro};
}
