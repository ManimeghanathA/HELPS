const $ = id => document.getElementById(id);
let shown = null;
function pending(state) {
  $('title').textContent = `${state.name} / ${state.date}`;
  $('status').textContent = 'Running';
  $('count').textContent = '-';
  $('area').textContent = '-';
  $('audit').textContent = 'Pending';
  $('map').hidden = true;
  $('noimage').hidden = false;
  $('noimage').textContent = 'Analysis in progress';
  $('downloads').hidden = true;
}
function display(result) {
  shown = result.id;
  $('title').textContent = `${result.name} / ${result.date}`;
  $('status').textContent = result.status;
  if (result.status !== 'complete') return;
  const s = result.summary;
  $('count').textContent = s.final_zones.toLocaleString();
  $('area').textContent = `${s.final_area_km2.toFixed(3)} km²`;
  $('audit').textContent = s.audits.passed ? 'Passed' : 'Failed';
  $('map').hidden = false;
  $('noimage').hidden = true;
  $('map').src = `/artifacts/${result.id}/final_zones.png`;
  $('map').alt = `Candidate polygon boundaries over ${result.name} Sentinel imagery`;
  $('downloads').hidden = false;
  for (const [id,file] of Object.entries({png:'final_zones.png',geojson:'final_zones.geojson',gpkg:'final_zones.gpkg',summary:'summary.json'})) {
    $(id).href = `/artifacts/${result.id}/${file}`;
  }
}
async function history() {
  const response = await fetch('/api/runs');
  const runs = await response.json();
  $('history').replaceChildren();
  if (!runs.length) $('history').textContent = 'No runs yet';
  for (const r of runs) {
    const button = document.createElement('button');
    button.textContent = r.name;
    const small = document.createElement('small');
    small.textContent = `${r.date} · ${r.status}`;
    button.append(small);
    button.onclick = async () => {
      if (r.status === 'complete') display(r);
      $('error').textContent = r.error || '';
      const log = await fetch(`/artifacts/${r.id}/run.log`);
      $('log').textContent = await log.text();
      $('progress').open = true;
    };
    $('history').append(button);
  }
  if (!shown) { const latest = runs.find(r => r.status === 'complete'); if (latest) display(latest); }
}
$('file').onchange = () => { if ($('file').files[0]) $('name').value = $('file').files[0].name.replace(/\.(geojson|json)$/i,''); };
$('form').onsubmit = async event => {
  event.preventDefault();
  $('error').textContent = '';
  $('run').disabled = true;
  try {
    const geojson = JSON.parse(await $('file').files[0].text());
    const response = await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({geojson,name:$('name').value,date:$('date').value})});
    const body = await response.json();
    if (!response.ok) throw new Error(body.error);
    $('progress').open = true;
    $('log').textContent = 'Starting analysis...';
  } catch (e) { $('error').textContent = e.message; $('run').disabled = false; }
};
$('scan').onclick = async () => {
  $('scan').disabled = true;
  $('scanstatus').textContent = 'Scanning Copernicus catalogue...';
  $('scanresults').replaceChildren();
  try {
    const response = await fetch('/api/historical-scan',{method:'POST'});
    const body = await response.json();
    if (!response.ok) throw new Error(body.error);
    const rows = body.best_date_per_month || [];
    if (!rows.length) {
      $('scanstatus').textContent = 'No low-cloud dates found.';
      return;
    }
    $('scanstatus').textContent = `Best monthly dates below ${body.maximum_cloud_percent}% cloud`;
    for (const row of rows) {
      const item = document.createElement('div');
      item.className = 'scanrow';
      const month = document.createElement('strong');
      month.textContent = row.month;
      const date = document.createElement('span');
      date.textContent = row.date;
      const cloud = document.createElement('small');
      cloud.textContent = `${Number(row.cloud_cover).toFixed(2)}%`;
      item.append(month,date,cloud);
      $('scanresults').append(item);
    }
  } catch (e) {
    $('scanstatus').textContent = e.message;
  } finally {
    $('scan').disabled = false;
  }
};
let previous = 'idle';
async function poll() {
  try {
    const response = await fetch('/api/state');
    const state = await response.json();
    $('run').disabled = state.status === 'running';
    $('logstatus').textContent = state.status;
    if (state.status === 'running' || previous === 'running') {
      $('log').textContent = state.log.join('\n');
      $('log').scrollTop = $('log').scrollHeight;
    }
    if (state.status !== previous) {
      if (state.status === 'running') pending(state);
      if (state.status === 'complete') display(state.result);
      if (state.status === 'failed') {
        $('error').textContent = state.error;
        $('status').textContent = 'Run failed';
        $('noimage').textContent = 'Analysis failed';
      }
      await history();
    }
    previous = state.status;
  } catch { $('logstatus').textContent = 'Connection lost'; }
  setTimeout(poll,1500);
}
$('map').onerror = () => { $('map').hidden = true; $('noimage').hidden = false; };
$('map').onload = () => { $('map').hidden = false; $('noimage').hidden = true; };
history().catch(() => {});
poll();
