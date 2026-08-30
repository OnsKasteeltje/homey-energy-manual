(() => {
  const root=document.getElementById('planner-shadow');
  if(!root)return;
  const section=[...root.querySelectorAll('.ps-section')].find(s=>s.querySelector('h2')?.textContent?.trim()==='Prijs & planneracties');
  if(!section)return;
  const rename=(from,to)=>{
    const row=[...section.querySelectorAll('.ps-action-row')].find(r=>r.querySelector('.ps-action-name')?.textContent?.trim()===from);
    const name=row?.querySelector('.ps-action-name');
    if(name)name.textContent=to;
    if(row)row.classList.add('ps-forecast-row');
  };
  rename('Tesla','Tesla plan');
  rename('Boiler','Boiler plan');
  rename('Accu','Accu plan');
  if(!document.getElementById('ps-forecast-label-style')){
    const style=document.createElement('style');
    style.id='ps-forecast-label-style';
    style.textContent=`
      #planner-shadow .ps-forecast-row .ps-action-name::after{content:' forecast';display:block;font-size:.58em;font-weight:500;opacity:.65;line-height:1.05}
      #planner-shadow .ps-forecast-row .ps-action-segment{outline:1px dashed color-mix(in srgb,currentColor 45%,transparent);outline-offset:-2px}
    `;
    document.head.append(style);
  }
})();
