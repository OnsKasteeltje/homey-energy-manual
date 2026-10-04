const $ = id => document.getElementById(id);
const form = $("ask-form");
const question = $("question");
const messages = $("messages");
const send = $("send");
const status = $("agent-status");

const STORAGE_KEY = "ems.ai.v0.4.session";
const MAX_STORED_MESSAGES = 40;
const POLL_MS = 1500;

let pageLeaving = false;
let pollTimer = null;
let state = loadState();

function loadState(){
  try{
    const parsed=JSON.parse(sessionStorage.getItem(STORAGE_KEY)||"{}");
    return {
      messages:Array.isArray(parsed.messages)?parsed.messages.slice(-MAX_STORED_MESSAGES):[],
      pending:parsed.pending&&typeof parsed.pending==="object"?parsed.pending:null
    };
  }catch{
    return {messages:[],pending:null};
  }
}

function saveState(){
  try{
    state.messages=state.messages.slice(-MAX_STORED_MESSAGES);
    sessionStorage.setItem(STORAGE_KEY,JSON.stringify(state));
  }catch{
    // Conversation persistence is a UX aid; storage failure must not block AI use.
  }
}

function newRequestId(){
  if(globalThis.crypto?.randomUUID)return crypto.randomUUID();
  return `req-${Date.now()}-${Math.random().toString(36).slice(2,12)}`;
}

function renderMessage(kind,text,meta){
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
  messages.scrollTo({top:messages.scrollHeight,behavior:"smooth"});
}

function addMessage(kind,text,meta=null,requestId=null){
  renderMessage(kind,text,meta);
  state.messages.push({kind,text,meta,requestId});
  saveState();
}

function restoreMessages(){
  for(const item of state.messages){
    if(!item||!["user","agent"].includes(item.kind)||typeof item.text!=="string")continue;
    renderMessage(item.kind,item.text,item.meta||null);
  }
}

function setBusy(busy){
  send.disabled=busy;
  send.textContent=busy?"Analyseert…":"Analyseer";
}

function responseMeta(d){
  return `${d.dateLocal} · ${d.model} · ${d.evidenceSummary?.timelinePoints??0} evidence-punten`;
}

function hasAgentReply(requestId){
  return state.messages.some(
    item=>item?.kind==="agent"&&item.requestId===requestId
  );
}

function finishSuccess(d,requestId){
  if(!hasAgentReply(requestId)){
    addMessage("agent",d.answer,responseMeta(d),requestId);
  }
  state.pending=null;
  saveState();
  setBusy(false);
}

function finishError(reason,requestId){
  if(!hasAgentReply(requestId)){
    const text=reason==="MODEL_NOT_CONFIGURED"
      ?"Het model is nog niet geconfigureerd op de Pi."
      :`Analyse niet beschikbaar: ${reason||"onbekende fout"}`;
    addMessage("agent",text,null,requestId);
  }
  state.pending=null;
  saveState();
  setBusy(false);
}

function schedulePoll(){
  if(pollTimer!==null)clearTimeout(pollTimer);
  pollTimer=setTimeout(()=>{
    pollTimer=null;
    resumePending();
  },POLL_MS);
}

async function submitRequest(text,requestId,{addUser=true}={}){
  if(addUser){
    addMessage("user",text,null,requestId);
  }
  state.pending={requestId,question:text,day:"today"};
  saveState();
  setBusy(true);

  try{
    const r=await fetch("/agent/ask",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({
        question:text,
        day:"today",
        requestId
      })
    });
    const d=await r.json();

    if(r.status===202||d.status==="PENDING"){
      schedulePoll();
      return;
    }
    if(!r.ok||d.status!=="OK"){
      finishError(d.reason||r.status,requestId);
      return;
    }
    finishSuccess(d,requestId);
  }catch{
    // The browser may have navigated away after the Pi accepted the job.
    // Keep the pending request and resolve it via /agent/result on return.
    if(!pageLeaving)schedulePoll();
  }
}

async function resumePending(){
  const pending=state.pending;
  if(!pending?.requestId||!pending?.question){
    setBusy(false);
    return;
  }

  setBusy(true);
  try{
    const qs=new URLSearchParams({requestId:pending.requestId});
    const r=await fetch(`/agent/result?${qs}`,{cache:"no-store"});
    const d=await r.json();

    if(r.status===404||d.status==="NOT_FOUND"){
      // The original page may have disappeared before the POST reached the Pi.
      // Re-use the same idempotency key so an accepted job can never double-run.
      await submitRequest(
        pending.question,
        pending.requestId,
        {addUser:false}
      );
      return;
    }
    if(r.status===202||d.status==="PENDING"){
      schedulePoll();
      return;
    }
    if(r.ok&&d.status==="OK"){
      finishSuccess(d,pending.requestId);
      return;
    }
    finishError(d.reason||r.status,pending.requestId);
  }catch{
    if(!pageLeaving)schedulePoll();
  }
}

async function health(){
  try{
    const r=await fetch("/agent/health",{cache:"no-store"});
    const d=await r.json();
    status.textContent=d.status==="READY"
      ? `AI gereed · ${d.model}`
      : "AI model niet geconfigureerd";
  }catch{
    status.textContent="AI service niet bereikbaar";
  }
}

form.addEventListener("submit",e=>{
  e.preventDefault();
  if(state.pending)return;
  const text=question.value.trim();
  if(!text)return;
  question.value="";
  submitRequest(text,newRequestId());
});

document.querySelectorAll("[data-question]").forEach(button=>{
  button.addEventListener("click",()=>{
    question.value=button.dataset.question;
    question.focus();
  });
});

window.addEventListener("pagehide",()=>{
  pageLeaving=true;
});

window.addEventListener("pageshow",()=>{
  pageLeaving=false;
});

restoreMessages();
health();
if(state.pending){
  resumePending();
}else{
  setBusy(false);
}
