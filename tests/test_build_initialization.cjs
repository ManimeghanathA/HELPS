const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const {esc, requestGate} = require('../static/unified_core.js');

const flush = () => new Promise(resolve => setImmediate(resolve));

function harness(api, initiallyHidden = false) {
 const nodes = new Map();
 const timers = new Map();
 const events = new Map();
 let nextTimer = 0;
 function node(id) {
  if (!nodes.has(id)) nodes.set(id, {
   elements: {date: {}}, hidden: false, innerHTML: '', textContent: '',
   reset() { this.resetCalled = true; },
   setAttribute() {}, removeAttribute() {}
  });
  return nodes.get(id);
 }
 node('build-panel').hidden = initiallyHidden;
 const context = {
  HELPS: {esc, requestGate, api, ready: Promise.resolve()},
  document: {getElementById: node, activeElement: null},
  addEventListener(event, listener) { events.set(event, listener); },
  setTimeout(callback) { timers.set(++nextTimer, callback); return nextTimer; },
  clearTimeout(id) { timers.delete(id); },
  FormData: class {
   constructor(form) { this.fields = {...form.fields}; }
   get(key) { return this.fields[key]; }
   delete(key) { delete this.fields[key]; }
  }
 };
 vm.runInNewContext(fs.readFileSync('static/unified_build.js', 'utf8'), context);
 return {
  node, timers,
  switchTab(detail) {
   node('build-panel').hidden = detail !== 'build';
   events.get('helps:tab')({detail});
  }
 };
}

test('returning to Build Knowledge restores persisted progress, failures and pending reviews', async () => {
 const jobs = [
  {job_id:'active', region_id:'rgb-hills', date:'2026-07-15', status:'running',
   stage:'Segmenting tile 2 of 4', progress:{percent:40}},
  {job_id:'failed', region_id:'rgb-lake', date:'2026-06-20', status:'failed',
   error:'Elevation source unavailable'},
  {job_id:'pending', region_id:'rgb-field', date:'2026-05-20', status:'completed',
   review:{decision:'pending'}}
 ];
 const h = harness(async path => {
  assert.equal(path, '/api/knowledge/rgb/jobs');
  return {jobs};
 }, true);
 assert.equal(h.node('build-jobs').innerHTML, '');
 h.switchTab('build');
 await flush();
 assert.match(h.node('build-jobs').innerHTML, /Segmenting tile 2 of 4/);
 assert.match(h.node('build-jobs').innerHTML, /40%/);
 assert.match(h.node('build-jobs').innerHTML, /Elevation source unavailable/);
 assert.match(h.node('build-jobs').innerHTML, /Review polygons/);
 assert.equal(h.timers.size, 1);
 h.switchTab('map');
 assert.equal(h.timers.size, 0);
 jobs[0] = {...jobs[0], status:'completed', stage:'Build complete', review:{decision:'pending'}};
 h.switchTab('build');
 await flush();
 assert.match(h.node('build-jobs').innerHTML, /Build complete/);
 assert.doesNotMatch(h.node('build-jobs').innerHTML, /Segmenting tile/);
});

test('submitting the RGB form sends both files and capture date and returns to the saved job list', async () => {
 const requests = [];
 const h = harness(async (path, options) => {
  requests.push({path, options});
  return path.endsWith('/build') ? {job_id:'accepted-upload'} : {jobs:[]};
 });
 await flush();
 const form = h.node('build-form');
 form.fields = {
  name:'Field', date:'2026-05-20', image:{name:'capture.tif', size:128},
  boundary:{name:'boundary.geojson', size:64}, resolution_m:''
 };
 await form.onsubmit({preventDefault() {}});
 const upload = requests.find(request => request.options?.method === 'POST');
 assert.equal(upload.path, '/api/knowledge/rgb/build');
 assert.deepEqual({...upload.options.body.fields}, {
  name:'Field', date:'2026-05-20', image:form.fields.image, boundary:form.fields.boundary
 });
 assert.equal(form.resetCalled, true);
 assert.match(h.node('build-progress').textContent, /queued/i);
 assert.equal(requests.at(-1).path, '/api/knowledge/rgb/jobs');
});
