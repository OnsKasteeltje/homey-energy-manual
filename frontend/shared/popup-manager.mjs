/* EMS Frontend V2 — one viewport-aware popup manager.
 * Opt in with data-ems-popup-anchor="popup-id" on the focusable trigger.
 * The popup's role and its contents remain owned by the individual feature.
 */
const MARGIN=12, GAP=8;
const active = {anchor:null,popup:null,restore:null,observer:null};
const clamp=(value,min,max)=>Math.max(min,Math.min(value,max));
export function placePopup(anchorRect, size, viewport, margin=MARGIN, gap=GAP) {
  const vw=Math.max(0,viewport.width), vh=Math.max(0,viewport.height);
  const w=Math.min(size.width,Math.max(0,vw-2*margin));
  const h=Math.min(size.height,Math.max(0,vh-2*margin));
  const spaces={
    bottom:vh-margin-anchorRect.bottom-gap,
    top:anchorRect.top-margin-gap,
    right:vw-margin-anchorRect.right-gap,
    left:anchorRect.left-margin-gap
  };
  const fits={bottom:spaces.bottom>=h,top:spaces.top>=h,right:spaces.right>=w,left:spaces.left>=w};
  const side=["bottom","top","right","left"].find(s=>fits[s]) ||
    ["bottom","top","right","left"].sort((a,b)=>spaces[b]-spaces[a])[0];
  const left=side==="right"?anchorRect.right+gap:
    side==="left"?anchorRect.left-w-gap:anchorRect.left+(anchorRect.width-w)/2;
  const top=side==="bottom"?anchorRect.bottom+gap:
    side==="top"?anchorRect.top-h-gap:anchorRect.top+(anchorRect.height-h)/2;
  return {
    side,
    left:clamp(left,margin,Math.max(margin,vw-margin-w)),
    top:clamp(top,margin,Math.max(margin,vh-margin-h)),
    maxWidth:Math.max(0,vw-2*margin),
    maxHeight:Math.max(0,vh-2*margin)
  };
}
function position() {
  if(!active.popup || !active.anchor)return;
  const p=active.popup, a=active.anchor;
  if(!a.isConnected){closePopup();return;}
  const viewport={width:window.innerWidth,height:window.innerHeight};
  const size={width:p.offsetWidth,height:p.offsetHeight};
  const result=placePopup(a.getBoundingClientRect(),size,viewport);
  p.style.left=result.left+"px";
  p.style.top=result.top+"px";
  p.style.maxWidth=result.maxWidth+"px";
  p.style.maxHeight=result.maxHeight+"px";
  p.dataset.placement=result.side;
}
export function closePopup() {
  if(!active.popup)return;
  const p=active.popup;
  active.observer?.disconnect();
  p.removeAttribute("data-open");
  p.hidden=true;
  p.removeAttribute("data-placement");
  p.style.removeProperty("left");
  p.style.removeProperty("top");
  p.style.removeProperty("max-width");
  p.style.removeProperty("max-height");
  const restore=active.restore;
  if(restore?.parent?.isConnected)restore.parent.insertBefore(p,restore.next?.isConnected&&restore.next.parentNode===restore.parent?restore.next:null);
  active.anchor=null;active.popup=null;active.restore=null;active.observer=null;
}
export function openPopup(anchor,popup) {
  if(!anchor||!popup)return;
  if(active.anchor===anchor&&active.popup===popup){position();return;}
  closePopup();
  active.anchor=anchor;active.popup=popup;
  active.restore={parent:popup.parentNode,next:popup.nextSibling};
  document.body.appendChild(popup);
  popup.classList.add("ems-floating-popup");
  popup.hidden=false;
  popup.setAttribute("data-open","true");
  position();
  if(typeof ResizeObserver!=="undefined"){
    active.observer=new ResizeObserver(position);
    active.observer.observe(popup);
    active.observer.observe(anchor);
  }
}
export function initPopupManager(root=document) {
  for(const anchor of root.querySelectorAll("[data-ems-popup-anchor]")){
    if(anchor.dataset.emsPopupBound==="true")continue;
    const popup=document.getElementById(anchor.dataset.emsPopupAnchor);
    if(!popup)continue;
    anchor.dataset.emsPopupBound="true";
    popup.hidden=true;
    popup.classList.add("ems-floating-popup");
    anchor.addEventListener("pointerenter",()=>openPopup(anchor,popup));
    anchor.addEventListener("focusin",()=>openPopup(anchor,popup));
    anchor.addEventListener("pointerleave",e=>{
      if(!popup.contains(e.relatedTarget))closePopupIf(anchor);
    });
    anchor.addEventListener("focusout",e=>{
      if(!popup.contains(e.relatedTarget)&&!anchor.contains(e.relatedTarget))closePopupIf(anchor);
    });
    anchor.addEventListener("click",()=>openPopup(anchor,popup));
    popup.addEventListener("pointerleave",e=>{
      if(!anchor.contains(e.relatedTarget))closePopupIf(anchor);
    });
  }
}
function closePopupIf(anchor){if(active.anchor===anchor)closePopup();}
if(typeof window!=="undefined"&&typeof document!=="undefined"){
  window.addEventListener("resize",position,{passive:true});
  window.addEventListener("scroll",position,{capture:true,passive:true});
  document.addEventListener("keydown",e=>{if(e.key==="Escape")closePopup();});
  document.addEventListener("pointerdown",e=>{
    if(active.popup&&!active.popup.contains(e.target)&&!active.anchor.contains(e.target))closePopup();
  });
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",()=>initPopupManager(),{once:true});
  else initPopupManager();
}
