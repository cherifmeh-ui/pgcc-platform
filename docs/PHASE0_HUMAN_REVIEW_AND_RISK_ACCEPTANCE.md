# Phase 0 — Revue humaine et acceptation des risques résiduels

**Statut :** procédure à appliquer — aucune approbation humaine ni acceptation de risque n'est présumée.
**Branche de référence :** `chore/phase0-stabilization`
**PR :** #1 (à maintenir en Draft tant que les gates ne sont pas levés).

## 1. Objectif et séparation des décisions

Deux décisions distinctes sont requises :

1. **Revue technique indépendante :** un ou plusieurs reviewers compétents vérifient le code, les contrôles, les tests et les preuves. Ils consignent les constats et leur décision sur la PR.
2. **Acceptation du risque résiduel :** le responsable métier ou le propriétaire du risque, disposant de l'autorité de décision, accepte explicitement un risque précis pour une durée déterminée. L'acceptation ne remplace ni une correction obligatoire ni une approbation de mise en production.

Le RSSI prépare l'analyse, challenge les mesures et recommande le traitement. Il ne doit pas accepter seul un risque dont un directeur métier ou le propriétaire du système porte les conséquences.

## 2. Organisation de la revue humaine

### Rôles à solliciter

| Domaine | Reviewer attendu | Périmètre minimal |
|---|---|---|
| Architecture et code | Architecte ou développeur senior indépendant de l'auteur | Diff complet, architecture, cohérence, non-régression, qualité et dette technique |
| Sécurité applicative | Expert sécurité indépendant / RSSI pair | Authentification, MFA, sessions, rotation/rejeu, RBAC, API, documents/RAG, audit |
| Données et exploitation | DBA / responsable infrastructure-production | Alembic, PostgreSQL, sauvegardes, restauration, TLS, proxy, secrets, réseau, supervision |

Une personne peut couvrir plusieurs domaines si ses compétences sont établies. L'auteur des changements ne constitue pas à lui seul une revue indépendante.

### Préparation du dossier reviewer

Fournir au reviewer :
- URL de la PR #1 et SHA exact à examiner ;
- architecture cible et modèle de données ;
- `docs/PHASE0_VALIDATION_STATUS.md` ;
- `docs/MODULE_MATURITY_REVIEW.md` ;
- `docs/PHASE0_DATABASE_VALIDATION_RUNBOOK.md` ;
- ce document et les issues ouvertes liées à la sécurité ;
- résultats CI associés au SHA exact et limites explicites des tests CI.

Avant la revue, expliquer le périmètre des 219 fichiers modifiés et des 1 570 commits annoncés par GitHub. Le comparatif `main...chore/phase0-stabilization` indique 1 570 commits en avance et 0 en retard. Ce chiffre ne prouve pas à lui seul une anomalie, mais le reviewer doit comprendre l'historique, le point de divergence et les changements inclus avant de donner son approbation. Si le périmètre est trop large, proposer une revue par lots/domaines sans réécrire l'historique ni modifier `main`.

### Demande de revue — texte à envoyer

> Objet : Demande de revue technique indépendante — plateforme PGCC / Phase 0  
>
> Bonjour,  
>
> Je sollicite une revue indépendante de la Phase 0 de la plateforme PGCC, avant toute décision de clôture ou de mise en production.  
>
> La revue porte sur le périmètre de la PR #1, branche `chore/phase0-stabilization`, au commit [SHA à confirmer au démarrage de la revue]. Les contrôles automatisés disponibles sont documentés dans le dépôt ; ils ne remplacent pas la revue du code ni les validations sur l'infrastructure cible.  
>
> Je vous propose de couvrir le domaine [architecture/code — sécurité applicative — données/exploitation], de relever les anomalies et risques, puis de conclure par l'une des décisions suivantes : approuvé, approuvé sous réserve de points non bloquants explicitement listés, ou modifications requises.  
>
> Merci de consigner vos commentaires et votre décision sur la PR GitHub, ou dans un compte rendu daté et nominatif qui sera référencé dans le dépôt.  
>
> Cordialement,

### Critères de clôture de la revue

- [ ] Reviewer identifié, compétent et indépendant de l'auteur des changements.
- [ ] SHA exact revu et périmètre de la PR compris.
- [ ] Revue du code et des configurations réalisée ; constats classés (bloquant, majeur, mineur, observation).
- [ ] Chaque constat bloquant/majeur corrigé et retesté, ou transformé en risque résiduel formellement traité lorsque cela est admissible.
- [ ] Approbation GitHub explicite ou compte rendu signé, daté et archivé.
- [ ] Aucun changement substantiel ajouté après la revue sans revue complémentaire du nouveau diff.

## 3. Registre d'acceptation des risques résiduels

Chaque risque doit faire l'objet d'une fiche distincte comportant au minimum :

| Champ | Contenu attendu |
|---|---|
| ID | Identifiant unique, ex. RR-001 |
| Actif / processus | Système, données, service ou processus exposé |
| Scénario | Menace, vulnérabilité, événement et conséquences |
| Évaluation | Vraisemblance, impact, niveau inhérent et résiduel selon l'échelle approuvée |
| Mesures existantes | Contrôles déjà opérationnels et preuves |
| Traitement restant | Mesures supplémentaires, responsable et échéance |
| Mesures compensatoires | Réduction temporaire du risque et preuve de fonctionnement |
| Décision | Réduire, éviter, transférer ou accepter temporairement |
| Propriétaire du risque | Responsable métier / directeur responsable de l'actif |
| Autorité d'acceptation | Personne habilitée selon la délégation et la politique interne |
| Validité | Date de début, date d'expiration et date de réexamen |
| Déclencheurs de réexamen | Incident, changement d'architecture, dépassement d'échéance, nouvelle menace |
| Approbations | Nom, fonction, date et signature/trace formelle |

Une acceptation ne doit jamais être formulée comme « tous les risques PGCC sont acceptés ». Elle doit identifier chaque scénario, ses conséquences, les mesures compensatoires et la date d'expiration.

### Circuit de décision recommandé

1. Le responsable technique décrit le scénario et fournit les preuves.
2. Le RSSI challenge l'évaluation, vérifie les contrôles et formule un avis sécurité.
3. Le propriétaire métier de l'actif confirme les impacts opérationnels et financiers.
4. L'autorité compétente accepte ou refuse selon les seuils et délégations internes.
5. Le secrétariat de gouvernance / responsable du registre consigne la décision, les conditions et la date de réexamen.
6. Le RSSI suit les échéances et escalade toute acceptation expirée ou toute aggravation du risque.

Si le niveau dépasse l'appétence au risque approuvée, si une obligation réglementaire/contractuelle est violée, ou si le contrôle est une condition impérative de sécurité, l'acceptation locale ne suffit pas : escalade à l'autorité supérieure et décision de non-mise-en-production tant que le point n'est pas résolu.

### Formulaire de décision — à compléter pour chaque risque

```text
ID du risque :
Actif / processus :
Scénario de risque :
Causes / vulnérabilités :
Conséquences :
Risque inhérent (méthode et score) :
Contrôles existants et preuves :
Risque résiduel (méthode et score) :
Options étudiées :
Mesures compensatoires :
Plan de traitement restant :
Responsable et échéance :
Avis du RSSI : favorable / défavorable / favorable sous conditions
Propriétaire du risque :
Autorité habilitée :
Décision : accepté temporairement / refusé / traitement exigé
Motif de la décision :
Conditions et limites :
Date d'effet :
Date d'expiration / réexamen :
Nom, fonction, date et signature :
```

## 4. Risques résiduels Phase 0 à instruire

La liste ci-dessous est un point de départ à confirmer par les responsables ; ce ne sont pas des acceptations déjà accordées.

| ID provisoire | Sujet | Preuve / action attendue | Décision attendue |
|---|---|---|---|
| RR-001 | Restauration réelle, sauvegardes chiffrées/offsite, WAL/PITR, RPO/RTO | Exercice de restauration sur environnement cible, contrôle d'intégrité et mesure chronométrée | DBA/Production + propriétaire du service |
| RR-002 | DNS, certificats, secrets, reverse proxy/LB, CIDR de proxies de confiance | Revue de la topologie réelle, inventaire des secrets/certificats et test depuis le réseau cible | Infrastructure + Sécurité |
| RR-003 | ACL des documents classés RESTRICTED, notamment lecture par owner | Décision métier sur le modèle owner/rôle/département, tests d'accès positifs et négatifs | Propriétaire des données + Sécurité |
| RR-004 | Cycle opérationnel ClamAV | Responsable des signatures, alertes de fraîcheur, indisponibilité, mises à jour et procédure incident | Exploitation + Sécurité |
| RR-005 | Historique GitHub / périmètre PR #1 (1 570 commits annoncés) | Explication du graphe, point de divergence, revue de tous les changements inclus | Mainteneur + reviewer indépendant |

Les éléments RR-001 et RR-002 sont des prérequis de mise en production si les services concernés doivent être exploités en production. Une simple signature d'acceptation ne remplace pas une sauvegarde restaurable, une configuration valide ou un contrôle de sécurité obligatoire.

## 5. Décision finale Phase 0

La Phase 0 ne pourra être déclarée close que lorsque :
- les workflows requis sont verts sur le SHA candidat final ;
- la revue humaine indépendante est enregistrée ;
- les constats bloquants sont corrigés ;
- les tests de restauration et validations d'exploitation requis sont exécutés sur l'environnement cible ;
- chaque risque résiduel est traité ou accepté par l'autorité habilitée, dans les limites de l'appétence au risque ;
- les responsables autorisent explicitement la clôture de Phase 0.

**État au 27 novembre 2026 :** CI sur le SHA `5b87a54150394521fe974ab3bfc82a3a423c3b2c` : deux workflows observés, chacun avec les cinq jobs réussis. PR #1 toujours Draft ; aucune revue GitHub enregistrée au dernier contrôle. Les validations opérationnelles sur l'environnement cible et les décisions formelles d'acceptation restent à obtenir.


## Actualisation du périmètre de revue — 28 novembre 2026

- SHA candidat au checkpoint : `9194419b8017d8b8154a7c29bc6322fbfc8e4d90`.
- Le compare GitHub `main...chore/phase0-stabilization` rapporte **1 693 commits en avance et 0 en retard** au moment de la vérification (le nombre historique 1 570 ci-dessus est donc obsolète). Le reviewer doit comprendre le graphe et le périmètre exact de la PR avant approbation ; ce nombre ne constitue pas à lui seul une preuve de problème.
- Le workflow PR `46140116019` sur le SHA candidat est vert 5/5 ; Backend 562 passed / 63 skipped, PostgreSQL 62 passed. Les environnements CI sont jetables et ne couvrent pas l'exploitation réelle.
- Point supplémentaire à inclure dans la revue Auth : coordination du refresh cookie entre onglets. La file d'attente Axios n'est locale qu'à un contexte JavaScript ; la concurrence entre onglets n'est pas démontrée comme maîtrisée. Exiger une preuve navigateur ou une décision formelle de contrainte/risque avant fermeture du gate.

Le statut demeure **en attente d'un reviewer indépendant**. Aucune approbation ni acceptation de risque n'est présumée par cette actualisation.


### Suivi dédié — concurrence de refresh entre onglets

Le point de revue statique est désormais suivi dans l'issue [#7 — Coordination du renouvellement de session entre onglets navigateur](https://github.com/cherifmeh-ui/pgcc-platform/issues/7). Cette issue est un gate Auth Phase 0 : elle reste ouverte jusqu'à l'implémentation, aux tests navigateur multi-onglets et à la preuve que le rejeu réel reste détecté.


### Actualisation du périmètre PR — 28 novembre 2026

Vérification GitHub du PR #1 après les derniers ajouts de tests :

- HEAD observé : 0f02eaed389844f6f439b70b187d7bc35104fd2a.
- Base/main : 91d47a8fe29b391245449b99b55e651fa444ccb8.
- PR : 1 751 commits en avance, 0 en retard, 236 fichiers modifiés, 33 749 additions et 1 048 suppressions selon les métadonnées GitHub.
- Le compare main...HEAD confirme 1 750 commits en avance sur le SHA précédent a1a1fd4 ; l'écart d'un commit correspond au dernier changement de test.
- La PR demeure ouverte, Draft et non fusionnée. Aucune revue GitHub indépendante n'est enregistrée.

**Conséquence pour la clôture :** le reviewer indépendant doit examiner le graphe d'historique et le diff complet, pas uniquement les changements Phase 0 récents. Le périmètre est trop large pour déclarer une approbation par simple inspection ciblée ; envisager une revue structurée par domaines et une stratégie de PR plus petite après analyse du graphe, sans réécrire l'historique ni toucher à main dans le cadre actuel.
