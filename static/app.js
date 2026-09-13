const form = document.querySelector('#weather-form');
const results = document.querySelector('#results');
const loading = document.querySelector('#loading');
const errorMessage = document.querySelector('#form-error');
const submitButton = document.querySelector('#submit-button');
const missionBoard = document.querySelector('.mission-board');
const timestampInput = document.querySelector('#timestamp');

const setText = (id, value, suffix = '') => {
  document.querySelector(`#${id}`).textContent = value == null ? '--' : `${value}${suffix}`;
};

const formatUtc = (iso) => new Intl.DateTimeFormat('en', {
  year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  timeZone: 'UTC', timeZoneName: 'short'
}).format(new Date(iso));

const prettyModel = (model) => model.replace('open-meteo-', '').replace(' (', ' / ').replace(')', '');

const validateTimestamp = () => {
  const value = timestampInput.value;
  const valid = !value || /^(?:[1-9]\d{3})-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value);
  timestampInput.setCustomValidity(valid ? '' : 'The year must contain exactly 4 digits.');
  return valid;
};

timestampInput.addEventListener('input', validateTimestamp);
timestampInput.addEventListener('change', validateTimestamp);

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  errorMessage.textContent = '';
  if (!validateTimestamp() || !form.reportValidity()) {
    errorMessage.textContent = 'Enter a valid UTC time with a 4-digit year.';
    return;
  }
  results.hidden = true;
  missionBoard.classList.remove('has-results');
  loading.classList.add('is-visible');
  submitButton.disabled = true;

  const localTimestamp = document.querySelector('#timestamp').value;
  const payload = {
    latitude: document.querySelector('#latitude').value,
    longitude: document.querySelector('#longitude').value,
    timestamp: `${localTimestamp}:00Z`
  };

  try {
    const response = await fetch('/api/weather', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Unable to retrieve weather data.');

    document.querySelector('#result-location').textContent = `${Number(data.location.latitude).toFixed(4)}°, ${Number(data.location.longitude).toFixed(4)}°`;
    document.querySelector('#result-time').textContent = `Requested ${formatUtc(data.requested_timestamp_utc)}`;
    document.querySelector('#daylight-value').textContent = data.daylight_status.replace('_', ' ');
    setText('wind-speed', data.wind.speed_kt); setText('wind-gust', data.wind.gust_kt);
    setText('temperature', data.temperature_c); setText('cloud-cover', data.cloud_cover_pct);
    setText('visibility', data.visibility_m); setText('pressure', data.pressure_hpa);
    setText('current-rain', data.precipitation.current_hour_mm); setText('daily-rain', data.precipitation.last_24h_mm);
    setText('wind-direction', data.wind.direction_deg); document.querySelector('#observation-time').textContent = formatUtc(data.observation_time_utc);
    document.querySelector('#model').textContent = prettyModel(data.source.model);
    document.querySelector('#interpolation').textContent = data.source.interpolated.applied ? 'Applied between hourly values' : 'Not applied';
    document.querySelector('#retrieved').textContent = `Retrieved ${formatUtc(data.source.retrieved_at_utc)} · ${data.source.provider}`;
    results.hidden = false;
    missionBoard.classList.add('has-results');
  } catch (error) {
    errorMessage.textContent = error.message;
  } finally {
    loading.classList.remove('is-visible');
    submitButton.disabled = false;
  }
});
