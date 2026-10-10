const $ = id => document.getElementById(id);
const number = value => Number(value || 0);
const fmtW = value => number(value).toLocaleString("nl-NL") + " W";
const localTime = value => new Date(value).toLocaleTimeString("nl-NL", {
  timeZone:"Europe/Amsterdam", hour:"2-digit", minute:"2-digit"
});
const localDateTime = value => new Date(value).toLocaleString("nl-NL", {
  timeZone:"Europe/Amsterdam", weekday:"short", hour:"2-digit", minute:"2-digit"
});
async function get(url, label) {
  const response = await fetch(url, {cache:"no-store"});
  if (!response.ok) throw new Error(label + " niet beschikbaar");
  return response.json();
}
async function load() {
  const [plan, ev] = await Promise.all([
    get("/web/planner/current", "Dynamisch plan"),
    get("/web/planner/ev-requirement", "EV requirement").catch(() => null)
  ]);
  if (plan.schema !== "EMS_WEB_DYNAMIC_PLAN_V1") throw new Error("Onbekend dynamisch plan");
  return {plan, ev};
}
function renderRequirement(ev) {
  const out = $("ev-summary");
  if (ev && ev.active && ev.status === "TRACKING" && number(ev.remainingKWh) > 0) {
    out.textContent = number(ev.remainingKWh).toLocaleString("nl-NL", {
      maximumFractionDigits:2
    }) + " kWh resterend · max " + (ev.maxA ?? "—") + " A · deadline " +
      (ev.deadlineAt ? localTime(ev.deadlineAt) : "—");
  } else {
    out.textContent = ev ? "Geen actieve deadline · " + (ev.status || "inactief") :
      "EV requirement niet beschikbaar";
  }
}
function render({plan, ev}) {
  $("freshness").textContent = "Plan " + localTime(plan.generatedAt) +
    " · geldig tot " + localTime(plan.validUntil);
  $("plan-mode").textContent = "Warmwaterbron: " + (plan.wwSourceMode || "onbekend") +
    ". Alle lijnen zijn plan/forecast, geen gemeten uitvoering. Verwarming heeft een aparte shadow-keten; realtime P1 blijft leidend.";
  renderRequirement(ev);

  const slots = plan.slots || [];
  const svg = $("pv-chart");
  svg.replaceChildren();
  if (!slots.length) { $("empty").hidden = false; return; }
  $("empty").hidden = true;
  const W = 1100, H = 390, p = {l:55,r:18,t:24,b:48};
  const iw = W-p.l-p.r, ih = H-p.t-p.b;
  const fields = [
    ["pvForecastW","pvline"],["evPlanW","evline"],["wwPlanW","wwline"],["quookerPlanW","quookerline"],
    ["gridExportAfterFlexW","exportline"],["gridImportAfterFlexW","importline"]
  ];
  const rawMax = Math.max(1000, ...slots.flatMap(s=>fields.map(([key])=>number(s[key]))));
  const rough = rawMax/4, pow = 10**Math.floor(Math.log10(rough)), n = rough/pow;
  const tickStep = (n<=1?1:n<=2?2:n<=2.5?2.5:n<=5?5:10)*pow;
  const max = tickStep*4;
  const viewStart = new Date(slots[0].start).getTime();
  const viewEnd = new Date(slots[slots.length-1].start).getTime() + 900000;
  const xFor = ms => p.l + (ms-viewStart)/(viewEnd-viewStart)*iw;
  const yFor = val => p.t + ih - number(val)/max*ih;
  const ns = "http://www.w3.org/2000/svg";
  svg.setAttribute("viewBox", "0 0 " + W + " " + H);
  const add = (tag, attrs, text) => {
    const el = document.createElementNS(ns, tag);
    Object.entries(attrs).forEach(([k,v]) => el.setAttribute(k,v));
    if (text != null) el.textContent = text;
    svg.appendChild(el);
    return el;
  };
  for (let i=0;i<=4;i++) {
    const y=p.t+ih*i/4;
    add("line",{x1:p.l,y1:y,x2:W-p.r,y2:y,class:"grid"});
    add("text",{x:p.l-8,y:y+4,class:"axis","text-anchor":"end"},
      (tickStep*(4-i)/1000).toLocaleString("nl-NL",{maximumFractionDigits:2})+"k");
  }
  for (const [field, cls] of fields) {
    const points=slots.map(s=>[
      xFor(new Date(s.start).getTime()+450000),
      yFor(s[field])
    ].join(",")).join(" ");
    add("polyline",{points,class:cls,fill:"none"});
  }
  const marker = (when,cls,label) => {
    if (!when) return;
    const ms=new Date(when).getTime();
    if (!Number.isFinite(ms) || ms < viewStart || ms > viewEnd) return;
    const x=xFor(ms);
    add("line",{x1:x,y1:p.t,x2:x,y2:p.t+ih,class:cls});
    add("text",{x:x+5,y:p.t+14,class:"ev-label"},label+" "+localTime(when));
  };
  if (ev && ev.active && ev.status === "TRACKING" && number(ev.remainingKWh)>0) {
    marker(ev.latestStartAt,"ev-latest","EV uiterlijk starten");
    marker(ev.deadlineAt,"ev-deadline","EV deadline");
  }
  for (let h=0;h<=24;h+=2) {
    const ms=viewStart+h*3600000;
    add("text",{x:xFor(ms),y:H-20,class:"axis","text-anchor":h===0?"start":h===24?"end":"middle"},localTime(ms));
  }
  const tooltip=$("tooltip");
  for (const slot of slots) {
    const start=new Date(slot.start).getTime();
    const end=start+900000;
    const hit=add("rect",{
      x:xFor(start),y:p.t,width:Math.max(1,xFor(end)-xFor(start)),
      height:ih,class:"hit"
    });
    hit.addEventListener("mousemove",event=>{
      tooltip.replaceChildren();
      const title=document.createElement("strong");
      title.textContent=localDateTime(slot.start);
      tooltip.appendChild(title);
      const values=[
        ["PV voorspeld",fmtW(slot.pvForecastW)],
        ["Tesla gepland",fmtW(slot.evPlanW)],
        ["Warm water gepland",fmtW(slot.wwPlanW)],
        ["Quooker gepland",slot.quookerPlanW==null?"—":fmtW(slot.quookerPlanW)],
        ["Quooker modus",slot.quookerMode||"—"],
        ["Quooker PV-kans",slot.quookerOpportunityAllowed===true?"toegestaan":slot.quookerOpportunityAllowed===false?"niet toegestaan":"—"],
        ["Export verwacht",fmtW(slot.gridExportAfterFlexW)],
        ["Import verwacht",fmtW(slot.gridImportAfterFlexW)],
        ["EV reden",slot.evReason || "—"],
        ["WW reden",slot.wwReason || "—"],
        ["Confidence",slot.confidence == null?"—":Math.round(slot.confidence*100)+"%"]
      ];
      for (const [label,value] of values) {
        const el=document.createElement("span");
        el.textContent=label+": "+value;
        tooltip.appendChild(el);
      }
      tooltip.hidden=false;
      const rect=svg.parentElement.getBoundingClientRect();
      tooltip.style.left=Math.min(rect.width-235,Math.max(8,event.clientX-rect.left+10))+"px";
      tooltip.style.top=Math.max(8,event.clientY-rect.top-100)+"px";
    });
    hit.addEventListener("mouseleave",()=>tooltip.hidden=true);
  }
}
load().then(render).catch(error=>{
  $("freshness").textContent=error.message;
  $("empty").hidden=false;
  $("pv-chart").hidden=true;
  $("ev-summary").textContent="Planner niet beschikbaar";
});
