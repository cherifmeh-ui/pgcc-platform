<!-- frontend/src/views/AppsView.vue -->
<template>
  <div class="apps-page">
    <!-- En-tête -->
    <div class="page-header">
      <h1>Inventaire des Applications Critiques</h1>
      <button v-if="canCreate" @click="openCreateModal" class="add-btn">+ Nouvelle application</button>
    </div>

    <!-- Heatmap Criticité -->
    <div class="heatmap-summary">
      <div v-for="level in critLevels" :key="level.label" class="heat-cell" :class="level.class">
        <strong>{{ level.count }}</strong>
        <span>{{ level.label }}</span>
      </div>
    </div>

    <!-- Tableau -->
    <div class="table-container">
      <table class="apps-table">
        <thead>
          <tr>
            <th>Nom / Module</th>
            <th>Propriétaire</th>
            <th>Hébergement Actuel → Cible</th>
            <th>Criticité</th>
            <th>Risque Principal</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="app in apps" :key="app.id">
            <td>
              <strong>{{ app.name }}</strong>
              <br/>
              <small v-if="app.module">{{ app.module }}</small>
            </td>
            <td>
              {{ app.owner || '-' }}
              <br/>
              <small v-if="app.direction">({{ app.direction }})</small>
            </td>
            <td>
              <span class="hosting-badge current">{{ app.hosting_current || 'N/A' }}</span>
              <span v-if="app.hosting_target" class="arrow">→</span>
              <span v-if="app.hosting_target" class="hosting-badge target">{{ app.hosting_target }}</span>
            </td>
            <td>
              <span class="crit-badge" :class="getCritClass(app.criticality)">
                {{ app.criticality }}
              </span>
            </td>
            <td>{{ app.main_risk || '-' }}</td>
            <td class="actions-cell">
              <button v-if="canUpdate" @click="editApp(app)" class="action-btn edit" title="Modifier">✏️</button>
              <button @click="openAiForApp(app)" class="action-btn ai" title="Analyse IA">✨</button>
              <button v-if="canDelete" @click="deleteApp(app.id)" class="action-btn delete" title="Supprimer">🗑️</button>
            </td>
          </tr>
          
          <!-- États Loading/Vide -->
          <tr v-if="loading"><td colspan="6" class="loading-row">Chargement de l'inventaire...</td></tr>
          <tr v-if="!loading && apps.length === 0"><td colspan="6" class="empty-state">Aucune application enregistrée.</td></tr>
        </tbody>
      </table>
    </div>

    <!-- Modal Création/Édition -->
    <Teleport to="body">
      <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
        <div class="modal-content">
          <h2>{{ editingApp ? 'Modifier Application' : 'Nouvelle Application' }}</h2>
          <form @submit.prevent="saveApp" class="app-form">
            <label>Nom *</label><input v-model="formData.name" required />
            <label>Module</label><input v-model="formData.module" placeholder="Ex: Messagerie, Compta..." />
            <label>Propriétaire</label><input v-model="formData.owner" />
            <label>Direction</label><input v-model="formData.direction" />
            <label>Niveau d'accès</label><input v-model="formData.access_level" />
            
            <div class="two-cols">
              <div><label>Hébergement Actuel</label><input v-model="formData.hosting_current" /></div>
              <div><label>Hébergement Cible</label><input v-model="formData.hosting_target" /></div>
            </div>

            <label>Criticité *</label>
            <select v-model="formData.criticality" required>
              <option value="">-- Choisir --</option>
              <option>Faible</option>
              <option>Moyenne</option>
              <option>Élevée</option>
              <option>Critique</option>
            </select>

            <label>Risque Principal</label><input v-model="formData.main_risk" />
            <label>Plan de Traitement</label><textarea v-model="formData.treatment_plan" rows="2"></textarea>
            <label>Commentaire</label><textarea v-model="formData.comment" rows="2"></textarea>

            <div class="modal-actions">
              <button type="button" @click="closeModal" class="cancel-btn">Annuler</button>
              <button type="submit" :disabled="saving" class="save-btn">
                {{ saving ? 'Sauvegarde...' : 'Enregistrer' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>

    <!-- Panneau Assistant IA -->
    <AiAssistantPanel 
      :is-open="showAiPanel" 
      :risk-data="selectedForAi"
      @close="showAiPanel = false"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import apiClient from '@/services/api';
import AiAssistantPanel from '@/components/AiAssistantPanel.vue';

const authStore = useAuthStore();

// --- État Local UI ---
const apps = ref([]);
const loading = ref(true);
const showModal = ref(false);
const editingApp = ref(null);
const saving = ref(false);

// --- État Assistant IA ---
const showAiPanel = ref(false);
const selectedForAi = ref(null);

// Formulaire création/modif
const formData = reactive({
  name: '', module: '', owner: '', direction: '', access_level: '',
  hosting_current: '', hosting_target: '', criticality: 'Moyenne',
  main_risk: '', treatment_plan: '', comment: ''
});

// --- Permissions RBAC (module "apps") ---
const canCreate = computed(() => authStore.canAccessModule('apps', 'create'));
const canUpdate = computed(() => authStore.canAccessModule('apps', 'update'));
const canDelete = computed(() => authStore.canAccessModule('apps', 'delete'));

// --- Calcul Heatmap Criticité ---
const critLevels = computed(() => {
  const b = [
    { label: 'Faible', class: 'low', count: 0 },
    { label: 'Moyenne', class: 'medium', count: 0 },
    { label: 'Élevée', class: 'high', count: 0 },
    { label: 'Critique', class: 'critical', count: 0 },
  ];
  apps.value.forEach(a => {
    const idx = b.findIndex(x => x.label === a.criticality);
    if (idx >= 0) b[idx].count++;
  });
  return b;
});

function getCritClass(c) {
  return { 'Faible': 'low', 'Moyenne': 'medium', 'Élevée': 'high', 'Critique': 'critical' }[c] || 'low';
}

// --- Actions CRUD ---
async function loadApps() {
  loading.value = true;
  try {
    // Endpoint corrigé : /apps/
    const { data } = await apiClient.get('/apps/');
    apps.value = data;
  } catch (err) {
    console.error('Erreur chargement apps:', err);
    alert("Impossible de charger l'inventaire. Vérifiez la connexion backend.");
  } finally {
    loading.value = false;
  }
}

function openCreateModal() {
  editingApp.value = null;
  Object.assign(formData, {
    name: '', module: '', owner: '', direction: '', access_level: '',
    hosting_current: '', hosting_target: '', criticality: 'Moyenne',
    main_risk: '', treatment_plan: '', comment: ''
  });
  showModal.value = true;
}

function editApp(app) {
  editingApp.value = app;
  Object.assign(formData, app);
  showModal.value = true;
}

function closeModal() {
  showModal.value = false;
  editingApp.value = null;
}

// --- Action Assistant IA (Mapping App -> RiskContext) ---
function openAiForApp(app) {
  selectedForAi.value = {
    ref: `APP-${app.name.replace(/\s+/g,'-').toUpperCase()}`,
    title: `${app.name} (${app.module || 'N/A'}) — ${app.criticality}`,
    description: app.comment || `Application ${app.name}, hébergée ${app.hosting_current}. Propriétaire : ${app.owner}.`,
    threat: app.main_risk || 'Non spécifié',
    impact: app.criticality === 'Critique' ? 5 : app.criticality === 'Élevée' ? 4 : app.criticality === 'Moyenne' ? 3 : 2,
    likelihood: 3, // Probabilité moyenne par défaut pour une app critique
    site: app.hosting_current || 'On-Premise'
  };
  showAiPanel.value = true;
}

async function saveApp() {
  saving.value = true;
  try {
    if (editingApp.value) {
      await apiClient.put(`/apps/${editingApp.value.id}`, formData);
    } else {
      await apiClient.post('/apps/', formData);
    }
    await loadApps();
    closeModal();
  } catch (err) {
    const detail = err.response?.data?.detail;
    alert(detail || 'Erreur lors de la sauvegarde.');
  } finally {
    saving.value = false;
  }
}

async function deleteApp(id) {
  if (!confirm('Supprimer définitivement cette application ?')) return;
  try {
    await apiClient.delete(`/apps/${id}`);
    await loadApps();
  } catch (err) {
    alert(err.response?.data?.detail || 'Erreur suppression.');
  }
}

onMounted(loadApps);
</script>

<style scoped>
.apps-page { max-width: 1500px; margin: 0 auto; padding: 1rem; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.page-header h1 { font-size: 1.5rem; color: #0f172a; }
.add-btn { padding: 0.6rem 1.2rem; background: #0ea5e9; color: white; border: none; border-radius: 6px; font-weight: 600; cursor: pointer; }
.add-btn:hover { background: #0284c7; }

/* Heatmap */
.heatmap-summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.75rem; margin-bottom: 1.5rem; }
.heat-cell { padding: 1rem; border-radius: 8px; text-align: center; color: white; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.heat-cell strong { font-size: 1.8rem; display: block; margin-bottom: 0.25rem; }
.low { background: #22c55e; } .medium { background: #eab308; } .high { background: #f97316; } .critical { background: #ef4444; }

/* Table */
.table-container { overflow-x: auto; background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.apps-table { width: 100%; border-collapse: collapse; min-width: 900px; }
.apps-table th, .apps-table td { padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid #e2e8f0; vertical-align: top; }
.apps-table th { background: #f8fafc; font-weight: 600; color: #475569; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.5px; position: sticky; top: 0; z-index: 10; }
.apps-table tr:hover { background: #f1f5f9; }

.badges { display: flex; gap: 0.5rem; align-items: center; }
.hosting-badge { display: inline-block; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.8rem; font-weight: 500; }
.hosting-badge.current { background: #e2e8f0; color: #475569; }
.hosting-badge.target { background: #dbeafe; color: #1d4ed8; }
.arrow { margin: 0 0.3rem; color: #94a3b8; font-weight: bold; }

.crit-badge { display: inline-block; padding: 0.25rem 0.6rem; border-radius: 12px; font-size: 0.8rem; font-weight: 700; color: white; }
.crit-badge.low { background: #22c55e; } .crit-badge.medium { background: #eab308; } .crit-badge.high { background: #f97316; } .crit-badge.critical { background: #ef4444; }

.actions-cell { display: flex; gap: 0.5rem; }
.action-btn { padding: 0.3rem 0.6rem; border: none; border-radius: 4px; cursor: pointer; font-size: 0.9rem; transition: all 0.2s; }
.action-btn:hover { transform: scale(1.05); }
.action-btn.edit { background: #dbeafe; color: #1d4ed8; }
.action-btn.delete { background: #fee2e2; color: #dc2626; }
.action-btn.ai { background: #ede9fe; color: #6d28d9; font-weight: bold; }

.loading-row, .empty-state { text-align: center; color: #64748b; padding: 2rem !important; font-style: italic; }

/* Modal */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; justify-content: center; align-items: center; z-index: 1000; backdrop-filter: blur(2px); }
.modal-content { background: white; border-radius: 12px; padding: 2rem; width: 90%; max-width: 600px; max-height: 90vh; overflow-y: auto; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1); }
.modal-content h2 { margin-top: 0; margin-bottom: 1.5rem; color: #0f172a; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.5rem; }
.app-form { display: flex; flex-direction: column; gap: 1rem; }
.app-form label { font-size: 0.85rem; font-weight: 600; color: #334155; margin-bottom: 0.25rem; display: block; }
.app-form input, .app-form textarea, .app-form select { width: 100%; padding: 0.6rem; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 0.95rem; box-sizing: border-box; }
.app-form input:focus, .app-form textarea:focus { outline: 2px solid #0ea5e9; border-color: transparent; }
.two-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.modal-actions { display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #e2e8f0; }
.cancel-btn { padding: 0.6rem 1.2rem; background: #e2e8f0; color: #475569; border: none; border-radius: 6px; cursor: pointer; font-weight: 500; }
.save-btn { padding: 0.6rem 1.2rem; background: #0ea5e9; color: white; border: none; border-radius: 6px; font-weight: 600; cursor: pointer; }
.save-btn:disabled { opacity: 0.6; cursor: not-allowed; }
</style>