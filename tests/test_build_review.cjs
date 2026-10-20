const test=require('node:test');
const assert=require('node:assert/strict');
const {reviewActions}=require('../static/unified_build.js');
test('replacement remains disabled until pending polygon preview loaded',()=>{
 assert.deepEqual(reviewActions('pending',false),{accept:false,reject:true});
 assert.deepEqual(reviewActions('pending',true),{accept:true,reject:true});
 for(const state of ['rejected','accepted'])assert.deepEqual(reviewActions(state,true),{accept:false,reject:false});
});
test('review uses dedicated preview and single explicit decision endpoints',()=>{
 const text=require('node:fs').readFileSync(require('node:path').join(__dirname,'../static/unified_build.js'),'utf8');
 assert.match(text,/preview\?format=geojson/);
 assert.match(text,/Confirm replacement/);
 assert.match(text,/Reject this build/);
 assert.match(text,/preview_token/);
 assert.doesNotMatch(text,/\/activate/);
});
