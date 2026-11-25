# Sécurité documentaire et feuille de route RAG

Mise à jour : 25 novembre 2026

## Contrôles déjà présents dans le dépôt

- Upload limité à 10 Mio + 1 octet, avec rejet au-delà de la limite.
- Formats limités à PDF et DOCX ; signature PDF contrôlée et structure DOCX vérifiée avant extraction.
- Extraction PDF limitée à 50 pages ; archive DOCX limitée en nombre d'entrées, taille décompressée et ratio de compression.
- Texte extrait limité à 2 000 000 caractères ; erreurs du parseur renvoyées sans détails internes.
- Classification dérivée de `doc_type` : `PSSI`, `PROCEDURE` et `REGLEMENT_INTERIEUR` sont `INTERNAL`; les autres types, inconnus ou absents sont `RESTRICTED`.
- Les rôles admin, executive et auditor peuvent consulter les deux classifications ; viewer est limité aux documents `INTERNAL`.
- Cette première politique est fondée sur le rôle et le type de document ; elle ne fournit pas encore de contrôle d'accès par département, propriétaire, dossier ou besoin d'en connaître.
- Le filtrage est appliqué à la liste, à l'aperçu et au téléchargement direct. Un document restreint ou inconnu est masqué au viewer par une réponse 404.
- La création et la suppression des documents ainsi que l'indexation RAG ajoutent leur événement d'audit dans la transaction métier.
- L'identité du fichier est protégée par l'index PostgreSQL unique `uq_documents_filename_ci`, insensible à la casse et aux espaces périphériques.
- Les tests unitaires et PostgreSQL couvrent classification, accès croisé liste/preview/download, extraction, suppression concurrente avec indexation et rollback de l'indexation si l'audit échoue.

## Constat précis sur le RAG

Le service actuel sait **indexer** un document : il génère les embeddings, remplace les chunks dans une transaction et journalise l'opération. Il ne contient pas de méthode de recherche/récupération de chunks et aucune route de requête RAG n'a été identifiée dans l'API actuelle.

En conséquence :
- Il n'existe pas encore de chemin de récupération RAG auquel appliquer ou tester un filtrage ACL.
- Les chunks ne portent pas de classification, de version documentaire ni de provenance de page fiable.
- Aucun endpoint de recherche RAG ne doit être exposé avant l'ajout d'un contrôle d'accès à la récupération.

### Règle obligatoire avant toute route de récupération

La récupération doit joindre `document_chunks` à `documents` et appliquer la politique d'accès **dans la requête SQL avant le classement/limitation des résultats**. Ne pas récupérer les meilleurs chunks puis filtrer seulement après le top-k : cela peut créer des fuites indirectes et dégrader le rappel. La même fonction de politique doit couvrir la liste, l'aperçu, le téléchargement et le contexte transmis au modèle.

Tests requis : viewer ne récupère jamais un chunk issu d'un document `RESTRICTED`, y compris lorsque ce chunk serait le meilleur résultat vectoriel ; les rôles privilégiés conservent l'accès prévu ; les types inconnus restent refusés par défaut ; aucune donnée restreinte ne figure dans le prompt ou les sources retournées.

## Risques résiduels et décisions de mise en production

- Aucun antivirus, moteur de détection ou mécanisme de quarantaine n'est intégré.
- L'extraction s'exécute dans le processus API ; les limites de taille ne remplacent pas un bac à sable isolé ni une politique de temps/mémoire au niveau du système.
- Les fichiers et textes extraits sont stockés dans PostgreSQL ; aucune stratégie complète de stockage objet privé, chiffrement applicatif, rétention et purge n'est encore formalisée.
- Aucun hash SHA-256 persistant du fichier original ni historique immuable des versions n'est enregistré.
- La suppression physique est possible lorsqu'aucune preuve ISO ne référence le document ; une politique d'archivage et de conservation doit être définie.
- L'indexation RAG est synchrone dans la requête API. Une file de travaux, des états `pending/processing/completed/failed`, des reprises et des limites de ressources restent à concevoir.
- Le contenu extrait est non fiable et peut contenir des instructions d'injection de prompt. Il doit toujours être traité comme une donnée, jamais comme une instruction système.
- Aucun workflow complet de validation/approbation des preuves n'est implémenté.

## Portes de sortie

Avant une mise en production, chaque risque ci-dessus doit être corrigé ou faire l'objet d'une acceptation formelle du propriétaire du système. Les points bloquants sont : antivirus/quarantaine ou acceptation documentée, isolation du parsing, politique de conservation, ACL RAG avant toute récupération, et revue de sécurité humaine.


## Addendum — état consolidé au 25 novembre 2026

Cette section prévaut sur les constats historiques ci-dessus lorsqu'ils sont contradictoires.

### Contrôles désormais présents et validés

- ClamAV est intégré au dépôt et au chemin d'upload avant toute extraction, écriture métier ou indexation RAG. L'indisponibilité du moteur bloque le dépôt (fail-closed) ; un verdict infecté est refusé.
- Le profil Docker Compose `antivirus` démarre un daemon ClamAV sur le réseau privé, sans port publié sur l'hôte.
- Le workflow CI démarre le vrai daemon, attend l'état healthy, accepte un contenu propre et confirme la détection du fichier de test EICAR.
- Les documents ont un SHA-256 persistant, un propriétaire et un département. La politique d'accès est appliquée aux opérations de liste, aperçu, téléchargement et contexte IA ; des tests PostgreSQL couvrent les accès autorisés et les refus inter-départements.
- La récupération de contexte IA réapplique la classification et l'ACL canonique avant insertion dans le prompt. Ne pas ajouter de nouvelle route de recherche vectorielle sans filtrage ACL dans la requête SQL avant le classement/top-k.
- Les mutations documentaires et événements d'audit sont intégrés à la même transaction dans les parcours déjà migrés ; la couverture transactionnelle doit être vérifiée pour chaque nouveau parcours.

### Durcissement du parseur en cours

- Le parseur reste exécuté dans le processus backend à ce stade ; il n'est donc pas encore considéré comme isolé.
- L'extraction PDF échoue désormais en cas d'erreur d'extraction d'une page au lieu d'indexer silencieusement un document partiel.
- Les limites d'extraction sont appliquées pendant l'accumulation du texte, et non uniquement après construction d'une grande chaîne.
- Les archives DOCX sont contrôlées avant parsing : nombre d'entrées, taille décompressée, ratio de compression, présence du document XML, doublons et entrées chiffrées.
- Les nouveaux tests unitaires de ces contrôles doivent réussir dans le workflow du HEAD courant avant validation.

### Conditions restantes avant clôture Phase 0

1. Déployer un service de parsing isolé : non-root, image minimale, réseau sans sortie Internet, aucun accès PostgreSQL/ClamAV/stockage, filesystem en lecture seule, limites CPU/mémoire/PID/temps et taille d'entrée bornée. Le backend doit valider la réponse du service et échouer fermé.
2. Ajouter des tests d'intégration Compose couvrant PDF/DOCX valide, fichier malformé, dépassement de délai, limite de mémoire et arrêt du service.
3. Répéter la restauration et mesurer les objectifs RPO/RTO dans l'environnement cible avec les responsables opérationnels ; les tests CI ne valent pas recette de reprise de production.
4. Configurer et vérifier en production TLS/reverse proxy, gestion des secrets, journalisation centralisée, supervision ClamAV et mise à jour des signatures.
5. Achever la revue des permissions et des frontières transactionnelles d'audit, puis faire accepter formellement les risques résiduels.

La Phase 0 demeure ouverte jusqu'à la validation des tests, de l'isolation et des contrôles opérationnels, puis la revue humaine finale.
