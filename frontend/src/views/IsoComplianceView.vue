<!-- frontend/src/views/IsoComplianceView.vue -->
<template>
  <div class="iso-page">
    <!-- En-tête & Score Global Intégré -->
    <div class="header-section">
      <div class="title-area">
        <h1>Matrice de Conformité ISO 27002:2022</h1>
        <p class="subtitle">Indicateur déclaratif : les liens risques/actions ne constituent pas une preuve de conformité. Chaque contrôle doit être évalué et justifié.</p>
      </div>
      
      <!-- Indicateurs déclaratifs et évaluations formelles -->
      <div class="compliance-kpi-grid">
        <div class="global-score-badge" :class="getScoreClass(matrixData?.overall_score)">
          <span class="score-val">{{ matrixData?.overall_score || 0 }}%</span>
          <span class="score-lbl">COUVERTURE DÉCLARÉE</span>
        </div>
        <div class="compliance-kpi-card">
          <strong>{{ matrixData?.evaluated_count || 0 }}/{{ matrixData?.total_controls || 0 }}</strong>
          <span>Contrôles évalués</span>
        </div>
        <div class="compliance-kpi-card">
          <strong>{{ matrixData?.applicable_count || 0 }}</strong>
          <span>Contrôles applicables évalués</span>
        </div>
        <div class="compliance-kpi-card">
          <strong>{{ matrixData?.average_maturity ?? '—' }}/5</strong>
          <span>Maturité moyenne</span>
        </div>
      </div>
    </div>

    <!-- Section 1: Heatmap Domaines (Style Blocs Pleins) -->
    <section class="domain-heatmap">
      <div class="heat-cell blue">
        <strong>{{ getDomainCount('Organisation') }}</strong>
        <span>Organisationnels<br/>(A.5)</span>
      </div>
      <div class="heat-cell purple">
        <strong>{{ getDomainCount('Personnel') }}</strong>
        <span>Personnes / RH<br/>(A.6)</span>
      </div>
      <div class="heat-cell orange">
        <strong>{{ getDomainCount('Physique') }}</strong>
        <span>Sécurité Physique<br/>(A.7)</span>
      </div>
      <div class="heat-cell pink">
        <strong>{{ getDomainCount('Technique') }}</strong>
        <span>Technologique<br/>(A.8)</span>
      </div>
    </section>

    <!-- Filtres Modernes -->
    <div class="filters-bar card-modern">
      <input v-model.trim="filterSearch" type="search" class="filter-select modern" placeholder="🔎 Rechercher référence ou contrôle..." aria-label="Rechercher un contrôle ISO" />
      <select v-model="filterDomain" class="filter-select modern">
        <option value="">📂 Tous les Domaines</option>
        <option v-for="d in domains" :key="d" :value="d">{{ d }}</option>
      </select>
      
      <select v-model="filterStatus" class="filter-select modern">
        <option value="">🚦 Tous les Statuts</option>
        <option value="Déclaré couvert">⚠️ Déclaré couvert</option>
        <option value="À vérifier">🟡 À vérifier</option>
        <option value="Non évalué">⚪ Non évalué</option>
      </select>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="loading-state card-modern">
      <div class="spinner-small"></div> Calcul de la matrice...
    </div>

    <!-- Table Grid Moderne -->
    <div v-else-if="matrixData" class="table-container card-modern">\n      <div class="compliance-table-toolbar"><span>{{ filteredRows.length }} contrôle(s)</span><button type="button" class="btn-export" @click="exportMatrixCsv" :disabled="filteredRows.length === 0">Exporter CSV</button></div>\n      <p class="methodology-note">{{ matrixData.methodology }}</p>
      <table class="iso-table modern">
        <thead>
          <tr>
            <th>Réf.</th>
            <th>Titre Contrôle</th>
            <th>Domaine</th>
            <th>Statut</th>
            <th>Liens Risques</th>
            <th>Action IA</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="filteredRows.length === 0">
            <td colspan="6" class="empty-filter-state">Aucun contrôle ne correspond aux filtres sélectionnés.</td>
          </tr>
          <tr v-for="row in filteredRows" :key="row.ref_code" class="table-row-hover">
            <td><code class="ref-code">{{ row.ref_code }}</code></td>
            <td class="title-cell">{{ row.title }}</td>
            <td>
              <span class="domain-tag" :class="'tag-' + normalizeDomain(row.domain)">
                {{ row.domain }}
              </span>
            </td>
            <td>
              <div class="status-cell">
                <span class="status-badge modern" :class="getStatusClass(row.status)">
                  {{ getStatusIcon(row.status) }} {{ row.status }}
                </span>
                <span v-if="row.latest_assessment_status" class="assessment-status-tag">
                  {{ row.latest_assessment_status }} · {{ row.latest_assessment_maturity }}/5
                </span>
                <span v-else class="assessment-status-tag muted">Aucune évaluation formelle</span>
              </div>
            </td>
            <td class="links-count">
              <span v-if="row.linked_risks_count > 0" class="link-pill active">
                🔗 {{ row.linked_risks_count }}
              </span>
              <span v-else class="link-pill inactive">—</span>
            </td>
            <td>
              <button @click="openAssessment(row)" class="btn-assess modern" title="Évaluer et consulter l'historique">
                📝 Évaluer
              </button>
              <button @click="askAiGapAnalysis(row)" class="btn-ai-gap modern" title="Analyser l'écart avec l'IA">
                ✨ Justifier
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    
    <div v-else class="error-state card-modern">Impossible de charger la matrice.</div>

    <!-- Modal d'évaluation formelle ISO -->
    <Teleport to="body">
      <div v-if="showAssessmentPanel" class="modal-overlay" @click.self="closeAssessment">
        <div class="ai-modal-card assessment-modal">
          <div class="modal-header">
            <div class="header-icon">📝</div>
            <div class="header-text">
              <h2>Évaluation du contrôle</h2>
              <p class="control-ref">{{ selectedControl?.ref_code }} — {{ selectedControl?.title }}</p>
            </div>
            <button @click="closeAssessment" class="close-btn">×</button>
          </div>
          <div class="assessment-form">
            <label>Applicabilité
              <select v-model="assessmentForm.applicability">
                <option>Applicable</option><option>Non applicable</option>
              </select>
            </label>
            <label>État d'implémentation
              <select v-model="assessmentForm.implementation_status">
                <option>Non démarré</option><option>En cours</option><option>Partiellement implémenté</option><option>Implémenté</option>
              </select>
            </label>
            <label>Niveau de maturité (0 à 5)
              <input v-model.number="assessmentForm.maturity_level" type="number" min="0" max="5" />
            </label>
            <label>Justification <textarea v-model="assessmentForm.justification" rows="3" maxlength="10000" placeholder="Décrire la situation, la mise en œuvre et les éléments vérifiés"></textarea></label>
            <label>Écart identifié / mesures à prévoir <textarea v-model="assessmentForm.gap_description" rows="3" maxlength="10000" placeholder="Écart, actions ou justification de non-applicabilité"></textarea></label>
            <div v-if="assessmentError" class="alert-error-box">{{ assessmentError }}</div>
            <button class="primary-action-btn" @click="saveAssessment" :disabled="assessmentSaving || !assessmentForm.justification.trim()">
              {{ assessmentSaving ? 'Enregistrement...' : 'Enregistrer une évaluation' }}
            </button>
          </div>
          <section class="assessment-history">
            <h3>Historique des évaluations</h3>
            <div v-if="assessmentLoading" class="loading-state">Chargement...</div>
            <div v-else-if="assessmentHistory.length === 0" class="empty-filter-state">Aucune évaluation formelle enregistrée.</div>
            <article v-for="entry in assessmentHistory" :key="entry.id" class="assessment-history-item">
              <div class="assessment-history-head"><strong>{{ entry.implementation_status }} · Maturité {{ entry.maturity_level }}/5</strong><span>{{ new Date(entry.assessed_at).toLocaleString() }}</span></div>
              <p><strong>{{ entry.applicability }}</strong> — {{ entry.justification }}</p>
              <p v-if="entry.gap_description">{{ entry.gap_description }}</p>
            </article>
          </section>
        </div>
      </div>
    </Teleport>

    <!-- Modal IA Gap Analysis (REDESIGN ÉLÉGANT) -->
    <Teleport to="body">
      <Transition name="fade-scale">
        <div v-if="showAiPanel" class="modal-overlay" @click.self="closeModal">
          <div class="ai-modal-card">
            
            <!-- Header du Modal -->
            <div class="modal-header">
              <div class="header-icon">✨</div>
              <div class="header-text">
                <h2>Analyse d'Écart IA</h2>
                <p class="control-ref">{{ aiPromptData?.control_ref }}</p>
              </div>
              <button @click="closeModal" class="close-btn">×</button>
            </div>

            <!-- Contexte Métier -->
            <div class="context-box">
              <div class="context-item">
                <span class="label">Contrôle :</span>
                <span class="value">{{ aiPromptData?.control_title }}</span>
              </div>
              <div class="context-item">
                <span class="label">Statut Actuel :</span>
                <span class="badge-warning">{{ aiPromptData?.current_status }}</span>
              </div>
            </div>

            <!-- Zone de Résultat IA -->
            <div class="result-area">
              <textarea 
                v-model="aiResponseText" 
                readonly 
                rows="6" 
                placeholder="En attente de réponse..."
                class="ai-output-area"
                :class="{ 'error-text': !!aiError }"
              ></textarea>
              
              <!-- Message d'Erreur Visible si échec réel -->
              <div v-if="aiError" class="alert-error-box">
                ⚠️ {{ aiError }}
              </div>
            </div>

            <!-- Actions Footer -->
            <div class="modal-footer">
              <button @click="runAiAnalysis" :disabled="aiLoading" class="primary-action-btn">
                <span v-if="!aiLoading">🚀 Lancer l'analyse</span>
                <span v-else class="loading-spinner-inline"></span> Analyse en cours...
              </button>
              <button @click="closeModal" class="secondary-action-btn">Fermer</button>
            </div>
            
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import apiClient from '@/services/api';

const loading = ref(true);
const matrixData = ref(null);
const filterDomain = ref('');
const filterStatus = ref('');
const filterSearch = ref('');
const showAssessmentPanel = ref(false);
const selectedControl = ref(null);
const assessmentHistory = ref([]);
const assessmentLoading = ref(false);
const assessmentSaving = ref(false);
const assessmentError = ref('');
const assessmentForm = ref({ applicability: 'Applicable', implementation_status: 'Non démarré', maturity_level: 0, justification: '', gap_description: '' });

// État IA
const showAiPanel = ref(false);
const aiPromptData = ref(null);
const aiResponseText = ref('');
const aiLoading = ref(false);
const aiError = ref(null); 

const domains = computed(() => {
  if (!matrixData.value) return [];
  const set = new Set(matrixData.value.rows.map(r => r.domain));
  return Array.from(set).sort();
});

const filteredRows = computed(() => {
  if (!matrixData.value) return [];
  return matrixData.value.rows.filter(r => {
    const matchDomain = !filterDomain.value || r.domain === filterDomain.value;
    const matchStatus = !filterStatus.value || r.status === filterStatus.value;
    const query = filterSearch.value.toLocaleLowerCase();
    const matchSearch = !query || r.ref_code.toLocaleLowerCase().includes(query) || r.title.toLocaleLowerCase().includes(query) || r.domain.toLocaleLowerCase().includes(query);
    return matchDomain && matchStatus && matchSearch;
  });
});

function getDomainCount(domainName) {
  if (!matrixData.value) return 0;
  let count = 0;
  matrixData.value.rows.forEach(r => {
    if (domainName === 'Organisation' && r.domain.includes('Organis')) count++;
    else if (domainName === 'Personnel' && (r.domain.includes('Personnel') || r.domain.includes('RH'))) count++;
    else if (domainName === 'Physique' && r.domain.includes('Physique')) count++;
    else if (domainName === 'Technique' && (r.domain.includes('Tech') || r.domain.includes('Cloud') || r.domain.includes('Network'))) count++;
  });
  return count;
}

function getStatusClass(status) {
  switch(status) {
    case 'Déclaré couvert': return 'st-declared';
    case 'À vérifier': return 'st-partial';
    case 'Non évalué': return 'st-uncovered';
    default: return '';
  }
}

function getStatusIcon(status) {
  switch(status) {
    case 'Déclaré couvert': return '⚠️';
    case 'À vérifier': return '🟡';
    case 'Non évalué': return '⚪';
    default: return '•';
  }
}

async function openAssessment(row) {
  selectedControl.value = row;
  showAssessmentPanel.value = true;
  assessmentError.value = '';
  assessmentForm.value = { applicability: 'Applicable', implementation_status: 'Non démarré', maturity_level: 0, justification: '', gap_description: '' };
  assessmentLoading.value = true;
  try {
    const { data } = await apiClient.get(`/compliance/controls/${encodeURIComponent(row.ref_code)}/assessments`);
    assessmentHistory.value = Array.isArray(data) ? data : [];
  } catch (error) {
    assessmentError.value = error.response?.data?.detail || "Impossible de charger l'historique.";
    assessmentHistory.value = [];
  } finally {
    assessmentLoading.value = false;
  }
}
function closeAssessment() {
  showAssessmentPanel.value = false;
  selectedControl.value = null;
}
async function saveAssessment() {
  if (!selectedControl.value || !assessmentForm.value.justification.trim()) return;
  assessmentSaving.value = true;
  assessmentError.value = '';
  try {
    const payload = { ...assessmentForm.value, justification: assessmentForm.value.justification.trim(), gap_description: assessmentForm.value.gap_description.trim() || null };
    const { data } = await apiClient.post(`/compliance/controls/${encodeURIComponent(selectedControl.value.ref_code)}/assessments`, payload);
    assessmentHistory.value = [data, ...assessmentHistory.value];
    assessmentForm.value = { applicability: 'Applicable', implementation_status: 'Non démarré', maturity_level: 0, justification: '', gap_description: '' };
  } catch (error) {
    assessmentError.value = error.response?.data?.detail || "Échec de l'enregistrement de l'évaluation.";
  } finally {
    assessmentSaving.value = false;
  }
}

function exportMatrixCsv() {
  const headers = ['Référence', 'Titre', 'Domaine', 'Statut', 'Risques liés'];
  const escapeCsv = (value) => {
    let text = String(value ?? '');
    if (/^[=+@\-]/.test(text)) text = "'" + text;
    return '"' + text.replace(/"/g, '""') + '"';
  };
  const lines = [headers, ...filteredRows.value.map(row => [
    row.ref_code, row.title, row.domain, row.status, row.linked_risks_count
  ])].map(row => row.map(escapeCsv).join(';'));
  const csv = '\uFEFF' + lines.join('\r\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'pgcc-matrice-conformite-iso27002.csv';
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function getScoreClass(score) {
  if (score >= 80) return 'score-high';
  if (score >= 50) return 'score-med';
  return 'score-low';
}

function normalizeDomain(dom) {
  return dom.toLowerCase().replace(/\s+/g, '-').substring(0, 4); 
}

async function fetchMatrix() {
  loading.value = true;
  try {
    const { data } = await apiClient.get('/compliance/matrix');
    matrixData.value = data;
  } catch (err) {
    console.error(err);
    alert("Erreur chargement conformité.");
  } finally {
    loading.value = false;
  }
}

function askAiGapAnalysis(row) {
  aiPromptData.value = {
    control_ref: row.ref_code,
    control_title: row.title,
    current_status: row.status
  };
  aiResponseText.value = ""; 
  aiError.value = null; 
  showAiPanel.value = true;
}

function closeModal() {
  showAiPanel.value = false;
  setTimeout(() => { // Reset après animation fermeture
    aiResponseText.value = "";
    aiError.value = null;
    aiPromptData.value = null;
  }, 300);
}

async function runAiAnalysis() {
  if (!aiPromptData.value) return;
  
  aiLoading.value = true;
  aiError.value = null;
  aiResponseText.value = "";
  
  try {
    const prompt = `Tu es expert ISO 27002:2022. Le contrôle ${aiPromptData.value.control_ref} (${aiPromptData.value.control_title}) est actuellement "${aiPromptData.value.current_status}" dans notre registre CTF. Rédige une justification courte (max 3 phrases) expliquant cet écart et proposant une action corrective prioritaire.`;
    
    // APPEL RÉEL SANS FALLBACK SIMULÉ
    const response = await apiClient.post('/ai/generate', { 
      prompt: prompt, 
      model: "phi3:latest" 
    });
    
    let result = "";
    if (response.data.response) result = response.data.response;
    else if (response.data.text) result = response.data.text;
    else if (typeof response.data === 'string') result = response.data;
    else result = JSON.stringify(response.data);
    
    aiResponseText.value = result.trim();
    
  } catch (err) {
    console.error("Erreur appel IA:", err);
    
    if (err.code === 'ECONNABORTED') {
      aiError.value = "⏱️ Timeout : L'IA locale (Ollama) n'a pas répondu dans les délais.";
    } else if (err.response?.data?.detail) {
      aiError.value = `❌ Erreur Backend : ${err.response.data.detail}`;
    } else {
      aiError.value = `❌ Échec Réseau : ${err.message || "Connexion impossible vers Ollama."}`;
    }
  } finally {
    aiLoading.value = false;
  }
}

onMounted(fetchMatrix);
</script>

<style scoped>
.compliance-kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:1rem; align-items:stretch; }
.compliance-kpi-card { background:#fff; border:1px solid #e2e8f0; border-radius:12px; padding:1rem; display:flex; flex-direction:column; justify-content:center; gap:.4rem; }
.compliance-kpi-card strong { font-size:1.45rem; color:#0f172a; }
.compliance-kpi-card span { font-size:.82rem; color:#64748b; }
.status-cell { display:flex; flex-direction:column; align-items:flex-start; gap:.4rem; }
.assessment-status-tag { font-size:.75rem; color:#0f766e; background:#f0fdfa; border:1px solid #99f6e4; border-radius:6px; padding:.2rem .45rem; }
.assessment-status-tag.muted { color:#64748b; background:#f8fafc; border-color:#e2e8f0; }
.btn-assess { border:1px solid #0f766e; background:#ecfdf5; color:#065f46; padding:.4rem .65rem; border-radius:7px; cursor:pointer; margin-right:.35rem; }
.assessment-modal { max-height:90vh; overflow-y:auto; width:min(760px,95vw); }
.assessment-form { display:grid; gap:.8rem; }
.assessment-form label { display:grid; gap:.35rem; color:#334155; font-weight:600; }
.assessment-form input,.assessment-form select,.assessment-form textarea { width:100%; border:1px solid #cbd5e1; border-radius:8px; padding:.65rem; font:inherit; }
.assessment-history { border-top:1px solid #e2e8f0; margin-top:1.2rem; padding-top:1rem; }
.assessment-history-item { border:1px solid #e2e8f0; border-radius:8px; padding:.75rem; margin:.5rem 0; }
.assessment-history-head { display:flex; justify-content:space-between; gap:.5rem; flex-wrap:wrap; }
.assessment-history-head span { color:#64748b; font-size:.85rem; }
.compliance-table-toolbar { display:flex; justify-content:space-between; align-items:center; gap:1rem; margin-bottom:1rem; color:#64748b; font-size:.9rem; }
.btn-export { border:1px solid #cbd5e1; background:#fff; color:#334155; padding:.5rem .8rem; border-radius:8px; cursor:pointer; font-weight:600; }
.btn-export:hover:not(:disabled) { background:#f1f5f9; }
.btn-export:disabled { opacity:.5; cursor:not-allowed; }
.empty-filter-state { text-align: center !important; padding: 2rem !important; color: #64748b; font-style: italic; }
.methodology-note { margin: 0 0 1rem; padding: 0.75rem 1rem; border-left: 4px solid #f59e0b; background: #fffbeb; color: #92400e; font-size: 0.9rem; line-height: 1.5; }
/* Styles Page Principale (Inchangés) */
.iso-page { padding: 2rem; max-width: 1400px; margin: 0 auto; background: #f8fafc; min-height: 100vh; }
.header-section { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 2rem; gap: 2rem; }
.title-area h1 { color: #0f172a; font-size: 1.8rem; margin-bottom: 0.25rem; }
.subtitle { color: #64748b; margin-bottom: 0; }
.global-score-badge { background: white; padding: 1.5rem 2rem; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); text-align: center; min-width: 160px; border-top: 5px solid transparent; transition: all 0.3s; }
.score-val { font-size: 2.8rem; font-weight: bold; display: block; line-height: 1; margin-bottom: 0.5rem; }
.score-lbl { font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }
.score-high { border-top-color: #22c55e; } .score-high .score-val { color: #22c55e; }
.score-med { border-top-color: #eab308; } .score-med .score-val { color: #eab308; }
.score-low { border-top-color: #ef4444; } .score-low .score-val { color: #ef4444; }
.domain-heatmap { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }
.heat-cell { padding: 1.5rem; border-radius: 12px; text-align: center; color: white; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.08); transition: transform 0.2s; cursor: default; }
.heat-cell:hover { transform: translateY(-2px); }
.heat-cell strong { font-size: 2.5rem; display: block; margin-bottom: 0.5rem; }
.heat-cell span { font-size: 0.85rem; opacity: 0.9; line-height: 1.3; }
.blue { background: #3b82f6; } .purple { background: #8b5cf6; } .orange { background: #f97316; } .pink { background: #ec4899; }
.filters-bar { display: flex; gap: 1rem; margin-bottom: 1.5rem; padding: 1rem; background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
.filter-select.modern { padding: 0.6rem 1rem; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 0.95rem; cursor: pointer; background: #f8fafc; min-width: 200px; }
.card-modern { background: white; border-radius: 12px; padding: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 1.5rem; }
.table-container { overflow-x: auto; }
.iso-table.modern { width: 100%; border-collapse: collapse; }
.iso-table.modern th, .iso-table.modern td { padding: 1rem; text-align: left; border-bottom: 1px solid #f1f5f9; vertical-align: middle; }
.iso-table.modern th { background: #f8fafc; font-weight: 600; color: #475569; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.5px; position: sticky; top: 0; z-index: 10; }
.table-row-hover:hover { background: #f8fafc; transition: background 0.2s; }
.ref-code { font-family: monospace; font-weight: 700; color: #0f172a; background: #f1f5f9; padding: 0.2rem 0.5rem; border-radius: 4px; }
.title-cell { font-weight: 500; color: #334155; }
.domain-tag { display: inline-block; padding: 0.25rem 0.6rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; text-transform: capitalize; }
.tag-orga { background: #dbeafe; color: #1d4ed8; } .tag-pers { background: #ede9fe; color: #6d28d9; } .tag-phys { background: #ffedd5; color: #c2410c; } .tag-tech { background: #fce7f3; color: #be185d; }
.status-badge.modern { display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.8rem; font-weight: 700; }
.st-declared { background: #fef3c7; color: #92400e; } .st-partial { background: #fef3c7; color: #92400e; } .st-uncovered { background: #fee2e2; color: #991b1b; }
.links-count .link-pill { padding: 0.2rem 0.5rem; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }
.active { background: #eff6ff; color: #1d4ed8; } .inactive { color: #94a3b8; }
.btn-ai-gap.modern { background: #ede9fe; color: #6d28d9; border: none; padding: 0.4rem 0.8rem; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 0.85rem; transition: all 0.2s; }
.btn-ai-gap.modern:hover { background: #ddd6fe; transform: translateY(-1px); }
.loading-state, .error-state { text-align: center; padding: 3rem; color: #64748b; font-style: italic; }

/* =========================================================
   NOUVEAU DESIGN MODAL IA (ÉLÉGANT & PROPRE)
   ========================================================= */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(15, 23, 42, 0.6); /* Fond sombre flou */
  backdrop-filter: blur(4px); z-index: 2000;
  display: flex; justify-content: center; align-items: center;
}

.ai-modal-card {
  background: white; width: 90%; max-width: 650px; border-radius: 16px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  overflow: hidden; display: flex; flex-direction: column;
  animation: slideUp 0.3s ease-out;
}

@keyframes slideUp {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.fade-scale-enter-active, .fade-scale-leave-active { transition: opacity 0.3s, transform 0.3s; }
.fade-scale-enter-from, .fade-scale-leave-to { opacity: 0; transform: scale(0.95); }

.modal-header {
  padding: 1.5rem 2rem; border-bottom: 1px solid #f1f5f9;
  display: flex; align-items: center; gap: 1rem; background: #f8fafc;
}
.header-icon { font-size: 1.8rem; }
.header-text h2 { margin: 0; font-size: 1.25rem; color: #0f172a; }
.control-ref { font-family: monospace; font-size: 0.85rem; color: #64748b; margin: 0; }
.close-btn {
  margin-left: auto; background: none; border: none; font-size: 1.5rem; 
  color: #94a3b8; cursor: pointer; transition: color 0.2s;
}
.close-btn:hover { color: #ef4444; }

.context-box {
  padding: 1.5rem 2rem; background: #fffbeb; /* Jaune très pâle pour contexte */
  border-bottom: 1px solid #fef3c7;
}
.context-item { display: flex; justify-content: space-between; margin-bottom: 0.5rem; }
.context-item:last-child { margin-bottom: 0; }
.label { font-weight: 600; color: #475569; font-size: 0.9rem; }
.value { color: #0f172a; font-size: 0.9rem; text-align: right; max-width: 60%; word-break: break-word;}
.badge-warning { background: #fef3c7; color: #92400e; padding: 0.2rem 0.6rem; border-radius: 12px; font-weight: 700; font-size: 0.8rem; }

.result-area {
  padding: 1.5rem 2rem; flex: 1;
}
.ai-output-area {
  width: 100%; height: 150px; padding: 1rem; border: 1px solid #e2e8f0; border-radius: 8px;
  font-family: 'Segoe UI', sans-serif; font-size: 0.95rem; line-height: 1.5;
  background: #ffffff; resize: none; outline: none; transition: border-color 0.2s;
}
.ai-output-area:focus-within { border-color: #0ea5e9; box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.1); }
.ai-output-area.error-text { border-color: #fecaca; background: #fff1f2; color: #9f1239; }

.alert-error-box {
  margin-top: 1rem; padding: 0.75rem 1rem; background: #fee2e2; border-left: 4px solid #ef4444;
  color: #991b1b; border-radius: 6px; font-size: 0.9rem; font-weight: 500;
}

.modal-footer {
  padding: 1.25rem 2rem; background: #f8fafc; border-top: 1px solid #e2e8f0;
  display: flex; justify-content: flex-end; gap: 1rem;
}
.primary-action-btn {
  padding: 0.75rem 1.5rem; background: #0ea5e9; color: white; border: none;
  border-radius: 8px; font-weight: 600; cursor: pointer; transition: all 0.2s;
  display: flex; align-items: center; gap: 0.5rem;
}
.primary-action-btn:hover:not(:disabled) { background: #0284c7; transform: translateY(-1px); }
.primary-action-btn:disabled { opacity: 0.7; cursor: not-allowed; }
.secondary-action-btn {
  padding: 0.75rem 1.5rem; background: white; color: #475569; border: 1px solid #cbd5e1;
  border-radius: 8px; font-weight: 600; cursor: pointer; transition: all 0.2s;
}
.secondary-action-btn:hover { background: #f1f5f9; border-color: #94a3b8; }

.loading-spinner-inline {
  width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white; border-radius: 50%; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>