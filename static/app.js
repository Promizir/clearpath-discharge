'use strict';
const $ = id => document.getElementById(id);
const originalNote = $('doctor-note').value;
let current = null;
let busy = false;
let pollTimer = null;
let pollGeneration = 0;
let aiEnabled = false;

function notice(message, error = false) {
  $('notice').textContent = message;
  $('notice').className = error ? 'error' : '';
  $('notice').hidden = false;
}
async function api(path, method = 'GET', body) {
  const response = await fetch(path, {
    method, headers: {'Content-Type': 'application/json'},
    ...(body === undefined ? {} : {body: JSON.stringify(body)})
  });
  const result = await response.json();
  if (!response.ok) {
    const detail = Array.isArray(result.detail)
      ? result.detail.map(e => `${e.loc.slice(1).join('.')}: ${e.msg}`).join('; ')
      : result.detail || 'The request could not be completed.';
    throw new Error(detail);
  }
  return result;
}
function textElement(tag, text, className = '') {
  const element = document.createElement(tag);
  element.textContent = text;
  element.className = className;
  return element;
}
function setBusy(value, button) {
  busy = value;
  document.querySelectorAll('button.busy').forEach(el => el.classList.remove('busy'));
  if (value && button) button.classList.add('busy');
  renderControls();
}
function renderControls() {
  const state = current?.snapshot;
  $('create-draft').disabled = busy;
  $('new-case').disabled = busy;
  $('save-note').disabled = busy || !state;
  $('approve-draft').disabled = busy || !state || state.draft.status === 'DOCTOR_APPROVED';
  $('run-checks').disabled = busy || !state || state.draft.status !== 'DOCTOR_APPROVED';
  $('download-report').disabled = busy || !state;
  $('copy-id').disabled = !state;
  $('load-example').disabled = busy;
}
function flow(id, state, message) {
  const el = $(id);
  el.classList.remove('done', 'flagged', 'running');
  if (state) el.classList.add(state);
  el.querySelector('small').textContent = message;
}
function finding(kind, label, title, description, lines = []) {
  const card = textElement('article', '', `finding ${kind}`);
  card.append(textElement('div', label, 'finding-label'), textElement('h3', title), textElement('p', description));
  if (lines.length) {
    const list = document.createElement('ul');
    lines.forEach(line => list.append(textElement('li', line)));
    card.append(list);
  }
  return card;
}
function render() {
  const state = current?.snapshot;
  $('draft-empty').hidden = Boolean(state);
  $('draft-content').hidden = !state;
  $('revision-badge').textContent = state ? `Revision ${state.revision}` : 'No draft';
  $('workflow-label').textContent = current ? `Workflow ${current.workflow_id.slice(0, 8)} · Revision ${state.revision}` : 'Create a workflow to begin';
  $('snapshot-json').textContent = current ? JSON.stringify(current, null, 2) : 'No workflow selected.';
  $('findings').replaceChildren();
  if (!state) {
    flow('flow-draft', '', 'Approval required'); flow('flow-pharmacy', '', 'Waiting'); flow('flow-billing', '', 'Waiting');
    $('findings').append(finding('', 'AWAITING INPUT', 'Ready when you are', 'Prepare and approve a draft to run the independent checks.'));
    renderControls(); return;
  }
  const draft = state.draft;
  const approved = draft.status === 'DOCTOR_APPROVED';
  $('generation-badge').textContent = draft.generation_mode === 'MOCK' ? 'Structured demo draft' : `${draft.generation_mode} · AI draft`;
  $('approval-badge').textContent = approved ? 'Doctor approved' : 'Awaiting doctor review';
  $('approval-badge').className = `badge ${approved ? 'green' : 'amber'}`;
  $('draft-encounter').textContent = `${draft.encounter.primary_diagnosis} · ${draft.encounter.procedure_performed}`;
  if (document.activeElement !== $('review-note')) $('review-note').value = draft.doctor_note;
  $('ai-summary-section').hidden = !draft.clinical_summary;
  $('ai-summary').textContent = draft.clinical_summary || '';
  $('ai-review-notes').replaceChildren(...draft.review_notes.map(note => textElement('li', note)));
  $('model-evidence').textContent = draft.model_name ? `Model: ${draft.model_name} · ${draft.inference_ms} ms` : '';
  $('draft-medicines').replaceChildren(...draft.proposed_medications.map(med => textElement('span', med.name)));
  if (!draft.proposed_medications.length) $('draft-medicines').append(textElement('span', 'No medicines supplied'));
  flow('flow-draft', approved ? 'done' : '', approved ? `Revision ${state.revision} approved` : 'Approval required');
  const running = state.parallel_status === 'RUNNING';
  const pharmacy = state.pharmacy_result, billing = state.billing_result;
  flow('flow-pharmacy', running ? 'running' : pharmacy?.flags.length ? 'flagged' : pharmacy ? 'done' : '', running ? 'Checking…' : pharmacy ? (pharmacy.flags.length ? 'Review required' : 'No demo rule match') : 'Waiting');
  flow('flow-billing', running ? 'running' : billing?.discrepancies.length ? 'flagged' : billing ? 'done' : '', running ? 'Reconciling…' : billing ? (billing.discrepancies.length ? 'Differences found' : 'Quantities match') : 'Waiting');
  if (pharmacy) $('findings').append(finding(pharmacy.flags.length ? 'pharmacy' : 'success', 'PHARMACY REVIEW', pharmacy.flags.length ? 'Medication conflict detected' : 'No match in the demo rule', pharmacy.flags.length ? 'The proposed medication conflicts with a documented allergy in the demonstration rule.' : 'This narrow check does not establish medication safety.', pharmacy.flags.map(f => `${f.medication} · ${f.matched_allergy}`)));
  if (billing) $('findings').append(finding(billing.discrepancies.length ? '' : 'success', 'BILLING RECONCILIATION', billing.discrepancies.length ? `${billing.discrepancies.length} item discrepancies` : 'Recorded quantities match', 'Comparison only. No charges have been changed.', billing.discrepancies.map(item => `${item.item_id.toLowerCase().replaceAll('_', ' ')}: used ${item.used_quantity}, billed ${item.billed_quantity} (${item.quantity_difference > 0 ? '+' : ''}${item.quantity_difference})`)));
  Object.entries(state.check_errors).forEach(([worker, message]) => $('findings').append(finding('pharmacy', `${worker.toUpperCase()} ERROR`, 'Check needs a retry', message)));
  if (!pharmacy && !billing && !Object.keys(state.check_errors).length) $('findings').append(finding('', running ? 'CHECKS IN PROGRESS' : 'AWAITING CHECKS', running ? 'Independent workers are running' : 'No findings yet', running ? 'Results are stored when the checks complete.' : 'Approve the draft, then run pharmacy and billing.'));
  renderControls();
}
function accept(response) {
  current = response;
  localStorage.setItem('clearpath.workflow', response.workflow_id);
  render();
}
async function action(button, operation) {
  if (busy) return;
  $('notice').hidden = true;
  setBusy(true, button);
  try { await operation(); }
  catch (error) { notice(error.message, true); }
  finally { setBusy(false); }
}
$('create-draft').addEventListener('click', () => action($('create-draft'), async () => {
  const doctor_note = $('doctor-note').value.trim();
  const proposed_medications = $('medications').value.split('\n').map(s => s.trim()).filter(Boolean).map(name => ({name}));
  if (!doctor_note) throw new Error('Enter a doctor’s note before preparing the draft.');
  accept(await api('/workflows', 'POST', {patient_id: 'PT-402', doctor_note, proposed_medications, use_ai: aiEnabled}));
  notice('Draft prepared. Review the note and proposed medicines before approving this revision.');
}));
$('approve-draft').addEventListener('click', () => action($('approve-draft'), async () => {
  if ($('review-note').value !== current.snapshot.draft.doctor_note) throw new Error('Save your note edit before approving this revision.');
  accept(await api(`/workflows/${current.workflow_id}/approve`, 'POST', {expected_revision: current.snapshot.revision}));
  notice('Revision approved for the demonstration. You can now run the independent checks.');
}));
$('save-note').addEventListener('click', () => action($('save-note'), async () => {
  accept(await api(`/workflows/${current.workflow_id}/note`, 'PATCH', {expected_revision: current.snapshot.revision, doctor_note: $('review-note').value}));
  notice('A new revision was saved. Previous approval, findings, and generated summary have been cleared.');
}));
$('run-checks').addEventListener('click', () => action($('run-checks'), async () => {
  if ($('review-note').value !== current.snapshot.draft.doctor_note) throw new Error('Save and approve your note edit before starting checks.');
  const id = current.workflow_id;
  const generation = ++pollGeneration;
  pollTimer = setInterval(async () => {
    try {
      const response = await api(`/workflows/${id}`);
      if (generation === pollGeneration && current?.workflow_id === id) accept(response);
    } catch (_) {}
  }, 600);
  flow('flow-pharmacy', 'running', 'Starting…'); flow('flow-billing', 'running', 'Starting…');
  try {
    const response = await api(`/workflows/${id}/checks`, 'POST', {expected_revision: current.snapshot.revision});
    ++pollGeneration;
    accept(response);
    notice(current.snapshot.parallel_status === 'COMPLETED' ? 'Checks completed. Findings require human review; this is not discharge clearance.' : 'Some checks failed. Review the error details and retry.', current.snapshot.parallel_status !== 'COMPLETED');
  } finally { ++pollGeneration; clearInterval(pollTimer); pollTimer = null; }
}));
$('new-case').addEventListener('click', () => {
  if (busy) return;
  current = null; localStorage.removeItem('clearpath.workflow'); $('notice').hidden = true; render();
});
$('load-example').addEventListener('click', () => { $('doctor-note').value = originalNote; $('medications').value = 'Amoxicillin'; });
$('copy-id').addEventListener('click', async () => {
  try { await navigator.clipboard.writeText(current.workflow_id); notice('Workflow ID copied. You can reopen it through the API after a restart.'); }
  catch (_) { notice(`Workflow ID: ${current.workflow_id}`); }
});
$('download-report').addEventListener('click', () => {
  const state = current.snapshot;
  const lines = ['CLEARPATH — DISCHARGE REVIEW PACKET', 'SYNTHETIC DEMONSTRATION · NOT DISCHARGE AUTHORIZATION', '', `Workflow: ${current.workflow_id}`, `Revision: ${state.revision}`, `Patient: ${state.draft.patient_name} (${state.draft.patient_id})`, `Draft status: ${state.draft.status}`, `Generation: ${state.draft.generation_mode}`, '', 'CLINICIAN NOTE', state.draft.doctor_note, '', ...(state.draft.clinical_summary ? ['AI-PREPARED SUMMARY — REVIEW REQUIRED', state.draft.clinical_summary, ''] : []), 'PROPOSED MEDICINES', ...state.draft.proposed_medications.map(m => `- ${m.name}`), '', 'REVIEW FINDINGS', JSON.stringify({pharmacy: state.pharmacy_result, billing: state.billing_result, errors: state.check_errors}, null, 2), '', 'The pharmacy rule is a limited synthetic example. Billing compares quantities only. Human clinical and administrative review remains required.'];
  const url = URL.createObjectURL(new Blob([lines.join('\n')], {type: 'text/plain;charset=utf-8'}));
  const link = document.createElement('a'); link.href = url; link.download = `clearpath-review-${current.workflow_id.slice(0, 8)}.txt`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('.view').forEach(view => view.hidden = view.id !== `${button.dataset.view}-view`);
  document.querySelectorAll('[data-view]').forEach(item => item.classList.toggle('active', item === button));
}));
async function initialize() {
  render();
  try {
    const config = await api('/api/config');
    aiEnabled = config.configured === true;
    $('input-mode').textContent = aiEnabled ? 'AMD inference' : 'Structured demo';
  } catch (_) {}
  const saved = localStorage.getItem('clearpath.workflow');
  if (saved) {
    try { accept(await api(`/workflows/${saved}`)); notice('Your last workflow was restored from persistent storage.'); }
    catch (_) { localStorage.removeItem('clearpath.workflow'); }
  }
}
initialize();
