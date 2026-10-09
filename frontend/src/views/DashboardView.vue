<!-- frontend/src/views/DashboardView.vue -->
<template>
  <div class="dashboard-container">
    <!-- En-tête -->
    <div class="header-section">
      <h1>Bienvenue, {{ authStore.user?.full_name || 'RSSI' }}</h1>
      <p class="subtitle">Vue d'ensemble de la posture cyber CTF</p>
      
      <!-- Indicateur de debug API (visible seulement en cas d'erreur) -->
      <div v-if="apiError" class="error-banner">
        ⚠️ Erreur API : {{ apiError }}
        <button @click="refreshStats" class="retry-btn">Réessayer</button>
      </div>
    </div>

    <!-- Cartes KPI -->
    <div class="kpi-grid">
      <div class="kpi-card critical">
        <span class="kpi-value">{{ stats.critical }}</span>
        <span class="kpi-label">Risques Critiques<br/>(≥20)</span>
      </div>
      
      <div class="kpi-card high">
        <span class="kpi-value">{{ stats.high }}</span>
        <span class="kpi-label">Risques Élevés<br/>(15–19)</span>
      </div>
      
      <div class="kpi-card medium">
        <span class="kpi-value">{{ stats.medium }}</span>
        <span class="kpi-label">Risques Modérés<br/>(5–14)</span>
      </div>
      
      <div class="kpi-card low">
        <span class="kpi-value">{{ stats.low }}</span>
        <span class="kpi-label">Risques Faibles<br/>(&lt;5)</span>
      </div>
    </div>

    <!-- Actions Rapides -->
    <div class="quick-actions-section">
      <h2>Actions Rapides</h2>
      <div class="actions-row">
        <router-link to="/risks" class="action-btn primary">
          📋 Consulter le registre des risques
        </router-link>
        
        <button @click="refreshStats" class="action-btn secondary" :disabled="loading">
          {{ loading ? 'Chargement...' : '🔄 Actualiser les données' }}
        </button>
      </div>
    </div>

    <!-- Derniers Risques Créés -->
    <div class="recent-risks-section">
      <h2>Derniers risques enregistrés</h2>
      
      <!-- État Loading -->
      <div v-if="loading" class="loading-state">
        <div class="spinner-small"></div>
        Chargement des risques...
      </div>

      <!-- État Vide -->
      <div v-else-if="recentRisks.length === 0 && !apiError" class="empty-state">
        <p>Aucun risque enregistré pour le moment.</p>
        <small>Vérifiez que vous avez créé au moins un risque via Swagger ou l'onglet "Registre des risques".</small>
      </div>

      <!-- Tableau des risques -->
      <table v-else-if="!apiError" class="risks-preview-table">
        <thead>
          <tr>
            <th>Réf.</th>
            <th>Titre</th>
            <th>Niveau</th>
            <th>Statut</th>
            <th>Date</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="risk in recentRisks.slice(0, 5)" :key="risk.id">
            <td><code>{{ risk.ref }}</code></td>
            <td>{{ truncate(risk.title, 40) }}</td>
            <td>
              <span class="badge" :class="getLevelClass(risk.risk_level)">
                {{ risk.risk_level }}
              </span>
            </td>
            <td>{{ risk.status }}</td>
            <td>{{ formatDate(risk.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import apiClient from '@/services/api'; // ← Utilise notre service centralisé

const authStore = useAuthStore();
const loading = ref(false);
const apiError = ref(null); 
const recentRisks = ref([]);

// Calcul des stats depuis la liste complète
const stats = reactive({
  critical: 0, // ≥20
  high: 0,     // 15-19
  medium: 0,   // 5-14
  low: 0,      // <5
});

async function fetchAllRisks() {
  loading.value = true;
  apiError.value = null; // Reset erreur
  
  try {
    console.log("🔍 Fetching risks via apiClient ...");
    
    // apiClient injecte automatiquement le token Access actuel
    const { data } = await apiClient.get('/risks/');
    
    console.log("✅ Risks received:", data);

    // Réinitialiser les compteurs
    stats.critical = 0;
    stats.high = 0;
    stats.medium = 0;
    stats.low = 0;
    
    if (!Array.isArray(data)) {
      throw new Error("Format de réponse API invalide.");
    }

    data.forEach(risk => {
      const lvl = risk.risk_level;
      if (lvl >= 20) stats.critical++;
      else if (lvl >= 15) stats.high++;
      else if (lvl >= 5) stats.medium++;
      else stats.low++;
    });
    
    // Garder les 5 plus récents pour le tableau
    recentRisks.value = [...data]
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
      .slice(0, 5);
      
  } catch (err) {
    console.error("❌ Erreur chargement dashboard:", err);
    const msg = err.response?.data?.detail || err.message || "Erreur inconnue";
    apiError.value = msg;
    recentRisks.value = []; 
  } finally {
    loading.value = false;
  }
}

function refreshStats() {
  fetchAllRisks();
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
  const date = new Date(isoString);
  return date.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' });
}

onMounted(fetchAllRisks);
</script>

<style scoped>
.dashboard-container { padding: 2rem; max-width: 1400px; margin: 0 auto; }
.header-section { margin-bottom: 2rem; }
h1 { color: #0f172a; font-size: 1.8rem; margin-bottom: 0.25rem; }
.subtitle { color: #64748b; margin-bottom: 1rem; }

/* Bannières d'information */
.error-banner {
  background: #fef2f2; border-left: 4px solid #ef4444; color: #991b1b;
  padding: 1rem; border-radius: 6px; margin-top: 1rem; display: flex; justify-content: space-between; align-items: center;
}
.retry-btn {
  background: #ef4444; color: white; border: none; padding: 0.4rem 0.8rem;
  border-radius: 4px; cursor: pointer; font-weight: 600;
}
.retry-btn:hover { background: #dc2626; }

.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.5rem; margin-bottom: 2.5rem; }
.kpi-card { background: white; border-radius: 12px; padding: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center; transition: transform 0.2s; }
.kpi-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.12); }
.kpi-value { font-size: 2.5rem; font-weight: bold; display: block; margin-bottom: 0.5rem; }
.kpi-label { font-size: 0.85rem; color: #64748b; line-height: 1.3; }

.critical .kpi-value { color: #ef4444; }
.high .kpi-value { color: #f97316; }
.medium .kpi-value { color: #eab308; }
.low .kpi-value { color: #22c55e; }

.quick-actions-section { margin-bottom: 2.5rem; }
.quick-actions-section h2 { font-size: 1.2rem; color: #334155; margin-bottom: 1rem; }
.actions-row { display: flex; gap: 1rem; flex-wrap: wrap; }
.action-btn { padding: 0.75rem 1.5rem; border-radius: 8px; font-weight: 600; cursor: pointer; transition: all 0.2s; border: none; text-decoration: none; display: inline-flex; align-items: center; gap: 0.5rem; }
.action-btn.primary { background: #0ea5e9; color: white; }
.action-btn.primary:hover { background: #0284c7; }
.action-btn.secondary { background: #f1f5f9; color: #475569; }
.action-btn.secondary:hover { background: #e2e8f0; }
.action-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.recent-risks-section { background: white; border-radius: 12px; padding: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.recent-risks-section h2 { font-size: 1.2rem; color: #334155; margin-bottom: 1rem; }

.loading-state { display: flex; align-items: center; justify-content: center; gap: 0.5rem; padding: 2rem; color: #64748b; }
.spinner-small { width: 20px; height: 20px; border: 3px solid #e2e8f0; border-top-color: #0ea5e9; border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.empty-state { text-align: center; color: #94a3b8; padding: 2rem; }
.empty-state small { display: block; margin-top: 0.5rem; font-size: 0.85rem; color: #cbd5e1; }

.risks-preview-table { width: 100%; border-collapse: collapse; }
.risks-preview-table th, .risks-preview-table td { padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid #e2e8f0; }
.risks-preview-table th { background: #f8fafc; font-weight: 600; color: #475569; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.5px; }
.risks-preview-table tr:hover { background: #f1f5f9; }
.badge { display: inline-block; padding: 0.25rem 0.6rem; border-radius: 12px; font-size: 0.8rem; font-weight: 700; color: white; }
.badge.critical { background: #ef4444; }
.badge.high { background: #f97316; }
.badge.medium { background: #eab308; }
.badge.low { background: #22c55e; }
</style>