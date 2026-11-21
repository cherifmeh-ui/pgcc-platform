<template>
  <section class="suppliers-page">
    <header><div><h1>Fournisseurs et tiers</h1><p>Référentiel des prestataires et contacts professionnels.</p></div><button v-if="canCreate" @click="openCreate">+ Nouveau fournisseur</button></header>
    <div class="filters">
      <input v-model="search" placeholder="Code ou raison sociale" @input="scheduleLoad">
      <select v-model="criticality" @change="load"><option value="">Toutes criticités</option><option v-for="v in levels" :key="v">{{v}}</option></select>
      <select v-model="status" @change="load"><option value="">Tous statuts</option><option v-for="v in statuses" :key="v">{{v}}</option></select>
      <label><input v-model="includeArchived" type="checkbox" @change="load"> Inclure les archivés</label>
    </div>
    <p v-if="error" class="error">{{error}}</p>
    <div class="table-wrap"><table><thead><tr><th>Code</th><th>Fournisseur</th><th>Service / Direction</th><th>Criticité</th><th>Statut</th><th>Contacts</th><th>Actions</th></tr></thead>
      <tbody><tr v-for="s in suppliers" :key="s.id"><td><b>{{s.code}}</b></td><td>{{s.legal_name}}<small>{{s.trade_name}}</small><small>{{s.country}}</small></td><td>{{s.service_category || '—'}}<small>{{s.direction || '—'}}</small></td><td><span :class="['level',levelClass(s.criticality)]">{{s.criticality}}</span></td><td>{{s.status}}<small v-if="s.archived_at">Archivé</small></td><td><button class="secondary" @click="openContacts(s)">Contacts</button></td><td><button v-if="canUpdate && !s.archived_at" class="secondary" @click="edit(s)">Modifier</button> <button v-if="canArchive && !s.archived_at" class="danger" @click="archive(s)">Archiver</button></td></tr>
      <tr v-if="loading"><td colspan="7" class="empty">Chargement…</td></tr><tr v-else-if="!suppliers.length"><td colspan="7" class="empty">Aucun fournisseur.</td></tr></tbody></table></div>
    <nav class="pagination"><button class="secondary" :disabled="offset===0" @click="previous">Précédent</button><span>{{offset+1}}–{{offset+suppliers.length}}</span><button class="secondary" :disabled="suppliers.length<limit" @click="next">Suivant</button><select v-model.number="limit" @change="offset=0;load()"><option :value="25">25 / page</option><option :value="50">50 / page</option><option :value="100">100 / page</option></select></nav>
    <div v-if="formOpen" class="overlay" @click.self="formOpen=false"><form class="modal" @submit.prevent="save">
      <h2>{{editing ? 'Modifier le fournisseur' : 'Nouveau fournisseur'}}</h2><div class="grid">
        <label>Code *<input v-model="form.code" required maxlength="40"></label><label>Raison sociale *<input v-model="form.legal_name" required maxlength="200"></label>
        <label>Nom commercial<input v-model="form.trade_name"></label><label>Pays<input v-model="form.country"></label>
        <label>Catégorie de service<input v-model="form.service_category"></label><label>Direction<input v-model="form.direction"></label>
        <label>Criticité<select v-model="form.criticality"><option v-for="v in levels" :key="v">{{v}}</option></select></label>
        <label>Dépendance<select v-model="form.dependency_level"><option v-for="v in levels" :key="v">{{v}}</option></select></label>
        <label>Statut<select v-model="form.status"><option v-for="v in statuses" :key="v">{{v}}</option></select></label><label>Localisation / hébergement<input v-model="form.hosting_location"></label>
      </div><label>Description<textarea v-model="form.description"></textarea></label><label>Données traitées<textarea v-model="form.data_categories"></textarea></label><label class="check"><input v-model="form.uses_subprocessors" type="checkbox"> Recours à des sous-traitants ultérieurs</label>
      <p v-if="formError" class="error">{{formError}}</p><div class="modal-actions"><button type="button" class="secondary" @click="formOpen=false">Annuler</button><button :disabled="saving">Enregistrer</button></div>
    </form></div>
    <div v-if="contactSupplier" class="overlay" @click.self="contactSupplier=null"><div class="modal"><h2>Contacts — {{contactSupplier.legal_name}}</h2>
      <ul><li v-for="c in contacts" :key="c.id">{{c.full_name}} — {{c.role || c.contact_type}} — {{c.email || 'Email non renseigné'}} <button v-if="canManageContacts && c.is_active" class="secondary" @click="deactivate(c)">Désactiver</button></li><li v-if="!contacts.length">Aucun contact actif.</li></ul>
      <form v-if="canManageContacts && !contactSupplier.archived_at" @submit.prevent="addContact"><h3>Ajouter un contact</h3><div class="grid"><label>Nom complet *<input v-model="contactForm.full_name" required></label><label>Fonction<input v-model="contactForm.role"></label><label>Email<input v-model="contactForm.email" type="email"></label><label>Téléphone<input v-model="contactForm.phone"></label><label>Type<select v-model="contactForm.contact_type"><option v-for="v in contactTypes" :key="v">{{v}}</option></select></label></div><p v-if="contactError" class="error">{{contactError}}</p><button :disabled="saving">Ajouter</button></form><div class="modal-actions"><button class="secondary" @click="contactSupplier=null">Fermer</button></div>
    </div></div>
  </section>
</template>
<script setup>
import {computed,onMounted,onUnmounted,reactive,ref} from 'vue';
import apiClient from '@/services/api';
import {useAuthStore} from '@/stores/auth';
const auth=useAuthStore();
const canCreate=computed(()=>auth.canAccessModule('suppliers','create'));
const canUpdate=computed(()=>auth.canAccessModule('suppliers','update'));
const canArchive=computed(()=>auth.canAccessModule('suppliers','archive'));
const canManageContacts=computed(()=>auth.canAccessModule('suppliers','manage_contacts'));
const levels=['Faible','Moyenne','Élevée','Critique'];
const statuses=['À qualifier','En évaluation','Approuvé','Approuvé sous conditions','Suspendu','Terminé'];
const contactTypes=['Commercial','Technique','Sécurité','Contractuel','Autre'];
const suppliers=ref([]),contacts=ref([]),loading=ref(false),saving=ref(false),error=ref(''),formError=ref(''),contactError=ref('');
const search=ref(''),criticality=ref(''),status=ref(''),includeArchived=ref(false),limit=ref(25),offset=ref(0);
const formOpen=ref(false),editing=ref(null),contactSupplier=ref(null);
const blank=()=>({code:'',legal_name:'',trade_name:'',country:'',service_category:'',description:'',business_owner_id:null,direction:'',criticality:'Moyenne',dependency_level:'Moyenne',data_categories:'',hosting_location:'',uses_subprocessors:false,status:'À qualifier'});
const form=reactive(blank()),contactForm=reactive({full_name:'',role:'',email:'',phone:'',contact_type:'Autre'});
let timer;
function scheduleLoad(){clearTimeout(timer);timer=setTimeout(()=>{offset.value=0;load()},300)}
async function load(){loading.value=true;error.value='';const params={limit:limit.value,offset:offset.value,include_archived:includeArchived.value};if(search.value.trim())params.search=search.value.trim();if(criticality.value)params.criticality=criticality.value;if(status.value)params.status=status.value;try{const {data}=await apiClient.get('/suppliers/',{params});suppliers.value=data}catch(e){error.value=e.response?.data?.detail||'Chargement impossible.'}finally{loading.value=false}}
function openCreate(){editing.value=null;Object.assign(form,blank());formOpen.value=true;formError.value=''}
function edit(s){editing.value=s;Object.assign(form,blank(),s);formOpen.value=true;formError.value=''}
async function save(){saving.value=true;formError.value='';try{if(editing.value)await apiClient.patch('/suppliers/'+editing.value.id,form);else await apiClient.post('/suppliers/',form);formOpen.value=false;await load()}catch(e){formError.value=e.response?.data?.detail||'Enregistrement impossible.'}finally{saving.value=false}}
async function archive(s){if(!confirm('Archiver '+s.code+' ? Les données historiques seront conservées.'))return;try{await apiClient.post('/suppliers/'+s.id+'/archive');await load()}catch(e){error.value=e.response?.data?.detail||'Archivage impossible.'}}
async function openContacts(s){contactSupplier.value=s;contacts.value=[];contactError.value='';try{const {data}=await apiClient.get('/suppliers/'+s.id+'/contacts');contacts.value=data}catch(e){contactError.value=e.response?.data?.detail||'Chargement contacts impossible.'}}
async function addContact(){saving.value=true;contactError.value='';try{await apiClient.post('/suppliers/'+contactSupplier.value.id+'/contacts',contactForm);Object.assign(contactForm,{full_name:'',role:'',email:'',phone:'',contact_type:'Autre'});await openContacts(contactSupplier.value)}catch(e){contactError.value=e.response?.data?.detail||'Création impossible.'}finally{saving.value=false}}
async function deactivate(c){try{await apiClient.patch('/suppliers/'+contactSupplier.value.id+'/contacts/'+c.id,{is_active:false});await openContacts(contactSupplier.value)}catch(e){contactError.value=e.response?.data?.detail||'Désactivation impossible.'}}
function previous(){offset.value=Math.max(0,offset.value-limit.value);load()}
function next(){offset.value+=limit.value;load()}
function levelClass(v){return ({Faible:'low',Moyenne:'medium',Élevée:'high',Critique:'critical'})[v]||''}
onMounted(load);onUnmounted(()=>clearTimeout(timer));
</script>
<style scoped>
.suppliers-page{max-width:1500px;margin:auto;color:#0f172a}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem}.page-header h1{margin:0}.page-header p{color:#64748b}.filters,.pagination{display:flex;gap:.7rem;align-items:center;flex-wrap:wrap;margin:1rem 0}.filters input:not([type=checkbox]){min-width:260px;flex:1}.filters input,.filters select,.grid input,.grid select,.modal textarea{padding:.6rem;border:1px solid #cbd5e1;border-radius:6px;box-sizing:border-box}.table-wrap{overflow:auto;border:1px solid #e2e8f0;border-radius:8px;background:white}table{border-collapse:collapse;width:100%;min-width:1000px}th,td{text-align:left;padding:.7rem;border-bottom:1px solid #e2e8f0;vertical-align:top}th{background:#f8fafc}small{display:block;color:#64748b;margin-top:.2rem}.level{color:white;padding:.2rem .5rem;border-radius:10px}.low{background:#16a34a}.medium{background:#ca8a04}.high{background:#ea580c}.critical{background:#dc2626}.secondary{background:#e2e8f0!important;color:#334155!important}.danger{background:#fee2e2!important;color:#991b1b!important}.empty{text-align:center;color:#64748b;padding:1.5rem}.pagination{justify-content:flex-end}.overlay{position:fixed;inset:0;background:#0008;display:flex;align-items:center;justify-content:center;z-index:1000;padding:1rem}.modal{background:white;border-radius:12px;padding:1.5rem;width:min(900px,96vw);max-height:90vh;overflow:auto}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.8rem}.modal label{display:flex;flex-direction:column;gap:.3rem;margin:.5rem 0}.modal .check{flex-direction:row}.modal textarea{width:100%;box-sizing:border-box}.modal-actions{display:flex;justify-content:flex-end;gap:.5rem;margin-top:1rem}.error{color:#b91c1c;background:#fef2f2;padding:.6rem}@media(max-width:700px){.grid{grid-template-columns:1fr}.page-header{align-items:flex-start;flex-direction:column}}
</style>
