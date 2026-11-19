<!-- frontend/src/components/AiAssistantPanel.vue -->
<template>
  <Teleport to="body">
    <div v-if="isOpen" class="ai-panel-overlay" @click.self="$emit('close')">
      <div class="ai-panel">
        <header class="panel-header">
          <h3>✨ Assistant IA PGCC</h3>
          <button @click="$emit('close')" class="close-btn">×</button>
        </header>

        <div class="panel-body">
          <!-- Contexte du risque analysé -->
          <div v-if="riskData" class="risk-context">
            <code>{{ riskData.ref }}</code> — {{ riskData.title }}
          </div>

          <!-- Tabs -->
          <div class="tabs">
            <button
              :class="{ active: tab === 'rewrite' }"
              @click="switchTab('rewrite')"
              :disabled="loading"
            >
              🗣️ Reformuler pour DG
            </button>
            <button
              :class="{ active: tab === 'controls' }"
              @click="switchTab('controls')"
              :disabled="loading"
            >
              🛡️ Contre-mesures ISO
            </button>
          </div>

          <!-- État Loading -->
          <div v-if="loading" class="loading-state">
            <div class="spinner"></div>
            <p>L'IA analyse votre demande...</p>
            <small>Patientez jusqu'à 2 minutes (modèle local Llama3). Ne fermez pas ce panneau.</small>
            <p class="elapsed">{{ elapsedSeconds }}s écoulées</p>
          </div>

          <!-- État Erreur -->
          <div v-else-if="error" class="error-state">
            <p class="error-text">{{ error }}</p>
            <button @click="runAnalysis" class="retry-btn">Réessayer</button>
          </div>

          <!-- Résultat -->
          <div v-else-if="result" class="result-content">
            <!-- Mode Texte (Reformulation DG) -->
            <div v-if="result.type === 'rewrite'" class="text-output">
              <pre>{{ result.content }}</pre>
              <button @click="copyToClipboard(result.content)" class="copy-btn">📋 Copier</button>
            </div>

            <!-- Mode Liste (Contrôles ISO) -->
            <div v-else-if="result.type === 'controls'" class="controls-list">
              <div v-for="(control, index) in result.controls" :key="index" class="control-card">
                <span class="priority-badge" :class="getPriorityClass(control.priority)">
                  {{ control.priority }}
                </span>
                <h4>{{ control.action }}</h4>
                <small>Réf. ISO : {{ control.iso_control_ref }}</small>
                <br/>
                <small>Effort estimé : {{ control.estimated_effort }}</small>
              </div>
            </div>
          </div>

          <!-- État Idle -->
          <div v-else class="idle-state">
            <p>Sélectionnez un onglet puis cliquez sur « Générer l'analyse ».</p>
          </div>
        </div>

        <footer class="panel-footer">
          <button
            @click="runAnalysis"
            :disabled="loading || !riskData"
            class="analyze-btn"
          >
            {{ loading ? 'Traitement en cours...' : '🚀 Générer l\'analyse' }}
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, onBeforeUnmount } from 'vue';
import apiClient from '@/services/api';

const props = defineProps({
  isOpen: Boolean,
  riskData: Object, // { ref, title, description, threat, impact, likelihood, site }
});

const emit = defineEmits(['close']);

const tab = ref('rewrite');
const loading = ref(false);
const error = ref(null);
const result = ref(null); // { type: 'rewrite'|'controls', content?, controls? }
const elapsedSeconds = ref(0);
let elapsedTimer = null;

// Reset quand le panneau s'ouvre
watch(() => props.isOpen, (newVal) => {
  if (newVal) {
    result.value = null;
    error.value = null;
    loading.value = false;
    stopTimer();
  } else {
    stopTimer();
  }
});

function switchTab(newTab) {
  tab.value = newTab;
  // Invalide le résultat précédent s'il ne correspond pas au nouvel onglet
  if (result.value && result.value.type !== newTab) {
    result.value = null;
  }
  error.value = null;
}

function startTimer() {
  elapsedSeconds.value = 0;
  elapsedTimer = setInterval(() => { elapsedSeconds.value++; }, 1000);
}
function stopTimer() {
  if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null; }
}
onBeforeUnmount(stopTimer);

async function runAnalysis() {
  if (!props.riskData) return;

  loading.value = true;
  error.value = null;
  result.value = null;
  startTimer();

  const endpoint = tab.value === 'rewrite'
    ? '/ai/rewrite-executive'
    : '/ai/suggest-controls';

  // Payload défensif : garantit des types valides pour le schéma Pydantic backend
  const payload = {
    ref: String(props.riskData.ref || 'SANS-REF'),
    title: String(props.riskData.title || 'Risque sans titre'),
    description: String(props.riskData.description || props.riskData.title || ''),
    threat: String(props.riskData.threat || ''),
    impact: Number(props.riskData.impact) || 3,
    likelihood: Number(props.riskData.likelihood) || 3,
    site: String(props.riskData.site || ''),
  };

  try {
    // ⚠️ CORRECTIF CLÉ : timeout porté à 180s POUR CET APPEL UNIQUEMENT.
    // Llama3 local peut prendre 90-120s ; le timeout global d'apiClient coupait avant.
    const { data } = await apiClient.post(endpoint, payload, { timeout: 180000 });

    if (tab.value === 'rewrite') {
      result.value = { type: 'rewrite', content: data.content || '(réponse vide)' };
    } else {
      result.value = { type: 'controls', controls: Array.isArray(data.controls) ? data.controls : [] };
    }
  } catch (err) {
    const status = err.response?.status;
    const detail = err.response?.data?.detail;

    if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
      error.value = "⏱️ Délai dépassé (3 min). Le modèle est peut-être en cours de chargement. Vérifiez 'ollama ps' puis réessayez.";
    } else if (Array.isArray(detail)) {
      // Erreur 422 Pydantic : detail est un tableau d'objets {loc, msg, type}
      error.value = "Données invalides : " + detail.map(d => `${(d.loc || []).join('.')} — ${d.msg}`).join(' | ');
    } else if (typeof detail === 'string') {
      error.value = detail;
    } else if (status === 401) {
      error.value = "🔒 Session expirée. Déconnectez-vous puis reconnectez-vous, et relancez l'analyse.";
    } else if (status === 503) {
      error.value = "🔌 Serveur IA indisponible. Lancez 'ollama serve' sur votre PC.";
    } else if (!err.response) {
      error.value = "🌐 Pas de réponse du backend. Vérifiez que Docker tourne (docker-compose ps) et que Vite proxy fonctionne.";
    } else {
      error.value = `Erreur HTTP ${status} : ${JSON.stringify(err.response?.data) || err.message}`;
    }
    console.error("Détail complet erreur IA:", err.response?.data || err);
  } finally {
    loading.value = false;
    stopTimer();
  }
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    alert("Copié dans le presse-papiers !");
  }).catch(() => {
    alert("Impossible de copier automatiquement. Sélectionnez le texte manuellement.");
  });
}

function getPriorityClass(priority) {
  const p = String(priority || '').toLowerCase();
  if (p.includes('haute')) return 'high';
  if (p.includes('moyenne')) return 'medium';
  return 'low';
}
</script>

<style scoped>
.ai-panel-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; justify-content: center; align-items: center; z-index: 2000;
}
.ai-panel {
  width: 90%; max-width: 600px; height: 80vh;
  background: white; border-radius: 12px; box-shadow: 0 20px 40px rgba(0,0,0,0.3);
  display: flex; flex-direction: column; overflow: hidden;
}
.panel-header {
  padding: 1rem 1.5rem; border-bottom: 1px solid #e2e8f0;
  display: flex; justify-content: space-between; align-items: center;
  background: #f8fafc;
}
.panel-header h3 { margin: 0; color: #0f172a; font-size: 1.1rem; }
.close-btn { background: none; border: none; font-size: 1.5rem; cursor: pointer; color: #64748b; }
.risk-context {
  background: #eff6ff; border-left: 3px solid #0ea5e9; padding: 0.6rem 0.8rem;
  border-radius: 4px; font-size: 0.85rem; color: #1e40af; margin-bottom: 0.5rem;
}
.tabs { display: flex; gap: 0.5rem; padding: 1rem 0 0; }
.tabs button {
  padding: 0.5rem 1rem; border: none; background: #f1f5f9; color: #475569;
  border-radius: 6px 6px 0 0; cursor: pointer; font-weight: 500; transition: all 0.2s;
}
.tabs button.active { background: #0ea5e9; color: white; }
.tabs button:disabled { opacity: 0.6; cursor: not-allowed; }
.panel-body { flex: 1; overflow-y: auto; padding: 1.5rem; }
.loading-state, .error-state, .idle-state { text-align: center; padding: 2rem; color: #64748b; }
.elapsed { font-size: 0.8rem; color: #94a3b8; margin-top: 0.5rem; }
.spinner { width: 30px; height: 30px; border: 3px solid #e2e8f0; border-top-color: #0ea5e9; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 1rem; }
@keyframes spin { to { transform: rotate(360deg); } }
.error-text { color: #dc2626; background: #fef2f2; padding: 0.8rem; border-radius: 6px; font-size: 0.9rem; }
.retry-btn { margin-top: 0.8rem; padding: 0.4rem 1rem; background: #e2e8f0; border: none; border-radius: 4px; cursor: pointer; }
.text-output pre { white-space: pre-wrap; font-family: inherit; line-height: 1.6; background: #f8fafc; padding: 1rem; border-radius: 6px; }
.copy-btn { margin-top: 0.5rem; padding: 0.4rem 0.8rem; background: #e2e8f0; border: none; border-radius: 4px; cursor: pointer; font-size: 0.85rem; }
.controls-list { display: flex; flex-direction: column; gap: 1rem; }
.control-card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; background: #fff; }
.priority-badge { display: inline-block; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: bold; color: white; margin-bottom: 0.5rem; }
.priority-badge.high { background: #ef4444; }
.priority-badge.medium { background: #f59e0b; }
.priority-badge.low { background: #22c55e; }
.control-card h4 { margin: 0 0 0.5rem; font-size: 1rem; color: #0f172a; }
.control-card small { color: #64748b; font-size: 0.85rem; }
.panel-footer { padding: 1rem 1.5rem; border-top: 1px solid #e2e8f0; background: #f8fafc; }
.analyze-btn {
  width: 100%; padding: 0.8rem; background: #0ea5e9; color: white;
  border: none; border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 1rem;
}
.analyze-btn:hover:not(:disabled) { background: #0284c7; }
.analyze-btn:disabled { opacity: 0.6; cursor: not-allowed; }
</style>