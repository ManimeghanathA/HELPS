const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const source = fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8');

test('Bhadra selection loads complete candidates, fits bounds, and never requests weather', async () => {
  const start = source.indexOf('const showOverviewRegion = async (region) => {');
  assert.notEqual(start, -1, 'direct region exploration is missing');
  const body = source.slice(start, source.indexOf('\n};', start) + 4);
  const geometry = {type: 'Polygon', coordinates: [[[75,13],[75.01,13],[75.01,13.01],[75,13]],
    [[75.002,13.002],[75.004,13.002],[75.002,13.004],[75.002,13.002]]]};
  const data = {type: 'FeatureCollection', features: [{type: 'Feature', properties: {zone_id: 'test'}, geometry}]};
  const requests = [], fitted = [], elements = {};
  for (const id of ['#region-select','#explorer-status','#active-sector-name','#active-sector-status']) elements[id] = {value: '', textContent: ''};
  const layer = {clearLayers() {}, addData(value) {this.data = value;}, getBounds() {return {isValid: () => true};}};
  const context = {document: {querySelector: id => elements[id]}, overviewCandidatesLayer: layer,
    overviewSelectionToken: 0, satelliteMap: {fitBounds(bounds) {fitted.push(bounds);}},
    fetch: async url => {requests.push(url); return {ok: true, json: async () => data};}};
  vm.createContext(context);
  vm.runInContext(body + '\nthis.showRegion = showOverviewRegion;', context);
  await context.showRegion({properties: {id: 'bhadra_reserve', status: 'ready', name: 'Bhadra'}});
  assert.deepEqual(requests, ['/api/gpkg-zones']);
  assert.equal(layer.data, data);
  assert.equal(fitted.length, 1);
  assert.match(elements['#explorer-status'].textContent, /1 candidate/);
});
