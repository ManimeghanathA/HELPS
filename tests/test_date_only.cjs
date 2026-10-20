const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {sourceSlots,sourceMethodHelp}=require('../static/unified_build.js');
test('date-only scan has no source selectors and explains fixed local inputs',()=>{
 assert.deepEqual(sourceSlots('date_only'),[]);
 assert.match(sourceMethodHelp('date_only'),/only.*Sentinel/i);
 assert.match(sourceMethodHelp('date_only'),/local/i);
});
test('date-only is the default and does not submit refresh or source overrides',()=>{
 const source=fs.readFileSync('static/unified_build.js','utf8');
 assert.match(source,/<select id="build-mode"><option value="date_only">/);
 assert.match(source,/source_mode:'date_only',date:/);
});
