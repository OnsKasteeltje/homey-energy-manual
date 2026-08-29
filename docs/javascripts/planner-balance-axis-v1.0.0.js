(() => {
  const root=document.getElementById('planner-shadow');
  if(!root)return;

  const fmtKw=w=>{
    const kw=Number(w)/1000;
    return `${kw.toLocaleString('nl-NL',{minimumFractionDigits:Number.isInteger(kw)?0:1,maximumFractionDigits:1})} kW`;
  };

  function parseWatts(chart){
    const vals=[];
    chart.querySelectorAll('.ps-bar[title]').forEach(bar=>{
      const m=bar.title.match(/(-?[\d.,]+)\s*W\b/);
      if(!m)return;
      const normalized=m[1].replace(/\./g,'').replace(',','.');
      const n=Number(normalized);
      if(Number.isFinite(n))vals.push(Math.abs(n));
    });
    return vals;
  }

  function decorate(chart){
    if(!chart||chart.dataset.axisReady==='1')return;
    const vals=parseWatts(chart);
    const max=Math.max(1000,...vals);
    const axis=document.createElement('div');
    axis.className='ps-balance-axis';
    [max,max/2,0,-max/2,-max].forEach((v,i)=>{
      const lab=document.createElement('span');
      lab.className=`ps-balance-axis-label ps-balance-axis-label-${i}`;
      lab.textContent=fmtKw(v);
      axis.append(lab);
    });
    const wrap=document.createElement('div');
    wrap.className='ps-balance-axis-wrap';
    chart.parentNode.insertBefore(wrap,chart);
    wrap.append(axis,chart);
    chart.dataset.axisReady='1';

    const section=wrap.closest('.ps-section');
    const note=section?.querySelector('.ps-chart-note');
    if(note&&!note.dataset.axisNote){
      note.textContent='Verwachting vóór flexibele lasten. Y-as = vermogen in kW. De middenlijn is 0 kW: blauw boven nul = netimport, groen onder nul = PV-overschot/export. Hover op base load voor de historische load-opbouw.';
      note.dataset.axisNote='1';
    }
  }

  function scan(){root.querySelectorAll('.ps-balance-chart').forEach(decorate);}
  scan();
  const observer=new MutationObserver(scan);
  observer.observe(root,{childList:true,subtree:true});
})();
