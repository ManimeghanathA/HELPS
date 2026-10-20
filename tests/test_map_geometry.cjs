// Execute the ranked renderer with a Leaflet boundary stub. Geometry must reach
// L.geoJSON unchanged; an exterior or bounding rectangle is not equivalent.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {execFileSync} = require('node:child_process');
const {test} = require('node:test');
const root = path.resolve(__dirname, '..');
const source = process.env.HELPS_JS_BASELINE
  ? execFileSync('git', ['show', 'HEAD:static/app.js'], {cwd: root, encoding: 'utf8'})
  : fs.readFileSync(path.join(root, 'static/app.js'), 'utf8');
const start = source.indexOf('const renderTacticalMapSpots = (data) => {');
assert.notEqual(start, -1);
const renderer = source.slice(start, source.indexOf('\n};', start) + 4);

function render(geometry) {
  const received = [];
  const layer = () => ({bindPopup() {return this;}, on() {return this;},
    addTo() {return this;}, setStyle() {return this;}, getBounds() {return {};}});
  const context = {
    tacticalMap: {fitBounds() {}, setView() {}}, tacticalSpotsLayer: {clearLayers() {}},
    radarSitesCount: null, radarClosestSite: null, shortZoneName: x => x,
    document: {},
    L: {divIcon: x => x, marker: layer, circle: layer, featureGroup: layer,
      geoJSON: value => {received.push(value); return layer();},
      polygon: () => {throw new Error('Exterior-only path used');},
      rectangle: () => {throw new Error('Bounding rectangle is not candidate geometry');}},
  };
  vm.createContext(context);
  vm.runInContext(renderer + '\nthis.render = renderTacticalMapSpots;', context);
  context.render({location: {latitude: 13, longitude: 75}, temperature_c: 25,
    wind: {speed_kt: 10, direction_deg: 270}, landing_zones: {spots: [{
      zone_id: 'test', latitude: 13, longitude: 75, area_m2: 900,
      geometry, bbox: [13, 75, 13.1, 75.1],
      polygon: [[13,75],[13,75.1],[13.1,75.1],[13,75]],
    }]}});
  return received;
}

const rings = [[[75,13],[75.01,13],[75.01,13.01],[75,13]],
               [[75.002,13.002],[75.004,13.002],[75.002,13.004],[75.002,13.002]]];
test('ranked Polygon preserves its excluded interior', () => {
  const geometry = {type: 'Polygon', coordinates: rings};
  assert.deepEqual(render(geometry), [geometry]);
});
test('ranked MultiPolygon preserves all parts and rings', () => {
  const geometry = {type: 'MultiPolygon', coordinates: [rings, [rings[0]]]};
  assert.deepEqual(render(geometry), [geometry]);
});
test('missing geometry is never replaced by an apparently usable rectangle', () => {
  assert.deepEqual(render(undefined), []);
});
