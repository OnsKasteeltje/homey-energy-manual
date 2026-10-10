import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import vm from "node:vm";

const source = readFileSync("frontend/heating/render/heating.js", "utf8");
const start = source.indexOf('  legend.innerHTML = "";');
const end = source.indexOf("  function draw(){", start);
assert.ok(start >= 0 && end > start, "heating room selection block exists");
const selection = source.slice(start, end);

function classList(){
  const values = new Set();
  return {
    toggle(name, enabled){
      if(enabled === undefined) enabled = !values.has(name);
      if(enabled) values.add(name);
      else values.delete(name);
    },
    contains(name){return values.has(name);},
  };
}

function setup(){
  const rooms = [
    {key:"woonkamer", displayName:"Woonkamer", color:"#008800"},
    {key:"eetkamer", displayName:"Eetkamer", color:"#0088cc"},
    {key:"keuken", displayName:"Keuken", color:"#cc8800"},
  ];
  const cards = new Map(rooms.map(room => [room.key,{classList:classList()}]));
  const legend = {children:[],innerHTML:"",append(button){this.children.push(button);}};
  const tooltip = {hidden:false};
  let draws = 0;
  const document = {
    createElement(tag){
      assert.equal(tag,"button");
      return {
        type:"", className:"", textContent:"", innerHTML:"",
        classList:classList(), attributes:new Map(),
        setAttribute(name,value){this.attributes.set(name,value);},
      };
    },
    querySelector(selector){
      const match = selector.match(/data-room="([^"]+)"/);
      return match ? cards.get(match[1]) : null;
    },
  };

  vm.runInNewContext(selection,{rooms,legend,document,$:()=>tooltip,draw:()=>{draws++;}});
  return {rooms,cards,legend,tooltip,draws:()=>draws};
}

test("all-off hides all six-style room series and cards in one click",()=>{
  const ui = setup();
  const [all,...buttons] = ui.legend.children;
  assert.equal(all.textContent,"Alles uit");
  all.onclick();
  assert.equal(all.textContent,"Alles aan");
  assert.equal(ui.draws(),1);
  for(const button of buttons){
    assert.equal(button.classList.contains("off"),true);
    assert.equal(button.attributes.get("aria-pressed"),"false");
  }
  for(const card of ui.cards.values()) assert.equal(card.classList.contains("off"),true);
  assert.equal(ui.tooltip.hidden,true);
});

test("all-on restores every room, and individual selection works after all-off",()=>{
  const ui = setup();
  const [all,first,...otherButtons] = ui.legend.children;
  all.onclick();
  first.onclick();
  assert.equal(all.textContent,"Alles uit");
  assert.equal(first.classList.contains("off"),false);
  assert.equal(first.attributes.get("aria-pressed"),"true");
  assert.equal(ui.cards.get("woonkamer").classList.contains("off"),false);
  for(const button of otherButtons) assert.equal(button.classList.contains("off"),true);
  all.onclick(); // partial selection -> everything off
  assert.equal(all.textContent,"Alles aan");
  all.onclick(); // all off -> everything on
  assert.equal(all.textContent,"Alles uit");
  assert.equal(ui.draws(),4);
  for(const button of ui.legend.children.slice(1)){
    assert.equal(button.classList.contains("off"),false);
    assert.equal(button.attributes.get("aria-pressed"),"true");
  }
  for(const card of ui.cards.values()) assert.equal(card.classList.contains("off"),false);
});

test("room visibility selection performs no backend writes",()=>{
  assert.ok(!selection.includes("fetch("));
  assert.ok(!selection.includes("physicalWrite"));
});
