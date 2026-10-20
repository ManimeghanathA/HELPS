const test=require('node:test'), assert=require('node:assert/strict');
const {createWorkspaceState}=require('../static/workspace_state.js');
test('late versions and views cannot overwrite current workspace',()=>{const s=createWorkspaceState();s.selectRegion('bhadra','a');const t=s.beginRequest();s.selectRegion('bhadra','b');assert.equal(s.applyResponse(t,{}),false);const t2=s.beginRequest();s.setView('map');assert.equal(s.applyResponse(t2,{}),false);});
