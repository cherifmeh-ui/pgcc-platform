<!-- frontend/src/components/ActionsPanel.vue -->
<template>
  <Teleport to="body">
    <div v-if="isOpen" class="panel-overlay" @click.self="$emit('close')">
      <div class="panel-container">
        <!-- Header -->
        <div class="panel-header">
          <h2>📋 Plan d'Action — {{ riskTitle }}</h2>
          <button @click="$emit('close')" class="close-btn">✕</button>
        </div>

        <!-- Corps scrollable -->
        <div class="panel-body">
          
          <!-- Formulaire Création Rapide -->
          <div class="quick-add-form">
            <h3>+ Nouvelle Tâche</h3>
            <input v-model="newAction.title" placeholder="Titre de l'action corrective..." required />
            <textarea v-model="newAction.description" rows="2" placeholder="Détails techniques..."></textarea>
            
            <div class="iso-action-link">
              <label>Contrôle ISO 27002 (optionnel)
                <select v-model="newAction.iso_control_ref" @change="loadControlAssessments(newAction.iso_control_ref)">
                  <option value="">Aucun contrôle ISO lié</option>
                  <option v-for="control in isoControls" :key="control.ref_code" :value="control.ref_code">{{ control.ref_code }} — {{ control.title }}</option>
                </select>
              </label>
              <label v-if="newAction.iso_control_ref">Évaluation ISO associée (optionnel)
                <select v-model="newAction.iso_assessment_id">
                  <option value="">Lien au contrôle uniquement</option>
                  <option v-for="assessment in isoAssessments" :key="assessment.id" :value="assessment.id">{{ assessment.implementation_status }} · {{ assessment.maturity_level }}/5 · {{ formatIsoAssessmentDate(assessment.assessed_at) }}</option>
                </select>
              </label>
            </div>
            <div class="form-row">
              <!-- ✅ VALEURS FRANÇAISES POUR MATCHER LE BACKEND -->
              <select v-model="newAction.priority">
                <option value="Basse">Basse</option>
                <option value="Moyenne">Moyenne</option>
                <option value="Haute">Haute</option>
                <option value="Critique">Critique</option>
              </select>
              
              <input type="date" v-model="newAction.due_date" />
              
              <select v-model="newAction.assigned_to"><option value="">Non assignée</option><option v-for="user in assignees" :key="user.id" :value="user.email">{{ user.full_name }}{{ user.department ? " — " + user.department : "" }}</option></select>
            </div>
            
            <button @click="addAction" :disabled="saving" class="btn-primary">
              {{ saving ? 'Ajout...' : '➕ Ajouter' }}
            </button>
          </div>

          <!-- Liste des Actions Existantes -->
          <div class="actions-list">
            <h3>Actions ({{ filteredActions.length }})</h3>
            <div class="action-filters" role="group" aria-label="Filtrer les actions">
              <button type="button" :class="{ active: actionFilter === 'all' }" @click="actionFilter = 'all'">Toutes ({{ riskActions.length }})</button>
              <button type="button" :class="{ active: actionFilter === 'open' }" @click="actionFilter = 'open'">Ouvertes ({{ riskActions.filter(a => a.status !== 'Terminé').length }})</button>
              <button type="button" :class="{ active: actionFilter === 'overdue' }" @click="actionFilter = 'overdue'">En retard ({{ overdueActions.length }})</button>
              <button type="button" :class="{ active: actionFilter === 'done' }" @click="actionFilter = 'done'">Terminées ({{ riskActions.filter(a => a.status === 'Terminé').length }})</button>
            </div>
            
            <div v-if="loading" class="loading-state">Chargement...</div>
            
            <div v-else-if="filteredActions.length === 0" class="empty-state">
              Aucune action enregistrée pour ce risque.<br/>
              <small>Ajoutez-en une ci-dessus.</small>
            </div>
            
            <ul v-else class="task-ul">
              <li v-for="act in filteredActions" :key="act.id" class="task-li" :class="'prio-' + act.priority.toLowerCase()">
                <div class="task-content">
                  <strong>{{ act.title }}</strong>
                  <p v-if="act.description">{{ act.description }}</p>
                  <p v-if="act.iso_control_id" class="iso-action-tag">ISO 27002 · {{ isoControls.find(control => control.control_id === act.iso_control_id)?.ref_code || ('#' + act.iso_control_id) }}{{ act.iso_assessment_id ? ' · Évaluation liée' : '' }}</p>
                  <div class="meta-info">
                    <!-- ✅ BADGES BASÉS SUR LES CHAÎNES RÉELLES -->
                    <span class="badge-status" :class="getStatusClass(act.status)">
                      {{ act.status }}
                    </span>
                    <span class="assignee">👤 {{ act.assigned_to || 'Non assigné' }}</span>
                    <span class="deadline" :class="{ overdue: isOverdue(act.due_date) }">
                      📅 {{ formatDate(act.due_date) }}
                    </span>
                  </div>
                </div>
                <div v-if="act.status === 'Terminé'" class="verification-inline">
                  <button type="button" class="verification-toggle" @click="openVerification(act)">Vérification d'efficacité · {{ verificationHistory[act.id]?.length || 0 }}</button>
                  <div v-if="verificationActionId === act.id" class="verification-form">
                    <article v-for="record in (verificationHistory[act.id] || [])" :key="record.id" class="verification-record">
                      <strong>{{ record.outcome }}</strong> · {{ formatIsoAssessmentDate(record.verified_at) }}
                      <p>{{ record.notes }}</p>
                    </article>
                    <label>Résultat
                      <select v-model="verificationForm.outcome">
                        <option value="Effective">Efficace</option>
                        <option value="Ineffective">Inefficace</option>
                        <option value="Follow-up required">Suivi complémentaire requis</option>
                      </select>
                    </label>
                    <label>Document de vérification (optionnel)
                      <select v-model="verificationForm.evidence_document_id">
                        <option value="">Aucun document</option>
                        <option v-for="doc in verificationDocuments" :key="doc.id" :value="doc.id">{{ doc.title }} — {{ doc.filename }}</option>
                      </select>
                    </label>
                    <label>Observations
                      <textarea v-model="verificationForm.notes" rows="2" maxlength="10000" placeholder="Résultat de la vérification, preuve de l'efficacité..."></textarea>
                    </label>
                    <p v-if="verificationError" class="verification-error">{{ verificationError }}</p>
                    <button type="button" class="btn-primary" @click="saveVerification(act.id)" :disabled="verificationSaving || !verificationForm.notes.trim()">{{ verificationSaving ? 'Enregistrement...' : 'Enregistrer la vérification' }}</button>
                  </div>
                </div>
                
                <div class="task-actions">
                  <button @click="toggleStatus(act)" class="icon-btn done" :disabled="act.status === 'Terminé'" :title="act.status === 'Terminé' ? 'Action clôturée' : act.status === 'En cours' ? 'Marquer terminé' : act.status === 'Bloqué' ? 'Reprendre l’action' : 'Démarrer l’action'">{{ act.status === 'Terminé' ? '✔️' : '▶️' }}</button>
                  <button @click="editAction(act)" class="icon-btn edit" title="Modifier">✏️</button>
                  <button @click="deleteAction(act.id)" class="icon-btn del" title="Supprimer">🗑️</button>
                </div>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue';
import apiClient from '@/services/api';

const props = defineProps({
  isOpen: Boolean,
  riskId: String, // UUID string
  riskTitle: String
});

const emit = defineEmits(['close']);

// État Local
const loading = ref(false);
const saving = ref(false);
const actions = ref([]);
const assignees = ref([]);
const isoControls = ref([]);
const isoAssessments = ref([]);
const verificationActionId = ref(null);
const verificationHistory = ref({});
const verificationDocuments = ref([]);
const verificationForm = ref({ outcome: 'Effective', notes: '', evidence_document_id: '' });
const verificationSaving = ref(false);
const verificationError = ref('');


// Formulaire création
const newAction = reactive({
  title: '',
  description: '',
  priority: 'Moyenne', // ✅ Valeur par défaut française
  due_date: null,
  assigned_to: '',
  iso_control_ref: '',
  iso_assessment_id: ''
});

// Filtrage (afficher seulement celles liées au risque actuel)
const actionFilter = ref("all");
const riskActions = computed(() => actions.value.filter(a => a.risk_id === props.riskId));
const overdueActions = computed(() => riskActions.value.filter(a => a.status !== "Terminé" && isOverdue(a.due_date)));
const filteredActions = computed(() => {
  if (actionFilter.value === "overdue") return overdueActions.value;
  if (actionFilter.value === "open") return riskActions.value.filter(a => a.status !== "Terminé");
  if (actionFilter.value === "done") return riskActions.value.filter(a => a.status === "Terminé");
  return riskActions.value;
});

// Charger les actions quand le panel s'ouvre ou que le riskId change
watch([() => props.isOpen, () => props.riskId], ([open, id]) => {
  if (open && id) { loadActions(id); loadAssignees(); loadIsoControls(); }
}, { immediate: true });

async function loadIsoControls() {
  try {
    const { data } = await apiClient.get('/compliance/matrix');
    isoControls.value = Array.isArray(data?.rows) ? data.rows : [];
  } catch (err) {
    console.warn('ISO controls unavailable for action linkage', err);
    isoControls.value = [];
  }
}
async function loadControlAssessments(refCode) {
  newAction.iso_assessment_id = '';
  isoAssessments.value = [];
  if (!refCode) return;
  try {
    const { data } = await apiClient.get(`/compliance/controls/${encodeURIComponent(refCode)}/assessments`);
    isoAssessments.value = Array.isArray(data) ? data : [];
  } catch (err) {
    console.warn('ISO assessments unavailable', err);
  }
}
function formatIsoAssessmentDate(value) {
  return value ? new Date(value).toLocaleDateString('fr-FR') : '—';
}

async function openVerification(action) {
  verificationActionId.value = action.id;
  verificationError.value = '';
  verificationForm.value = { outcome: 'Effective', notes: '', evidence_document_id: '' };
  try {
    const [historyResponse, documentsResponse] = await Promise.all([
      apiClient.get(`/actions/${action.id}/verifications`),
      apiClient.get('/documents/'),
    ]);
    verificationHistory.value = { ...verificationHistory.value, [action.id]: Array.isArray(historyResponse.data) ? historyResponse.data : [] };
    verificationDocuments.value = Array.isArray(documentsResponse.data) ? documentsResponse.data : [];
  } catch (error) {
    verificationError.value = error.response?.data?.detail || "Impossible de charger la vérification.";
  }
}
async function saveVerification(actionId) {
  verificationSaving.value = true;
  verificationError.value = '';
  try {
    const payload = {
      outcome: verificationForm.value.outcome,
      notes: verificationForm.value.notes.trim(),
      evidence_document_id: verificationForm.value.evidence_document_id || null,
    };
    await apiClient.post(`/actions/${actionId}/verifications`, payload);
    const { data } = await apiClient.get(`/actions/${actionId}/verifications`);
    verificationHistory.value = { ...verificationHistory.value, [actionId]: Array.isArray(data) ? data : [] };
    verificationForm.value = { outcome: 'Effective', notes: '', evidence_document_id: '' };
  } catch (error) {
    verificationError.value = error.response?.data?.detail || "Échec de l'enregistrement.";
  } finally {
    verificationSaving.value = false;
  }
}

async function loadAssignees() {
  try {
    const { data } = await apiClient.get("/actions/assignees");
    assignees.value = Array.isArray(data) ? data : [];
  } catch (err) {
    console.error("Erreur chargement responsables des actions:", err);
    assignees.value = [];
  }
}

async function loadActions(riskId) {
  loading.value = true;
  try {
    const { data } = await apiClient.get(`/actions/?risk_id=${riskId}`);
    actions.value = data;
  } catch (err) {
    console.error("Erreur chargement actions:", err);
    alert("Impossible de charger les plans d'action.");
  } finally {
    loading.value = false;
  }
}

async function addAction() {
  if (!newAction.title.trim()) return alert("Le titre est obligatoire.");
  
  saving.value = true;
  try {
    const payload = {
      ...newAction,
      title: newAction.title.trim(),
      description: newAction.description.trim() || null,
      risk_id: props.riskId,
      iso_control_ref: newAction.iso_control_ref || null,
      iso_assessment_id: newAction.iso_assessment_id || null,
      due_date: newAction.due_date ? new Date(newAction.due_date).toISOString() : null
    };
    
    await apiClient.post('/actions/', payload);
    
    // Reset form & Reload list
    Object.assign(newAction, { title:'', description:'', priority:'Moyenne', due_date:null, assigned_to:'', iso_control_ref:'', iso_assessment_id:'' });
    await loadActions(props.riskId);
  } catch (err) {
    alert(err.response?.data?.detail || "Erreur lors de l'ajout.");
  } finally {
    saving.value = false;
  }
}

async function toggleStatus(action) {
  // Respect the backend lifecycle: completed actions cannot be reopened.
  if (action.status === 'Terminé') return;
  const nextStatus = action.status === 'En cours' ? 'Terminé' : 'En cours';
  try {
    await apiClient.put(`/actions/${action.id}`, { status: nextStatus });
    await loadActions(props.riskId);
  } catch (err) {
    alert(err.response?.data?.detail || "Transition de statut impossible.");
  }
}

function editAction(action) {
  const newTitle = prompt("Nouveau titre :", action.title);
  if (newTitle !== null && newTitle !== action.title) {
    apiClient.put(`/actions/${action.id}`, { title: newTitle })
      .then(() => loadActions(props.riskId))
      .catch(() => alert("Erreur modification."));
  }
}

async function deleteAction(id) {
  if (!confirm("Supprimer cette tâche ?")) return;
  try {
    await apiClient.delete(`/actions/${id}`);
    await loadActions(props.riskId);
  } catch (err) {
    alert("Erreur suppression.");
  }
}

// Helpers UI
function getStatusClass(status) {
  switch(status) {
    case 'À faire': return 'st-todo';
    case 'En cours': return 'st-in-progress';
    case 'Terminé': return 'st-done';
    case 'Bloqué': return 'st-blocked';
    default: return '';
  }
}

function formatDate(isoStr) {
  if (!isoStr) return 'Pas de deadline';
  return new Date(isoStr).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' });
}

function isOverdue(isoStr) {
  if (!isoStr) return false;
  const due = new Date(isoStr);
  if (Number.isNaN(due.getTime())) return false;
  // A date-only deadline remains valid through the end of that calendar day.
  due.setHours(23, 59, 59, 999);
  return due < new Date();
}
</script>

<style scoped>
.panel-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 2000;
  display: flex; justify-content: center; align-items: center; backdrop-filter: blur(3px);
}
.panel-container {
  background: white; width: 95%; max-width: 800px; height: 90vh; border-radius: 12px;
  display: flex; flex-direction: column; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.25);
}
.panel-header {
  padding: 1.5rem; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center;
}
.panel-header h2 { margin: 0; font-size: 1.25rem; color: #0f172a; }
.close-btn { background: none; border: none; font-size: 1.5rem; cursor: pointer; color: #64748b; }
.close-btn:hover { color: #ef4444; }

.panel-body { flex: 1; overflow-y: auto; padding: 1.5rem; }

/* Quick Add Form */
.quick-add-form { background: #f8fafc; padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem; border: 1px dashed #cbd5e1; }
.quick-add-form h3 { margin-top: 0; font-size: 1rem; color: #334155; }
.quick-add-form input, .quick-add-form textarea, .quick-add-form select {
  width: 100%; padding: 0.5rem; margin-bottom: 0.5rem; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 0.9rem;
}
.iso-action-link { display:grid; grid-template-columns:1fr 1fr; gap:.5rem; margin:.5rem 0; }
.iso-action-link label { display:grid; gap:.3rem; font-size:.85rem; color:#475569; font-weight:600; }
.iso-action-link select { width:100%; padding:.5rem; border:1px solid #cbd5e1; border-radius:6px; background:white; }
.iso-action-tag { display:inline-block; margin:.35rem 0; padding:.2rem .5rem; background:#ede9fe; color:#5b21b6; border-radius:999px; font-size:.75rem; font-weight:600; }
@media (max-width:600px) { .iso-action-link { grid-template-columns:1fr; } }
.form-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.5rem; margin-bottom: 0.5rem; }
.btn-primary { background: #0ea5e9; color: white; border: none; padding: 0.6rem 1.2rem; border-radius: 6px; cursor: pointer; font-weight: 600; width: 100%; }
.btn-primary:disabled { opacity: 0.6; }

/* Action filters */
.action-filters { display: flex; gap: .4rem; flex-wrap: wrap; margin: .5rem 0 1rem; }
.action-filters button { border: 1px solid #cbd5e1; background: white; color: #334155; border-radius: 999px; padding: .35rem .7rem; cursor: pointer; font-size: .8rem; }
.action-filters button.active { background: #0f172a; color: white; border-color: #0f172a; }
.action-filters button:hover { border-color: #64748b; }

/* Task List */
.verification-inline { margin-top:.6rem; }
.verification-toggle { background:#f1f5f9; border:1px solid #cbd5e1; color:#334155; border-radius:6px; padding:.35rem .6rem; cursor:pointer; font-size:.8rem; }
.verification-form { display:grid; gap:.5rem; padding:.7rem; margin-top:.4rem; border:1px solid #dbeafe; border-radius:8px; background:#f8fafc; }
.verification-form label { display:grid; gap:.25rem; font-size:.8rem; color:#475569; font-weight:600; }
.verification-form select,.verification-form textarea { width:100%; padding:.45rem; border:1px solid #cbd5e1; border-radius:6px; font:inherit; }
.verification-record { padding:.5rem; border-bottom:1px solid #e2e8f0; font-size:.8rem; }
.verification-record p { margin:.25rem 0; white-space:pre-wrap; }
.verification-error { color:#b91c1c; font-size:.8rem; }
.task-ul { list-style: none; padding: 0; margin: 0; }
.task-li {
  display: flex; justify-content: space-between; align-items: flex-start;
  padding: 1rem; border-bottom: 1px solid #f1f5f9; transition: background 0.2s;
}
.task-li:hover { background: #f8fafc; }
.task-li.prio-critique { border-left: 4px solid #ef4444; } /* ✅ Classes adaptées aux noms FR */
.task-li.prio-haute { border-left: 4px solid #f97316; }
.task-li.prio-moyenne { border-left: 4px solid #eab308; }
.task-li.prio-basse { border-left: 4px solid #22c55e; }

.task-content strong { display: block; color: #0f172a; margin-bottom: 0.25rem; }
.task-content p { color: #64748b; font-size: 0.9rem; margin: 0 0 0.5rem 0; }
.meta-info { display: flex; gap: 1rem; font-size: 0.8rem; color: #94a3b8; flex-wrap: wrap; }
.badge-status { padding: 0.1rem 0.4rem; border-radius: 4px; font-weight: 600; text-transform: uppercase; font-size: 0.7rem; }
.st-todo { background: #fef3c7; color: #92400e; }
.st-in-progress { background: #dbeafe; color: #1e40af; }
.st-done { background: #dcfce7; color: #166534; }
.st-blocked { background: #fee2e2; color: #991b1b; }
.deadline.overdue { color: #ef4444; font-weight: bold; }

.task-actions { display: flex; gap: 0.5rem; }
.icon-btn:disabled { cursor: not-allowed; opacity: .35; }
.icon-btn { background: none; border: none; cursor: pointer; font-size: 1.1rem; padding: 0.2rem; opacity: 0.7; transition: all 0.2s; }
.icon-btn:hover { opacity: 1; transform: scale(1.1); }
.icon-btn.done:hover { color: #22c55e; }
.icon-btn.edit:hover { color: #3b82f6; }
.icon-btn.del:hover { color: #ef4444; }

.loading-state, .empty-state { text-align: center; padding: 2rem; color: #64748b; }
</style>