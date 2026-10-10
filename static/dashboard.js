'use strict';
let revision = '', csrf = '', dirty = false, busy = false;
const form = document.querySelector('#settings');
const fields = document.querySelector('#fields');
function message(text, error = false) {
  const box = document.querySelector('#message');
  box.textContent = text; box.classList.toggle('error', error); box.style.display = 'block';
}
async function api(path, payload) {
  const options = payload === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf}, body: JSON.stringify(payload)};
  const response = await fetch(path, {...options, cache: 'no-store'});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Request failed.');
  return data;
}
async function load() {
  const data = await api('/api/settings');
  for (const [name, value] of Object.entries(data.values)) {
    const input = form.elements.namedItem(name);
    if (!input) continue;
    if (input.type === 'checkbox') input.checked = value;
    else input.value = value;
  }
  revision = data.revision; csrf = data.csrf; dirty = false; fields.disabled = false;
}
form.addEventListener('input', () => { dirty = true; });
form.addEventListener('change', () => { dirty = true; });
form.addEventListener('submit', async event => {
  event.preventDefault(); if (busy) return;
  const values = {};
  for (const input of form.elements) {
    if (!input.name) continue;
    values[input.name] = input.type === 'checkbox' ? input.checked : input.type === 'number' ? Number(input.value) : input.value;
  }
  busy = true; fields.disabled = true;
  try { const data = await api('/api/save', {revision, values}); revision = data.revision; dirty = false; message(data.message); }
  catch (error) { message(error.message, true); }
  finally { busy = false; fields.disabled = false; refresh(); }
});
document.querySelector('#apply').addEventListener('click', async () => {
  if (dirty) { message('Save your changes before applying, or reload to discard them.', true); return; }
  if (busy) return;
  busy = true; fields.disabled = true;
  try { const data = await api('/api/restart', {revision}); message(data.message); }
  catch (error) { message(error.message, true); }
  finally { busy = false; fields.disabled = false; refresh(); }
});
document.querySelector('#reload').addEventListener('click', async () => {
  if (dirty && !window.confirm('Discard unsaved changes and reload?')) return;
  try { await load(); message('Settings reloaded.'); } catch (error) { message(error.message, true); }
});
const preview = document.querySelector('#preview');
preview.addEventListener('load', () => { preview.hidden = false; document.querySelector('#preview-empty').hidden = true; });
preview.addEventListener('error', () => { preview.hidden = true; document.querySelector('#preview-empty').hidden = false; });
async function refresh() {
  try {
    const status = await api('/api/status');
    document.querySelector('#health').textContent = status.running ? status.active ? 'Display running' : 'Scheduled off' : 'Display not reporting';
    document.querySelector('#mode').textContent = status.running ? (status.mode || 'Starting').replaceAll('_', ' ') : 'Waiting for display';
    const spotify = {ready: 'Connected', reauth_required: 'Needs authorization', retryable: 'Reconnecting', disabled: 'Disabled'};
    document.querySelector('#spotify').textContent = status.running ? spotify[status.spotify] || 'Unknown' : '—';
    document.querySelector('#calendar').textContent = status.running ? status.calendar === 'ready' ? 'Connected' : status.calendar === 'disabled' ? 'Disabled' : 'Needs authorization' : '—';
    document.querySelector('#markets').textContent = !status.running ? '—' : status.markets_refresh_error ? 'Using cached data · retrying' : status.markets_updated_at ? 'Data available' : 'Waiting for data';
    document.querySelector('#apply-state').textContent = status.pending_restart ? 'Saved settings await application or a fresh display report.' : 'Saved settings are active.';
    if (status.running) preview.src = `/preview.png?t=${Date.now()}`;
    else { preview.hidden = true; document.querySelector('#preview-empty').hidden = false; }
  } catch (error) { document.querySelector('#health').textContent = 'Dashboard connection lost'; }
}
load().then(refresh).catch(error => message(error.message, true));
setInterval(refresh, 2000);
