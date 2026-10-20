const {test}=require('node:test');const assert=require('node:assert/strict');const H=require('../static/unified_core.js');
test('clock switches at local 06/18 boundaries and advances across midnight',()=>{
 assert.equal(H.clockScene(new Date(2026,9,17,5,59)).theme,'dark');
 assert.equal(H.clockScene(new Date(2026,9,17,6)).theme,'light');
 assert.equal(H.clockScene(new Date(2026,9,17,18)).theme,'dark');
 const a=H.clockScene(new Date(2026,9,17,23)),b=H.clockScene(new Date(2026,9,18,1));assert.equal(a.period,b.period);assert.ok(b.progress>a.progress);
 assert.equal(H.clockScene(new Date(2026,9,17,12)).progress,.5);
});
test('helicopter bearing has cardinal directions and unknown/coincident defaults',()=>{
 assert.equal(H.bearingTo({lat:0,lng:0},{lat:1,lng:0}),0);assert.equal(H.bearingTo({lat:0,lng:0},{lat:0,lng:1}),90);
 assert.equal(H.bearingTo({lat:0,lng:0},{lat:-1,lng:0}),180);assert.equal(H.bearingTo({lat:0,lng:0},{lat:0,lng:-1}),270);assert.equal(H.bearingTo({lat:0,lng:0},{lat:0,lng:0}),0);assert.equal(H.bearingTo({lat:null,lng:0},{lat:1,lng:0}),0);
});
test('region list retains planned regions as disabled and escapes their names',()=>{
 const rows=[{properties:{id:'bhadra_reserve',name:'Bhadra'}},{properties:{id:'planned',name:'<Future>'}}];
 const html=H.regionList(rows,id=>id==='bhadra');assert.match(html,/Bhadra/);assert.match(html,/&lt;Future&gt;/);assert.match(html,/data-region-index="1"[^>]*disabled/);assert.match(html,/Planned/);
});
test('solid rotor loader rotates blades while retaining a stationary aircraft body',()=>{const svg=H.rotorSvg();assert.match(svg,/loader-blades/);assert.match(svg,/loader-fuselage/);assert.doesNotMatch(svg,/M29 29 5 22/);});
test('map position uses helicopter icon, rotates toward target and retains origin coordinates',()=>{
 let position,options;const layers=[];global.L={map:()=>({setView(){return this},on(){},removeLayer(){},fitBounds(){}}),tileLayer:()=>({addTo(){return this}}),divIcon:o=>o,marker:(coordinates,o)=>{position=coordinates;options=o;return {addTo(){return this},on(){},setLatLng(v){position=v;return this},setIcon(o){options.icon=o;return this}}}};
 try{const map=H.mapFactory('map');map.marker(0,0,{draggable:false,target:{latitude:0,longitude:1}});assert.deepEqual(position,[0,0]);assert.match(options.icon.html,/rotate\(90/);assert.match(options.icon.html,/helicopter-position/);assert.equal(options.draggable,false);map.marker(1,2,{draggable:false});assert.deepEqual(position,[1,2]);assert.match(options.icon.html,/rotate\(0/);}finally{delete global.L;}
});
