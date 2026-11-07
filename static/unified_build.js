(function(root) {
'use strict';

const reviewActions = (decision, previewReady) => ({
  accept: decision === 'pending' && previewReady,
  reject: decision === 'pending'
});

if (typeof module !== 'undefined') module.exports = {reviewActions};
if (!root.document || !root.HELPS) return;

const H = root.HELPS;
const E = H.esc;
const $ = id => root.document.getElementById(id);
const panel = $('build-panel');
if (!panel) return;

panel.innerHTML = `
  <div class="section-heading">
    <p class="eyebrow">OFFLINE KNOWLEDGE</p>
    <h1>Build regional knowledge</h1>
    <p>Upload a boundary and dated RGB imagery. Review the resulting candidate polygons before publishing them.</p>
  </div>
  <div class="build-grid">
    <section class="panel build-section">
      <h2>New RGB build</h2>
      <form id="build-form">
        <div class="field-grid">
          <label class="field">Region name
            <input name="name" required maxlength="80" placeholder="A name you recognise">
          </label>
          <label class="field">Capture date
            <input name="date" type="date" required aria-describedby="build-date-help">
            <small id="build-date-help">Use the date the image was captured.</small>
          </label>
        </div>
        <label class="field">Region boundary
          <input name="boundary" type="file" accept=".geojson,.json,application/geo+json" required aria-describedby="build-boundary-help">
          <small id="build-boundary-help">GeoJSON Polygon or MultiPolygon. Up to 2 MiB, 4 km², and 8 km across.</small>
        </label>
        <label class="field">RGB GeoTIFF
          <input name="image" type="file" accept=".tif,.tiff,image/tiff" required aria-describedby="build-image-help">
          <small id="build-image-help">One georeferenced 8-bit RGB or RGBA image, up to 256 MiB, with valid pixels covering the entire boundary.</small>
        </label>
        <label class="field">Working resolution
          <select name="resolution_m" aria-describedby="build-resolution-help">
            <option value="">Automatic from imagery</option>
            <option value="0.5">0.5 metres per pixel</option>
            <option value="1">1 metre per pixel</option>
            <option value="2">2 metres per pixel</option>
          </select>
          <small id="build-resolution-help">Processing uses 0.5 to 2 metres per pixel and up to 32 tiles. Choose a resolution at least as coarse as the source imagery.</small>
        </label>
        <button id="build-start" type="submit" class="primary">Start processing</button>
      </form>
      <p class="build-status" id="build-progress" role="status">After the build is queued, you can close HELPS. Keep this computer awake while the worker runs.</p>
    </section>
    <section class="panel build-section">
      <h2>Build jobs</h2>
      <p class="muted">Processing progress and review decisions are saved on the server.</p>
      <button id="build-refresh" type="button">Refresh jobs</button>
      <div id="build-job-status" class="build-status" role="status"></div>
      <div id="build-jobs" class="scan-list"></div>
    </section>
  </div>
  <section id="build-review" class="build-review" aria-label="Build review"></section>`;

const form = $('build-form');
const jobsElement = $('build-jobs');
const reviewElement = $('build-review');
const listGate = H.requestGate();
const reviewGate = H.requestGate();
const activeJob = job => ['queued', 'running'].includes(job.status);
const jobPath = id => '/api/knowledge/jobs/' + encodeURIComponent(id);
const setStatus = message => { $('build-progress').textContent = message; };
let pollTimer, reviewMap;

const captureCalendar = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit'
});
const calendarParts = Object.fromEntries(captureCalendar.formatToParts(new Date()).map(part => [part.type, part.value]));
form.elements.date.max = [calendarParts.year, calendarParts.month, calendarParts.day].join('-');

function jobCard(job) {
  const region = job.region_name || String(job.region_id || '').replace(/^rgb-/, '');
  const percent = job.progress?.percent;
  const decision = job.review?.decision;
  const state = {
    queued: 'Queued', running: 'Processing', completed: 'Completed', failed: 'Failed'
  }[job.status];
  const label = {
    pending: 'Ready for review', accepted: 'Accepted', rejected: 'Rejected'
  }[decision] || state;
  return `<article class="scan-card">
    <strong>${E(region)} · ${E(job.date)}</strong> <span class="badge">${E(label)}</span>
    ${job.stage ? `<div>${E(job.stage)}</div>` : ''}
    ${activeJob(job) && Number.isFinite(percent) ? `<div><progress value="${percent}" max="100" aria-label="Build progress"></progress><small>${percent}%</small></div>` : ''}
    ${job.error ? `<div class="error">${E(job.error)}</div>` : ''}
    ${decision === 'pending' ? `<button type="button" data-review-job="${E(job.job_id)}">Review polygons</button>` : ''}
    ${job.status === 'failed' && job.resumable !== false ? `<button type="button" data-resume-job="${E(job.job_id)}">Retry processing</button>` : ''}
  </article>`;
}

let renderedJobs;
async function refreshJobs() {
  clearTimeout(pollTimer);
  const token = listGate.begin();
  const status = $('build-job-status');
  let pollAgain = false;
  try {
    const {jobs} = await H.api('/api/knowledge/rgb/jobs');
    if (!listGate.current(token)) return;
    const ordered = [...jobs].sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')));
    const html = ordered.map(jobCard).join('');
    if (html !== renderedJobs) {
      const focused = root.document.activeElement?.dataset;
      const focusedKey = focused?.reviewJob || focused?.resumeJob;
      jobsElement.innerHTML = html;
      if (focusedKey) {
        const buttons = [...jobsElement.querySelectorAll('[data-review-job], [data-resume-job]')];
        buttons.find(button => button.dataset.reviewJob === focusedKey || button.dataset.resumeJob === focusedKey)?.focus();
      }
      renderedJobs = html;
    }
    status.textContent = jobs.length ? '' : 'No RGB builds yet.';
    pollAgain = jobs.some(activeJob);
  } catch (error) {
    if (!listGate.current(token)) return;
    status.textContent = 'Could not refresh jobs. ' + error.message;
    pollAgain = true;
  } finally {
    if (pollAgain && listGate.current(token) && !panel.hidden) {
      pollTimer = setTimeout(refreshJobs, 2000);
    }
  }
}

async function submitBuild(event) {
  event.preventDefault();
  const button = $('build-start');
  if (button.disabled) return;
  const body = new FormData(form);
  if (body.get('boundary').size > 2 * 1024 ** 2) {
    setStatus('The boundary exceeds 2 MiB.');
    return;
  }
  if (body.get('image').size > 256 * 1024 ** 2) {
    setStatus('The RGB GeoTIFF exceeds 256 MiB.');
    return;
  }
  if (!body.get('resolution_m')) body.delete('resolution_m');
  button.disabled = true;
  setStatus('Uploading and validating the boundary and imagery…');
  try {
    await H.api('/api/knowledge/rgb/build', {method: 'POST', body});
    form.reset();
    setStatus('Build queued. Follow its progress under Build jobs.');
    await refreshJobs();
  } catch (error) {
    setStatus(error.message);
  } finally {
    button.disabled = false;
  }
}

function closeReview() {
  reviewGate.begin();
  reviewMap?.destroy();
  reviewMap = null;
  reviewElement.replaceChildren();
}

async function showBuildReview(id) {
  closeReview();
  const token = reviewGate.begin();
  const path = jobPath(id);
  setStatus('Loading the proposed map…');
  const {proposed, current, decision, validation, source_completeness, temporal_summary, parameters, evidence_note} =
    await H.api(path + '/preview');
  if (!reviewGate.current(token)) return;
  reviewElement.innerHTML = `<div class="panel build-section">
    <p class="eyebrow">UNPUBLISHED BUILD REVIEW</p>
    <h2>Inspect the proposed candidate polygons</h2>
    <div class="review-metrics">
      <div><strong>${proposed.candidate_count.toLocaleString()}</strong><span>Proposed candidates</span></div>
      <div><strong>${proposed.slope_zone_count.toLocaleString()}</strong><span>Measured slope subregions</span></div>
      <div><strong>${(proposed.total_area_m2 / 1e6).toFixed(3)} km²</strong><span>Candidate area</span></div>
      <div><strong>${E(proposed.date)}</strong><span>Capture date</span></div>
    </div>
    <p>${current.date ? `Current observation ${E(current.date)}` : 'This is the first observation for this region.'}${current.counts ? ' · ' + current.counts.terrain.toLocaleString() + ' candidates' : ''}</p>
    <p class="muted">Proposed dataset <code>${E(proposed.dataset_id)}</code></p>
    <div class="review-layout">
      <div>
        <div id="build-preview-map" class="build-preview-map" aria-label="Proposed candidate polygons"></div>
        <p id="build-preview-status" role="status">Loading complete polygon boundaries…</p>
      </div>
      <div>
        <h3>Selected candidate</h3>
        <div id="build-preview-detail" class="review-feature">Select a polygon to inspect its features.</div>
      </div>
    </div>
    <details>
      <summary>Validation and source details</summary>
      ${H.featureCard({validation, source_completeness, temporal_summary, parameters, evidence_note})}
    </details>
    <div class="review-decisions">
      <button id="build-accept" type="button" disabled>${current.dataset_id ? 'Confirm replacement' : 'Accept and publish'}</button>
      <button id="build-reject" type="button" ${reviewActions(decision, false).reject ? '' : 'disabled'}>Reject this build</button>
      <button id="build-close" type="button">Close review</button>
      <span id="build-decision-status" role="status"></span>
    </div>
  </div>`;

  const accept = $('build-accept');
  const reject = $('build-reject');
  const previewStatus = $('build-preview-status');
  const decisionStatus = $('build-decision-status');
  let previewToken;
  let deciding = false;

  async function decide(action) {
    if (!reviewGate.current(token) || deciding) return;
    deciding = true;
    accept.disabled = reject.disabled = true;
    try {
      await H.post(path + '/' + action, action === 'accept' ? {preview_token: previewToken} : {});
    } catch (error) {
      if (reviewGate.current(token)) {
        decisionStatus.textContent = error.message + ' Close and reopen the review to try again.';
      }
      return;
    }
    if (action === 'accept') root.dispatchEvent(new CustomEvent('helps:datasets-changed'));
    if (reviewGate.current(token)) {
      closeReview();
      setStatus(action === 'accept' ? 'Build accepted and published.' : 'Build rejected.');
    }
    await refreshJobs();
  }

  reject.onclick = () => decide('reject');
  $('build-close').onclick = closeReview;
  if (!panel.hidden) {
    reviewElement.scrollIntoView({
      behavior: root.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
      block: 'start'
    });
  }

  try {
    const collection = await H.api(path + '/preview?format=geojson');
    if (!reviewGate.current(token)) return;
    reviewMap = H.mapFactory('build-preview-map', {onCandidate: feature => {
      reviewMap.focus(feature);
      $('build-preview-detail').innerHTML = H.featureCard(feature.properties);
    }});
    if (collection.boundary) reviewMap.showRegion(collection.boundary);
    if (collection.features.length) {
      if (!collection.boundary) reviewMap.showOnly(collection.features[0]);
      reviewMap.showCandidates(collection);
      previewStatus.textContent = collection.features.length.toLocaleString() + ' candidate boundaries loaded.';
    } else {
      previewStatus.textContent = 'This build found no candidate polygons.';
    }
    reviewMap.invalidate();
    previewToken = collection.preview_token;
    const latestDecision = collection.decision || decision;
    if (!deciding) {
      const actions = reviewActions(latestDecision, Boolean(previewToken));
      accept.disabled = !actions.accept;
      reject.disabled = !actions.reject;
      accept.onclick = () => decide('accept');
      decisionStatus.textContent = latestDecision === 'pending' ? 'Choose whether to publish this build.' : H.title(latestDecision);
      setStatus('Review the proposed candidate polygons below.');
    }
  } catch (error) {
    if (reviewGate.current(token)) {
      previewStatus.textContent = error.message;
      setStatus('Could not load the proposed polygons.');
    }
  }
}

async function resumeBuild(button) {
  button.disabled = true;
  try {
    await H.post('/api/knowledge/rgb/jobs/' + encodeURIComponent(button.dataset.resumeJob) + '/resume', {});
    setStatus('Build queued again.');
    await refreshJobs();
  } catch (error) {
    setStatus(error.message);
  } finally {
    button.disabled = false;
  }
}

form.onsubmit = submitBuild;
$('build-refresh').onclick = refreshJobs;
jobsElement.onclick = event => {
  const button = event.target.closest('button');
  if (button?.dataset.reviewJob) return showBuildReview(button.dataset.reviewJob).catch(error => setStatus(error.message));
  if (button?.dataset.resumeJob) return resumeBuild(button);
};
root.addEventListener('helps:tab', event => {
  if (event.detail === 'build') {
    refreshJobs();
    reviewMap?.invalidate();
  } else {
    clearTimeout(pollTimer);
  }
});
if (!panel.hidden) refreshJobs();

})(typeof window !== 'undefined' ? window : globalThis);
