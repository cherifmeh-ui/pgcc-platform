<!-- frontend/src/views/DashboardView.vue -->
<template>
  <div class="dashboard-page">
    <!-- En-tête & Actions Globales -->
    <div class="header-section">
      <h1>Tableau de Bord Stratégique</h1>
      <p class="subtitle">Vue consolidée des risques SI, applications critiques et conformité CTF.</p>
      
      <div class="actions-row">
        <button @click="fetchAllRisks" :disabled="loading" class="action-btn secondary">
          {{ loading ? 'Actualisation...' : '🔄 Actualiser les données' }}
        </button>
        <button @click="generateReport" :disabled="generatingReport" class="action-btn primary">
          {{ generatingReport ? 'Analyse IA en cours...' : '✨ Générer Synthèse DG' }}
        </button>
      </div>
    </div>

    <!-- Messages d'Erreur API -->
    <div v-if="apiError" class="error-banner">
      <span>{{ apiError }}</span>
      <button @click="fetchAllRisks" class="retry-btn">Réessayer</button>
    </div>

    <!-- Section 1: KPIs Risques -->
    <section class="kpi-section">
      <h2>Indicateurs Clés de Risque</h2>
      <div class="kpi-grid">
        <div class="kpi-card critical">
          <span class="kpi-value">{{ stats.critical }}</span>
          <span class="kpi-label">Risques Inacceptables<br/>(Score ≥ 20)</span>
        </div>
        <div class="kpi-card high">
          <span class="kpi-value">{{ stats.high }}</span>
          <span class="kpi-label">Risques Critiques<br/>(Score 15-19)</span>
        </div>
        <div class="kpi-card medium">
          <span class="kpi-value">{{ stats.medium }}</span>
          <span class="kpi-label">Risques Élevés<br/>(Score 5-14)</span>
        </div>
        <div class="kpi-card low">
          <span class="kpi-value">{{ stats.low }}</span>
          <span class="kpi-label">Risques Modérés/Faibles<br/>(Score < 5)</span>
        </div>
      </div>
    </section>

    <!-- SECTION 2 : SUIVI DES PLANS D'ACTION (NOUVEAU) -->
    <section class="pac-kpi-section" v-if="actionsLoaded && actionStats.total > 0">
      <h2>Suivi des Plans d'Action Correctifs</h2>
      <div class="kpi-grid">
        <div class="kpi-card overdue-alert">
          <span class="kpi-value">{{ actionStats.overdue }}</span>
          <span class="kpi-label">Actions en retard<br/>(Deadline dépassée)</span>
        </div>
        <div class="kpi-card progress-active">
          <span class="kpi-value">{{ actionStats.inProgress }}</span>
          <span class="kpi-label">Actions en cours<br/>(Traitement actif)</span>
        </div>
        <div class="kpi-card blocked-alert">
          <span class="kpi-value">{{ actionStats.blocked }}</span>
          <span class="kpi-label">Actions bloquées</span>
        </div>
        <div class="kpi-card success-rate">
          <span class="kpi-value">{{ actionStats.completionRate }}%</span>
          <span class="kpi-label">Taux de réalisation<br/>(Terminé / Total)</span>
        </div>
      </div>
    </section>

    <!-- Section 3: Graphiques Chart.js -->
    <section class="charts-section" v-if="chartDataReady">
      <h2>Analyse Visuelle</h2>
      <div class="grid-layout">
        <!-- Barre : Répartition par Niveau -->
        <div class="card chart-card">
          <h3>Répartition des Risques par Criticité</h3>
          <Bar :data="riskLevelChartData" :options="barOptions" />
        </div>
        
        <!-- Camembert : Origine des Menaces -->
        <div class="card chart-card">
          <h3>Typologie des Menaces</h3>
          <Pie :data="threatCategoryChartData" :options="pieOptions" />
        </div>

        <!-- NOUVEAU : Donut Statut Actions -->
        <div class="card chart-card" v-if="reportData && reportData.charts_data.pac_status">
          <h3>État d'avancement des Actions</h3>
          <Doughnut :data="pacStatusChartData" :options="doughnutOptions" />
        </div>
      </div>
    </section>

    <!-- Section 4: Rapport IA & Top Risques -->
    <section class="insights-section" v-if="reportData">
      <h2>Synthèse Direction Générale</h2>
      <div class="grid-layout">
        
        <!-- Encadré Texte IA -->
        <div class="card ai-insight-card">
          <h3>💡 Note de Synthèse (IA Phi3)</h3>
          <p class="ai-text">{{ reportData.ai_summary }}</p>
          <small class="timestamp">Généré le {{ new Date(reportData.generated_at).toLocaleString('fr-FR') }}</small>
        </div>

        <!-- Liste Top 5 Risques -->
        <div class="card top-risks-card">
          <h3>🔥 Priorités Absolues (Top 5)</h3>
          <ul class="risk-list">
            <li v-for="risk in reportData.top_5_risks" :key="risk.ref">
              <span class="badge-critical">{{ risk.score }}/25</span>
              <strong>{{ risk.ref }}</strong> - {{ truncate(risk.title, 40) }}
              <br/><small>{{ risk.site }} | Statut: {{ risk.status }}</small>
            </li>
          </ul>
        </div>
        
        <!-- Alertes Apps -->
        <div class="card apps-alert-card">
          <h3>⚠️ Applications Exposées</h3>
          <p>Criticité Haute/Critique détectée sur :</p>
          <div class="tags-container">
             <span v-for="app in reportData.obsolete_apps" :key="app" class="tag-app">{{ app }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Section 5: Derniers Risques Enregistrés -->
    <section class="recent-risks-section">
      <h2>Derniers Risques Enregistrés</h2>
      <div v-if="loading" class="loading-state">
        <div class="spinner-small"></div> Chargement...
      </div>
      <table v-else-if="recentRisks.length > 0" class="risks-preview-table">
        <thead>
          <tr>
            <th>Réf.</th>
            <th>Titre</th>
            <th>Niveau</th>
            <th>Date</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="risk in recentRisks" :key="risk.id">
            <td><code>{{ risk.ref }}</code></td>
            <td>{{ truncate(risk.title, 50) }}</td>
            <td><span class="badge" :class="getLevelClass(risk.risk_level)">{{ risk.risk_level }}</span></td>
            <td>{{ formatDate(risk.created_at) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-state">
        Aucun risque récent.<br/>
        <small>Vérifiez que vous avez créé au moins un risque via Swagger ou l'onglet "Registre des risques".</small>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import apiClient from '@/services/api';

// Imports Chart.js (Ajout de Doughnut)
import { Bar, Pie, Doughnut } from 'vue-chartjs';
import { 
  Chart as ChartJS, 
  Title, Tooltip, Legend, ArcElement, CategoryScale, LinearScale, BarElement 
} from 'chart.js';

// Enregistrement des modules Chart.js
ChartJS.register(Title, Tooltip, Legend, ArcElement, CategoryScale, LinearScale, BarElement);

const authStore = useAuthStore();

// --- État Local UI ---
const loading = ref(false);
const generatingReport = ref(false);
const apiError = ref(null);
const recentRisks = ref([]);
const reportData = ref(null); // Données du endpoint /reports/dg-summary
const actionsLoaded = ref(false);
const actionStats = reactive({ total: 0, overdue: 0, inProgress: 0, blocked: 0, done: 0, completionRate: 0 });

// Calcul des stats depuis la liste complète (pour les KPIs rapides sans appel IA)
const stats = reactive({
  critical: 0, high: 0, medium: 0, low: 0,
});

// Flag pour savoir si les données sont prêtes pour les graphiques
const chartDataReady = computed(() => Object.keys(stats).some(k => stats[k] > 0));

// --- Options Chart.js ---
const barOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { position: 'top' }, title: { display: false } }
};
const pieOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { position: 'right' }, title: { display: false } }
};
const doughnutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  cutout: '60%', // Effet donut creux
  plugins: { legend: { position: 'bottom' }, title: { display: false } }
};

// --- Données Graphiques Dynamiques ---
const riskLevelChartData = computed(() => ({
  labels: ['Faible (<5)', 'Modéré (5-9)', 'Élevé (10-14)', 'Critique (≥15)'],
  datasets: [{
    label: 'Nombre de risques',
    data: [stats.low, stats.medium, stats.high, stats.critical],
    backgroundColor: ['#22c55e', '#eab308', '#f97316', '#ef4444']
  }]
}));

const threatCategoryChartData = computed(() => {
  const cats = reportData.value?.charts_data?.categories || {};
  const labels = Object.keys(cats);
  const values = Object.values(cats);
  
  return {
    labels: labels.length ? labels : ['Données indisponibles'],
    datasets: [{
      data: values.length ? values : [1],
      backgroundColor: ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#64748b']
    }]
  };
});

// ⬇️ NOUVEAU : Données pour le graphique Donut Actions ⬇️
const pacStatusChartData = computed(() => {
  const statuses = reportData.value?.charts_data?.pac_status || {};
  const labels = Object.keys(statuses);
  const values = Object.values(statuses);
  
  return {
    labels: labels.length ? labels : ['Aucune action'],
    datasets: [{
      data: values.length ? values : [1],
      backgroundColor: ['#fef3c7', '#dbeafe', '#dcfce7', '#fee2e2'], // Jaune, Bleu, Vert, Rouge clair
      borderColor: ['#fbbf24', '#3b82f6', '#22c55e', '#ef4444'],
      borderWidth: 2
    }]
  };
});

// --- Fonctions Logique ---

async function fetchAllRisks() {
  loading.value = true;
  apiError.value = null;
  try {
    const { data } = await apiClient.get('/risks/');
    
    // Reset Stats
    stats.critical = 0; stats.high = 0; stats.medium = 0; stats.low = 0;
    
    if (!Array.isArray(data)) throw new Error("Format invalide");
    
    data.forEach(risk => {
      const lvl = risk.risk_level || 0;
      if (lvl >= 20) stats.critical++;
      else if (lvl >= 15) stats.high++;
      else if (lvl >= 5) stats.medium++;
      else stats.low++;
    });
    
    // Garder les 5 plus récents
    recentRisks.value = [...data]
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
      .slice(0, 5);
      
  } catch (err) {
    console.error("Erreur dashboard:", err);
    apiError.value = err.response?.data?.detail || "Impossible de charger les risques.";
  } finally {
    loading.value = false;
  }
}

async function fetchActionStats() {
  try {
    const { data } = await apiClient.get('/actions/');
    if (!Array.isArray(data)) throw new Error("Format invalide");
    const now = new Date();
    const total = data.length;
    const done = data.filter(a => a.status === "Terminé").length;
    actionStats.total = total;
    actionStats.done = done;
    actionStats.inProgress = data.filter(a => a.status === "En cours").length;
    actionStats.blocked = data.filter(a => a.status === "Bloqué").length;
    actionStats.overdue = data.filter(a => a.status !== "Terminé" && a.due_date && new Date(a.due_date) < now).length;
    actionStats.completionRate = total ? Math.round((done / total) * 100) : 0;
  } catch (err) {
    console.error("Erreur chargement indicateurs plans d'action:", err);
    actionStats.total = 0;
  } finally {
    actionsLoaded.value = true;
  }
}

async function generateReport() {
  generatingReport.value = true;
  apiError.value = null;
  try {
    // Appel au nouveau backend Phase 8.5 (avec timeout étendu)
    const response = await apiClient.get('/reports/dg-summary', { 
      timeout: 180000 // 3 minutes pour laisser le temps à l'IA locale
    });
    
    reportData.value = response.data; 
    
  } catch (err) {
    console.error("Erreur génération rapport:", err);
    if (err.code === 'ECONNABORTED') {
        apiError.value = "⏱️ Délai dépassé (3 min). Le modèle IA est peut-être en train de charger.";
    } else {
        apiError.value = err.response?.data?.detail || "Impossible de générer la synthèse.";
    }
  } finally {
    generatingReport.value = false;
  }
}

function getLevelClass(level) {
  if (level >= 20) return 'critical';
  if (level >= 15) return 'high';
  if (level >= 5) return 'medium';
  return 'low';
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

onMounted(() => { fetchAllRisks(); fetchActionStats(); });
</script>

<style scoped>
.dashboard-page { padding: 2rem; max-width: 1400px; margin: 0 auto; }
.header-section { margin-bottom: 2rem; }
h1 { color: #0f172a; font-size: 1.8rem; margin-bottom: 0.25rem; }
.subtitle { color: #64748b; margin-bottom: 1rem; }

/* Boutons Actions */
.actions-row { display: flex; gap: 1rem; margin-top: 1rem; }
.action-btn { padding: 0.75rem 1.5rem; border-radius: 8px; font-weight: 600; cursor: pointer; transition: all 0.2s; border: none; }
.action-btn.primary { background: #0ea5e9; color: white; }
.action-btn.primary:hover:not(:disabled) { background: #0284c7; }
.action-btn.secondary { background: #f1f5f9; color: #475569; }
.action-btn.secondary:hover:not(:disabled) { background: #e2e8f0; }
.action-btn:disabled { opacity: 0.6; cursor: not-allowed; }

/* Erreur Banner */
.error-banner {
  background: #fef2f2; border-left: 4px solid #ef4444; color: #991b1b;
  padding: 1rem; border-radius: 6px; margin-bottom: 1.5rem; display: flex; justify-content: space-between; align-items: center;
}
.retry-btn { background: #ef4444; color: white; border: none; padding: 0.4rem 0.8rem; border-radius: 4px; cursor: pointer; }

/* Sections Titres */
.kpi-section h2, .pac-kpi-section h2, .charts-section h2, .insights-section h2, .recent-risks-section h2 {
  font-size: 1.3rem; color: #334155; margin-bottom: 1rem; border-bottom: 2px solid #f1f5f9; padding-bottom: 0.5rem;
}

/* Grid Layout Global */
.grid-layout { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }

/* Cartes Générales */
.card { background: white; border-radius: 12px; padding: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }

/* KPI Cards */
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }
.kpi-card { text-align: center; padding: 1.5rem; border-radius: 12px; background: white; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.kpi-value { font-size: 2.5rem; font-weight: bold; display: block; margin-bottom: 0.5rem; }
.kpi-label { font-size: 0.85rem; color: #64748b; line-height: 1.3; }
.critical .kpi-value { color: #ef4444; }
.high .kpi-value { color: #f97316; }
.medium .kpi-value { color: #eab308; }
.low .kpi-value { color: #22c55e; }

/* ⬇️ STYLES SPÉCIFIQUES PAC (NOUVEAU) ⬇️ */
.pac-kpi-section { margin-bottom: 2rem; }
.overdue-alert .kpi-value { color: #ef4444; } /* Rouge vif */
.progress-active .kpi-value { color: #f97316; } /* Orange */
.success-rate .kpi-value { color: #22c55e; }
.blocked-alert .kpi-value { color: #dc2626; } /* Vert */

/* Charts */
.chart-card { height: 350px; display: flex; flex-direction: column; }
.chart-card h3 { margin: 0 0 1rem 0; font-size: 1rem; color: #475569; }

/* Insights IA */
.ai-insight-card { border-left: 4px solid #0ea5e9; background: #f8fafc; }
.ai-text { font-size: 1rem; line-height: 1.6; color: #334155; font-style: italic; margin-bottom: 1rem; }
.timestamp { display: block; color: #94a3b8; font-size: 0.8rem; text-align: right; }

.top-risks-card ul { list-style: none; padding: 0; margin: 0; }
.top-risks-card li { padding: 0.75rem 0; border-bottom: 1px solid #f1f5f9; }
.badge-critical { background: #fee2e2; color: #dc2626; padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: bold; font-size: 0.8rem; margin-right: 0.5rem; }

.apps-alert-card p { color: #64748b; margin-bottom: 1rem; }
.tags-container { display: flex; flex-wrap: wrap; gap: 0.5rem; }
.tag-app { background: #dbeafe; color: #1d4ed8; padding: 0.3rem 0.6rem; border-radius: 4px; font-size: 0.85rem; font-weight: 500; }

/* Recent Risks Table */
.recent-risks-section { background: white; border-radius: 12px; padding: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-top: 2rem;}
.loading-state { display: flex; align-items: center; justify-content: center; gap: 0.5rem; padding: 2rem; color: #64748b; }
.spinner-small { width: 20px; height: 20px; border: 3px solid #e2e8f0; border-top-color: #0ea5e9; border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.empty-state { text-align: center; color: #94a3b8; padding: 2rem; }
.risks-preview-table { width: 100%; border-collapse: collapse; }
.risks-preview-table th, .risks-preview-table td { padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid #e2e8f0; }
.risks-preview-table th { background: #f8fafc; font-weight: 600; color: #475569; font-size: 0.85rem; text-transform: uppercase; }
.badge { display: inline-block; padding: 0.25rem 0.6rem; border-radius: 12px; font-size: 0.8rem; font-weight: 700; color: white; }
.badge.critical { background: #ef4444; }
.badge.high { background: #f97316; }
.badge.medium { background: #eab308; }
.badge.low { background: #22c55e; }
</style>