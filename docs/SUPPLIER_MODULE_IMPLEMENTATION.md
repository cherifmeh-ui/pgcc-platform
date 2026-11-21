# Implémentation — Référentiel Fournisseurs

## Tranche 1 — Référentiel et contacts

- Modèles SQLAlchemy `Supplier` et `SupplierContact`.
- Migration Alembic `0012_supplier_register`.
- API CRUD de base, archivage logique, recherche et pagination par limit/offset.
- Gestion des contacts professionnels, désactivation plutôt que suppression.
- Permissions dédiées `suppliers:read/create/update/archive/manage_contacts/export`.
- Journalisation des créations, modifications et archivages.
- Codes fournisseurs normalisés et indexés avec unicité insensible à la casse.
- Aucun endpoint de suppression physique et aucun stockage de secrets.

### Routes

- `GET/POST /api/v1/suppliers/`
- `GET/PATCH /api/v1/suppliers/{supplier_id}`
- `POST /api/v1/suppliers/{supplier_id}/archive`
- `GET/POST /api/v1/suppliers/{supplier_id}/contacts`
- `PATCH /api/v1/suppliers/{supplier_id}/contacts/{contact_id}`

### Suite

Contrats et pièces justificatives, évaluations versionnées, accès tiers et relations explicites avec actifs/risques seront ajoutés dans des tranches indépendantes avec migrations et tests dédiés.


## Tranche 2 — Contrats et clauses SSI

- Modèle SupplierContract relié au fournisseur par FK RESTRICT.
- Référence contractuelle unique par fournisseur, insensible à la casse.
- Dates contrôlées côté API et base; préavis borné; renouvellement explicite.
- Clauses SSI suivies individuellement : confidentialité, notification d'incident, droit d'audit, continuité, réversibilité, localisation, sous-traitance, restitution/destruction.
- Référence facultative au document existant (documents.id) : aucun stockage binaire ni duplication documentaire.
- API : lecture paginée, création et modification; aucune suppression physique.
- Permissions dédiées : lecture Admin/Auditor, gestion Admin.
- Migration Alembic 0013_supplier_contracts; downgrade limité à la nouvelle table.
- Pas d'automatisation de statut ni d'alertes avant mise en place d'un service de notifications et de règles de date validées.


## Tranche 2 — Contrats et clauses SSI

- Modèle SupplierContract relié au fournisseur par FK RESTRICT.
- Référence contractuelle unique par fournisseur, insensible à la casse.
- Dates contrôlées côté API et base; préavis borné; renouvellement explicite.
- Clauses SSI suivies individuellement : confidentialité, notification d'incident, droit d'audit, continuité, réversibilité, localisation, sous-traitance, restitution/destruction.
- Référence facultative au document existant (documents.id) : aucun stockage binaire ni duplication documentaire.
- API : lecture paginée, création et modification; aucune suppression physique.
- Permissions dédiées : lecture Admin/Auditor, gestion Admin.
- Migration Alembic 0013_supplier_contracts; downgrade limité à la nouvelle table.
- Pas d'automatisation de statut ni d'alertes avant mise en place d'un service de notifications et de règles de date validées.

## Tranche 3 — Évaluations de sécurité fournisseurs

- Évaluations historisées par fournisseur et type (initiale, périodique, renouvellement, incident, changement majeur).
- Chaque évaluation conserve un instantané JSONB du questionnaire et sa version : les changements futurs ne modifient pas l'historique.
- Réponses structurées avec score, commentaire et référence facultative à une preuve du module Documents.
- Calcul pondéré déterministe côté serveur, score sur 100 et niveau de risque explicite; les données manquantes ne sont jamais assimilées à la conformité.
- Cycle : Brouillon → À valider → Validée. Les réponses deviennent non modifiables après soumission.
- Séparation des tâches : l'évaluateur ne peut pas valider sa propre évaluation.
- Une approbation simple est interdite pour un risque Élevé ou Critique; une approbation conditionnelle ou un refus est alors requis.
- Permissions dédiées : Admin pour évaluer et valider; Admin/Auditor en lecture.
- Migration Alembic 0014_supplier_assessments; aucune modification des tables historiques.
- La validation reste une décision humaine; le score ne modifie pas automatiquement le statut du fournisseur.
### Contrôle de confiance du questionnaire

- Le client ne transmet plus la définition ni les pondérations du questionnaire.
- Les versions publiées sont définies côté serveur; la création charge une copie profonde de la version autorisée et la conserve en instantané dans l'évaluation.
- Une version inconnue est rejetée. Cela empêche un utilisateur de modifier les pondérations ou les questions afin de manipuler le score.
- Toute évolution du référentiel doit publier une nouvelle version; les évaluations historiques conservent leur propre instantané.

## Tranche 4 — Relations Fournisseurs ↔ Cartographie

- Table d'association dédiée `supplier_asset_links`, sans détourner le graphe technique `asset_relationships`.
- Typologie métier : héberge, maintient, administre, accède, fournit, autre.
- Qualification des accès : aucun, standard, privilégié; indicateur séparé d'accès aux données.
- Périmètre de prestation, date de prochaine revue et statut conservés sur le lien.
- Consultation réservée aux rôles Admin/Auditor; création et terminaison réservées à Admin.
- Les relations sont terminées logiquement, jamais supprimées physiquement; l'historique est conservé.
- Les actifs retirés/décommissionnés et fournisseurs archivés ne peuvent pas recevoir de nouveau lien.
- Les deux clés étrangères utilisent RESTRICT afin d'éviter les suppressions en cascade sur les référentiels.
- Migration additive `0015_supplier_asset_links`; aucun changement des tables Cartographie ou des modules historiques.


### Tranche 5 — Consultation croisée depuis les deux référentiels

- Depuis une fiche fournisseur, l'utilisateur autorisé consulte les actifs liés, leurs rôles, niveaux d'accès, accès aux données et échéances de revue.
- Depuis la fiche d'un actif, l'utilisateur autorisé consulte les fournisseurs associés avec leur code, raison sociale, type de relation et qualification d'accès.
- La consultation inverse est exposée par `GET /suppliers/assets/{asset_id}/suppliers`; la consultation fournisseur par `GET /suppliers/{supplier_id}/assets`.
- Les listes retournent les identifiants lisibles des référentiels associés, sans imposer au profil auditeur un accès général à l'inventaire.
- Les autorisations `read_assets` et `manage_assets` restent dans le périmètre RBAC `suppliers`; elles ne sont pas dupliquées dans le module `assets`.
- La gestion et la terminaison logique restent réservées à Admin; les profils Auditor peuvent consulter; Executive ne reçoit pas l'accès détaillé aux liens.
- Les écrans existants de Cartographie, fournisseurs, risques et dépendances sont conservés; les nouvelles sections sont conditionnées par les permissions dédiées.


### Tranche 6 — Cycle de vie des autorisations d'accès fournisseurs

Une relation fournisseur–actif ne constitue pas une autorisation. Le modèle `supplier_access_requests` porte une décision d'accès interne distincte, nominative et limitée dans le temps.

- Demande interne : justification, périmètre, niveau Standard/Privilégié, accès aux données, dates de début/fin et prochaine revue.
- Éligibilité : fournisseur approuvé ou approuvé sous conditions, relation fournisseur–actif active, actif non retiré/décommissionné et demande non rétroactive.
- Décision : approbation ou refus avec commentaire obligatoire; le demandeur ne peut pas approuver sa propre demande.
- Révocation : réservée à Admin, motif obligatoire, auteur et horodatage conservés.
- Expiration : clôture explicite par Admin après la date de fin; l'identité et la date de décision initiale sont conservées.
- Unicité : index PostgreSQL partiel garantissant au plus une demande/autorisation ouverte par relation fournisseur–actif, y compris en cas de concurrence.
- Consultation : Admin et Auditor; demande, décision, révocation et expiration réservées à Admin.
- Journalisation : création, décision, révocation et expiration sont inscrites dans le journal de sécurité.
- L'autorisation est une preuve de gouvernance; elle ne provisionne ni ne désactive techniquement un compte dans les systèmes cibles. La révocation doit être suivie de l'action technique correspondante et de sa vérification.
- Les dates de revue sont enregistrées; les rappels automatiques et la synchronisation avec IAM/PAM restent des étapes ultérieures.


### Tranche 7 — Contrôle de cohérence et analyse d'impact

- L'analyse d'impact distingue désormais les relations d'inventaire fournisseur–actif des autorisations réellement approuvées.
- Seules les autorisations au statut `Approuvé`, dont la période couvre la date courante et dont le fournisseur n'est pas archivé, sont comptabilisées comme accès actifs.
- Les indicateurs distinguent les niveaux déclarés sur les relations et les accès privilégiés / accès aux données effectivement autorisés.
- Les fiches Cartographie affichent explicitement que les métadonnées de relation ne constituent pas une autorisation d'accès.
- L'index PostgreSQL partiel garantit l'unicité d'une demande/autorisation ouverte par relation, même en cas de soumissions concurrentes.


## Tranche 8 — Revues périodiques des autorisations d'accès

- Nouvelle table append-only `supplier_access_reviews`, liée à l'autorisation par FK RESTRICT.
- Historique immuable des revues : réviseur, date, décision, commentaire, niveau et accès aux données avant/après, prochaine échéance.
- Décisions possibles : maintien, réduction effective des privilèges ou révocation.
- Une réduction ne peut jamais augmenter les droits; elle doit réduire le niveau Privilégié vers Standard et/ou retirer l'accès aux données.
- Une revue ne peut être réalisée ni par le demandeur initial ni par l'approbateur initial.
- Seules les autorisations approuvées et actuellement dans leur période de validité peuvent être revues.
- Toute décision non révocatoire doit fixer une nouvelle date de revue comprise entre la date du jour et la fin de l'autorisation.
- La révocation par revue conserve les métadonnées de révocation et libère l'index partiel des demandes ouvertes.
- Permissions : Admin pour exécuter une revue; Admin/Auditor pour consulter l'historique.
- API : GET/POST `/{supplier_id}/access-requests/{access_request_id}/reviews`.
- Migration additive `0017_supplier_access_reviews`; aucune modification destructive des données historiques.
- La revue est une décision de gouvernance. La désactivation ou l'ajustement technique des comptes fournisseurs doit être exécuté et vérifié dans les systèmes cibles.
