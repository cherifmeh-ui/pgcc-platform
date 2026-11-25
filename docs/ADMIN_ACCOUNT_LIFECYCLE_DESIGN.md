# Administration du cycle de vie des comptes — décision d'architecture Phase 0

Date : 2026-11-25  
Branche de référence : `chore/phase0-stabilization`  
Statut : conception validée pour implémentation ; aucune route d'administration n'est déclarée disponible à ce stade.

## 1. Constat vérifié

- Le modèle `User` porte les états de compte, MFA, verrouillage et `auth_version`.
- Le mécanisme `User.before_update` incrémente `auth_version` sur les changements sensibles.
- Les dépendances `get_current_user`, `require_role` et `require_permission` fournissent les contrôles d'identité et RBAC.
- Le routeur API v1 inclut actuellement `me`, `auth`, `security_logs`, risques, IA, applications, rapports, actions, conformité, documents, actifs et fournisseurs.
- Aucun endpoint de gestion administrative des utilisateurs n'est inclus dans ce routeur.
- La table `RefreshTokenSession` permet de révoquer les sessions de renouvellement actives.

## 2. API cible proposée

Préfixe : `/admin/users`. Toutes les routes doivent exiger un compte actif de rôle `admin` et MFA actif, en plus d'une permission dédiée `users:manage`. L'autorisation est contrôlée côté serveur, jamais par le frontend seul.

| Route | Action | Règles |
|---|---|---|
| GET `/` | Liste paginée | Ne jamais exposer les hashes, secrets MFA ou codes de secours |
| GET `/{user_id}` | Détail | Même minimisation des champs sensibles |
| PATCH `/{user_id}` | Modifier nom, département, rôle, activation | Validation stricte, audit atomique, révocation des sessions si changement sensible |
| POST `/{user_id}/mfa/reset` | Réinitialiser MFA | Effacer secret et codes de secours, désactiver MFA, incrémenter auth_version, révoquer refresh sessions |
| POST `/{user_id}/sessions/revoke` | Révoquer les sessions | Révoquer toutes les sessions actives et incrémenter auth_version |

La création initiale d'un compte reste un flux séparé à définir (invitation contrôlée ou provisioning). Aucun mot de passe temporaire ne doit être retourné en clair par une API d'administration.

## 3. Invariants transactionnels obligatoires

1. Verrouiller la ligne utilisateur cible avec `SELECT ... FOR UPDATE`.
2. Vérifier l'identité de l'administrateur, son rôle, son MFA et ses permissions.
3. Interdire à un administrateur de désactiver son propre compte ou de supprimer ses propres privilèges.
4. Empêcher la désactivation ou rétrogradation du dernier administrateur actif avec MFA.
5. Toute mutation sensible, la révocation des refresh sessions et l'événement `enqueue_audit_event` doivent appartenir à la même transaction.
6. En cas d'échec d'audit ou de contrainte DB, rollback intégral ; ne jamais conserver une mutation sans son événement d'audit.
7. L'événement d'audit doit identifier l'acteur, la cible, l'action et les champs modifiés sans journaliser de secret.
8. L'API ne doit jamais accepter `auth_version`, `password_hash`, `mfa_secret` ou `backup_codes_hashed` depuis les payloads client.
9. Protéger les opérations concurrentes de dernier administrateur par verrouillage cohérent des administrateurs actifs et tests PostgreSQL de concurrence.

## 4. Tests d'acceptation

- Un utilisateur non-admin, un admin sans MFA et un compte désactivé reçoivent un refus.
- Les rôles inconnus et champs sensibles injectés sont rejetés.
- Un changement de rôle/désactivation/reset MFA incrémente `auth_version` et invalide les access tokens et refresh sessions.
- Une révocation de session seule invalide également les access tokens.
- L'échec de `enqueue_audit_event` annule la mutation et la révocation.
- Deux demandes concurrentes ne peuvent pas désactiver/rétrograder simultanément les deux derniers administrateurs actifs.
- Un administrateur ne peut pas se retirer lui-même le dernier accès administrateur.
- Les réponses n'exposent jamais les hashes de mot de passe, secret MFA ou hashes des codes de secours.
- Tests API unitaires et intégration PostgreSQL couvrant les scénarios positifs, refus, rollback et concurrence.

## 5. Critères de clôture

L'implémentation ne sera considérée validée qu'après tests backend, intégration PostgreSQL, revue RBAC, revue d'audit et CI complète verte sur le HEAD final de la branche. Ce document est une spécification, pas une preuve d'implémentation.
