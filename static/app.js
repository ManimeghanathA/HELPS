const form = document.querySelector('#weather-form');
const results = document.querySelector('#results');
const loading = document.querySelector('#loading');
const errorMessage = document.querySelector('#form-error');
const submitButton = document.querySelector('#submit-button');
const missionBoard = document.querySelector('.mission-board');
const timestampInput = document.querySelector('#timestamp');
const radarSpotsContainer = document.querySelector('#radar-spots-container');
const locationsList = document.querySelector('#locations-list');
const outOfRangeAlert = document.querySelector('#out-of-range-alert');
const outOfRangeText = document.querySelector('#out-of-range-text');
const radarSitesCount = document.querySelector('#radar-sites-count');
const radarClosestSite = document.querySelector('#radar-closest-site');
const sitesCountBadge = document.querySelector('#sites-count-badge');
const flightApproach = document.querySelector('#flight-approach');

const radarScaleInner = document.querySelector('#radar-scale-inner');
const radarScaleMiddle = document.querySelector('#radar-scale-middle');
const radarScaleOuter = document.querySelector('#radar-scale-outer');
const radarLegendRadius = document.querySelector('#radar-legend-radius');

// Radar Zoom & Scale State
let currentLandingData = null;
let currentWeatherData = null;
let selectedRangeMode = 'auto'; // 'auto' | '1' | '2' | '5' | '10'
let activeScaleRadiusKm = 1.0;

// Dark Mode Theme Controller (Pearl Green / Navy Blue / Raven Black)
const themeToggleBtn = document.querySelector('#theme-toggle-btn');
const themeToggleIcon = themeToggleBtn?.querySelector('.theme-toggle-icon');

const MOON_SVG = `
  <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
    <path d="M12.3 2a10 10 0 0 0-.19 20 10 10 0 0 0 8.7-5.06 1 1 0 0 0-1.12-1.46 8 8 0 1 1-8.85-12.36 1 1 0 0 0 .16-1.12 1 1 0 0 0-1.3-.4z"/>
  </svg>
`;

const SUN_SVG = `
  <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
    <path d="M12 7c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5zM2 13h2c.55 0 1-.45 1-1s-.45-1-1-1H2c-.55 0-1 .45-1 1s.45 1 1 1zm18 0h2c.55 0 1-.45 1-1s-.45-1-1-1h-2c-.55 0-1 .45-1 1s.45 1 1 1zM11 2v2c0 .55.45 1 1 1s1-.45 1-1V2c0-.55-.45-1-1-1s-1 .45-1 1zm0 18v2c0 .55.45 1 1 1s1-.45 1-1v-2c0-.55-.45-1-1-1s-1 .45-1 1zM5.99 4.58a.996.996 0 0 0-1.41 0 .996.996 0 0 0 0 1.41l1.06 1.06c.39.39 1.03.39 1.41 0s.39-1.03 0-1.41L5.99 4.58zm12.37 12.37a.996.996 0 0 0-1.41 0 .996.996 0 0 0 0 1.41l1.06 1.06c.39.39 1.03.39 1.41 0a.996.996 0 0 0 0-1.41l-1.06-1.06zm1.06-10.96a.996.996 0 0 0 0-1.41.996.996 0 0 0-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41s1.03.39 1.41 0l1.06-1.06zM7.05 18.36a.996.996 0 0 0 0-1.41.996.996 0 0 0-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41s1.03.39 1.41 0l1.06-1.06z"/>
  </svg>
`;

const applyTheme = (theme) => {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('helps_theme', theme);
  if (themeToggleIcon) {
    if (theme === 'dark') {
      themeToggleIcon.innerHTML = SUN_SVG;
      themeToggleBtn?.setAttribute('title', 'Switch to Day Mode');
      themeToggleBtn?.setAttribute('aria-label', 'Switch to Day Mode');
    } else {
      themeToggleIcon.innerHTML = MOON_SVG;
      themeToggleBtn?.setAttribute('title', 'Switch to Night Mode');
      themeToggleBtn?.setAttribute('aria-label', 'Switch to Night Mode');
    }
  }
};

const savedTheme = localStorage.getItem('helps_theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
applyTheme(savedTheme);

themeToggleBtn?.addEventListener('click', () => {
  const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  applyTheme(newTheme);
});

// Dynamic interactive mouse tracking gradient for Light and Dark Mode
let mouseMoveTicking = false;
window.addEventListener('pointermove', (e) => {
  if (!mouseMoveTicking) {
    window.requestAnimationFrame(() => {
      const xPercent = ((e.clientX / window.innerWidth) * 100).toFixed(1);
      const yPercent = ((e.clientY / window.innerHeight) * 100).toFixed(1);
      document.documentElement.style.setProperty('--mouse-x', `${xPercent}%`);
      document.documentElement.style.setProperty('--mouse-y', `${yPercent}%`);
      mouseMoveTicking = false;
    });
    mouseMoveTicking = true;
  }
}, { passive: true });

// Set default timestamp to the June 1, 2026 satellite baseline pass
if (!timestampInput.value) {
  timestampInput.value = '2026-06-01T12:00';
}

const setText = (id, value, suffix = '') => {
  const el = document.querySelector(`#${id}`);
  if (el) {
    el.textContent = value == null ? '--' : `${value}${suffix}`;
  }
};

const formatUtc = (iso) => new Intl.DateTimeFormat('en', {
  year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  timeZone: 'UTC', timeZoneName: 'short'
}).format(new Date(iso));

const prettyModel = (model) => model ? model.replace('open-meteo-', '').replace(' (', ' / ').replace(')', '') : '--';

const formatDist = (km) => {
  if (km < 1) {
    return `${Math.round(km * 1000)} m`;
  }
  return `${km.toFixed(km % 1 === 0 ? 0 : 1)} km`;
};

const validateTimestamp = () => {
  if (!timestampInput) return true;
  const value = timestampInput.value;
  const valid = !value || /^(?:[1-9]\d{3})-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value);
  if (typeof timestampInput.setCustomValidity === 'function') {
    timestampInput.setCustomValidity(valid ? '' : 'The year must contain exactly 4 digits.');
  }
  return valid;
};

timestampInput?.addEventListener('input', validateTimestamp);
timestampInput?.addEventListener('change', validateTimestamp);

// ----------------------------------------------------
// Interactive Satellite Map of India & Operational Boundaries
// ----------------------------------------------------
let satelliteMap = null;
let regionsLayerGroup = null;
let currentQueryMarker = null;

const initSatelliteMap = async () => {
  const mapElement = document.querySelector('#india-satellite-map');
  if (!mapElement || typeof L === 'undefined') return;

  // Initialize Map centered on Southern/Central India (Karnataka Focus)
  satelliteMap = L.map('india-satellite-map', {
    center: [14.50, 76.50],
    zoom: 7,
    minZoom: 4,
    maxZoom: 16,
    zoomControl: false,
    attributionControl: false
  });

  // Custom Zoom Control top-right
  L.control.zoom({ position: 'topright' }).addTo(satelliteMap);

  // Satellite Imagery Layer (ESRI World Imagery)
  const esriSatellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 18,
    attribution: 'Esri Satellite'
  }).addTo(satelliteMap);

  // CartoDB Dark Labels layer overlay for crisp geographical names
  L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}{r}.png', {
    maxZoom: 18,
    subdomains: 'abcd',
    opacity: 0.8
  }).addTo(satelliteMap);

  regionsLayerGroup = L.layerGroup().addTo(satelliteMap);

  // Fetch real GeoJSON operational region boundaries from Flask endpoint
  try {
    const res = await fetch('/api/operational-regions');
    if (!res.ok) throw new Error('Failed to load operational regions');
    const geojsonData = await res.json();

    const statusStyles = {
      ready: {
        color: '#22c55e',
        fillColor: '#16a34a',
        fillOpacity: 0.28,
        weight: 2.5,
        dashArray: null
      },
      in_progress: {
        color: '#eab308',
        fillColor: '#ca8a04',
        fillOpacity: 0.22,
        weight: 2,
        dashArray: '6, 6'
      },
      under_consideration: {
        color: '#ef4444',
        fillColor: '#dc2626',
        fillOpacity: 0.18,
        weight: 2,
        dashArray: '4, 4'
      }
    };

    const geojsonLayer = L.geoJSON(geojsonData, {
      style: (feature) => {
        const status = feature.properties.status || 'under_consideration';
        return statusStyles[status] || statusStyles.under_consideration;
      },
      onEachFeature: (feature, layer) => {
        const props = feature.properties;
        const popupContent = `
          <div style="font-family:'Courier Prime',monospace; padding:2px;">
            <h4 style="color:${props.color}; margin:0 0 6px 0; font-size:12px; text-transform:uppercase;">${props.name}</h4>
            <p style="margin:2px 0; font-size:11px;"><strong>Status:</strong> <span style="color:${props.color}; font-weight:700;">${props.status_label}</span></p>
            <p style="margin:2px 0; font-size:11px;"><strong>Sites Available:</strong> ${props.sites_count > 0 ? props.sites_count.toLocaleString() + ' Verified Zones' : 'Pipeline Processing'}</p>
            <p style="margin:4px 0 8px 0; font-size:10px; color:#cbd5e1; line-height:1.3;">${props.description}</p>
            ${props.status === 'ready' ? `<button type="button" class="region-popup-action" data-lat="${props.center[0]}" data-lon="${props.center[1]}">Select &amp; Scan Region &nearr;</button>` : `<span style="font-size:10px; color:#94a3b8; font-style:italic;">Data acquisition in progress</span>`}
          </div>
        `;
        layer.bindPopup(popupContent, { maxWidth: 280 });

        layer.on('mouseover', function () {
          this.setStyle({
            weight: 3.5,
            fillOpacity: 0.45
          });
          const focusEl = document.querySelector('#active-sector-name');
          const statusEl = document.querySelector('#active-sector-status');
          if (focusEl) focusEl.textContent = props.name;
          if (statusEl) {
            statusEl.textContent = props.status_label;
            statusEl.style.color = props.color;
          }
        });

        layer.on('mouseout', function () {
          const status = props.status || 'under_consideration';
          this.setStyle(statusStyles[status]);
        });

        layer.on('click', function () {
          if (props.center) {
            document.querySelector('#latitude').value = props.center[0];
            document.querySelector('#longitude').value = props.center[1];
          }
        });
      }
    }).addTo(regionsLayerGroup);

    // Focus map by default on the entire South India peninsula
    satelliteMap.setView([13.0, 77.5], 6);
  } catch (err) {
    console.error('Error rendering operational regions on satellite map:', err);
    satelliteMap.setView([13.0, 77.5], 6);
  }
};

// Initialize Satellite Map on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  initSatelliteMap();
});

// Delegate click from region popup action buttons
document.addEventListener('click', (e) => {
  const btn = e.target.closest('.region-popup-action');
  if (btn) {
    const lat = btn.getAttribute('data-lat');
    const lon = btn.getAttribute('data-lon');
    if (lat && lon) {
      document.querySelector('#latitude').value = lat;
      document.querySelector('#longitude').value = lon;
      form.dispatchEvent(new Event('submit', { cancelable: true }));
    }
  }
});

// Preset region chips
document.querySelectorAll('.preset-chip').forEach((chip) => {
  chip.addEventListener('click', (e) => {
    e.preventDefault();
    const lat = parseFloat(chip.getAttribute('data-lat'));
    const lon = parseFloat(chip.getAttribute('data-lon'));
    document.querySelector('#latitude').value = lat;
    document.querySelector('#longitude').value = lon;
    form.dispatchEvent(new Event('submit', { cancelable: true }));
  });
});

// Shorten zone ID for compact radar blip label
const shortZoneName = (zoneId) => {
  if (!zoneId) return 'SPOT';
  const parts = zoneId.split('_');
  const num = parts[parts.length - 1];
  return `Z-${parseInt(num, 10) || num}`;
};

// Compute optimal adaptive zoom diameter from closest points
const computeAdaptiveRadius = (spots) => {
  if (!spots || spots.length === 0) {
    return 10.0;
  }
  // Look at closest 5 spots to choose a responsive framing
  const sample = spots.slice(0, Math.min(5, spots.length));
  const maxSampleDist = Math.max(...sample.map(s => s.distance_km));

  if (maxSampleDist <= 0.5) return 0.75;
  if (maxSampleDist <= 0.8) return 1.0;
  if (maxSampleDist <= 1.5) return 2.0;
  if (maxSampleDist <= 3.5) return 5.0;
  return 10.0;
};

// Update ring text and legend labels
const updateRadarScaleLabels = (radiusKm) => {
  if (radarScaleInner) radarScaleInner.textContent = formatDist(radiusKm * 0.25);
  if (radarScaleMiddle) radarScaleMiddle.textContent = formatDist(radiusKm * 0.50);
  if (radarScaleOuter) radarScaleOuter.textContent = formatDist(radiusKm);
  if (radarLegendRadius) radarLegendRadius.textContent = `${formatDist(radiusKm)} scan radius`;
};

// Render tactical radar blips based on the current active scale radius
const renderRadarBlips = () => {
  radarSpotsContainer.innerHTML = '';
  if (!currentLandingData) return;

  const spots = currentLandingData.spots || [];
  const radiusKm = activeScaleRadiusKm;
  let visibleCount = 0;

  spots.forEach((spot) => {
    const dist = spot.distance_km;
    // Show spots within current zoom frame (with a slight overflow margin)
    if (dist > radiusKm * 1.08) {
      return;
    }

    visibleCount++;
    const shortName = shortZoneName(spot.zone_id);
    const suitability = spot.suitability || {};
    const statusCode = suitability.status_code || 'optimal';

    // Compute polar coordinates for current zoom diameter
    const rad = (spot.bearing_deg * Math.PI) / 180.0;
    const normDist = Math.min(1.0, dist / radiusKm);
    const radarX = (50.0 + normDist * 44.0 * Math.sin(rad)).toFixed(2);
    const radarY = (50.0 - normDist * 44.0 * Math.cos(rad)).toFixed(2);

    const blip = document.createElement('div');
    blip.className = `landing-spot landing-spot--${statusCode}`;
    blip.id = `blip-${spot.zone_id}`;
    blip.style.left = `${radarX}%`;
    blip.style.top = `${radarY}%`;
    blip.tabIndex = 0;
    blip.setAttribute('aria-label', `Landing spot ${shortName}, distance ${spot.distance_km} km`);

    blip.innerHTML = `
      <span></span>
      <b>${shortName}</b>
      <div class="spot-detail">
        <strong>
          <span>${spot.zone_id}</span>
          <span class="spot-score-chip spot-score-chip--${statusCode}">${suitability.score}%</span>
        </strong>
        <small><strong>Distance:</strong> ${spot.distance_km} km (${spot.bearing_deg}° ${spot.compass})</small>
        <small><strong>Usable Area:</strong> ${spot.area_m2.toLocaleString()} m² (${spot.length_m} × ${spot.width_m} m)</small>
        <small><strong>Max Clearance:</strong> ${spot.max_clear_diameter_m} m (${spot.clearance_label})</small>
        <small><strong>Suitability:</strong> ${suitability.status}</small>
      </div>
    `;

    // Synchronize hover & click between radar blip and location card
    const highlightSpot = () => {
      document.querySelectorAll('.landing-spot.is-highlighted').forEach(el => el.classList.remove('is-highlighted'));
      document.querySelectorAll('.location-card.is-active').forEach(el => el.classList.remove('is-active'));
      blip.classList.add('is-highlighted');
      const card = document.querySelector(`#card-${spot.zone_id}`);
      if (card) {
        card.classList.add('is-active');
        card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    };

    const unhighlightSpot = () => {
      blip.classList.remove('is-highlighted');
      const card = document.querySelector(`#card-${spot.zone_id}`);
      if (card) card.classList.remove('is-active');
    };

    blip.addEventListener('mouseenter', highlightSpot);
    blip.addEventListener('mouseleave', unhighlightSpot);
    blip.addEventListener('click', highlightSpot);

    radarSpotsContainer.appendChild(blip);
  });

  // Update summary line
  if (spots.length > 0) {
    const closest = spots[0];
    const modeLabel = selectedRangeMode === 'auto' ? ' (Adaptive Zoom)' : '';
    radarSitesCount.textContent = `${visibleCount} visible in ${formatDist(radiusKm)}${modeLabel}`;
    radarClosestSite.textContent = `Closest: ${closest.distance_km} km ${closest.compass}`;
  }
};

// Helicopter Fleet Profiles Info Cache for dynamic hint display
const HELI_SPECS = {
  hal_dhruv: 'HAL Dhruv: Rotor ⌀13.2 m · Req Footprint ⌀27.0 m · Max Slope 10° · Max Crosswind 25 kt · Cruise 130 kt',
  hal_prachand: 'HAL Prachand (LCH): Rotor ⌀13.3 m · Req Footprint ⌀28.0 m · Max Slope 12° · Max Crosswind 30 kt · Cruise 140 kt',
  hal_luh: 'HAL LUH: Rotor ⌀11.6 m · Req Footprint ⌀24.0 m · Max Slope 10° · Max Crosswind 22 kt · Cruise 125 kt',
  mi_17: 'Mil Mi-17 V5: Rotor ⌀21.3 m · Req Footprint ⌀45.0 m · Max Slope 7° · Max Crosswind 20 kt · Cruise 120 kt',
  ec_135: 'Eurocopter EC135: Rotor ⌀10.2 m · Req Footprint ⌀21.0 m · Max Slope 12° · Max Crosswind 30 kt · Cruise 135 kt'
};

const helicopterSelect = document.querySelector('#helicopter-model');
const missionSelect = document.querySelector('#mission-context');
const heliSpecsText = document.querySelector('#heli-specs-text');

if (helicopterSelect && heliSpecsText) {
  helicopterSelect.addEventListener('change', () => {
    heliSpecsText.textContent = HELI_SPECS[helicopterSelect.value] || HELI_SPECS.hal_dhruv;
  });
}

// Render location briefing cards list
const renderLocationsList = () => {
  locationsList.innerHTML = '';
  if (!currentLandingData) return;

  const spots = currentLandingData.spots || [];
  const totalInRange = currentLandingData.total_candidates_in_range || 0;
  const nearestDist = currentLandingData.nearest_available_distance_km;
  const heliInfo = currentLandingData.helicopter || {};

  if (totalInRange > 0) {
    sitesCountBadge.textContent = totalInRange;
    outOfRangeAlert.hidden = true;
  } else {
    sitesCountBadge.textContent = '0';
    outOfRangeAlert.hidden = false;
    outOfRangeText.textContent = nearestDist != null
      ? `Nearest verified landing zone is ${nearestDist} km away in the Bhadra region. Use a preset above to inspect active clusters.`
      : 'No verified landing zones found near these coordinates in the database.';
    return;
  }

  spots.forEach((spot) => {
    const shortName = shortZoneName(spot.zone_id);
    const suitability = spot.suitability || {};
    const statusCode = suitability.status_code || 'optimal';
    const rank = spot.rank || 1;
    const margin = suitability.clearance_margin_m != null ? suitability.clearance_margin_m : 0;
    const marginClass = margin >= 5.0 ? 'pass' : (margin >= 0 ? 'tight' : 'fail');
    const marginText = margin >= 0 ? `+${margin} m` : `${margin} m`;
    const etaText = suitability.eta_seconds != null ? (suitability.eta_seconds < 60 ? `${suitability.eta_seconds}s` : `${Math.round(suitability.eta_seconds / 60)}m`) : '--';

    const card = document.createElement('article');
    card.className = `location-card`;
    card.id = `card-${spot.zone_id}`;
    card.innerHTML = `
      <div class="location-card-top">
        <div class="location-card-header-left">
          <span class="location-rank-badge location-rank-badge--${Math.min(rank, 3)}">#${rank}</span>
          <span class="location-card-id">${spot.zone_id} &middot; ${shortName}</span>
        </div>
        <span class="location-card-badge location-card-badge--${statusCode}">
          ${suitability.summary_badge} (${suitability.score}%)
        </span>
      </div>
      <div class="location-card-metrics">
        <div>
          <dt>Distance / Bearing</dt>
          <dd>${spot.distance_km} km &middot; ${spot.compass}</dd>
        </div>
        <div>
          <dt>ETA (${heliInfo.cruise_speed_kt || 130} kt)</dt>
          <dd>${etaText}</dd>
        </div>
        <div>
          <dt>Usable Area</dt>
          <dd>${spot.area_m2.toLocaleString()} m²</dd>
        </div>
        <div>
          <dt>Clearance Margin</dt>
          <dd class="location-margin--${marginClass}">⌀${spot.max_clear_diameter_m}m (${marginText})</dd>
        </div>
      </div>
      <div class="location-card-footer">
        <div class="location-card-footer-row">
          <span class="location-card-approach">${suitability.recommended_approach || 'Clear flight corridor'}</span>
          <span>${spot.size_class}</span>
        </div>
        <div class="location-card-rationale">
          ${suitability.rationale || 'Candidate verified via terrain and building subtraction database.'}
        </div>
      </div>
    `;

    const highlightCard = () => {
      document.querySelectorAll('.landing-spot.is-highlighted').forEach(el => el.classList.remove('is-highlighted'));
      document.querySelectorAll('.location-card.is-active').forEach(el => el.classList.remove('is-active'));
      card.classList.add('is-active');
      const blip = document.querySelector(`#blip-${spot.zone_id}`);
      if (blip) {
        blip.classList.add('is-highlighted');
      }
    };

    const unhighlightCard = () => {
      card.classList.remove('is-active');
      const blip = document.querySelector(`#blip-${spot.zone_id}`);
      if (blip) blip.classList.remove('is-highlighted');
    };

    card.addEventListener('mouseenter', highlightCard);
    card.addEventListener('mouseleave', unhighlightCard);
    card.addEventListener('click', highlightCard);

    locationsList.appendChild(card);
  });
};

// Recompute radar scale and re-render
const applyRadarZoom = (rangeMode) => {
  selectedRangeMode = rangeMode;

  document.querySelectorAll('.range-btn').forEach((btn) => {
    btn.classList.toggle('is-active', btn.getAttribute('data-range') === String(rangeMode));
  });

  if (rangeMode === 'auto') {
    activeScaleRadiusKm = computeAdaptiveRadius(currentLandingData ? currentLandingData.spots : []);
  } else {
    activeScaleRadiusKm = parseFloat(rangeMode) || 10.0;
  }

  updateRadarScaleLabels(activeScaleRadiusKm);
  renderRadarBlips();
};

// Wire Range Toolbar Buttons
document.querySelectorAll('.range-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    const range = btn.getAttribute('data-range');
    applyRadarZoom(range);
  });
});

// Wire Zoom Stepper Buttons (+ / -)
const rangeSteps = [0.5, 1.0, 2.0, 5.0, 10.0];

document.querySelector('#zoom-in-btn')?.addEventListener('click', () => {
  let next = rangeSteps.filter(r => r < activeScaleRadiusKm).pop();
  if (!next) next = 0.5;
  applyRadarZoom(next);
});

document.querySelector('#zoom-out-btn')?.addEventListener('click', () => {
  let next = rangeSteps.find(r => r > activeScaleRadiusKm);
  if (!next) next = 10.0;
  applyRadarZoom(next);
});

// Main Search Form Submission
form.addEventListener('submit', async (event) => {
  event.preventDefault();
  errorMessage.textContent = '';
  if (!validateTimestamp() || !form.reportValidity()) {
    errorMessage.textContent = 'Enter a valid UTC time with a 4-digit year.';
    return;
  }
  loading.classList.add('is-visible');
  submitButton.disabled = true;

  const localTimestamp = document.querySelector('#timestamp').value;
  const heliModel = document.querySelector('#helicopter-model')?.value || 'hal_dhruv';
  const missionContext = document.querySelector('#mission-context')?.value || 'hybrid_balanced';

  const payload = {
    latitude: document.querySelector('#latitude').value,
    longitude: document.querySelector('#longitude').value,
    timestamp: `${localTimestamp}:00Z`,
    helicopter_model: heliModel,
    mission_context: missionContext
  };

  try {
    const response = await fetch('/api/weather', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Unable to retrieve telemetry data.');

    // Save global state
    currentWeatherData = data;
    currentLandingData = data.landing_zones;

    // Populate Weather Information
    document.querySelector('#result-location').textContent = `${Number(data.location.latitude).toFixed(4)}°, ${Number(data.location.longitude).toFixed(4)}°`;
    document.querySelector('#result-time').textContent = `Requested ${formatUtc(data.requested_timestamp_utc)}`;
    document.querySelector('#daylight-value').textContent = data.daylight_status.replace('_', ' ');
    setText('wind-speed', data.wind.speed_kt);
    setText('wind-gust', data.wind.gust_kt);
    setText('temperature', data.temperature_c);
    setText('cloud-cover', data.cloud_cover_pct);
    setText('visibility', data.visibility_m);
    setText('pressure', data.pressure_hpa);
    setText('current-rain', data.precipitation.current_hour_mm);
    setText('daily-rain', data.precipitation.last_24h_mm);
    setText('wind-direction', data.wind.direction_deg);
    document.querySelector('#observation-time').textContent = formatUtc(data.observation_time_utc);

    // Populate Aircraft & Mission details
    const heliInfo = data.landing_zones?.helicopter || {};
    const missionInfo = data.landing_zones?.mission || {};
    const heliNameEl = document.querySelector('#heli-profile-name');
    if (heliNameEl) heliNameEl.textContent = heliInfo.name || 'HAL Dhruv';
    const heliFootprintEl = document.querySelector('#heli-footprint-info');
    if (heliFootprintEl) heliFootprintEl.textContent = `Req ⌀${heliInfo.min_clear_diameter_m || 27.0} m · Max Slope ${heliInfo.max_slope_deg || 10}° · Max X-Wind ${heliInfo.max_crosswind_kt || 25} kt`;
    const missionPriorityEl = document.querySelector('#mission-priority-name');
    if (missionPriorityEl) missionPriorityEl.textContent = `${missionInfo.name || 'Hybrid'} (${missionInfo.priority_focus || ''})`;

    document.querySelector('#retrieved').textContent = `Retrieved ${formatUtc(data.source.retrieved_at_utc)} · ${data.source.provider}`;

    // Approach vector recommendation
    const windDir = data.wind.direction_deg || 0;
    const speed = data.wind.speed_kt || 0;
    const headwindHeading = Math.round((windDir + 180) % 360);
    if (flightApproach) {
      flightApproach.textContent = `Heading ${String(headwindHeading).padStart(3, '0')}° into ${String(windDir).padStart(3, '0')}° wind (${speed} kt)`;
    }

    // Render Landing Zones with Responsive Adaptive Zoom
    applyRadarZoom(selectedRangeMode);
    renderLocationsList();
    renderTacticalMapSpots(data);

    results.hidden = false;
    missionBoard.classList.add('has-results');
  } catch (error) {
    errorMessage.textContent = error.message;
  } finally {
    loading.classList.remove('is-visible');
    submitButton.disabled = false;
  }
});

// Return to Satellite Overview / Landing Page
const returnToLandingPage = () => {
  missionBoard.classList.remove('has-results');
  results.hidden = true;
  loading.classList.remove('is-visible');
  if (errorMessage) errorMessage.textContent = '';
  
  if (satelliteMap) {
    setTimeout(() => {
      satelliteMap.invalidateSize();
      satelliteMap.setView([13.0, 77.5], 6);
    }, 100);
  }
};

document.querySelector('#top-back-to-map-btn')?.addEventListener('click', returnToLandingPage);
document.querySelector('#radar-back-to-map-btn')?.addEventListener('click', returnToLandingPage);
document.querySelector('#results-back-to-map-btn')?.addEventListener('click', returnToLandingPage);
document.querySelectorAll('.back-to-map-btn').forEach(btn => btn.addEventListener('click', returnToLandingPage));

// ----------------------------------------------------
// Tactical Geospatial Map (Result Page View 2)
// ----------------------------------------------------
let tacticalMap = null;
let tacticalQueryMarker = null;
let tacticalSpotsLayer = null;
let tacticalRadiusCircle = null;

const initTacticalMap = () => {
  const mapElement = document.querySelector('#tactical-satellite-map');
  if (!mapElement || typeof L === 'undefined' || tacticalMap) return;

  tacticalMap = L.map('tactical-satellite-map', {
    center: [13.78, 75.66],
    zoom: 13,
    minZoom: 6,
    maxZoom: 18,
    zoomControl: true,
    attributionControl: false
  });

  // Esri World Imagery (Satellite)
  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 18,
    attribution: 'Esri Satellite'
  }).addTo(tacticalMap);

  // CartoDB Labels overlay
  L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}{r}.png', {
    maxZoom: 18,
    subdomains: 'abcd',
    opacity: 0.8
  }).addTo(tacticalMap);

  tacticalSpotsLayer = L.layerGroup().addTo(tacticalMap);
};

// Render landing spots on the Tactical Satellite Map
const renderTacticalMapSpots = (data) => {
  if (!tacticalMap) {
    initTacticalMap();
  }
  if (!tacticalMap || !tacticalSpotsLayer) return;

  tacticalSpotsLayer.clearLayers();

  const queryLat = parseFloat(data.location.latitude);
  const queryLon = parseFloat(data.location.longitude);

  if (isNaN(queryLat) || isNaN(queryLon)) return;

  // Custom icon for the query center point
  const queryCenterIcon = L.divIcon({
    className: 'custom-query-marker',
    html: `<div style="
      width: 18px;
      height: 18px;
      background: #ff5252;
      border: 2.5px solid #ffffff;
      border-radius: 50%;
      box-shadow: 0 0 10px rgba(255, 82, 82, 0.9);
      display: flex;
      align-items: center;
      justify-content: center;
    "><div style="width: 4px; height: 4px; background: #ffffff; border-radius: 50%;"></div></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9]
  });

  tacticalQueryMarker = L.marker([queryLat, queryLon], { icon: queryCenterIcon })
    .bindPopup(`
      <div style="font-family:'Courier Prime',monospace; padding:4px;">
        <h4 style="margin:0 0 4px; color:#ff5252; font-size:12px; text-transform:uppercase;">QUERY POINT</h4>
        <p style="margin:2px 0; font-size:11px;"><strong>Coordinates:</strong> ${queryLat.toFixed(4)}°, ${queryLon.toFixed(4)}°</p>
        <p style="margin:2px 0; font-size:11px;"><strong>Weather:</strong> ${data.temperature_c}°C · Wind ${data.wind.speed_kt} kt (${data.wind.direction_deg}°)</p>
      </div>
    `)
    .addTo(tacticalSpotsLayer);

  // Active Radius Circle (e.g. 10km search radius)
  const radiusMeters = 10000;
  tacticalRadiusCircle = L.circle([queryLat, queryLon], {
    radius: radiusMeters,
    color: '#38bdf8',
    weight: 1.5,
    dashArray: '5, 5',
    fillColor: '#0284c7',
    fillOpacity: 0.05
  }).addTo(tacticalSpotsLayer);

  const spots = data.landing_zones?.spots || [];
  const statusColors = {
    optimal: '#84cc16',
    caution: '#f59e0b',
    warning: '#ef4444'
  };

  const spotMarkers = [];

  spots.forEach((spot) => {
    const lat = spot.latitude != null ? spot.latitude : spot.center_lat;
    const lon = spot.longitude != null ? spot.longitude : spot.center_lon;
    if (lat == null || lon == null) return;

    const shortName = shortZoneName(spot.zone_id);
    const suitability = spot.suitability || {};
    const statusCode = suitability.status_code || 'optimal';
    const color = statusColors[statusCode] || '#84cc16';
    const rank = spot.rank || 1;

    const popupHtml = `
      <div style="font-family:'Courier Prime',monospace; padding:4px; max-width:260px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; border-bottom:1px solid #334155; padding-bottom:4px;">
          <strong style="color:${color}; font-size:12px;">#${rank} ${spot.zone_id}</strong>
          <span style="background:${color}; color:#0b141a; padding:1px 6px; border-radius:2px; font-size:10px; font-weight:700;">${suitability.score}% MATCH</span>
        </div>
        <p style="margin:3px 0; font-size:11px;"><strong>Status:</strong> <span style="color:${color}; font-weight:700;">${suitability.status || 'Landable Area'}</span></p>
        <p style="margin:3px 0; font-size:11px;"><strong>Distance:</strong> ${spot.distance_km} km (${spot.bearing_deg}° ${spot.compass})</p>
        <p style="margin:3px 0; font-size:11px;"><strong>Clearance:</strong> ⌀${spot.max_clear_diameter_m} m (${spot.clearance_label || 'Safe'})</p>
        <p style="margin:3px 0; font-size:11px;"><strong>Usable Area:</strong> ${spot.area_m2.toLocaleString()} m²</p>
        <p style="margin:3px 0; font-size:11px;"><strong>Dimensions:</strong> ${spot.length_m} m × ${spot.width_m} m</p>
        <p style="margin:3px 0; font-size:11px;"><strong>Slope:</strong> ${spot.slope_deg != null ? spot.slope_deg + '°' : '--'}</p>
        <p style="margin:6px 0 0; font-size:10px; color:#cbd5e1; line-height:1.3; font-style:italic;">${suitability.briefing || suitability.rationale || ''}</p>
      </div>
    `;

    const onZoneSelect = () => {
      document.querySelectorAll('.location-card.is-active').forEach(el => el.classList.remove('is-active'));
      const card = document.querySelector(`#card-${spot.zone_id}`);
      if (card) {
        card.classList.add('is-active');
        card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    };

    // 1. Draw Exact Landable Area Polygon from annotations if available, or fall back to subtle bounds
    let polyLayer = null;

    if (spot.polygon && Array.isArray(spot.polygon) && spot.polygon.length > 2) {
      polyLayer = L.polygon(spot.polygon, {
        color: color,
        weight: 2.5,
        fillColor: color,
        fillOpacity: 0.35,
      });
      polyLayer.bindPopup(popupHtml);
      polyLayer.on('click', onZoneSelect);
      polyLayer.on('mouseover', function() {
        this.setStyle({ weight: 4, fillOpacity: 0.6 });
      });
      polyLayer.on('mouseout', function() {
        this.setStyle({ weight: 2.5, fillOpacity: 0.35 });
      });
      polyLayer.addTo(tacticalSpotsLayer);
      spotMarkers.push(polyLayer);
    } else if (spot.bbox && Array.isArray(spot.bbox) && spot.bbox.length === 4) {
      // Fallback only if raw polygon vertices are missing
      const bounds = [[spot.bbox[0], spot.bbox[1]], [spot.bbox[2], spot.bbox[3]]];
      polyLayer = L.rectangle(bounds, {
        color: color,
        weight: 2,
        fillColor: color,
        fillOpacity: 0.35
      });
      polyLayer.bindPopup(popupHtml);
      polyLayer.on('click', onZoneSelect);
      polyLayer.addTo(tacticalSpotsLayer);
      spotMarkers.push(polyLayer);
    }

    // 2. Compact Badge Tag Marker placed directly on the landing zone center
    const labelLat = lat;
    const labelLon = lon;
    const badgeIcon = L.divIcon({
      className: 'custom-spot-marker',
      html: `
        <div style="
          background: ${color};
          color: #0b141a;
          font-family: 'Courier Prime', monospace;
          font-weight: 700;
          font-size: 11px;
          padding: 2px 6px;
          border-radius: 3px;
          border: 1.5px solid #ffffff;
          box-shadow: 0 2px 8px rgba(0,0,0,0.6);
          white-space: nowrap;
          transform: translate(-50%, -50%);
          cursor: pointer;
        ">#${rank} ${shortName}</div>
      `,
      iconSize: [0, 0]
    });

    const labelMarker = L.marker([labelLat, labelLon], { icon: badgeIcon });
    labelMarker.bindPopup(popupHtml);
    labelMarker.on('click', onZoneSelect);
    labelMarker.addTo(tacticalSpotsLayer);
    spotMarkers.push(labelMarker);
  });

  // Zoom bounds to include query point and spots
  if (spotMarkers.length > 0) {
    const group = L.featureGroup([tacticalQueryMarker, ...spotMarkers]);
    tacticalMap.fitBounds(group.getBounds(), { padding: [40, 40], maxZoom: 15 });
  } else {
    tacticalMap.setView([queryLat, queryLon], 13);
  }
};

// View Switcher (Radar View vs Map View) Tab Event Handlers
const viewTabRadar = document.querySelector('#view-tab-radar');
const viewTabMap = document.querySelector('#view-tab-map');
const tacticalRadarView = document.querySelector('#tactical-radar-view');
const tacticalMapView = document.querySelector('#tactical-map-view');
const visualizerTitle = document.querySelector('#tactical-view-title');

const switchVisualizerView = (view) => {
  if (view === 'radar') {
    viewTabRadar?.classList.add('is-active');
    viewTabMap?.classList.remove('is-active');
    if (tacticalRadarView) tacticalRadarView.style.display = 'flex';
    if (tacticalMapView) tacticalMapView.style.display = 'none';
    if (visualizerTitle) visualizerTitle.textContent = 'Landing Zone Scan';
  } else {
    viewTabMap?.classList.add('is-active');
    viewTabRadar?.classList.remove('is-active');
    if (tacticalRadarView) tacticalRadarView.style.display = 'none';
    if (tacticalMapView) tacticalMapView.style.display = 'flex';
    if (visualizerTitle) visualizerTitle.textContent = 'Tactical Geospatial Map';

    if (!tacticalMap) {
      initTacticalMap();
    }
    setTimeout(() => {
      if (tacticalMap) {
        tacticalMap.invalidateSize();
        if (currentWeatherData) {
          renderTacticalMapSpots(currentWeatherData);
        }
      }
    }, 80);
  }
};

viewTabRadar?.addEventListener('click', () => switchVisualizerView('radar'));
viewTabMap?.addEventListener('click', () => switchVisualizerView('map'));


