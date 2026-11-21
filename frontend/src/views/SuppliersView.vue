<template>
  <section class="suppliers-page">
    <header><div><h1>Fournisseurs et tiers</h1><p>Référentiel des prestataires et contacts professionnels.</p></div><button v-if="canCreate" @click="openCreate">+ Nouveau fournisseur</button></header>
    <section v-if="canReadSupplierRisks" class="tprm-overview" aria-labelledby="tprm-title">
      <div class="overview-heading"><div><h2 id="tprm-title">Pilotage des risques fournisseurs</h2><p>Indicateurs consolidés — {{supplierOverview?.as_of ? new Date(supplierOverview.as_of+'T00:00:00').toLocaleDateString() : 'à actualiser'}}</p></div><button class="secondary" :disabled="overviewLoading" @click="loadOverview">{{overviewLoading?'Actualisation…':'Actualiser'}}</button></div>
      <p v-if="overviewError" class="error">{{overviewError}}</p>
      <div v-if="overviewLoading && !supplierOverview" class="overview-loading">Chargement des indicateurs…</div>
      <template v-else-if="supplierOverview">
        <div class="kpi-grid">
          <article class="kpi"><span>Fournisseurs actifs</span><strong>{{supplierOverview.suppliers.total_active}}</strong><small>{{supplierOverview.suppliers.critical_or_high}} de criticité élevée / critique</small></article>
          <article class="kpi" :class="{'kpi-alert':supplierOverview.suppliers.critical_without_current_assessment>0}"><span>Sans évaluation valide</span><strong>{{supplierOverview.suppliers.critical_without_current_assessment}}</strong><small>Fournisseurs élevés / critiques</small></article>
          <article class="kpi"><span>Risques distincts liés</span><strong>{{supplierOverview.risks.distinct_linked}}</strong><small>{{supplierOverview.risks.by_level.critique + supplierOverview.risks.by_level.inacceptable}} critiques / inacceptables</small></article>
          <article class="kpi" :class="{'kpi-alert':supplierOverview.access.overdue_reviews>0}"><span>Accès privilégiés actifs</span><strong>{{supplierOverview.access.privileged_active}}</strong><small>{{supplierOverview.access.overdue_reviews}} revues d'accès en retard</small></article>
          <article class="kpi" :class="{'kpi-alert':supplierOverview.assessments.overdue_reviews>0}"><span>Revues d'évaluation échues</span><strong>{{supplierOverview.assessments.overdue_reviews}}</strong><small>{{supplierOverview.assessments.latest_validated}} évaluations validées</small></article>
          <article class="kpi" :class="{'kpi-alert':supplierOverview.contracts.expiring_within_90_days>0}"><span>Contrats à échéance</span><strong>{{supplierOverview.contracts.expiring_within_90_days}}</strong><small>Dans les 90 prochains jours</small></article>
          <article class="kpi" :class="{'kpi-alert':supplierOverview.contracts.with_missing_security_clauses>0}"><span>Contrats avec clauses SSI manquantes</span><strong>{{supplierOverview.contracts.with_missing_security_clauses}}</strong><small>Sur {{supplierOverview.contracts.active_or_renewal}} contrats actifs / à renouveler</small></article>
        </div>
        <div class="risk-distribution"><strong>Répartition des risques fournisseurs associés</strong><div class="risk-levels"><span>Inacceptables <b>{{supplierOverview.risks.by_level.inacceptable}}</b></span><span>Critiques <b>{{supplierOverview.risks.by_level.critique}}</b></span><span>Élevés <b>{{supplierOverview.risks.by_level.eleve}}</b></span><span>Modérés <b>{{supplierOverview.risks.by_level.modere}}</b></span><span>Faibles <b>{{supplierOverview.risks.by_level.faible}}</b></span></div></div>
        <p class="overview-note">Cette synthèse est un outil d'aide à la décision. Elle ne modifie ni les cotations ni les décisions du registre central des risques.</p>
        <div class="snapshot-history">
          <div class="overview-heading"><div><h3>Historique mensuel</h3><p>Instantanés enregistrés pour suivre l'évolution des indicateurs.</p></div><button v-if="canManageSupplierRisks" class="secondary" :disabled="snapshotSaving" @click="captureSnapshot">{{snapshotSaving?'Enregistrement…':'Capturer le mois'}}</button></div>
          <p v-if="snapshotMessage" class="overview-note">{{snapshotMessage}}</p>
          <p v-if="trendError" class="error">{{trendError}}</p>
          <p v-if="concentrationError" class="error">{{concentrationError}}</p>
          <div v-if="supplierConcentration.length" class="trend-comparison">
            <h4>Concentration des risques par fournisseur</h4>
            <p class="overview-note">Classement indicatif selon le niveau maximal des risques centraux liés, leur nombre et les accès privilégiés actifs. Aucun score fournisseur n'est calculé.</p>
            <div class="table-wrap"><table><thead><tr><th>Fournisseur</th><th>Criticité</th><th>Risques liés</th><th>Niveau maximal lié</th><th>Répartition critique / inacceptable</th><th>Accès privilégiés actifs</th></tr></thead><tbody>
              <tr v-for="item in supplierConcentration" :key="item.supplier_id"><td><b>{{item.supplier_code}}</b><small>{{item.supplier_name}}</small></td><td>{{item.criticality}}</td><td>{{item.linked_risk_count}}</td><td>{{item.highest_linked_risk_level ?? 'Non coté'}}</td><td>{{item.risk_levels.critique + item.risk_levels.inacceptable}}</td><td>{{item.active_privileged_accesses}}</td></tr>
            </tbody></table></div>
          </div>
          <div v-if="supplierTrends?.available" class="trend-comparison">
            <h4>Évolution entre les deux derniers mois capturés</h4>
            <p class="overview-note" v-if="!supplierTrends.comparison_available">Une deuxième capture mensuelle est nécessaire pour calculer les évolutions.</p>
            <div v-else class="table-wrap"><table><thead><tr><th>Indicateur</th><th>Mois précédent</th><th>Mois courant</th><th>Écart</th><th>Lecture</th></tr></thead><tbody>
              <tr v-for="metric in supplierTrends.metrics" :key="metric.key"><td>{{metric.label}}</td><td>{{metric.previous ?? '—'}}</td><td>{{metric.current ?? '—'}}</td><td>{{metric.delta===null?'—':(metric.delta>0?'+':'')+metric.delta}}</td><td><span :class="['trend-state',metric.trend]">{{trendLabel(metric.trend)}}</span></td></tr>
            </tbody></table></div>
            <p class="overview-note">{{supplierTrends.interpretation}}</p>
          </div>
          <p v-if="snapshotError" class="error">{{snapshotError}}</p>
          <div v-if="snapshots.length" class="table-wrap"><table><thead><tr><th>Mois</th><th>Fournisseurs critiques sans évaluation</th><th>Risques distincts</th><th>Accès privilégiés</th><th>Contrats avec lacunes SSI</th></tr></thead><tbody><tr v-for="item in snapshots" :key="item.id"><td>{{new Date(item.snapshot_month+'T00:00:00').toLocaleDateString(undefined,{month:'long',year:'numeric'})}}</td><td>{{item.indicators.suppliers.critical_without_current_assessment}}</td><td>{{item.indicators.risks.distinct_linked}}</td><td>{{item.indicators.access.privileged_active}}</td><td>{{item.indicators.contracts.with_missing_security_clauses}}</td></tr></tbody></table></div>
          <p v-else class="overview-note">Aucun instantané mensuel enregistré pour le moment.</p>
        </div>
      </template>
    </section>
    <div class="filters">
      <input v-model="search" placeholder="Code ou raison sociale" @input="scheduleLoad">
      <select v-model="criticality" @change="load"><option value="">Toutes criticités</option><option v-for="v in levels" :key="v">{{v}}</option></select>
      <select v-model="status" @change="load"><option value="">Tous statuts</option><option v-for="v in statuses" :key="v">{{v}}</option></select>
      <label><input v-model="includeArchived" type="checkbox" @change="load"> Inclure les archivés</label>
    </div>
    <p v-if="error" class="error">{{error}}</p>
    <div class="table-wrap"><table><thead><tr><th>Code</th><th>Fournisseur</th><th>Service / Direction</th><th>Criticité</th><th>Statut</th><th>Contacts</th><th>Actions</th></tr></thead>
      <tbody><tr v-for="s in suppliers" :key="s.id"><td><b>{{s.code}}</b></td><td>{{s.legal_name}}<small>{{s.trade_name}}</small><small>{{s.country}}</small></td><td>{{s.service_category || '—'}}<small>{{s.direction || '—'}}</small></td><td><span :class="['level',levelClass(s.criticality)]">{{s.criticality}}</span></td><td>{{s.status}}<small v-if="s.archived_at">Archivé</small></td><td><button v-if="canReadContacts" class="secondary" @click="openContacts(s)">Contacts</button><span v-else>—</span><button v-if="canReadContracts" class="secondary" @click="openContracts(s)">Contrats</button><button v-if="canReadAssessments" class="secondary" @click="openAssessments(s)">Évaluations SSI</button><button v-if="canReadAssets" class="secondary" @click="openSupplierAssets(s)">Actifs liés</button></td><td><button v-if="canUpdate && !s.archived_at" class="secondary" @click="edit(s)">Modifier</button> <button v-if="canArchive && !s.archived_at" class="danger" @click="archive(s)">Archiver</button></td></tr>
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
    <div v-if="contractSupplier" class="overlay" @click.self="contractSupplier=null"><div class="modal"><h2>Contrats — {{contractSupplier.legal_name}}</h2>
      <p v-if="contractError" class="error">{{contractError}}</p>
      <div class="table-wrap"><table><thead><tr><th>Référence</th><th>Objet</th><th>Période</th><th>Statut</th><th>Clauses SSI</th></tr></thead><tbody>
        <tr v-for="c in contracts" :key="c.id"><td>{{c.reference}}</td><td>{{c.title}}</td><td>{{c.start_date}} → {{c.end_date || 'Sans échéance'}}</td><td>{{c.status}}</td><td>{{clauseCount(c)}} / 8</td></tr>
        <tr v-if="!contracts.length"><td colspan="5" class="empty">Aucun contrat enregistré.</td></tr></tbody></table></div>
      <form v-if="canManageContracts && !contractSupplier.archived_at" @submit.prevent="createContract"><h3>Ajouter un contrat</h3>
        <div class="grid">
          <label>Référence *<input v-model="contractForm.reference" required maxlength="100"></label>
          <label>Objet *<input v-model="contractForm.title" required maxlength="200"></label>
          <label>Type<select v-model="contractForm.contract_type"><option v-for="x in contractTypes" :key="x">{{x}}</option></select></label>
          <label>Statut<select v-model="contractForm.status"><option v-for="x in contractStatuses" :key="x">{{x}}</option></select></label>
          <label>Date début *<input v-model="contractForm.start_date" type="date" required></label>
          <label>Date fin<input v-model="contractForm.end_date" type="date"></label>
          <label>Préavis (jours)<input v-model.number="contractForm.notice_period_days" type="number" min="0" max="3650"></label>
          <label>Document contractuel existant<select v-model="contractForm.document_id"><option :value="null">Aucun document associé</option><option v-for="doc in documents" :key="doc.id" :value="doc.id">{{doc.title}} — {{doc.filename}}</option></select></label>
        </div>
        <label class="check"><input v-model="contractForm.auto_renew" type="checkbox"> Renouvellement automatique</label>
        <div class="clauses"><label v-for="clause in clauseFields" :key="clause.key" class="check"><input v-model="contractForm[clause.key]" type="checkbox">{{clause.label}}</label></div>
        <p v-if="contractFormError" class="error">{{contractFormError}}</p><button :disabled="saving">Enregistrer le contrat</button>
      </form><div class="modal-actions"><button class="secondary" @click="contractSupplier=null">Fermer</button></div>
    </div></div>

    <div v-if="assessmentSupplier" class="overlay" @click.self="assessmentSupplier=null"><div class="modal">
      <h2>Évaluations SSI — {{assessmentSupplier.legal_name}}</h2>
      <p v-if="assessmentError" class="error">{{assessmentError}}</p>
      <div class="table-wrap"><table><thead><tr><th>Date</th><th>Type</th><th>Version</th><th>Score</th><th>Risque</th><th>Statut</th><th>Décision</th><th>Action</th></tr></thead><tbody>
        <tr v-for="a in assessments" :key="a.id"><td>{{new Date(a.created_at).toLocaleDateString()}}</td><td>{{a.assessment_type}}</td><td>{{a.questionnaire_version}}</td><td>{{a.score ?? '—'}}</td><td>{{a.risk_level ?? '—'}}</td><td>{{a.status}}</td><td>{{a.decision || '—'}}</td><td><button v-if="canAssess && a.status==='Brouillon' && a.assessed_by_id===auth.user?.id" class="secondary" @click="selectAssessment(a)">Répondre</button><button v-if="canValidate && a.status==='À valider'" class="secondary" @click="selectForValidation(a)">Valider</button></td></tr>
        <tr v-if="!assessments.length"><td colspan="8" class="empty">Aucune évaluation.</td></tr>
      </tbody></table></div>
      <div v-if="canAssess && !assessmentSupplier.archived_at">
        <button v-if="!activeAssessment" @click="createAssessment" :disabled="saving">Créer une évaluation initiale (questionnaire CTF-TPRM-1.0)</button>
        <div v-if="activeAssessment" class="assessment-editor">
          <h3>Questionnaire {{activeAssessment.questionnaire_version}}</h3><p>{{activeAssessment.scope}}</p>
          <div v-for="q in activeAssessment.questionnaire_snapshot" :key="q.id" class="question">
            <label>{{q.label}} <small>Poids : {{q.weight}} — score de 0 à {{q.max_score}}</small>
              <select v-model.number="answerMap[q.id].score"><option v-for="n in q.max_score+1" :key="n" :value="n-1">{{n-1}}</option></select>
              <textarea v-model="answerMap[q.id].comment" placeholder="Commentaire / justification"></textarea>
            </label>
          </div>
          <p v-if="assessmentFormError" class="error">{{assessmentFormError}}</p>
          <div class="modal-actions"><button class="secondary" @click="activeAssessment=null">Fermer</button><button class="secondary" @click="saveAnswers" :disabled="saving">Enregistrer les réponses</button><button @click="submitAssessment" :disabled="saving">Soumettre pour validation</button></div>
        </div>
      </div>
      <div v-if="validationAssessment && canValidate" class="assessment-editor">
        <h3>Validation de l'évaluation</h3><p>Score : {{validationAssessment.score}} / 100 — Risque : {{validationAssessment.risk_level}}</p>
        <label>Décision<select v-model="validationForm.decision"><option>Approuvé</option><option>Approuvé sous conditions</option><option>Refusé</option></select></label>
        <label>Commentaire de validation<textarea v-model="validationForm.validation_comment" minlength="5" required></textarea></label>
        <label>Prochaine revue<input v-model="validationForm.next_review_at" type="date"></label>
        <p v-if="assessmentFormError" class="error">{{assessmentFormError}}</p>
        <button @click="validateAssessment" :disabled="saving">Confirmer la validation</button>
      </div>
      <div class="modal-actions"><button class="secondary" @click="assessmentSupplier=null">Fermer</button></div>
    </div></div>
    <div v-if="assetSupplier" class="overlay" @click.self="assetSupplier=null"><div class="modal"><h2>Actifs liés — {{assetSupplier.legal_name}}</h2>
      <p v-if="assetLinkError" class="error">{{assetLinkError}}</p>
      <div class="table-wrap"><table><thead><tr><th>Actif</th><th>Relation</th><th>Niveau déclaré</th><th>Données déclarées</th><th>Statut</th><th>Revue</th><th v-if="canManageAssets">Action</th></tr></thead><tbody>
        <tr v-for="link in supplierAssetLinks" :key="link.id"><td>{{link.asset_reference ? `${link.asset_reference} — ${link.asset_name}` : assetLabel(link.asset_id)}}</td><td>{{link.relationship_type}}</td><td>{{link.access_level}}</td><td>{{link.data_access?'Oui':'Non'}}</td><td>{{link.status}}</td><td>{{link.review_due_at||'—'}}</td><td v-if="canManageAssets"><button v-if="link.status!=='Terminé'" class="danger" @click="terminateAssetLink(link)">Terminer</button></td></tr>
        <tr v-if="!supplierAssetLinks.length"><td :colspan="canManageAssets?7:6" class="empty">Aucun actif lié.</td></tr></tbody></table></div>
      <section v-if="canReadSupplierRisks" class="assessment-editor"><h3>Risques associés au fournisseur</h3>
        <p class="muted">Les risques restent dans le registre central PGCC. Cette association documente uniquement le lien de dépendance fournisseur ; elle ne modifie pas automatiquement leur cotation.</p>
        <div class="table-wrap"><table><thead><tr><th>Référence</th><th>Risque</th><th>Type de dépendance</th><th>Contexte</th><th>Créé le</th></tr></thead><tbody>
          <tr v-for="link in supplierRiskLinks" :key="link.id"><td>{{riskLabel(link.risk_id)}}</td><td>{{riskTitle(link.risk_id)}}</td><td>{{link.relationship_type}}</td><td>{{link.relationship_context}}</td><td>{{new Date(link.created_at).toLocaleDateString()}}</td></tr>
          <tr v-if="!supplierRiskLinks.length"><td colspan="5" class="empty">Aucun risque associé.</td></tr>
        </tbody></table></div>
        <form v-if="canManageSupplierRisks && !assetSupplier.archived_at" @submit.prevent="createSupplierRiskLink"><h4>Associer un risque existant</h4>
          <label>Risque *<select v-model="supplierRiskForm.risk_id" required><option value="">Sélectionner un risque</option><option v-for="risk in availableRisks" :key="risk.id" :value="risk.id">{{risk.ref}} — {{risk.title}} (niveau {{risk.risk_level}})</option></select></label>
          <label>Type de dépendance *<select v-model="supplierRiskForm.relationship_type"><option>Dépendance opérationnelle</option><option>Hébergement</option><option>Maintenance</option><option>Accès aux données</option><option>Accès privilégié</option><option>Sous-traitance</option><option>Autre</option></select></label>
          <label>Contexte métier et conséquences possibles *<textarea v-model="supplierRiskForm.relationship_context" minlength="5" maxlength="2000" required placeholder="Décrire le service fourni, la dépendance, les conséquences d'une indisponibilité ou d'une compromission…"></textarea></label>
          <button :disabled="saving || !supplierRiskForm.risk_id">Associer au registre des risques</button>
        </form>
      </section>
      <section v-if="canReadAccess" class="assessment-editor"><h3>Autorisations d’accès aux actifs</h3>
        <p class="muted">Une relation fournisseur–actif ne vaut pas autorisation d’accès. Seules les demandes approuvées et encore valides constituent une autorisation enregistrée.</p>
        <div class="table-wrap"><table><thead><tr><th>Actif</th><th>Accès</th><th>Période</th><th>Revue</th><th>Statut</th><th>Décision</th><th>Actions</th></tr></thead><tbody>
          <tr v-for="a in supplierAccessRequests" :key="a.id"><td>{{assetLabel(a.asset_id)}}</td><td>{{a.access_level}}<small v-if="a.data_access">Accès aux données</small><small>{{a.scope}}</small></td><td>{{a.start_date}} → {{a.end_date}}</td><td>{{a.review_due_at}}</td><td>{{a.status}}</td><td>{{a.decision_comment||'—'}}</td><td>
            <button v-if="canDecideAccess && a.status==='Demandé' && a.requested_by_id!==auth.user?.id" class="secondary" @click="decideAccess(a,'Approuvé')">Approuver</button>
            <button v-if="canDecideAccess && a.status==='Demandé' && a.requested_by_id!==auth.user?.id" class="danger" @click="decideAccess(a,'Refusé')">Refuser</button>
            <button v-if="canRevokeAccess && ['Approuvé','Suspendu'].includes(a.status)" class="danger" @click="revokeAccess(a)">Révoquer</button>
            <button v-if="canExpireAccess && ['Approuvé','Suspendu'].includes(a.status) && a.end_date < today" class="secondary" @click="expireAccess(a)">Clôturer comme expirée</button>
            <button v-if="canReviewAccess && a.status==='Approuvé' && a.start_date<=today && a.end_date>=today" class="secondary" @click="openAccessReview(a)">Effectuer la revue</button>
          </td></tr>
          <tr v-if="!supplierAccessRequests.length"><td colspan="7" class="empty">Aucune demande d’accès enregistrée.</td></tr></tbody></table></div>
        <form v-if="canRequestAccess && !assetSupplier.archived_at && supplierAssetLinks.some(x=>x.status==='Actif')" @submit.prevent="createAccessRequest"><h4>Nouvelle demande d’accès interne</h4><div class="grid">
          <label>Relation fournisseur–actif *<select v-model="accessRequestForm.supplier_asset_link_id" required><option value="">Sélectionner</option><option v-for="link in supplierAssetLinks.filter(x=>x.status==='Actif')" :key="link.id" :value="link.id">{{link.asset_reference}} — {{link.asset_name}} ({{link.relationship_type}})</option></select></label>
          <label>Niveau demandé *<select v-model="accessRequestForm.access_level"><option>Standard</option><option>Privilégié</option></select></label>
          <label class="check"><input v-model="accessRequestForm.data_access" type="checkbox"> Accès aux données</label>
          <label>Date de début *<input v-model="accessRequestForm.start_date" type="date" :min="today" required></label>
          <label>Date de fin *<input v-model="accessRequestForm.end_date" type="date" :min="accessRequestForm.start_date||today" required></label>
          <label>Date de revue *<input v-model="accessRequestForm.review_due_at" type="date" :min="accessRequestForm.start_date||today" :max="accessRequestForm.end_date||undefined" required></label>
        </div><label>Justification *<textarea v-model="accessRequestForm.justification" minlength="10" maxlength="2000" required></textarea></label><label>Périmètre précis *<textarea v-model="accessRequestForm.scope" minlength="3" maxlength="1000" required></textarea></label><button :disabled="saving">Soumettre la demande</button></form>
        <div v-if="selectedAccessReview" class="assessment-editor">
          <h4>Revue périodique — {{assetLabel(selectedAccessReview.asset_id)}}</h4>
          <p>Niveau actuel : {{selectedAccessReview.access_level}} · Accès aux données : {{selectedAccessReview.data_access?'Oui':'Non'}} · Échéance actuelle : {{selectedAccessReview.review_due_at}}</p>
          <div class="table-wrap"><table><thead><tr><th>Date</th><th>Réviseur</th><th>Décision</th><th>Avant</th><th>Après</th><th>Commentaire</th><th>Prochaine revue</th></tr></thead><tbody>
            <tr v-for="r in accessReviewHistory" :key="r.id"><td>{{new Date(r.reviewed_at).toLocaleDateString()}}</td><td>{{r.reviewed_by_id}}</td><td>{{r.outcome}}</td><td>{{r.previous_access_level}} / données : {{r.previous_data_access?'Oui':'Non'}}</td><td>{{r.resulting_access_level}} / données : {{r.resulting_data_access?'Oui':'Non'}}</td><td>{{r.comment}}</td><td>{{r.next_review_at||'—'}}</td></tr>
            <tr v-if="!accessReviewHistory.length"><td colspan="7" class="empty">Aucune revue antérieure.</td></tr>
          </tbody></table></div>
          <form @submit.prevent="submitAccessReview">
            <label>Décision de revue<select v-model="accessReviewForm.outcome"><option>Maintenue</option><option>Réduite</option><option>Révoquée</option></select></label>
            <div v-if="accessReviewForm.outcome==='Réduite'" class="grid">
              <label>Nouveau niveau<select v-model="accessReviewForm.new_access_level"><option>Standard</option><option>Privilégié</option></select></label>
              <label class="check"><input v-model="accessReviewForm.new_data_access" type="checkbox"> Maintenir l'accès aux données</label>
              <small>La décision doit réduire réellement les privilèges ou supprimer l'accès aux données.</small>
            </div>
            <label v-if="accessReviewForm.outcome!=='Révoquée'">Prochaine revue *<input v-model="accessReviewForm.next_review_at" type="date" :min="today" :max="selectedAccessReview.end_date" required></label>
            <label>Commentaire et justification *<textarea v-model="accessReviewForm.comment" minlength="5" maxlength="2000" required></textarea></label>
            <p class="muted">Le réviseur ne peut être ni le demandeur ni l'approbateur initial. La revue est historisée sans suppression.</p>
            <div class="modal-actions"><button :disabled="saving">Enregistrer la revue</button><button type="button" class="secondary" @click="selectedAccessReview=null">Fermer</button></div>
          </form>
        </div>
      </section>
      <form v-if="canManageAssets && !assetSupplier.archived_at" @submit.prevent="createAssetLink"><h3>Associer un actif</h3><div class="grid">
        <label>Actif *<select v-model="assetLinkForm.asset_id" required><option value="">Sélectionner un actif</option><option v-for="a in selectableAssets" :key="a.id" :value="a.id">{{a.reference}} — {{a.name}}</option></select></label>
        <label>Relation *<select v-model="assetLinkForm.relationship_type"><option v-for="x in assetRelationshipTypes" :key="x">{{x}}</option></select></label>
        <label>Niveau d’accès<select v-model="assetLinkForm.access_level"><option>Aucun</option><option>Standard</option><option>Privilégié</option></select></label>
        <label class="check"><input v-model="assetLinkForm.data_access" type="checkbox"> Accès aux données</label>
        <label>Prochaine revue<input v-model="assetLinkForm.review_due_at" type="date"></label>
      </div><label>Périmètre<textarea v-model="assetLinkForm.scope" maxlength="1000"></textarea></label><button :disabled="saving || !selectableAssets.length">Associer l’actif</button></form>
      <div class="modal-actions"><button class="secondary" @click="assetSupplier=null">Fermer</button></div>
    </div></div>
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
const canReadContacts=computed(()=>auth.canAccessModule('suppliers','read_contacts'));
const canReadContracts=computed(()=>auth.canAccessModule('suppliers','read_contracts'));
const canManageContracts=computed(()=>auth.canAccessModule('suppliers','manage_contracts'));
const canReadDocuments=computed(()=>auth.canAccessModule('documents','read'));
const canReadAssessments=computed(()=>auth.canAccessModule('suppliers','read_assessments'));
const canReadAssets=computed(()=>auth.canAccessModule('suppliers','read_assets'));
const canManageAssets=computed(()=>auth.canAccessModule('suppliers','manage_assets'));
const canReadAccess=computed(()=>auth.canAccessModule('suppliers','read_access_requests'));
const canRequestAccess=computed(()=>auth.canAccessModule('suppliers','request_access'));
const canDecideAccess=computed(()=>auth.canAccessModule('suppliers','decide_access'));
const canRevokeAccess=computed(()=>auth.canAccessModule('suppliers','revoke_access'));
const canExpireAccess=computed(()=>auth.canAccessModule('suppliers','expire_access'));
const canReviewAccess=computed(()=>auth.canAccessModule('suppliers','review_access'));
const canManageSupplierRisks=computed(()=>auth.canAccessModule('suppliers','manage_risks')&&auth.canAccessModule('risks','update'));
const canReadSupplierRisks=computed(()=>auth.canAccessModule('suppliers','read')&&auth.canAccessModule('risks','read'));
const supplierOverview=ref(null),overviewLoading=ref(false),overviewError=ref('');
const snapshots=ref([]),snapshotSaving=ref(false),snapshotError=ref(''),snapshotMessage=ref('');
const supplierTrends=ref(null),trendError=ref('');
const supplierConcentration=ref([]),concentrationError=ref('');
async function loadSupplierConcentration(){if(!canReadSupplierRisks.value)return;try{const {data}=await apiClient.get('/suppliers/overview/concentration',{params:{limit:10}});supplierConcentration.value=data}catch(e){concentrationError.value=e.response?.data?.detail||'Analyse de concentration indisponible.'}}

async function loadSupplierTrends(){if(!canReadSupplierRisks.value)return;try{const {data}=await apiClient.get('/suppliers/overview/trends',{params:{limit:12}});supplierTrends.value=data}catch(e){trendError.value=e.response?.data?.detail||'Comparaison mensuelle indisponible.'}}
function trendLabel(value){return ({deteriorating:'Dégradation',improving:'Amélioration',stable:'Stable',change:'Variation à analyser',insufficient_data:'Données insuffisantes'})[value]||'—'}

async function loadSnapshots(){if(!canReadSupplierRisks.value)return;try{const {data}=await apiClient.get('/suppliers/overview/snapshots',{params:{limit:24}});snapshots.value=data}catch(e){snapshotError.value=e.response?.data?.detail||'Chargement de l’historique impossible.'}}
async function captureSnapshot(){snapshotSaving.value=true;snapshotError.value='';snapshotMessage.value='';try{await apiClient.post('/suppliers/overview/snapshots/capture');snapshotMessage.value='Instantané mensuel enregistré.';await loadSnapshots()}catch(e){snapshotError.value=e.response?.status===409?'Un instantané existe déjà pour le mois en cours.':(e.response?.data?.detail||'Capture impossible.')}finally{snapshotSaving.value=false}}
async function loadOverview(){if(!canReadSupplierRisks.value)return;overviewLoading.value=true;overviewError.value='';try{const {data}=await apiClient.get('/suppliers/overview/risk');supplierOverview.value=data}catch(e){overviewError.value=e.response?.data?.detail||'Chargement de la synthèse impossible.'}finally{overviewLoading.value=false}}
const canAssess=computed(()=>auth.canAccessModule('suppliers','assess'));
const canValidate=computed(()=>auth.canAccessModule('suppliers','validate_assessment'));
const levels=['Faible','Moyenne','Élevée','Critique'];
const statuses=['À qualifier','En évaluation','Approuvé','Approuvé sous conditions','Suspendu','Terminé'];
const contactTypes=['Commercial','Technique','Sécurité','Contractuel','Autre'];
const suppliers=ref([]),contacts=ref([]),contracts=ref([]),documents=ref([]),assessments=ref([]),loading=ref(false),saving=ref(false),error=ref(''),formError=ref(''),contactError=ref(''),contractError=ref(''),contractFormError=ref('');
const search=ref(''),criticality=ref(''),status=ref(''),includeArchived=ref(false),limit=ref(25),offset=ref(0);
const formOpen=ref(false),editing=ref(null),assetSupplier=ref(null),supplierAssetLinks=ref([]),selectableAssets=ref([]),supplierAccessRequests=ref([]),assetLinkError=ref(''),supplierRiskLinks=ref([]),availableRisks=ref([]),supplierRiskForm=reactive({risk_id:'',relationship_type:'Dépendance opérationnelle',relationship_context:''}),selectedAccessReview=ref(null),accessReviewHistory=ref([]),accessReviewForm=reactive({outcome:'Maintenue',comment:'',next_review_at:'',new_access_level:'Standard',new_data_access:false}),contactSupplier=ref(null),contractSupplier=ref(null),assessmentSupplier=ref(null),activeAssessment=ref(null),validationAssessment=ref(null);
const assessmentError=ref(''),assessmentFormError=ref('');
const answerMap=reactive({});
const validationForm=reactive({decision:'Approuvé sous conditions',validation_comment:'',next_review_at:''});

const contractTypes=['Service','Maintenance','Hébergement','Infogérance','Licence','Autre'];
const contractStatuses=['Brouillon','En validation','Actif','À renouveler','Expiré','Résilié'];
const clauseFields=[{key:'clause_confidentiality',label:'Confidentialité'},{key:'clause_incident_notification',label:'Notification des incidents'},{key:'clause_audit_right',label:'Droit d’audit'},{key:'clause_business_continuity',label:'Continuité d’activité'},{key:'clause_reversibility',label:'Réversibilité'},{key:'clause_data_location',label:'Localisation des données'},{key:'clause_subcontracting',label:'Encadrement de la sous-traitance'},{key:'clause_data_return_destruction',label:'Restitution / destruction des données'}];
const blankContract=()=>({reference:'',title:'',contract_type:'Service',description:'',start_date:'',end_date:null,notice_period_days:90,auto_renew:false,status:'Brouillon',internal_owner_id:null,document_id:null,clause_confidentiality:false,clause_incident_notification:false,clause_audit_right:false,clause_business_continuity:false,clause_reversibility:false,clause_data_location:false,clause_subcontracting:false,clause_data_return_destruction:false});
const contractForm=reactive(blankContract());
const blank=()=>({code:'',legal_name:'',trade_name:'',country:'',service_category:'',description:'',business_owner_id:null,direction:'',criticality:'Moyenne',dependency_level:'Moyenne',data_categories:'',hosting_location:'',uses_subprocessors:false,status:'À qualifier'});
const assetRelationshipTypes=['Héberge','Maintient','Administre','Accède','Fournit','Autre'];
const assetLinkForm=reactive({asset_id:'',relationship_type:'Maintient',access_level:'Aucun',data_access:false,scope:'',review_due_at:''});
const accessRequestForm=reactive({supplier_asset_link_id:'',access_level:'Standard',data_access:false,justification:'',scope:'',start_date:'',end_date:'',review_due_at:''});
const form=reactive(blank()),contactForm=reactive({full_name:'',role:'',email:'',phone:'',contact_type:'Autre'});
let timer;
function scheduleLoad(){clearTimeout(timer);timer=setTimeout(()=>{offset.value=0;load()},300)}
async function load(){loading.value=true;error.value='';const params={limit:limit.value,offset:offset.value,include_archived:includeArchived.value};if(search.value.trim())params.search=search.value.trim();if(criticality.value)params.criticality=criticality.value;if(status.value)params.status=status.value;try{const {data}=await apiClient.get('/suppliers/',{params});suppliers.value=data}catch(e){error.value=e.response?.data?.detail||'Chargement impossible.'}finally{loading.value=false}}
function openCreate(){editing.value=null;Object.assign(form,blank());formOpen.value=true;formError.value=''}
function edit(s){editing.value=s;Object.assign(form,blank(),s);formOpen.value=true;formError.value=''}
async function save(){saving.value=true;formError.value='';try{if(editing.value)await apiClient.patch('/suppliers/'+editing.value.id,form);else await apiClient.post('/suppliers/',form);formOpen.value=false;await load()}catch(e){formError.value=e.response?.data?.detail||'Enregistrement impossible.'}finally{saving.value=false}}
async function archive(s){if(!confirm('Archiver '+s.code+' ? Les données historiques seront conservées.'))return;try{await apiClient.post('/suppliers/'+s.id+'/archive');await load()}catch(e){error.value=e.response?.data?.detail||'Archivage impossible.'}}

const today=new Date().toISOString().slice(0,10);
async function createSupplierRiskLink(){if(!assetSupplier.value)return;saving.value=true;assetLinkError.value='';try{await apiClient.post('/suppliers/'+assetSupplier.value.id+'/risks',{risk_id:supplierRiskForm.risk_id,relationship_type:supplierRiskForm.relationship_type,relationship_context:supplierRiskForm.relationship_context});supplierRiskForm.risk_id='';supplierRiskForm.relationship_context='';const {data}=await apiClient.get('/suppliers/'+assetSupplier.value.id+'/risks');supplierRiskLinks.value=data}catch(e){assetLinkError.value=e.response?.data?.detail||'Association au risque impossible.'}finally{saving.value=false}}
async function openSupplierAssets(s){assetSupplier.value=s;supplierAssetLinks.value=[];supplierAccessRequests.value=[];supplierRiskLinks.value=[];assetLinkError.value='';Object.assign(supplierRiskForm,{risk_id:'',relationship_type:'Dépendance opérationnelle',relationship_context:''});Object.assign(assetLinkForm,{asset_id:'',relationship_type:'Maintient',access_level:'Aucun',data_access:false,scope:'',review_due_at:''});Object.assign(accessRequestForm,{supplier_asset_link_id:'',access_level:'Standard',data_access:false,justification:'',scope:'',start_date:today,end_date:'',review_due_at:''});try{const requests=[apiClient.get('/suppliers/'+s.id+'/assets'),canManageAssets.value?apiClient.get('/assets/'):Promise.resolve({data:[]}),canReadAccess.value?apiClient.get('/suppliers/'+s.id+'/access-requests'):Promise.resolve({data:[]}),canReadSupplierRisks.value?apiClient.get('/suppliers/'+s.id+'/risks'):Promise.resolve({data:[]}),canReadSupplierRisks.value?apiClient.get('/risks/'):Promise.resolve({data:[]})];const [links,assets,access,risks,allRisks]=await Promise.all(requests);supplierAssetLinks.value=links.data;selectableAssets.value=assets.data.filter(a=>!['Retiré','Décommissionné'].includes(a.lifecycle_status));supplierAccessRequests.value=access.data;supplierRiskLinks.value=risks.data;availableRisks.value=allRisks.data}catch(e){assetLinkError.value=e.response?.data?.detail||'Chargement des actifs ou autorisations impossible.'}}
async function openAccessReview(item){selectedAccessReview.value=item;accessReviewHistory.value=[];Object.assign(accessReviewForm,{outcome:'Maintenue',comment:'',next_review_at:item.review_due_at>=today?item.review_due_at:item.end_date,new_access_level:'Standard',new_data_access:false});try{const r=await apiClient.get('/suppliers/'+assetSupplier.value.id+'/access-requests/'+item.id+'/reviews');accessReviewHistory.value=r.data}catch(e){assetLinkError.value=e.response?.data?.detail||'Historique des revues indisponible.'}}
async function submitAccessReview(){if(!selectedAccessReview.value)return;saving.value=true;assetLinkError.value='';try{const payload={outcome:accessReviewForm.outcome,comment:accessReviewForm.comment,next_review_at:accessReviewForm.outcome==='Révoquée'?null:accessReviewForm.next_review_at};if(accessReviewForm.outcome==='Réduite'){payload.new_access_level=accessReviewForm.new_access_level;payload.new_data_access=accessReviewForm.new_data_access}await apiClient.post('/suppliers/'+assetSupplier.value.id+'/access-requests/'+selectedAccessReview.value.id+'/reviews',payload);selectedAccessReview.value=null;await openSupplierAssets(assetSupplier.value)}catch(e){assetLinkError.value=e.response?.data?.detail||'Enregistrement de la revue impossible.'}finally{saving.value=false}}
async function createAccessRequest(){saving.value=true;assetLinkError.value='';try{await apiClient.post('/suppliers/'+assetSupplier.value.id+'/access-requests',accessRequestForm);await openSupplierAssets(assetSupplier.value)}catch(e){assetLinkError.value=e.response?.data?.detail||'Création de la demande impossible.'}finally{saving.value=false}}
async function decideAccess(item,decision){const comment=prompt('Commentaire obligatoire pour cette décision :');if(!comment||comment.trim().length<5)return;saving.value=true;try{await apiClient.post('/suppliers/'+assetSupplier.value.id+'/access-requests/'+item.id+'/decision',{decision,comment});await openSupplierAssets(assetSupplier.value)}catch(e){assetLinkError.value=e.response?.data?.detail||'Décision impossible.'}finally{saving.value=false}}
async function revokeAccess(item){const reason=prompt('Motif obligatoire de révocation :');if(!reason||reason.trim().length<5)return;saving.value=true;try{await apiClient.post('/suppliers/'+assetSupplier.value.id+'/access-requests/'+item.id+'/revoke',{reason});await openSupplierAssets(assetSupplier.value)}catch(e){assetLinkError.value=e.response?.data?.detail||'Révocation impossible.'}finally{saving.value=false}}
async function expireAccess(item){if(!confirm('Clôturer cette autorisation comme expirée ?'))return;saving.value=true;try{await apiClient.post('/suppliers/'+assetSupplier.value.id+'/access-requests/'+item.id+'/expire');await openSupplierAssets(assetSupplier.value)}catch(e){assetLinkError.value=e.response?.data?.detail||'Clôture impossible.'}finally{saving.value=false}}
function riskLabel(id){const r=availableRisks.value.find(x=>x.id===id);return r?.ref||id}
function riskTitle(id){const r=availableRisks.value.find(x=>x.id===id);return r?.title||'Risque du registre central'}
function assetLabel(id){const a=selectableAssets.value.find(x=>x.id===id);return a?a.reference+' — '+a.name:id}
async function createAssetLink(){saving.value=true;assetLinkError.value='';try{const payload={...assetLinkForm,review_due_at:assetLinkForm.review_due_at||null};await apiClient.post('/suppliers/'+assetSupplier.value.id+'/assets',payload);await openSupplierAssets(assetSupplier.value)}catch(e){assetLinkError.value=e.response?.data?.detail||'Association impossible.'}finally{saving.value=false}}
async function terminateAssetLink(link){if(!confirm('Terminer cette relation ? Son historique sera conservé.'))return;saving.value=true;try{await apiClient.post('/suppliers/'+assetSupplier.value.id+'/assets/'+link.id+'/terminate');await openSupplierAssets(assetSupplier.value)}catch(e){assetLinkError.value=e.response?.data?.detail||'Terminaison impossible.'}finally{saving.value=false}}
async function openAssessments(s){assessmentSupplier.value=s;assessments.value=[];activeAssessment.value=null;validationAssessment.value=null;assessmentError.value='';assessmentFormError.value='';try{const {data}=await apiClient.get('/suppliers/'+s.id+'/assessments');assessments.value=data}catch(e){assessmentError.value=e.response?.data?.detail||'Chargement des évaluations impossible.'}}
async function createAssessment(){saving.value=true;assessmentFormError.value='';try{const {data}=await apiClient.post('/suppliers/'+assessmentSupplier.value.id+'/assessments',{assessment_type:'Initiale',scope:'Évaluation générale de sécurité du fournisseur et de la prestation fournie à la CTF.',questionnaire_version:'CTF-TPRM-1.0'});await openAssessments(assessmentSupplier.value);selectAssessment(data)}catch(e){assessmentFormError.value=e.response?.data?.detail||'Création de l’évaluation impossible.'}finally{saving.value=false}}
function selectAssessment(a){activeAssessment.value=a;validationAssessment.value=null;assessmentFormError.value='';for(const q of a.questionnaire_snapshot){const existing=a.answers.find(x=>x.question_id===q.id);answerMap[q.id]={score:existing?.score??0,comment:existing?.comment??''}}}
function selectForValidation(a){validationAssessment.value=a;activeAssessment.value=null;assessmentFormError.value='';Object.assign(validationForm,{decision:'Approuvé sous conditions',validation_comment:'',next_review_at:a.next_review_at||''})}
async function saveAnswers(){if(!activeAssessment.value)return;saving.value=true;assessmentFormError.value='';try{const answers=activeAssessment.value.questionnaire_snapshot.map(q=>({question_id:q.id,score:answerMap[q.id].score,comment:answerMap[q.id].comment||null}));const {data}=await apiClient.put('/suppliers/'+assessmentSupplier.value.id+'/assessments/'+activeAssessment.value.id+'/answers',{answers});activeAssessment.value=data;await openAssessments(assessmentSupplier.value);selectAssessment(data)}catch(e){assessmentFormError.value=e.response?.data?.detail||'Enregistrement des réponses impossible.'}finally{saving.value=false}}
async function submitAssessment(){if(!activeAssessment.value)return;saving.value=true;assessmentFormError.value='';try{await saveAnswers();const id=activeAssessment.value?.id;if(!id)return;await apiClient.post('/suppliers/'+assessmentSupplier.value.id+'/assessments/'+id+'/submit');activeAssessment.value=null;await openAssessments(assessmentSupplier.value)}catch(e){assessmentFormError.value=e.response?.data?.detail||'Soumission impossible. Vérifiez les réponses obligatoires.'}finally{saving.value=false}}
async function validateAssessment(){if(!validationAssessment.value)return;saving.value=true;assessmentFormError.value='';try{await apiClient.post('/suppliers/'+assessmentSupplier.value.id+'/assessments/'+validationAssessment.value.id+'/validate',{...validationForm,next_review_at:validationForm.next_review_at||null});validationAssessment.value=null;await openAssessments(assessmentSupplier.value)}catch(e){assessmentFormError.value=e.response?.data?.detail||'Validation impossible.'}finally{saving.value=false}}
async function openContracts(s){contractSupplier.value=s;contracts.value=[];documents.value=[];contractError.value='';contractFormError.value='';Object.assign(contractForm,blankContract());try{const {data}=await apiClient.get('/suppliers/'+s.id+'/contracts');contracts.value=data;if(canReadDocuments.value){const docs=await apiClient.get('/documents/');documents.value=docs.data}}catch(e){contractError.value=e.response?.data?.detail||'Chargement des contrats ou documents impossible.'}}
function clauseCount(c){return clauseFields.filter(x=>c[x.key]).length}
async function createContract(){saving.value=true;contractFormError.value='';try{const payload={...contractForm};if(!payload.end_date)payload.end_date=null;await apiClient.post('/suppliers/'+contractSupplier.value.id+'/contracts',payload);await openContracts(contractSupplier.value)}catch(e){contractFormError.value=e.response?.data?.detail||'Création du contrat impossible.'}finally{saving.value=false}}
async function openContacts(s){contactSupplier.value=s;contacts.value=[];contactError.value='';try{const {data}=await apiClient.get('/suppliers/'+s.id+'/contacts');contacts.value=data}catch(e){contactError.value=e.response?.data?.detail||'Chargement contacts impossible.'}}
async function addContact(){saving.value=true;contactError.value='';try{await apiClient.post('/suppliers/'+contactSupplier.value.id+'/contacts',contactForm);Object.assign(contactForm,{full_name:'',role:'',email:'',phone:'',contact_type:'Autre'});await openContacts(contactSupplier.value)}catch(e){contactError.value=e.response?.data?.detail||'Création impossible.'}finally{saving.value=false}}
async function deactivate(c){try{await apiClient.patch('/suppliers/'+contactSupplier.value.id+'/contacts/'+c.id,{is_active:false});await openContacts(contactSupplier.value)}catch(e){contactError.value=e.response?.data?.detail||'Désactivation impossible.'}}
function previous(){offset.value=Math.max(0,offset.value-limit.value);load()}
function next(){offset.value+=limit.value;load()}
function levelClass(v){return ({Faible:'low',Moyenne:'medium',Élevée:'high',Critique:'critical'})[v]||''}
onMounted(()=>{load();loadOverview();loadSnapshots();loadSupplierTrends();loadSupplierConcentration()});onUnmounted(()=>clearTimeout(timer));
</script>
<style scoped>
.suppliers-page{max-width:1500px;margin:auto;color:#0f172a}.tprm-overview{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:1rem;margin:1rem 0 1.5rem}.overview-heading{display:flex;justify-content:space-between;align-items:center;gap:1rem}.overview-heading h2{font-size:1.1rem;margin:0}.overview-heading p,.overview-note{font-size:.82rem;color:#64748b;margin:.3rem 0}.kpi-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.75rem;margin:1rem 0}.kpi{border:1px solid #e2e8f0;border-radius:8px;padding:.85rem;display:flex;flex-direction:column;gap:.25rem;min-width:0}.kpi span{font-size:.82rem;color:#475569}.kpi strong{font-size:1.65rem;color:#0f172a}.kpi small{color:#64748b}.kpi-alert{border-color:#fca5a5;background:#fff7f7}.kpi-alert strong{color:#b91c1c}.risk-distribution{border-top:1px solid #e2e8f0;padding-top:.8rem;font-size:.85rem}.snapshot-history{border-top:1px solid #e2e8f0;margin-top:1rem;padding-top:1rem}.snapshot-history h3{font-size:1rem;margin:0}.trend-comparison{margin:.9rem 0;padding:.75rem;border:1px solid #e2e8f0;border-radius:8px}.trend-comparison h4{font-size:.92rem;margin:0 0 .5rem}.trend-comparison table{min-width:760px}.trend-state{display:inline-block;border-radius:5px;padding:.2rem .4rem;font-size:.78rem;background:#f1f5f9;color:#334155}.trend-state.deteriorating{background:#fee2e2;color:#991b1b}.trend-state.improving{background:#dcfce7;color:#166534}.snapshot-history .table-wrap{margin-top:.75rem}.snapshot-history table{min-width:720px}.risk-levels{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.6rem}.risk-levels span{background:#f1f5f9;border-radius:6px;padding:.4rem .55rem;color:#334155}.risk-levels b{margin-left:.25rem}.overview-loading{padding:1rem;color:#64748b}@media(max-width:900px){.kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:560px){.kpi-grid{grid-template-columns:1fr}.overview-heading{align-items:flex-start;flex-direction:column}}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem}.page-header h1{margin:0}.page-header p{color:#64748b}.filters,.pagination{display:flex;gap:.7rem;align-items:center;flex-wrap:wrap;margin:1rem 0}.filters input:not([type=checkbox]){min-width:260px;flex:1}.filters input,.filters select,.grid input,.grid select,.modal textarea{padding:.6rem;border:1px solid #cbd5e1;border-radius:6px;box-sizing:border-box}.table-wrap{overflow:auto;border:1px solid #e2e8f0;border-radius:8px;background:white}table{border-collapse:collapse;width:100%;min-width:1000px}th,td{text-align:left;padding:.7rem;border-bottom:1px solid #e2e8f0;vertical-align:top}th{background:#f8fafc}small{display:block;color:#64748b;margin-top:.2rem}.level{color:white;padding:.2rem .5rem;border-radius:10px}.low{background:#16a34a}.medium{background:#ca8a04}.high{background:#ea580c}.critical{background:#dc2626}.secondary{background:#e2e8f0!important;color:#334155!important}.danger{background:#fee2e2!important;color:#991b1b!important}.empty{text-align:center;color:#64748b;padding:1.5rem}.pagination{justify-content:flex-end}.overlay{position:fixed;inset:0;background:#0008;display:flex;align-items:center;justify-content:center;z-index:1000;padding:1rem}.modal{background:white;border-radius:12px;padding:1.5rem;width:min(900px,96vw);max-height:90vh;overflow:auto}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.8rem}.modal label{display:flex;flex-direction:column;gap:.3rem;margin:.5rem 0}.modal .check{flex-direction:row}.modal textarea{width:100%;box-sizing:border-box}.assessment-editor{border-top:1px solid #e2e8f0;margin-top:1rem;padding-top:1rem}.question{padding:.6rem;border:1px solid #e2e8f0;border-radius:6px;margin:.5rem 0}.question textarea{width:100%;min-height:55px}.question select{max-width:160px}.clauses{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.3rem}.modal-actions{display:flex;justify-content:flex-end;gap:.5rem;margin-top:1rem}.error{color:#b91c1c;background:#fef2f2;padding:.6rem}@media(max-width:700px){.grid{grid-template-columns:1fr}.page-header{align-items:flex-start;flex-direction:column}}
</style>
