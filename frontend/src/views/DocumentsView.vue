<!-- frontend/src/views/DocumentsView.vue -->
<template>
  <div class="docs-page">
    <!-- En-tête -->
    <div class="header-section">
      <h1>Bibliothèque Documentaire</h1>
      <p class="subtitle">Centralisez vos PSSI, procédures et contrats pour l'analyse IA souveraine.</p>
      
      <button v-if="canCreate" @click="openUploadModal" class="add-doc-btn">+ Importer un document</button>
    </div>

    <!-- Messages d'Erreur / Info Globaux -->
    <div v-if="globalMessage" :class="['message-banner', globalMessageType]">
      {{ globalMessage }}
      <button @click="globalMessage = null" class="close-msg">×</button>
    </div>

    <!-- Zone Drag & Drop Visuelle (Si aucun doc) -->
    <div v-if="!loading && documents.length === 0" class="empty-drop-zone card-modern">
      <div class="drop-icon">📄</div>
      <h3>Aucun document importé</h3>
      <p>Glissez-déposez vos fichiers PDF ou Word ici,<br/>ou cliquez sur "+ Importer un document".</p>
    </div>

    <!-- Tableau des Documents -->
    <div v-else-if="!loading" class="table-container card-modern">
      <div class="document-filters">
        <input v-model="searchQuery" type="search" placeholder="Rechercher titre, fichier, auteur..." aria-label="Rechercher dans les documents" />
        <select v-model="typeFilter" aria-label="Filtrer par type"><option value="">Tous les types</option><option v-for="type in documentTypes" :key="type" :value="type">{{ type }}</option></select>
        <select v-model="indexFilter" aria-label="Filtrer par indexation"><option value="">Tous les statuts</option><option value="indexed">Indexés</option><option value="pending">À indexer</option></select>
        <span class="filter-count">{{ filteredDocuments.length }} / {{ documents.length }}</span>
      </div>
      <table class="docs-table modern">
        <thead>
          <tr>
            <th>Type</th>
            <th>Titre</th>
            <th>Fichier Original</th>
            <th>Version</th>
            <th>Auteur / Direction</th>
            <th>Taille</th>
            <th>Statut Indexation</th>
            <th>Date</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="doc in filteredDocuments" :key="doc.id" class="table-row-hover">
            <td><span class="type-badge" :class="'badge-' + normalizeType(doc.doc_type)">{{ doc.doc_type }}</span></td>
            <td class="title-cell"><strong>{{ doc.title }}</strong></td>
            <td><code>{{ doc.filename }}</code></td>
            <td>{{ doc.version || '—' }}</td>
            <td>{{ doc.author || '—' }}</td>
            <td>{{ formatSize(doc.file_size_kb) }}</td>
            <td>
              <span v-if="doc.is_indexed" class="status-pill indexed">✅ Prêt IA</span>
              <span v-else class="status-pill pending">⏳ À indexer</span>
            </td>
            <td>{{ formatDate(doc.created_at) }}</td>
            <td class="actions-cell">
              <!-- Bouton Télécharger -->
              <button @click="downloadDoc(doc)" class="action-btn dl" title="Télécharger">⬇️</button>
              <button v-if="canUpdate && !doc.is_indexed" @click="indexDoc(doc)" :disabled="indexingId === doc.id" class="action-btn" title="Indexer pour l’Assistant IA">{{ indexingId === doc.id ? "⏳" : "🧠" }}</button>
              <!-- Bouton Supprimer -->
              <button v-if="canDelete" @click="deleteDoc(doc.id)" class="action-btn del" title="Supprimer">🗑️</button>
            </td>
          </tr>
        <tr v-if="filteredDocuments.length === 0"><td colspan="9" class="no-results">Aucun document ne correspond aux filtres.</td></tr>
        </tbody>
      </table>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="loading-state card-modern">Chargement de la bibliothèque...</div>

    <!-- MODAL UPLOAD (Drag & Drop + Formulaire) -->
    <Teleport to="body">
      <Transition name="fade-scale">
        <div v-if="showUploadModal" class="modal-overlay" @click.self="closeModal">
          <div class="upload-modal-card">
            
            <div class="modal-header">
              <h2>📤 Importer un Document</h2>
              <button @click="closeModal" class="close-btn">×</button>
            </div>

            <form @submit.prevent="handleUpload" class="upload-form">
              
              <!-- Zone Drop -->
              <div 
                class="drop-area" 
                :class="{ 'drag-over': isDragging }"
                @dragover.prevent="isDragging = true"
                @dragleave.prevent="isDragging = false"
                @drop.prevent="handleDrop"
              >
                <input 
                  type="file" 
                  ref="fileInputRef" 
                  accept=".pdf,.docx,.doc" 
                  @change="handleFileSelect" 
                  hidden
                />
                <div class="drop-content">
                  <span class="big-icon">☁️</span>
                  <p>Glissez votre fichier ici ou <label for="file-trigger" class="link-label">parcourir</label></p>
                  <small>(Formats supportés : PDF, DOCX)</small>
                </div>
                <input type="checkbox" id="file-trigger" style="display:none" @click="$refs.fileInputRef.click()" />
                
                <!-- Prévisualisation Nom Fichier Sélectionné -->
                <div v-if="selectedFileName" class="file-preview">
                  📎 {{ selectedFileName }}
                </div>
              </div>

              <!-- Champs Métadonnées -->
              <div class="meta-fields">
                <label>Titre du Document *</label>
                <input v-model="formData.title" required placeholder="Ex: PSSI CTF Version 2024" />

                <label>Type *</label>
                <select v-model="formData.doc_type" required>
                  <option value="" disabled>Sélectionnez...</option>
                  <option value="PSSI">Politique Sécurité (PSSI)</option>
                  <option value="PROCEDURE">Procédure Opératoire</option>
                  <option value="CONTRAT">Contrat Prestataire</option>
                  <option value="AUDIT_REPORT">Rapport d'Audit</option>
                  <option value="REGLEMENT_INTERIEUR">Règlement Intérieur</option>
                </select>

                <div class="row-2-cols">
                  <div>
                    <label>Version</label>
                    <input v-model="formData.version" placeholder="v1.0" />
                  </div>
                  <div>
                    <label>Auteur / Direction</label>
                    <input v-model="formData.author" placeholder="DI / RSSI" />
                  </div>
                </div>
              </div>

              <div class="modal-actions">
                <button type="button" @click="closeModal" class="cancel-btn">Annuler</button>
                <button type="submit" :disabled="uploading || !selectedFile" class="save-btn">
                  {{ uploading ? 'Envoi...' : 'Importer' }}
                </button>
              </div>
            </form>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import apiClient from '@/services/api';

const authStore = useAuthStore();
const loading = ref(false);
const documents = ref([]);
const searchQuery = ref("");
const typeFilter = ref("");
const indexFilter = ref("");
const documentTypes = computed(() => [...new Set(documents.value.map(doc => doc.doc_type).filter(Boolean))].sort());
const filteredDocuments = computed(() => {
  const query = searchQuery.value.trim().toLocaleLowerCase();
  return documents.value.filter(doc => {
    const matchesQuery = !query || [doc.title, doc.filename, doc.author, doc.doc_type].some(value => String(value || "").toLocaleLowerCase().includes(query));
    const matchesType = !typeFilter.value || doc.doc_type === typeFilter.value;
    const matchesIndex = !indexFilter.value || (indexFilter.value === "indexed" ? doc.is_indexed : !doc.is_indexed);
    return matchesQuery && matchesType && matchesIndex;
  });
});
const showUploadModal = ref(false);
const uploading = ref(false);
const isDragging = ref(false);
const selectedFile = ref(null);
const selectedFileName = ref('');
const fileInputRef = ref(null); // ✅ REF CORRECT POUR ACCÉDER AU DOM INPUT

// État Global Message (pour afficher les erreurs/infos hors modal)
const globalMessage = ref(null);
const globalMessageType = ref('info'); // 'success', 'error', 'warning'

// Formulaire Upload
const formData = reactive({
  title: '',
  doc_type: '',
  version: '',
  author: ''
});

// Permissions
const canCreate = computed(() => authStore.canAccessModule('documents', 'create'));
const canDelete = computed(() => authStore.canAccessModule('documents', 'delete'));
const canUpdate = computed(() => authStore.canAccessModule('documents', 'update'));
const indexingId = ref(null);

// Helpers UI
function normalizeType(type) {
  return type.toLowerCase().replace(/_/g, '-');
}

function formatSize(kb) {
  if (!kb) return '0 Ko';
  if (kb < 1024) return `${Math.round(kb)} Ko`;
  return `${(kb / 1024).toFixed(1)} Mo`;
}

function formatDate(isoString) {
  if (!isoString) return '-';
  return new Date(isoString).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' });
}

function showMessage(msg, type = 'info') {
  globalMessage.value = msg;
  globalMessageType.value = type;
  setTimeout(() => { globalMessage.value = null; }, 5000); // Auto-dismiss après 5s
}

// Actions CRUD
async function loadDocuments() {
  loading.value = true;
  try {
    const response = await apiClient.get('/documents/');
    documents.value = Array.isArray(response.data) ? response.data : [];
  } catch (err) {
    console.error('Erreur chargement docs:', err);
    showMessage("Impossible de charger la liste des documents.", "error");
    documents.value = [];
  } finally {
    loading.value = false;
  }
}

function openUploadModal() {
  resetForm();
  showUploadModal.value = true;
}

function closeModal() {
  showUploadModal.value = false;
  resetForm();
}

function resetForm() {
  selectedFile.value = null;
  selectedFileName.value = '';
  Object.assign(formData, { title: '', doc_type: '', version: '', author: '' });
  // Reset input file element si nécessaire
  if (fileInputRef.value) fileInputRef.value.value = '';
}

function handleFileSelect(event) {
  const file = event.target.files[0];
  if (file) validateAndSetFile(file);
}

function handleDrop(event) {
  isDragging.value = false;
  const file = event.dataTransfer.files[0];
  if (file) validateAndSetFile(file);
}

function validateAndSetFile(file) {
  const allowedTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
  if (!allowedTypes.includes(file.type) && !file.name.match(/\.(pdf|docx)$/i)) {
    showMessage("Format non supporté. Utilisez uniquement PDF ou DOCX.", "error");
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    showMessage("Le fichier dépasse la limite de 10 Mo.", "error");
    selectedFile.value = null;
    selectedFileName.value = "";
    return;
  }
  selectedFile.value = file;
  selectedFileName.value = file.name;
  if (!formData.title) formData.title = file.name.replace(/\.[^/.]+$/, "");
}

async function handleUpload() {
  if (!selectedFile.value) return alert("Veuillez sélectionner un fichier.");
  if (!formData.title || !formData.doc_type) return alert("Titre et Type sont obligatoires.");

  uploading.value = true;
  try {
    const form = new FormData();
    form.append('file', selectedFile.value);
    form.append('title', formData.title);
    form.append('doc_type', formData.doc_type);
    if (formData.version) form.append('version', formData.version);
    if (formData.author) form.append('author', formData.author);

    await apiClient.post('/documents/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });

    // SUCCESS PATH
    closeModal();
    await loadDocuments(); // Rafraîchir la liste immédiatement
    showMessage(`✅ Document "${formData.title}" importé avec succès !`, "success");
    
  } catch (err) {
    console.error(err);
    
    // Gestion spécifique de l'erreur 409 (Doublon)
    if (err.response?.status === 409) {
       const detail = err.response.data.detail || "Le document existe déjà.";
       showMessage(detail, "warning");
       
       // Optionnel : Proposer de supprimer l'ancien pour mettre à jour
       if(confirm("Souhaitez-vous supprimer l'ancien document pour le remplacer par cette nouvelle version ?")) {
           // Trouver l'ID du document existant (approximation par nom)
           // Note: Idéalement, le backend devrait renvoyer l'ID du doublon dans la réponse 409
           // Pour MVP, on suppose que l'utilisateur gère ça manuellement via le tableau ci-dessous
           alert("Action supprimée temporairement désactivée. Veuillez utiliser le bouton corbeille dans le tableau principal.");
       }
    } else {
       const errorMsg = err.response?.data?.detail || "Erreur lors de l'envoi du fichier.";
       showMessage(errorMsg, "error");
    }
  } finally {
    uploading.value = false;
  }
}

async function indexDoc(doc) {
  indexingId.value = doc.id;
  try {
    const response = await apiClient.post(`/documents/${doc.id}/index`);
    await loadDocuments();
    showMessage(response.data?.message || "Document indexé pour l'Assistant IA.", "success");
  } catch (err) {
    showMessage(err.response?.data?.detail || "Échec de l'indexation du document.", "error");
  } finally {
    indexingId.value = null;
  }
}

async function deleteDoc(id) {
  if (!confirm("Supprimer définitivement ce document ? Cette action est irréversible.")) return;
  try {
    await apiClient.delete(`/documents/${id}`);
    await loadDocuments();
    showMessage("🗑️ Document supprimé.", "info");
  } catch (err) {
    showMessage(err.response?.data?.detail || "Erreur suppression.", "error");
  }
}

async function downloadDoc(doc) {
  try {
    const response = await apiClient.get(`/documents/${doc.id}/download`, {
      responseType: 'blob',
    });
    const objectUrl = URL.createObjectURL(response.data);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = doc.filename || 'document';
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  } catch (err) {
    showMessage(err.response?.data?.detail || "Téléchargement du document impossible.", "error");
  }
}

onMounted(loadDocuments);
</script>

<style scoped>
.docs-page { padding: 2rem; max-width: 1400px; margin: 0 auto; background: #f8fafc; min-height: 100vh; }
.header-section { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; }
h1 { color: #0f172a; font-size: 1.8rem; margin-bottom: 0.25rem; }
.subtitle { color: #64748b; margin-bottom: 0; }
.add-doc-btn { padding: 0.75rem 1.5rem; background: #0ea5e9; color: white; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; transition: all 0.2s; }
.add-doc-btn:hover { background: #0284c7; transform: translateY(-1px); }

/* Message Banner */
.message-banner {
  padding: 1rem 1.5rem; border-radius: 8px; margin-bottom: 1.5rem;
  display: flex; justify-content: space-between; align-items: center;
  font-weight: 500; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}
.message-banner.info { background: #eff6ff; color: #1d4ed8; border-left: 4px solid #3b82f6; }
.message-banner.success { background: #dcfce7; color: #166534; border-left: 4px solid #22c55e; }
.message-banner.warning { background: #fef3c7; color: #92400e; border-left: 4px solid #eab308; }
.message-banner.error { background: #fee2e2; color: #991b1b; border-left: 4px solid #ef4444; }
.close-msg { background: none; border: none; font-size: 1.2rem; cursor: pointer; opacity: 0.7; }
.close-msg:hover { opacity: 1; }

/* Empty Drop Zone */
.empty-drop-zone { text-align: center; padding: 4rem 2rem; border: 2px dashed #cbd5e1; border-radius: 12px; background: white; }
.drop-icon { font-size: 3rem; color: #94a3b8; margin-bottom: 1rem; }
.empty-drop-zone h3 { color: #334155; margin: 0 0 0.5rem 0; }
.empty-drop-zone p { color: #64748b; line-height: 1.5; }

/* Table Styles */
.card-modern { background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); overflow: hidden; }
.table-container { width: 100%; }
.document-filters { display: flex; gap: 0.75rem; align-items: center; padding: 1rem; border-bottom: 1px solid #e2e8f0; flex-wrap: wrap; }
.document-filters input, .document-filters select { min-height: 40px; padding: 0.5rem 0.75rem; border: 1px solid #cbd5e1; border-radius: 8px; background: #fff; color: #334155; }
.document-filters input { flex: 1; min-width: 220px; }
.filter-count { color: #64748b; font-size: 0.85rem; margin-left: auto; }
.no-results { text-align: center; padding: 2rem; color: #64748b; }
.docs-table.modern { width: 100%; border-collapse: collapse; }
.docs-table.modern th, .docs-table.modern td { padding: 1rem 1.5rem; text-align: left; border-bottom: 1px solid #f1f5f9; vertical-align: middle; }
.docs-table.modern th { background: #f8fafc; font-weight: 600; color: #475569; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.5px; position: sticky; top: 0; z-index: 10; }
.table-row-hover:hover { background: #f8fafc; transition: background 0.2s; }

.type-badge { display: inline-block; padding: 0.25rem 0.6rem; border-radius: 12px; font-size: 0.75rem; font-weight: 700; text-transform: capitalize; }
.badge-pssi { background: #dbeafe; color: #1d4ed8; } /* Bleu */
.badge-procedure { background: #dcfce7; color: #166534; } /* Vert */
.badge-contrat { background: #fef3c7; color: #92400e; } /* Jaune */
.badge-audit-report { background: #fee2e2; color: #991b1b; } /* Rouge */
.badge-reglement-interieur { background: #ede9fe; color: #6d28d9; } /* Violet */

.status-pill { padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
.indexed { background: #dcfce7; color: #166534; }
.pending { background: #fef3c7; color: #92400e; }

.actions-cell { display: flex; gap: 0.5rem; }
.action-btn { padding: 0.3rem 0.6rem; border: none; border-radius: 4px; cursor: pointer; font-size: 0.9rem; transition: all 0.15s; }
.action-btn:hover { transform: scale(1.1); }
.action-btn.dl { background: #dbeafe; color: #1d4ed8; }
.action-btn.del { background: #fee2e2; color: #dc2626; }

.loading-state { text-align: center; padding: 3rem; color: #64748b; font-style: italic; }

/* Modal Upload Styles */
.modal-overlay { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(4px); z-index: 2000; display: flex; justify-content: center; align-items: center; }
.upload-modal-card { background: white; width: 90%; max-width: 600px; border-radius: 16px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25); overflow: hidden; animation: slideUp 0.3s ease-out; }
@keyframes slideUp { from { transform: translateY(20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
.modal-header { padding: 1.5rem 2rem; border-bottom: 1px solid #f1f5f9; display: flex; justify-content: space-between; align-items: center; background: #f8fafc; }
.modal-header h2 { margin: 0; font-size: 1.25rem; color: #0f172a; }
.close-btn { background: none; border: none; font-size: 1.5rem; color: #94a3b8; cursor: pointer; }
.close-btn:hover { color: #ef4444; }
.upload-form { padding: 2rem; }

/* Drop Area */
.drop-area { 
  border: 2px dashed #cbd5e1; border-radius: 12px; padding: 2rem; text-align: center; 
  transition: all 0.2s; background: #f8fafc; cursor: pointer; position: relative;
}
.drop-area.drag-over { border-color: #0ea5e9; background: #eff6ff; transform: scale(1.02); }
.big-icon { font-size: 2.5rem; display: block; margin-bottom: 0.5rem; color: #64748b; }
.link-label { color: #0ea5e9; font-weight: 600; cursor: pointer; text-decoration: underline; }
.file-preview { margin-top: 1rem; padding: 0.5rem; background: #e2e8f0; border-radius: 6px; font-size: 0.9rem; color: #334155; word-break: break-all; }

/* Meta Fields */
.meta-fields { margin-top: 1.5rem; display: flex; flex-direction: column; gap: 1rem; }
.meta-fields label { font-size: 0.85rem; font-weight: 600; color: #334155; margin-bottom: 0.25rem; display: block; }
.meta-fields input, .meta-fields select { width: 100%; padding: 0.6rem; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 0.95rem; box-sizing: border-box; }
.row-2-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }

.modal-actions { display: flex; justify-content: flex-end; gap: 1rem; margin-top: 2rem; padding-top: 1.5rem; border-top: 1px solid #e2e8f0; }
.cancel-btn { padding: 0.6rem 1.2rem; background: #e2e8f0; color: #475569; border: none; border-radius: 6px; cursor: pointer; font-weight: 500; }
.save-btn { padding: 0.6rem 1.2rem; background: #0ea5e9; color: white; border: none; border-radius: 6px; font-weight: 600; cursor: pointer; }
.save-btn:disabled { opacity: 0.6; cursor: not-allowed; }
</style>