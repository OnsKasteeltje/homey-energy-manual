const $ = id => document.getElementById(id);
const form = $("ask-form");
const question = $("question");
const messages = $("messages");
const send = $("send");
const status = $("agent-status");

function addMessage(kind,text,meta){
  const article=document.createElement("article");
  article.className="message "+kind;
  const small=document.createElement("small");
  small.textContent=kind==="user"?"Jij":"EMS AI";
  const p=document.createElement("p");
  p.textContent=text;
  article.append(small,p);
  if(meta){
    const note=document.createElement("span");
    note.className="message-meta";
    note.textContent=meta;
    article.append(note);
  }
  messages.append(article);
  article.scrollIntoView({behavior:"smooth",block:"end"});
}

async function health(){
  try{
    const r=await fetch("/agent/health",{cache:"no-store"});
    const d=await r.json();
    status.textContent=d.status==="READY" ? `AI gereed · ${d.model}` : "AI model niet geconfigureerd";
  }catch{
    status.textContent="AI service niet bereikbaar";
  }
}

async function ask(text){
  addMessage("user",text);
  send.disabled=true;
  send.textContent="Analyseert…";
  try{
    const r=await fetch("/agent/ask",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({question:text,day:"today"})
    });
    const d=await r.json();
    if(!r.ok){
      const reason=d.reason==="MODEL_NOT_CONFIGURED"
        ? "Het model is nog niet geconfigureerd op de Pi."
        : `Analyse niet beschikbaar: ${d.reason||r.status}`;
      addMessage("agent",reason);
      return;
    }
    const meta=`${d.dateLocal} · ${d.model} · ${d.evidenceSummary?.timelinePoints??0} evidence-punten`;
    addMessage("agent",d.answer,meta);
  }catch(e){
    addMessage("agent","De analyse-service is niet bereikbaar.");
  }finally{
    send.disabled=false;
    send.textContent="Analyseer";
  }
}

form.addEventListener("submit",e=>{
  e.preventDefault();
  const text=question.value.trim();
  if(!text)return;
  question.value="";
  ask(text);
});

document.querySelectorAll("[data-question]").forEach(button=>{
  button.addEventListener("click",()=>{
    question.value=button.dataset.question;
    question.focus();
  });
});

health();
