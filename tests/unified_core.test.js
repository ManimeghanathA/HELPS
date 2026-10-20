const {test}=require('node:test');
const assert=require('node:assert/strict');
let core;try{core=require('../static/unified_core.js');}catch{}
test('current selection is authoritative, never newest unpublished observation',()=>{
 assert.ok(core,'unified core exists');
 const records=[{dataset_id:'old',region_id:'bhadra',active:true},{dataset_id:'new',region_id:'bhadra',date:'2099-01-01'}];
 assert.equal(core.currentDataset(records,{bhadra:'old'},'bhadra_reserve').dataset_id,'old');
 assert.equal(core.currentDataset(records,{},'unknown'),null);
});
test('slope ceilings classify measured data and distinguish unsupported data',()=>{
 assert.ok(core);assert.deepEqual(core.slopeCeilings,[0,2,4,6,8,12,15]);
 assert.equal(core.slopeCeiling(10),12);assert.equal(core.slopeCeiling(16),'>15');assert.equal(core.slopeCeiling(null),'Unknown');
});
test('request generations reject delayed responses independently',()=>{
 assert.ok(core);const a=core.requestGate(),b=core.requestGate();const old=a.begin(),fresh=a.begin(),other=b.begin();
 assert.equal(a.current(old),false);assert.equal(a.current(fresh),true);assert.equal(b.current(other),true);
});
test('readable feature evidence retains nested factors without raw JSON or executable markup',()=>{
 assert.ok(core);const html=core.featureCard({terrain_id:'<script>',area_m2:42,score_contributions:{wind:2},geometry:{type:'Polygon',coordinates:[]}});
 assert.match(html,/&lt;script&gt;/);assert.match(html,/Wind/);assert.match(html,/42/);assert.doesNotMatch(html,/coordinates|<script>|\{"/);
});
test('independent map instances preserve full multipart features and do not navigate tabs',()=>{
 const maps=[];global.L={map:()=>{const m={layers:new Set(),setView(){return this},removeLayer(l){this.layers.delete(l)},fitBounds(){},on(){},getContainer(){return {classList:{toggle(){}}}},invalidateSize(){},remove(){}};maps.push(m);return m;},tileLayer:()=>({addTo(m){m.layers.add(this);return this}}),geoJSON:(data,options)=>({data,options,addTo(m){m.layers.add(this);return this},getBounds:()=>({isValid:()=>true}),bringToFront(){}})};
 const full={type:'Feature',properties:{terrain_id:'multi'},geometry:{type:'MultiPolygon',coordinates:[[[[0,0],[1,0],[0,0]],[[.2,.2],[.3,.2],[.2,.2]]],[[[3,3],[4,3],[3,3]]]]}};
 const a=core.mapFactory('one'),b=core.mapFactory('two');a.showOnly(full);b.showCandidates({type:'FeatureCollection',features:[]});
 const selected=[...maps[0].layers].find(l=>l.data?.features?.[0]===full);assert.ok(selected);assert.equal(selected.data.features[0].geometry,full.geometry);assert.notEqual(a.map,b.map);b.clear();assert.ok(maps[0].layers.has(selected));delete global.L;
});
test('current region options include newly published regions and retain valid selection',()=>{const rows=[{region_id:'bhadra',dataset_id:'b'},{region_id:'new',dataset_id:'n'},{region_id:'old-only',dataset_id:'x'}],selected={bhadra:'b',new:'n'};assert.deepEqual(core.availableRegions(rows,selected),['bhadra','new']);});
test('single candidate maps use satellite imagery rather than street tiles',()=>{const maps=[];global.L={map:()=>{const m={layers:new Set(),setView(){return this},removeLayer(l){this.layers.delete(l)},fitBounds(){},on(){}};maps.push(m);return m;},tileLayer:url=>({url,addTo(m){m.layers.add(this);return this}}),geoJSON:data=>({data,addTo(m){m.layers.add(this);return this},getBounds:()=>({isValid:()=>true})})};try{core.mapFactory('inline').showOnly({type:'Feature',geometry:{type:'Polygon',coordinates:[]},properties:{}});const urls=[...maps[0].layers].map(l=>l.url).filter(Boolean);assert.equal(urls.length,1);assert.match(urls[0],/World_Imagery/);}finally{delete global.L;}});

 test('programmatic fits finish before picker bounds are read',()=>{
 let options;global.L={map:()=>({setView(){return this},removeLayer(){},fitBounds(bounds,value){options=value;},on(){}}),tileLayer:()=>({addTo(){return this}}),geoJSON:()=>({addTo(){return this},getBounds:()=>({isValid:()=>true})})};
 try{core.mapFactory('picker').showRegion({type:'FeatureCollection',features:[]});assert.equal(options.animate,false);}finally{delete global.L;}
 });
