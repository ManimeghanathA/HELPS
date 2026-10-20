const test=require('node:test');
const assert=require('node:assert/strict');
const {cloud}=require('../static/unified_build.js');
const {sourceOptions,keepBuildDate}=require('../static/unified_build.js');
test('dated observation evidence filters while timeless sources remain available',()=>{
 const rows=[{slot:'spectral',date:'2026-06-01',available:true},{slot:'spectral',date:'2026-07-01',available:true},{slot:'spectral',available:true},{slot:'dem',date:'2020-01-01',available:true}];
 assert.equal(sourceOptions(rows,'spectral','2026-07-01').length,2);
 assert.equal(sourceOptions(rows,'dem','2026-07-01').length,1);
 assert.equal(keepBuildDate('2026-07-01','2026-06-02','2026-10-17',true),'2026-07-01');
 assert.equal(keepBuildDate('2026-06-01','2026-06-02','2026-10-17',true),'');
 assert.equal(keepBuildDate('2026-07-01','','2026-10-17',false),'');
});
test('unknown cloud evidence remains unknown',()=>{
 assert.equal(cloud({}),'Cloud interference unknown');
 assert.equal(cloud({qa_state:'measured',cloud_fraction:.2}),'Cloud interference unknown');
});
test('measured AOI quality and product metadata are clearly distinguished',()=>{
 assert.equal(cloud({qa_state:'metadata_only',cloud_fraction:.2}),'20.0% product cloud · metadata only');
 assert.equal(cloud({qa_state:'measured',cloud_shadow_fraction:.1,cloud_fraction:.2}),'10.0% AOI cloud / shadow · measured');
});

test('partial observation coverage is explicit beside measured cloud interference',()=>{assert.match(cloud({qa_state:'measured',cloud_shadow_fraction:.1,coverage_fraction:.5}),/50.00% AOI observed; remaining area unknown/);});

test('temporal inventory excludes current observation and merges repeated dated references',()=>{
 const {scanHistory}=require('../static/unified_build.js');
 const rows=scanHistory({current_date:'2026-06-01',versions:[{date:'2026-06-01',active:true},{date:'2026-05-15'}],history:[{date:'2026-05-15',qa_state:'measured'},{date:'2026-06-01'}]});
 assert.equal(rows.length,1);assert.equal(rows[0].date,'2026-05-15');assert.equal(rows[0].qa_state,'measured');
 assert.match(cloud({qa_state:'measured',cloud_shadow_fraction:.1,coverage_fraction:.99967}),/99.97% AOI observed/);
});
