(() => {
  const ROOT_ID='planner-shadow';
  const STATE='https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/energy-state-v2.json';
  const PLAN='https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/energy-planner-shadow.json';
  const root=document.getElementById(ROOT_ID); if(!root)return;
  const el=(t,c,x)=>{const n=document.createElement(t);if(c)n.className=c;if(x!==undefined)n.textContent=x;return n;};
  const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
  const fmtW=v=>finite(v)?`${Number(v).toLocaleString('nl-NL',{maximumFractionDigits:0})} W`:'—';
  const fmtA=v=>finite(v)?`${Number(v).toLocaleString('nl-NL',{maximumFractionDigits:1})} A`:'—';
  const time=iso=>{const d=new Date(iso);return Number.isNaN(d.getTime())?'—':d.toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'});};
  const fetchJson=async url=>{const r=await fetch(`${url}?evidence=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw new Error(`${r.status}`);return r.json();};
  const unwrapPlan=p=>p?.plan?.plan?.actions?p.plan:(p?.plan||p||{});
  const revOf=x=>{const v=x?.sourceRevision??x?.source_revision??x?.revision??x?.state_revision??x?.meta?.state_revision;return finite(v)?Number(v):null;};
  const currentAction=payload=>{const p=unwrapPlan(payload),actions=Array.isArray(p?.plan?.actions)?p.plan.actions:[],now=Date.now();return actions.find(a=>{const s=Date.parse(a?.start||'');const e=Date.parse(a?.end||'');return Number.isFinite(s)&&s<=now&&now<(Number.isFinite(e)?e:s+900000);})||actions.find(a=>Date.parse(a?.start||'')>=now)||actions[0]||null;};
  const evidenceOf=state=>state?.control_evidence||state?.controlEvidence||null;
  const planText=(asset,a)=>{if(!a)return '—';if(asset==='ev'){const action=String(a.tesla||'HOLD');const target=a.teslaTargetW??a.evTargetW;return `${action}${finite(target)?` · ${fmtW(target)}`:''}`;}const action=String(a.warmWater||'HOLD');const target=a.warmWaterTargetW??a.wwTargetW;return `${action}${finite(target)?` · ${fmtW(target)}`:''}`;};
  const intentText=(asset,e)=>{const i=e?.power_intent??e?.powerIntent;if(!i)return 'Niet gepubliceerd';const invalid=i.valid===false?'INVALID · ':'';if(asset==='ev')return `${invalid}${fmtW(i?.targets?.ev?.target_W)}`;const ww=i?.targets?.ww;if(!ww)return 'Niet gepubliceerd';if(finite(ww.target_W))return `${invalid}${fmtW(ww.target_W)}`;return `${invalid}${ww.target_on===true?'ON':ww.target_on===false?'OFF':'HOLD'}`;};
  const adapterText=(asset,e)=>{const a=asset==='ev'?e?.adapter?.ev:e?.adapter?.warm_water??e?.adapter?.warmWater;if(!a)return 'Niet gepubliceerd';if(asset==='ev'){const parts=[];if(finite(a?.command?.requested_A))parts.push(fmtA(a.command.requested_A));if(finite(a?.electrical?.executable_W))parts.push(fmtW(a.electrical.executable_W));if(a?.status)parts.push(String(a.status));return parts.join(' · ')||'—';}const value=a?.command?.value;return `${value===true?'ON':value===false?'OFF':'HOLD'}${a?.status?` · ${a.status}`:''}`;};
  const physicalText=(asset,state,e)=>{const a=asset==='ev'?e?.adapter?.ev:e?.adapter?.warm_water??e?.adapter?.warmWater;const writes=a?.deviceWrites??a?.device_writes;if(writes===false)return 'NONE · SHADOW';if(writes===true)return 'LIVE write toegestaan';return `Niet in evidencecontract · actueel ${asset==='ev'?(state?.tesla?.charging?'laden':'niet laden'):(state?.hot_water?.boiler_on?'boiler AAN':'boiler UIT')}`;};
  const row=(asset,label,a,state,e)=>{const r=el('div','ps-evidence-row');r.append(el('div','ps-evidence-asset',label));[['PLAN',planText(asset,a)],['POWER INTENT',intentText(asset,e)],['ADAPTER',adapterText(asset,e)],['PHYSICAL',physicalText(asset,state,e)]].forEach(([k,v])=>{const c=el('div','ps-evidence-cell');c.append(el('span','ps-evidence-key',k),el('strong','ps-evidence-value',v));r.append(c);});return r;};
  const addStyles=()=>{if(document.getElementById('ps-control-evidence-style'))return;const s=document.createElement('style');s.id='ps-control-evidence-style';s.textContent='.ps-control-evidence{margin-top:1.25rem}.ps-evidence-note{margin:.25rem 0 .75rem;color:var(--md-default-fg-color--light);font-size:.84rem}.ps-evidence-grid{display:grid;gap:.55rem}.ps-evidence-row{display:grid;grid-template-columns:minmax(5rem,.7fr) repeat(4,minmax(7rem,1fr));gap:.5rem;align-items:stretch}.ps-evidence-asset,.ps-evidence-cell{border:1px solid var(--md-default-fg-color--lightest);border-radius:.45rem;padding:.55rem .65rem;min-width:0}.ps-evidence-asset{font-weight:700;display:flex;align-items:center}.ps-evidence-key{display:block;font-size:.68rem;letter-spacing:.04em;color:var(--md-default-fg-color--light);margin-bottom:.15rem}.ps-evidence-value{font-size:.82rem;overflow-wrap:anywhere}.ps-evidence-rev{margin-top:.6rem;font-size:.76rem;color:var(--md-default-fg-color--light)}@media(max-width:760px){.ps-evidence-row{grid-template-columns:1fr 1fr}.ps-evidence-asset{grid-column:1/-1}.ps-evidence-cell{min-height:4rem}}';document.head.append(s);};
  async function render(){
    if(root.querySelector('.ps-control-evidence'))return;
    addStyles();
    const section=el('section','ps-section ps-control-evidence');section.append(el('h2','', 'Plan → Power Intent → adapter'));
    const note=el('div','ps-evidence-note','End-to-end bewijs voor het actuele kwartier. Power Intent en adapterwaarden worden uitsluitend uit gepubliceerde runtimecontracten gelezen en nooit door de frontend gereconstrueerd.');section.append(note);
    try{
      const [plan,state]=await Promise.all([fetchJson(PLAN),fetchJson(STATE)]),a=currentAction(plan),e=evidenceOf(state),grid=el('div','ps-evidence-grid');
      grid.append(row('ev','Tesla',a,state,e),row('ww','Boiler',a,state,e));section.append(grid);
      const planRevRaw=unwrapPlan(plan)?.inputs?.sourceRevision??plan?.sourceRevision,planRev=finite(planRevRaw)?Number(planRevRaw):null,stateRev=revOf(state),intentRev=revOf(e?.power_intent??e?.powerIntent),evRev=revOf(e?.adapter?.ev),wwRev=revOf(e?.adapter?.warm_water??e?.adapter?.warmWater),parts=[`slot ${a?`${time(a.start)}–${time(a.end)}`:'—'}`,`plan rev ${planRev??'—'}`,`state rev ${stateRev??'—'}`,`intent rev ${intentRev??'—'}`,`EV adapter rev ${evRev??'—'}`,`WW adapter rev ${wwRev??'—'}`];
      const complete=[planRev,stateRev,intentRev,evRev,wwRev].every(v=>v!==null),aligned=complete&&[stateRev,intentRev,evRev,wwRev].every(v=>v===stateRev);parts.push(!complete?'evidence: INCOMPLETE':aligned?'evidence: REVISION ALIGNED':'evidence: REVISION MISMATCH');section.append(el('div','ps-evidence-rev',parts.join(' · ')));
    }catch(err){section.append(el('div','ps-empty',`Control evidence niet bereikbaar (${err.message}).`));}
    const anchor=[...root.querySelectorAll('.ps-section')].find(x=>/Prijs & planneracties/i.test(x.querySelector('h2')?.textContent||''));if(anchor)anchor.insertAdjacentElement('afterend',section);else root.append(section);
  }
  render();
})();
