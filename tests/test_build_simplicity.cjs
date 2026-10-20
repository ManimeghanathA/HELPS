const test=require('node:test');const assert=require('node:assert/strict');
const {sourceSlots,sourceMethodHelp,searchWarnings}=require('../static/unified_build.js');
test('automatic preparation hides manual raster and obstacle selectors',()=>{
 assert.deepEqual(sourceSlots('acquire'),['dem','restrictions']);
 assert.ok(sourceSlots('import').includes('spectral'));
 assert.ok(sourceSlots('retained').includes('retained_seed'));
 assert.ok(!sourceSlots('acquire').includes('reviewed_exclusions'));
});
test('source methods explain whether boundaries change',()=>{
 assert.match(sourceMethodHelp('retained'),/saved polygon boundaries/);
 assert.match(sourceMethodHelp('import'),/own.*files/);
 assert.match(sourceMethodHelp('acquire'),/missing/);
});
test('repeated quality failures collapse into one honest message',()=>{
 const rows=Array.from({length:10},(_,i)=>({stage:'scl_quality',date:'2026-01-'+(i+1),error:'unavailable'}));
 assert.equal(searchWarnings(rows).length,1);assert.match(searchWarnings(rows)[0],/10/);
 assert.match(searchWarnings(rows)[0],/catalog/);
});
