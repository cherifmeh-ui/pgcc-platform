<!-- frontend/src/views/RisksView.vue -->
<template>
  <div class="risks-page">
    <!-- En-tête de page -->
    <div class="page-header">
      <h1>Registre des Risques SI</h1>
      <button v-if="canCreate" @click="openCreateModal" class="add-risk-btn">+ Nouveau risque</button>
    </div>

    <!-- Heatmap résumé (Barre de couleurs) -->
    <div class="heatmap-summary">
      <div v-for="level in riskLevels" :key="level.range" class="heat-cell" :class="level.class">
        <strong>{{ level.count }}</strong>
        <span>{{ level.label }}</span>
      </div>
    </div>

    <section class="risk-matrix-card">
      <div class="matrix-header"><div><h2>Matrice des risques</h2><p>Impact × Probabilité · Cliquez sur une cellule pour filtrer.</p></div><button v-if="matrixFilter" @click="matrixFilter = null">Réinitialiser</button></div>
      <div class="matrix-axis-row"><span>Impact 5</span><span>Impact 4</span><span>Impact 3</span><span>Impact 2</span><span>Impact 1</span></div>
      <div class="matrix-grid">
        <button v-for="cell in matrixCells" :key="cell.impact + '-' + cell.likelihood" class="matrix-cell" :class="[getRiskClass(cell.score), { selected: matrixFilter && matrixFilter.impact === cell.impact && matrixFilter.likelihood === cell.likelihood }]" @click="toggleMatrixFilter(cell)" :title="'Impact ' + cell.impact + ' × Probabilité ' + cell.likelihood + ' = ' + cell.score"><small>{{ cell.score }}</small><strong>{{ cell.count }}</strong></button>
      </div><div class="matrix-x-label">PROBABILITÉ (1 → 5) · IMPACT (5 → 1)</div>
    </section>
    <div class="risk-filters"><input v-model="riskSearch" type="search" placeholder="Recherche référence, titre, menace, site..." /><select v-model="statusFilter"><option value="">Tous les statuts</option><option>Ouvert</option><option>En traitement</option><option>Traité</option><option>Accepté</option></select><select v-model="siteFilter"><option value="">Tous les sites</option><option v-for="site in riskSites" :key="site" :value="site">{{ site }}</option></select><span>{{ filteredRisks.length }} / {{ risks.length }}</span><button @click="exportRisksCsv" class="export-btn">Export CSV</button></div>
    <!-- Tableau principal des risques -->
    <div class="table-container">
      <table class="risks-table">
        <thead>
          <tr>
            <th>Réf.</th>
            <th>Titre</th>
            <th>Site</th>
            <th>Responsable</th>
            <th>Niveau</th>
            <th>Statut</th>
            <th>MAJ</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="risk in filteredRisks" :key="risk.id">
            <td><code>{{ risk.ref }}</code></td>
            <td>
              {{ risk.title }}
              <br/>
              <small v-if="risk.threat" class="threat-hint">Menace : {{ truncate(risk.threat, 40) }}</small>
            </td>
            <td>{{ risk.site || '-' }}</td>
            <td>{{ getOwnerName(risk.owner_id) }}</td>
            <td>
              <span class="risk-badge" :class="getRiskClass(risk.risk_level)">
                {{ risk.risk_level }}
              </span>
            </td>
            <td>
              <span class="status-pill" :class="'status-' + normalizeStatus(risk.status)">
                {{ risk.status }}
              </span>
            </td>
            <td>
              <small>{{ formatDate(risk.updated_at || risk.created_at) }}</small>
            </td>
            <td class="actions-cell">
              <!-- Bouton Éditer -->
              <button v-if="canUpdate" @click="editRisk(risk)" class="action-btn edit" title="Modifier">✏️</button>
              
              <!-- Bouton Assistant IA -->
              <button @click="openAiAssistant(risk)" class="action-btn ai" title="Assistant IA">✨</button>
              
              <!-- Bouton Plan d'Action (Phase 8.5) -->
              <button 
                @click="openActionsPanel(risk)" 
                class="action-btn pac" 
                title="Plan d'Action Correctif"
              >📝</button>
              
              <!-- Bouton Supprimer -->
              <button v-if="canDelete" @click="deleteRisk(risk.id)" class="action-btn delete" title="Supprimer">🗑️</button>
            </td>
          </tr>
          <!-- États Loading / Vide -->
          <tr v-if="loading">
            <td colspan="8" class="loading-row">Chargement...</td>
          </tr>
          <tr v-if="!loading && filteredRisks.length === 0">
            <td colspan="8" class="empty-state">{{ risks.length === 0 ? "Aucun risque enregistré." : "Aucun risque ne correspond aux filtres." }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Modal Création/Édition -->
    <Teleport to="body">
      <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
        <div class="modal-content">
          <h2>{{ editingRisk ? 'Modifier le risque' : 'Créer un nouveau risque' }}</h2>
          <form @submit.prevent="saveRisk" class="risk-form">
            
            <label>Référence *</label>
            <input v-model="formData.ref" required maxlength="50" placeholder="R-SIE-XXX" />

            <label>Titre *</label>
            <textarea v-model="formData.title" required rows="2" placeholder="Description courte du risque"></textarea>

            <!-- Description détaillée pour l'IA -->
            <label>Description détaillée</label>
            <textarea 
              v-model="formData.description" 
              rows="3" 
              placeholder="Contexte technique complet utilisé par l'assistant IA..."
            ></textarea>

            <label>Menace associée</label>
            <textarea v-model="formData.threat" rows="2" placeholder="Quelle menace exploite cette vulnérabilité ?"></textarea>

            <div class="matrix-inputs">
              <div>
                <label>Impact (1-5)</label>
                <select v-model.number="formData.impact">
                  <option v-for="i in 5" :key="i" :value="i">{{ i }}</option>
                </select>
              </div>
              <div>
                <label>Probabilité (1-5)</label>
                <select v-model.number="formData.likelihood">
                  <option v-for="i in 5" :key="i" :value="i">{{ i }}</option>
                </select>
              </div>
            </div>

            <label>Site concerné</label>
            <input v-model="formData.site" placeholder="Ex: Tunis Siège, Gabès Rig..." />

            <label>Responsable du risque</label>
            <select v-model="formData.owner_id"><option value="">Non attribué</option><option v-for="owner in riskOwners" :key="owner.id" :value="owner.id">{{ owner.full_name }}{{ owner.department ? " — " + owner.department : "" }}</option></select>

            <label>Statut</label>
            <select v-model="formData.status">
              <option>Ouvert</option>
              <option>En traitement</option>
              <option>Traité</option>
              <option>Accepté</option>
            </select>

            <label>Plan de traitement (synthèse rapide)</label>
            <textarea v-model="formData.treatment_plan" rows="3" placeholder="Mesures correctives prévues..."></textarea>

            <div class="computed-level">
              Niveau calculé : <strong>{{ formData.impact * formData.likelihood }}</strong>/25
              <span class="level-label" :class="getRiskClass(formData.impact * formData.likelihood)">
                {{ getRiskLabel(formData.impact * formData.likelihood) }}
              </span>
            </div>

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

    <!-- Composant Panneau Assistant IA -->
    <AiAssistantPanel
      :is-open="showAiPanel"
      :risk-data="selectedRiskForAi"
      @close="showAiPanel = false"
    />

    <!-- Composant Panneau Plan d'Action (PAC) -->
    <ActionsPanel
      v-if="showActionsPanel"
      :is-open="showActionsPanel"
      :risk-id="selectedRiskIdForActions"
      :risk-title="selectedRiskTitleForActions"
      @close="handleCloseActionsPanel"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import apiClient from '@/services/api';
import AiAssistantPanel from '@/components/AiAssistantPanel.vue';
import ActionsPanel from '@/components/ActionsPanel.vue'; // ✅ IMPORT CRUCIAL POUR LE PAC

const authStore = useAuthStore();

// --- État Local UI ---
const risks = ref([]);
const riskOwners = ref([]);
const loading = ref(true);
const showModal = ref(false);
const editingRisk = ref(null);
const saving = ref(false);

// --- État Assistant IA ---
const showAiPanel = ref(false);
const selectedRiskForAi = ref(null);

// --- État Plan d'Action (Phase 8.5) ---
// ⚠️ DÉCLARATION AVANT UTILISATION DANS LES FONCTIONS
const showActionsPanel = ref(false);
const selectedRiskIdForActions = ref(null);
const selectedRiskTitleForActions = ref('');

// Formulaire création/modif (avec description ajoutée)
const formData = reactive({
  ref: '',
  title: '',
  description: '',
  threat: '',
  impact: 3,
  likelihood: 3,
  site: '',
  owner_id: '',
  status: 'Ouvert',
  treatment_plan: '',
});

// --- Permissions RBAC ---
const riskSearch = ref("");
const statusFilter = ref("");
const siteFilter = ref("");
const matrixFilter = ref(null);
const riskSites = computed(() => [...new Set(risks.value.map(r => r.site).filter(Boolean))].sort());
const matrixCells = computed(() => {
  const cells = [];
  for (let impact = 5; impact >= 1; impact--) {
    for (let likelihood = 1; likelihood <= 5; likelihood++) {
      const score = impact * likelihood;
      const count = risks.value.filter(r => r.impact === impact && r.likelihood === likelihood).length;
      cells.push({ impact, likelihood, score, count });
    }
  }
  return cells;
});
const filteredRisks = computed(() => {
  const query = riskSearch.value.trim().toLocaleLowerCase();
  return risks.value.filter(risk => {
    const matchesSearch = !query || [risk.ref, risk.title, risk.description, risk.threat, risk.site].some(v => String(v || "").toLocaleLowerCase().includes(query));
    const matchesStatus = !statusFilter.value || risk.status === statusFilter.value;
    const matchesSite = !siteFilter.value || risk.site === siteFilter.value;
    const matchesMatrix = !matrixFilter.value || (risk.impact === matrixFilter.value.impact && risk.likelihood === matrixFilter.value.likelihood);
    return matchesSearch && matchesStatus && matchesSite && matchesMatrix;
  });
});
function exportRisksCsv() {
  const headers = ["Référence", "Titre", "Description", "Menace", "Impact", "Probabilité", "Score", "Site", "Statut", "Plan de traitement", "Créé le", "Mis à jour le"];
  const escapeCsv = value => {
    let text = String(value ?? "");
    // Prevent spreadsheet formula injection in exported data.
    if (/^[=+@\\-]/.test(text)) text = "'" + text;
    return '"' + text.replace(/"/g, '""') + '"';
  };
  const rows = filteredRisks.value.map(r => [r.ref, r.title, r.description, r.threat, r.impact, r.likelihood, r.risk_level, r.site, r.status, r.treatment_plan, r.created_at, r.updated_at]);
  const csv = [headers, ...rows].map(row => row.map(escapeCsv).join(";")).join("\r\n");
  const blob = new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "registre-risques-" + new Date().toISOString().slice(0, 10) + ".csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function toggleMatrixFilter(cell) {
  if (matrixFilter.value && matrixFilter.value.impact === cell.impact && matrixFilter.value.likelihood === cell.likelihood) matrixFilter.value = null;
  else matrixFilter.value = { impact: cell.impact, likelihood: cell.likelihood };
}

const canCreate = computed(() => authStore.canAccessModule('risks', 'create'));
const canUpdate = computed(() => authStore.canAccessModule('risks', 'update'));
const canDelete = computed(() => authStore.canAccessModule('risks', 'delete'));

// --- Calcul Heatmap ---
const riskLevels = computed(() => {
  const buckets = [
    { range: '1-4', label: 'Faible', class: 'low', count: 0 },
    { range: '5-9', label: 'Modéré', class: 'medium', count: 0 },
    { range: '10-14', label: 'Élevé', class: 'high', count: 0 },
    { range: '15-19', label: 'Critique', class: 'critical', count: 0 },
    { range: '20-25', label: 'Inacceptable', class: 'extreme', count: 0 },
  ];
  risks.value.forEach(r => {
    const lvl = r.risk_level || 0;
    if (lvl <= 4) buckets[0].count++;
    else if (lvl <= 9) buckets[1].count++;
    else if (lvl <= 14) buckets[2].count++;
    else if (lvl <= 19) buckets[3].count++;
    else buckets[4].count++;
  });
  return buckets;
});

function getRiskClass(level) {
  if (level <= 4) return 'low';
  if (level <= 9) return 'medium';
  if (level <= 14) return 'high';
  if (level <= 19) return 'critical';
  return 'extreme';
}

function getRiskLabel(level) {
  if (level <= 4) return 'Faible';
  if (level <= 9) return 'Modéré';
  if (level <= 14) return 'Élevé';
  if (level <= 19) return 'Critique';
  return 'Inacceptable';
}

function normalizeStatus(status) {
  return (status || '').toLowerCase().replace(/\s+/g, '-');
}

function truncate(text, maxLen) {
  return text && text.length > maxLen ? text.substring(0, maxLen) + '...' : text;
}

function formatDate(isoString) {
  if (!isoString) return '-';
  try {
    return new Date(isoString).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' });
  } catch {
    return '-';
  }
}

// --- Actions CRUD ---
async function loadRiskOwners() {
  try {
    const { data } = await apiClient.get("/risks/owners");
    riskOwners.value = Array.isArray(data) ? data : [];
  } catch (err) {
    console.error("Erreur chargement responsables:", err);
    riskOwners.value = [];
  }
}
function getOwnerName(ownerId) {
  if (!ownerId) return "Non attribué";
  const owner = riskOwners.value.find(user => user.id === ownerId);
  return owner ? owner.full_name : "Utilisateur";
}

async function loadRisks() {
  loading.value = true;
  try {
    const { data } = await apiClient.get('/risks/');
    risks.value = Array.isArray(data) ? data : [];
  } catch (err) {
    console.error('Erreur chargement risques:', err);
    risks.value = [];
  } finally {
    loading.value = false;
  }
}

function openCreateModal() {
  editingRisk.value = null;
  Object.assign(formData, {
    ref: '', title: '', description: '', threat: '', impact: 3, likelihood: 3,
    site: '', owner_id: '', status: 'Ouvert', treatment_plan: ''
  });
  showModal.value = true;
}

function editRisk(risk) {
  editingRisk.value = risk;
  Object.assign(formData, {
    ref: risk.ref,
    title: risk.title,
    description: risk.description || '',
    threat: risk.threat || '',
    impact: risk.impact,
    likelihood: risk.likelihood,
    site: risk.site || '',
    owner_id: risk.owner_id || '',
    status: risk.status,
    treatment_plan: risk.treatment_plan || ''
  });
  showModal.value = true;
}

function closeModal() {
  showModal.value = false;
  editingRisk.value = null;
}

// --- Action Assistant IA (payload complet et typé) ---
function openAiAssistant(risk) {
  selectedRiskForAi.value = {
    ref: risk.ref || 'SANS-REF',
    title: risk.title || 'Risque sans titre',
    description: risk.description || risk.treatment_plan || risk.title || '',
    threat: risk.threat || '',
    impact: risk.impact || 3,
    likelihood: risk.likelihood || 3,
    site: risk.site || ''
  };
  showAiPanel.value = true;
}

// --- Action Plan d'Action (UNE SEULE FOIS !) ---
function openActionsPanel(risk) {
  selectedRiskIdForActions.value = risk.id;
  selectedRiskTitleForActions.value = risk.title;
  showActionsPanel.value = true;
}

// Handler pour fermer le panel et recharger si besoin
function handleCloseActionsPanel() {
  showActionsPanel.value = false;
  // Optionnel : Recharger les risques pour voir si le statut a changé suite aux actions
  // loadRisks(); 
}

async function saveRisk() {
  saving.value = true;
  try {
    // Nettoyage du payload : owner_id vide → null (le backend attend UUID ou null, pas "")
    const payload = { ...formData };
    if (!payload.owner_id || !payload.owner_id.trim()) {
      payload.owner_id = null;
    }

    if (editingRisk.value) {
      await apiClient.put(`/risks/${editingRisk.value.id}`, payload);
    } else {
      await apiClient.post('/risks/', payload);
    }
    await loadRisks();
    closeModal();
  } catch (err) {
    const detail = err.response?.data?.detail;
    if (Array.isArray(detail)) {
      alert('Données invalides : ' + detail.map(d => `${(d.loc || []).join('.')} — ${d.msg}`).join('\n'));
    } else {
      alert(detail || 'Erreur sauvegarde risque.');
    }
  } finally {
    saving.value = false;
  }
}

async function deleteRisk(id) {
  if (!confirm('Supprimer définitivement ce risque ? Cette action est irréversible.')) return;
  try {
    await apiClient.delete(`/risks/${id}`);
    await loadRisks();
  } catch (err) {
    alert(err.response?.data?.detail || 'Erreur suppression.');
  }
}

onMounted(() => { loadRisks(); loadRiskOwners(); });
</script>

<style scoped>
/* Styles existants améliorés */
.risks-page { max-width: 1400px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.page-header h1 { font-size: 1.5rem; color: #0f172a; }
.add-risk-btn { padding: 0.6rem 1.2rem; background: #0ea5e9; color: white; border: none; border-radius: 6px; font-weight: 600; cursor: pointer; }
.add-risk-btn:hover { background: #0284c7; }

/* Heatmap */
.heatmap-summary { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0.75rem; margin-bottom: 1.5rem; }
.heat-cell { padding: 1rem; border-radius: 8px; text-align: center; color: white; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.08); transition: transform 0.2s; }
.heat-cell:hover { transform: translateY(-2px); }
.heat-cell strong { font-size: 1.8rem; display: block; }
.heat-cell span { font-size: 0.85rem; opacity: 0.9; }
.low { background: #22c55e; }
.medium { background: #eab308; }
.high { background: #f97316; }
.critical { background: #ef4444; }
.extreme { background: #7f1d1d; }

.risk-matrix-card { background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem; margin-bottom: 1.25rem; }
.matrix-header { display: flex; justify-content: space-between; align-items: center; gap: 1rem; margin-bottom: 1rem; }
.matrix-header h2 { margin: 0; color: #0f172a; font-size: 1.1rem; }
.matrix-header p { margin: .3rem 0 0; color: #64748b; font-size: .85rem; }
.matrix-axis-row { max-width: 540px; margin: 0 auto .35rem; display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); text-align: center; color: #64748b; font-size: .65rem; }\n.matrix-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: .35rem; max-width: 540px; margin: auto; }
.matrix-cell { aspect-ratio: 1; border: 2px solid transparent; border-radius: 6px; color: white; cursor: pointer; display: flex; flex-direction: column; justify-content: center; align-items: center; gap: .15rem; }
.matrix-cell small { font-size: .7rem; opacity: .9; }
.matrix-cell strong { font-size: 1.1rem; }
.matrix-cell.selected { border-color: #0f172a; outline: 2px solid white; }
.matrix-cell:hover { filter: brightness(.92); transform: scale(1.03); }
.matrix-x-label { text-align: center; color: #64748b; font-size: .75rem; font-weight: 700; margin-top: .5rem; }
.risk-filters { display: flex; gap: .75rem; flex-wrap: wrap; align-items: center; margin: 0 0 1rem; }
.risk-filters input, .risk-filters select { min-height: 40px; padding: .5rem .75rem; border: 1px solid #cbd5e1; border-radius: 8px; background: white; }
.risk-filters input { flex: 1; min-width: 220px; }
.risk-filters span { color: #64748b; font-size: .85rem; }\n.export-btn { min-height: 40px; padding: .5rem .75rem; border: 1px solid #cbd5e1; border-radius: 8px; background: #0f172a; color: white; cursor: pointer; }
@media (max-width: 640px) { .heatmap-summary { grid-template-columns: repeat(2, 1fr); } .matrix-cell strong { font-size: .9rem; } }
\n/* Table */
.table-container { overflow-x: auto; background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.risks-table { width: 100%; border-collapse: collapse; min-width: 900px; }
.risks-table th, .risks-table td { padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid #e2e8f0; vertical-align: middle; }
.risks-table th { background: #f8fafc; font-weight: 600; color: #475569; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.5px; position: sticky; top: 0; z-index: 10; }
.risks-table tr:hover { background: #f1f5f9; }
.threat-hint { color: #64748b; font-size: 0.8rem; }

.risk-badge { display: inline-block; padding: 0.25rem 0.6rem; border-radius: 12px; font-size: 0.8rem; font-weight: 700; color: white; }
.risk-badge.low { background: #22c55e; }
.risk-badge.medium { background: #eab308; }
.risk-badge.high { background: #f97316; }
.risk-badge.critical { background: #ef4444; }
.risk-badge.extreme { background: #7f1d1d; }

.status-pill { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
.status-ouvert { background: #fef3c7; color: #92400e; }
.status-en-traitement { background: #dbeafe; color: #1e40af; }
.status-traité { background: #dcfce7; color: #166534; }
.status-accepté { background: #f3e8ff; color: #6b21a8; }

.actions-cell { display: flex; gap: 0.4rem; }
.action-btn { padding: 0.3rem 0.6rem; border: none; border-radius: 4px; cursor: pointer; font-size: 0.9rem; transition: all 0.15s; }
.action-btn:hover { transform: scale(1.1); }
.action-btn.edit { background: #dbeafe; color: #1d4ed8; }
.action-btn.delete { background: #fee2e2; color: #dc2626; }
.action-btn.ai { background: #ede9fe; color: #6d28d9; font-weight: bold; }
.action-btn.pac { background: #fef3c7; color: #92400e; font-weight: bold; } /* ✅ Style Plan d'Action */

.loading-row, .empty-state { text-align: center; color: #64748b; padding: 2rem !important; }

/* Modal */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; justify-content: center; align-items: center; z-index: 1000; backdrop-filter: blur(2px); }
.modal-content { background: white; border-radius: 12px; padding: 2rem; width: 90%; max-width: 650px; max-height: 90vh; overflow-y: auto; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1); }
.modal-content h2 { margin-top: 0; margin-bottom: 1.5rem; color: #0f172a; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.5rem; }
.risk-form { display: flex; flex-direction: column; gap: 1rem; }
.risk-form label { font-size: 0.85rem; font-weight: 600; color: #334155; margin-bottom: 0.25rem; display: block; }
.risk-form input, .risk-form textarea, .risk-form select { width: 100%; padding: 0.6rem; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 0.95rem; box-sizing: border-box; }
.risk-form input:focus, .risk-form textarea:focus { outline: 2px solid #0ea5e9; border-color: transparent; }
.matrix-inputs { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.computed-level { background: #f1f5f9; padding: 0.75rem; border-radius: 6px; text-align: center; font-size: 0.9rem; display: flex; justify-content: center; align-items: center; gap: 0.75rem; }
.level-label { padding: 0.2rem 0.6rem; border-radius: 12px; font-weight: 700; color: white; font-size: 0.8rem; }
.level-label.low { background: #22c55e; }
.level-label.medium { background: #eab308; }
.level-label.high { background: #f97316; }
.level-label.critical { background: #ef4444; }
.level-label.extreme { background: #7f1d1d; }
.modal-actions { display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #e2e8f0; }
.cancel-btn { padding: 0.6rem 1.2rem; background: #e2e8f0; color: #475569; border: none; border-radius: 6px; cursor: pointer; font-weight: 500; }
.save-btn { padding: 0.6rem 1.2rem; background: #0ea5e9; color: white; border: none; border-radius: 6px; font-weight: 600; cursor: pointer; }
.save-btn:disabled { opacity: 0.6; cursor: not-allowed; }
</style>