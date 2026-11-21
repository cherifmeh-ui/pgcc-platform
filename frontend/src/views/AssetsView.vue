<template>
  <section class="assets-page">
    <header class="page-header">
      <div><h1>Cartographie des actifs</h1><p>Inventaire, propriétaires, criticité et dépendances.</p></div>
      <button v-if="canCreate" @click="openCreate">+ Nouvel actif</button>
    </header>
    <div class="filters">
      <input v-model="search" placeholder="Rechercher référence, nom, hostname…" @input="loadAssets" />
      <select v-model="typeFilter" @change="loadAssets"><option value="">Tous les types</option><option v-for="t in assetTypes" :key="t.value" :value="t.value">{{ t.label }}</option></select>
      <select v-model="criticalityFilter" @change="loadAssets"><option value="">Toutes criticités</option><option v-for="v in levels" :key="v">{{ v }}</option></select>
      <select v-model="statusFilter" @change="loadAssets"><option value="">Tous les statuts</option><option v-for="v in lifecycle" :key="v">{{ v }}</option></select>
    </div>
    <div class="summary">
      <article><strong>{{ assets.length }}</strong><span>Actifs affichés</span></article>
      <article><strong>{{ assets.filter(a => a.criticality === 'Critique').length }}</strong><span>Critiques</span></article>
      <article><strong>{{ assets.filter(a => !a.owner).length }}</strong><span>Sans propriétaire</span></article>
    </div>
    <div class="table-wrap">
      <table><thead><tr><th>Référence / Actif</th><th>Type</th><th>Direction / propriétaire</th><th>Criticité</th><th>Statut</th><th>Localisation</th><th>Actions</th></tr></thead>
      <tbody>
        <tr v-for="asset in assets" :key="asset.id">
          <td><b>{{ asset.reference }}</b><br>{{ asset.name }}<small v-if="asset.hostname">{{ asset.hostname }}</small></td>
          <td>{{ typeLabel(asset.asset_type) }}</td><td>{{ asset.direction || '—' }}<small>{{ asset.owner || 'Propriétaire non renseigné' }}</small></td>
          <td><span class="criticality" :class="critClass(asset.criticality)">{{ asset.criticality }}</span></td>
          <td>{{ asset.lifecycle_status }}</td><td>{{ asset.location || '—' }}</td>
          <td class="actions"><button @click="showRelations(asset)">Relations</button><button v-if="canUpdate" @click="editAsset(asset)">Modifier</button><button v-if="canDelete && !asset.retired_at" @click="retireAsset(asset)">Retirer</button></td>
        </tr>
        <tr v-if="loading"><td colspan="7" class="empty">Chargement…</td></tr><tr v-else-if="assets.length===0"><td colspan="7" class="empty">Aucun actif trouvé.</td></tr>
      </tbody></table>
    </div>
    <div v-if="showForm" class="overlay" @click.self="showForm=false">
      <form class="modal" @submit.prevent="saveAsset"><h2>{{ editing ? 'Modifier l’actif' : 'Nouvel actif' }}</h2>
        <div class="grid">
          <label>Référence *<input v-model="form.reference" required maxlength="50" /></label><label>Nom *<input v-model="form.name" required maxlength="200" /></label>
          <label>Type<select v-model="form.asset_type"><option v-for="t in assetTypes" :key="t.value" :value="t.value">{{ t.label }}</option></select></label>
          <label>Application existante<select v-model="form.application_id"><option value="">— Aucune —</option><option v-for="app in applications" :key="app.id" :value="app.id">{{ app.name }}</option></select></label>
          <label>Propriétaire<input v-model="form.owner" /></label><label>Gestionnaire<input v-model="form.custodian" /></label>
          <label>Direction<input v-model="form.direction" /></label><label>Localisation<input v-model="form.location" /></label>
          <label>Criticité<select v-model="form.criticality"><option v-for="v in levels" :key="v">{{ v }}</option></select></label>
          <label>Statut<select v-model="form.lifecycle_status"><option v-for="v in lifecycle" :key="v">{{ v }}</option></select></label>
          <label>Confidentialité<select v-model="form.confidentiality"><option value="">Non évaluée</option><option v-for="v in levels" :key="v">{{ v }}</option></select></label>
          <label>Intégrité<select v-model="form.integrity"><option value="">Non évaluée</option><option v-for="v in levels" :key="v">{{ v }}</option></select></label>
          <label>Disponibilité<select v-model="form.availability"><option value="">Non évaluée</option><option v-for="v in levels" :key="v">{{ v }}</option></select></label>
          <label>Classification<input v-model="form.classification" /></label><label>Hostname<input v-model="form.hostname" /></label>
          <label>Adresse IP<input v-model="form.ip_address" /></label><label>FQDN<input v-model="form.fqdn" /></label>
          <label>Système d’exploitation<input v-model="form.operating_system" /></label><label>Version<input v-model="form.version" /></label>
          <label>Fabricant<input v-model="form.manufacturer" /></label><label>Modèle<input v-model="form.model" /></label><label>Numéro de série<input v-model="form.serial_number" /></label>
        </div>
        <label>Description<textarea v-model="form.description" rows="2"></textarea></label><label>Commentaire<textarea v-model="form.comment" rows="2"></textarea></label>
        <div class="modal-actions"><button type="button" class="secondary" @click="showForm=false">Annuler</button><button type="submit" :disabled="saving">{{ saving ? 'Enregistrement…' : 'Enregistrer' }}</button></div>
      </form>
    </div>
    <div v-if="relationAsset" class="overlay" @click.self="relationAsset=null"><div class="modal"><h2>Dépendances — {{ relationAsset.name }}</h2>
      <section class="risk-links" v-if="canReadRisks"><h3>Risques associés</h3><ul><li v-for="link in riskLinks" :key="link.id"><strong>{{ riskLabel(link.risk_id) }}</strong><span v-if="link.relationship_context"> — {{ link.relationship_context }}</span><button v-if="canUpdate" type="button" class="unlink" @click="unlinkRisk(link.risk_id)">Dissocier</button></li><li v-if="riskLinks.length===0">Aucun risque lié.</li></ul><form v-if="canUpdate" class="relation-form" @submit.prevent="linkRisk"><label>Risque à associer<select v-model="riskForm.risk_id" required><option value="">Sélectionner un risque</option><option v-for="r in availableRisks.filter(x => !riskLinks.some(l => l.risk_id === x.id))" :key="r.id" :value="r.id">{{ r.ref }} — {{ r.title }}</option></select></label><label>Contexte de la liaison<input v-model="riskForm.relationship_context" maxlength="500" placeholder="Pourquoi cet actif est concerné ?"/></label><button type="submit" :disabled="saving">Associer le risque</button></form></section><ul class="relations"><li v-for="r in relations" :key="r.id">{{ r.source_asset_id === relationAsset.id ? '→' : '←' }} {{ r.relationship_type }} <code>{{ r.source_asset_id === relationAsset.id ? r.target_asset_id : r.source_asset_id }}</code><p>{{ r.description || '' }}</p></li><li v-if="relations.length===0">Aucune relation enregistrée.</li></ul>
      <form v-if="canUpdate" @submit.prevent="addRelation" class="relation-form"><label>Actif cible<select v-model="relationForm.target_asset_id" required><option value="">Sélectionner</option><option v-for="a in assets.filter(x => x.id !== relationAsset.id)" :key="a.id" :value="a.id">{{ a.reference }} — {{ a.name }}</option></select></label><label>Relation<select v-model="relationForm.relationship_type"><option v-for="r in relationTypes" :key="r">{{ r }}</option></select></label><label>Description<input v-model="relationForm.description" maxlength="500" /></label><button type="submit" :disabled="saving">Ajouter la relation</button></form>
      <div class="modal-actions"><button class="secondary" @click="relationAsset=null">Fermer</button></div>
    </div></div>
  </section>
</template>
<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import apiClient from '@/services/api';
import { useAuthStore } from '@/stores/auth';
const auth=useAuthStore();
const canCreate=computed(()=>auth.canAccessModule('assets','create')),canUpdate=computed(()=>auth.canAccessModule('assets','update')),canDelete=computed(()=>auth.canAccessModule('assets','delete')),canReadRisks=computed(()=>auth.canAccessModule('risks','read'));
const assets=ref([]),applications=ref([]),riskLinks=ref([]),availableRisks=ref([]),loading=ref(false),saving=ref(false),search=ref(''),typeFilter=ref(''),criticalityFilter=ref(''),statusFilter=ref('');
const showForm=ref(false),editing=ref(null),relationAsset=ref(null),relations=ref([]),riskForm=reactive({risk_id:'',relationship_context:''});
const levels=['Faible','Moyenne','Élevée','Critique'],lifecycle=['Identifié','Actif','En maintenance','En projet','Retiré','Décommissionné'];
const assetTypes=[{value:'process',label:'Processus'},{value:'information',label:'Information'},{value:'application',label:'Application'},{value:'hardware',label:'Matériel'},{value:'software',label:'Logiciel'},{value:'infrastructure',label:'Infrastructure'},{value:'network',label:'Réseau'},{value:'service',label:'Service'},{value:'cloud_resource',label:'Ressource Cloud'},{value:'facility',label:'Site / Local'},{value:'other',label:'Autre'}];
const relationTypes=['depends_on','hosts','connects_to','stores','processes','supports','contains','communicates_with','supplied_by','other'];
const emptyForm=()=>({reference:'',name:'',description:'',asset_type:'other',application_id:'',owner:'',custodian:'',direction:'',location:'',lifecycle_status:'Identifié',criticality:'Moyenne',confidentiality:'',integrity:'',availability:'',classification:'',hostname:'',ip_address:'',fqdn:'',operating_system:'',version:'',manufacturer:'',model:'',serial_number:'',discovery_source:'',source_reference:'',comment:''});
const form=reactive(emptyForm()),relationForm=reactive({target_asset_id:'',relationship_type:'depends_on',description:''});
function typeLabel(type){return assetTypes.find(t=>t.value===type)?.label||type}
function critClass(v){return ({Faible:'low',Moyenne:'medium',Élevée:'high',Critique:'critical'})[v]||'low'}
async function loadAssets(){loading.value=true;try{const params={limit:500};if(search.value.trim())params.q=search.value.trim();if(typeFilter.value)params.asset_type=typeFilter.value;if(criticalityFilter.value)params.criticality=criticalityFilter.value;if(statusFilter.value)params.lifecycle_status=statusFilter.value;const {data}=await apiClient.get('/assets/',{params});assets.value=data}catch(e){console.error(e);alert(e.response?.data?.detail||'Erreur chargement inventaire')}finally{loading.value=false}}
async function loadApplications(){try{const {data}=await apiClient.get('/apps/');applications.value=data}catch(e){console.warn('Applications list unavailable',e)}}
function openCreate(){editing.value=null;Object.assign(form,emptyForm());showForm.value=true}
function editAsset(asset){editing.value=asset;Object.assign(form,emptyForm(),asset,{application_id:asset.application_id||''});showForm.value=true}
async function saveAsset(){saving.value=true;try{const payload={...form,application_id:form.application_id||null};if(editing.value)await apiClient.patch('/assets/'+editing.value.id,payload);else await apiClient.post('/assets/',payload);showForm.value=false;await loadAssets()}catch(e){alert(e.response?.data?.detail||'Erreur sauvegarde actif')}finally{saving.value=false}}
async function retireAsset(asset){if(!confirm('Retirer l’actif '+asset.reference+' ? Il sera archivé et non supprimé.'))return;try{await apiClient.delete('/assets/'+asset.id);await loadAssets()}catch(e){alert(e.response?.data?.detail||'Erreur retrait actif')}}
async function showRelations(asset){relationAsset.value=asset;relations.value=[];riskLinks.value=[];if(canReadRisks.value){try{const [links,riskList]=await Promise.all([apiClient.get('/assets/'+asset.id+'/risks'),apiClient.get('/risks/')]);riskLinks.value=links.data;availableRisks.value=riskList.data}catch(e){console.warn('Risks unavailable',e)}}try{const {data}=await apiClient.get('/assets/'+asset.id+'/relationships');relations.value=data}catch(e){alert(e.response?.data?.detail||'Erreur chargement relations')}}\nfunction riskLabel(id){const risk=availableRisks.value.find(r=>r.id===id);return risk?risk.ref+' — '+risk.title:id}\nasync function linkRisk(){saving.value=true;try{await apiClient.post('/assets/'+relationAsset.value.id+'/risks',riskForm);riskForm.risk_id='';riskForm.relationship_context='';await showRelations(relationAsset.value)}catch(e){alert(e.response?.data?.detail||'Erreur association risque')}finally{saving.value=false}}\nasync function unlinkRisk(riskId){if(!confirm('Dissocier ce risque de l’actif ?'))return;try{await apiClient.delete('/assets/'+relationAsset.value.id+'/risks/'+riskId);await showRelations(relationAsset.value)}catch(e){alert(e.response?.data?.detail||'Erreur dissociation risque')}}
async function addRelation(){saving.value=true;try{await apiClient.post('/assets/'+relationAsset.value.id+'/relationships',relationForm);Object.assign(relationForm,{target_asset_id:'',relationship_type:'depends_on',description:''});await showRelations(relationAsset.value)}catch(e){alert(e.response?.data?.detail||'Erreur ajout relation')}finally{saving.value=false}}
onMounted(()=>{loadAssets();loadApplications()});
</script>
<style scoped>
.assets-page{max-width:1600px;margin:0 auto;padding:1rem;color:#0f172a}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;gap:1rem}.page-header h1{margin:0;font-size:1.5rem}.page-header p{color:#64748b;margin:.4rem 0}.assets-page button{border:0;border-radius:6px;padding:.55rem .85rem;background:#0ea5e9;color:white;cursor:pointer;font-weight:600}.assets-page button:disabled{opacity:.6;cursor:wait}.filters{display:flex;gap:.75rem;margin-bottom:1rem;flex-wrap:wrap}.filters input{flex:1;min-width:220px}.filters input,.filters select,.grid input,.grid select,.modal label>input,.modal label>select,.modal textarea{padding:.6rem;border:1px solid #cbd5e1;border-radius:6px;background:white;box-sizing:border-box;width:100%}.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:.75rem;margin-bottom:1rem}.summary article{background:white;border:1px solid #e2e8f0;border-radius:8px;padding:1rem;display:flex;flex-direction:column}.summary strong{font-size:1.6rem}.summary span{color:#64748b}.table-wrap{overflow:auto;background:white;border:1px solid #e2e8f0;border-radius:8px}table{border-collapse:collapse;width:100%;min-width:1100px}th,td{text-align:left;padding:.7rem;border-bottom:1px solid #e2e8f0;vertical-align:top}th{background:#f8fafc;color:#475569;font-size:.85rem}td small{display:block;color:#64748b;margin-top:.25rem}.actions{white-space:nowrap}.actions button{margin-right:.3rem;padding:.35rem .55rem;font-size:.8rem}.criticality{display:inline-block;padding:.25rem .5rem;border-radius:12px;color:white;font-size:.8rem;font-weight:700}.low{background:#22c55e}.medium{background:#eab308}.high{background:#f97316}.critical{background:#ef4444}.empty{text-align:center;padding:2rem;color:#64748b}.overlay{position:fixed;inset:0;background:#0008;display:flex;align-items:center;justify-content:center;z-index:1000;padding:1rem}.modal{background:white;border-radius:12px;padding:1.5rem;width:min(900px,96vw);max-height:90vh;overflow:auto;box-shadow:0 15px 50px #0003}.modal h2{margin-top:0}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem}.modal label{display:flex;flex-direction:column;gap:.35rem;margin:.5rem 0;font-weight:600;font-size:.9rem}.modal textarea{resize:vertical}.modal-actions{display:flex;justify-content:flex-end;gap:.5rem;margin-top:1rem}.secondary{background:#e2e8f0!important;color:#334155!important}.risk-links{border:1px solid #fecaca;background:#fff7f7;border-radius:8px;padding:1rem;margin:1rem 0}.risk-links h3{margin:.2rem 0 .75rem}.risk-links ul{padding-left:1.2rem}.risk-links li{margin:.5rem 0}.risk-links .unlink{background:#dc2626;padding:.25rem .5rem;margin-left:.5rem;font-size:.75rem}.relations{padding-left:1.2rem}.relations li{padding:.5rem 0}.relations code{font-size:.75rem;word-break:break-all}.relation-form{border-top:1px solid #e2e8f0;margin-top:1rem;padding-top:1rem}@media(max-width:700px){.grid{grid-template-columns:1fr}.summary{grid-template-columns:1fr}.page-header{align-items:flex-start;flex-direction:column}}
</style>