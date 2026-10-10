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

// Select the closest *visible* series segment within a small pixel radius.
// A flat 0 W baseline is shared by many series and cannot identify one line.
function closestPlannerLine(slots, fields, px, py, xAt, yAt, radius) {
  if (slots.length < 2 || !Number.isFinite(px) || !Number.isFinite(py)) return null;
  const step = xAt(1) - xAt(0);
  if (!(step > 0)) return null;
  const position = (px - xAt(0)) / step;
  if (position < 0 || position > slots.length - 1) return null;
  const at = Math.min(slots.length - 2, Math.floor(position));
  let best = null;
  let distance = radius;
  for (const [field] of fields) {
    for (let i = Math.max(0, at - 1); i <= Math.min(slots.length - 2, at + 1); i++) {
      const a = slots[i][field], b = slots[i + 1][field];
      if (typeof a !== "number" || !Number.isFinite(a) ||
          typeof b !== "number" || !Number.isFinite(b) || (a === 0 && b === 0)) continue;
      const x1 = xAt(i), x2 = xAt(i + 1), y1 = yAt(a), y2 = yAt(b);
      const dx = x2 - x1, dy = y2 - y1;
      const fraction = Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) /
        (dx * dx + dy * dy)));
      const error = Math.hypot(px - (x1 + dx * fraction), py - (y1 + dy * fraction));
      if (error < distance) {
        distance = error;
        best = {field, slot: slots[Math.max(0, Math.min(slots.length - 1,
          Math.round(position)))]};
      }
    }
  }
  return best;
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
    ["pvForecastW","pvline","PV voorspeld"],
    ["evPlanW","evline","Tesla gepland"],
    ["wwPlanW","wwline","Warm water gepland"],
    ["quookerPlanW","quookerline","Quooker gepland"],
    ["gridExportAfterFlexW","exportline","Export verwacht"],
    ["gridImportAfterFlexW","importline","Import verwacht"]
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
  // One transparent hit surface; report only the nearest actual graph line.
  const hit=add("rect",{x:p.l,y:p.t,width:iw,height:ih,class:"hit"});
  hit.addEventListener("mousemove",event=>{
    const matrix=svg.getScreenCTM();
    if (!matrix) { tooltip.hidden=true; return; }
    const pointer=svg.createSVGPoint();
    pointer.x=event.clientX;
    pointer.y=event.clientY;
    const point=pointer.matrixTransform(matrix.inverse());
    const scale=Math.hypot(matrix.a,matrix.b);
    const selection=closestPlannerLine(slots,fields,point.x,point.y,
      i=>xFor(new Date(slots[i].start).getTime()+450000),yFor,12/scale);
    if (!selection) { tooltip.hidden=true; return; }

    const {field,slot}=selection;
    const label=fields.find(([key])=>key===field)[2];
    tooltip.replaceChildren();
    const title=document.createElement("strong");
    title.textContent=localDateTime(slot.start);
    tooltip.appendChild(title);
    const addDetail=(name,value)=>{
      const row=document.createElement("span");
      row.textContent=name+": "+value;
      tooltip.appendChild(row);
    };
    addDetail(label,slot[field]==null?"—":fmtW(slot[field]));
    if (field==="quookerPlanW") {
      addDetail("Quooker modus",slot.quookerMode||"—");
      addDetail("PV-kans",slot.quookerOpportunityAllowed===true?"toegestaan":
        slot.quookerOpportunityAllowed===false?"niet toegestaan":"—");
    } else if (field==="evPlanW") {
      addDetail("EV reden",slot.evReason||"—");
    } else if (field==="wwPlanW") {
      addDetail("WW reden",slot.wwReason||"—");
    } else if (field==="pvForecastW") {
      addDetail("Confidence",slot.confidence==null?"—":
        Math.round(slot.confidence*100)+"%");
    }
    tooltip.hidden=false;
    const rect=svg.parentElement.getBoundingClientRect();
    tooltip.style.left=Math.min(Math.max(8,rect.width-tooltip.offsetWidth-8),
      Math.max(8,event.clientX-rect.left+12))+"px";
    tooltip.style.top=Math.min(Math.max(8,rect.height-tooltip.offsetHeight-8),
      Math.max(8,event.clientY-rect.top-tooltip.offsetHeight-12))+"px";
  });
  hit.addEventListener("mouseleave",()=>tooltip.hidden=true);
}
load().then(render).catch(error=>{
  $("freshness").textContent=error.message;
  $("empty").hidden=false;
  $("pv-chart").hidden=true;
  $("ev-summary").textContent="Planner niet beschikbaar";
});
