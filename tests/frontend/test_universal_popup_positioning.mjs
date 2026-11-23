import test from "node:test";
import assert from "node:assert/strict";
import {placePopup} from "../../frontend/shared/popup-manager.mjs";
const rect=(left,top,width,height)=>({left,top,width,height,right:left+width,bottom:top+height});
const viewport={width:390,height:700};
test("bottom if there is space",()=>{
  const p=placePopup(rect(60,100,140,60),{width:260,height:180},viewport);
  assert.equal(p.side,"bottom");
  assert.ok(p.left>=12&&p.left+260<=378);
});
test("flip above near bottom",()=>{
  const p=placePopup(rect(45,610,150,50),{width:260,height:180},viewport);
  assert.equal(p.side,"top");
  assert.ok(p.top>=12&&p.top+180<=688);
});
test("clamp oversized overlays into small viewport",()=>{
  const p=placePopup(rect(2,2,35,35),{width:900,height:900},{width:320,height:200});
  assert.equal(p.left,12);
  assert.ok(p.top>=12);
  assert.equal(p.maxWidth,296);
  assert.equal(p.maxHeight,176);
});
test("right-edge tooltip is moved fully into viewport",()=>{
  const p=placePopup(rect(360,140,25,45),{width:260,height:150},viewport);
  assert.ok(p.left>=12&&p.left+260<=378);
});
