const test=require('node:test');
const assert=require('node:assert/strict');
const {inputReadinessHTML}=require('../static/unified_build.js');
const esc=s=>String(s??'Unknown').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

test('input actions and unsafe source strings are rendered as text',()=>{
 const html=inputReadinessHTML([{kind:'osm',action:'reuse_processed',snapshot_id:'one',metadata:{snapshot_date:'2026-10-18'},raw_directory:'C:/raw/<bad>',processed_directory:'C:/processed',access:[{key:'osm',location:'C:/<secret>',download_url:'/api/knowledge/input-file?key=osm'}]}],esc);
 assert.match(html,/Reusing processed/);assert.match(html,/2026-10-18/);assert.match(html,/&lt;bad&gt;/);assert.doesNotMatch(html,/<secret>/);
 assert.match(html,/Copy location/);assert.match(html,/Download file/);
});

test('missing sources describe download and raw processing without claiming readiness',()=>{
 const html=inputReadinessHTML([{kind:'sentinel',action:'download',metadata:{},access:[]},{kind:'dem',action:'process_raw',metadata:{},access:[]}],esc);
 assert.match(html,/Download required/);assert.match(html,/Process existing raw/);assert.match(html,/Unknown/);
});
