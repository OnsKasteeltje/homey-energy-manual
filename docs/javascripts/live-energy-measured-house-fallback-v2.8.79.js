(function(){
  'use strict';
  // UI-only normalization: when Energy Core fail-closes house_load_w because of SOURCE_SKEW,
  // retain the physically measured P1/PV house candidate for display and residual allocation.
  function apply(state){
    const raw=state?.raw||state;
    if(!raw) return;
    raw.energy_budget=raw.energy_budget||{};
    const current=Number(raw.energy_budget.house_load_w);
    if(raw.energy_budget.house_load_w!==null && raw.energy_budget.house_load_w!==undefined && Number.isFinite(current)) return;
    const candidate=Number(raw.balance?.physical_house_candidate_w);
    if(Number.isFinite(candidate) && candidate>=0){
      raw.energy_budget.house_load_w=candidate;
      raw.energy_budget.house_load_ui_source='BALANCE_PHYSICAL_HOUSE_CANDIDATE';
    }
  }
  document.addEventListener('energycorev2state',e=>apply(e.detail));
  document.addEventListener('DOMContentLoaded',()=>setTimeout(()=>apply(window.EnergyCoreV2?.state),250));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(()=>apply(window.EnergyCoreV2?.state),80));
})();
