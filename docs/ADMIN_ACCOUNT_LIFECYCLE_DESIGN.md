# Administration du cycle de vie des comptes — décision d'architecture Phase 0

Date : 2026-11-25  
Branche de référence : `chore/phase0-stabilization`  
Statut : première tranche implémentée et validée par CI/PostgreSQL sur le HEAD 91ec0cc ; les contrôles de production et la revue humaine restent ouverts.

## 1. Constat vérifié

- Le modèle `User` porte les états de compte, MFA, verrouillage et `auth_version`.
- Le mécanisme `User.before_update` incrémente `auth_version` sur les changements sensibles.
- Les dépendances `get_current_user`, `require_role` et `require_permission` fournissent les contrôles d'identité et RBAC.
- Le routeur API v1 inclut actuellement `me`, `auth`, `security_logs`, risques, IA, applications, rapports, actions, conformité, documents, actifs et fournisseurs.
- Aucun endpoint de gestion administrative des utilisateurs n'est inclus dans ce routeur.
- La table `RefreshTokenSession` permet de révoquer les sessions de renouvellement actives.

## 2.1 État de l'implémentation initiale — 2026-11-25

- Routeur `/admin/users` ajouté et inclus dans l'API v1.
- Permission RBAC dédiée `users:manage`, réservée au rôle `admin`.
- Dépendance d'authentification existante appliquée à chaque route : compte actif, rôle cohérent, MFA obligatoire pour le rôle admin et contrôle `auth_version`.
- Routes implémentées : liste paginée, détail, modification du nom/département/rôle/activation, reset MFA et révocation des sessions.
- Les mutations ajoutent un événement à l'audit outbox dans la même transaction que les changements métier et la révocation des refresh sessions.
- Les opérations de réduction du nombre d'administrateurs MFA actifs verrouillent les lignes concernées et refusent la perte du dernier administrateur MFA actif.\n- Les trois routes de mutation revalident également le rôle, l'activation, le MFA et la version de sécurité de l'acteur après acquisition des verrous, afin d'éviter qu'une requête autorisée avant une rétrogradation concurrente conserve ses privilèges (TOCTOU).
- Les réponses n'exposent ni hash de mot de passe, ni secret MFA, ni hash de codes de secours. Les champs de sécurité internes ne sont pas modifiables via le schéma d'entrée.
- Tests unitaires du contrat RBAC, des champs autorisés et de minimisation de réponse ajoutés dans `backend/tests/test_admin_user_lifecycle.py`.
- **Validation CI observée :** run 45586284593 entièrement vert sur le HEAD 91ec0cc ; tests PostgreSQL couvrant rétrogradations concurrentes, refus d'un acteur obsolète, révocation de refresh sessions, rejet d'un ancien access token et rollback d'audit. Les combinaisons de mutations restantes et la revue humaine demeurent à vérifier.
- La création/provisionnement de comptes reste volontairement hors périmètre de cette première tranche.

## 3. API cible proposée

Préfixe : `/admin/users`. Toutes les routes doivent exiger un compte actif de rôle `admin` et MFA actif, en plus d'une permission dédiée `users:manage`. L'autorisation est contrôlée côté serveur, jamais par le frontend seul.

| Route | Action | Règles |
|---|---|---|
| GET `/` | Liste paginée | Ne jamais exposer les hashes, secrets MFA ou codes de secours |
| GET `/{user_id}` | Détail | Même minimisation des champs sensibles |
| PATCH `/{user_id}` | Modifier nom, département, rôle, activation | Validation stricte, audit atomique, révocation des sessions si changement sensible |
| POST `/{user_id}/mfa/reset` | Réinitialiser MFA | Effacer secret et codes de secours, désactiver MFA, incrémenter auth_version, révoquer refresh sessions |
| POST `/{user_id}/sessions/revoke` | Révoquer les sessions | Révoquer toutes les sessions actives et incrémenter auth_version |

La création initiale d'un compte reste un flux séparé à définir (invitation contrôlée ou provisioning). Aucun mot de passe temporaire ne doit être retourné en clair par une API d'administration.

## 4. Invariants transactionnels obligatoires

1. Verrouiller la ligne utilisateur cible avec `SELECT ... FOR UPDATE`.
2. Vérifier l'identité de l'administrateur, son rôle, son MFA et ses permissions.
3. Interdire à un administrateur de désactiver son propre compte ou de supprimer ses propres privilèges.
4. Empêcher la désactivation ou rétrogradation du dernier administrateur actif avec MFA.
5. Toute mutation sensible, la révocation des refresh sessions et l'événement `enqueue_audit_event` doivent appartenir à la même transaction.
6. En cas d'échec d'audit ou de contrainte DB, rollback intégral ; ne jamais conserver une mutation sans son événement d'audit.
7. L'événement d'audit doit identifier l'acteur, la cible, l'action et les champs modifiés sans journaliser de secret.
8. L'API ne doit jamais accepter `auth_version`, `password_hash`, `mfa_secret` ou `backup_codes_hashed` depuis les payloads client.
9. Protéger les opérations concurrentes de dernier administrateur par verrouillage cohérent des administrateurs actifs et tests PostgreSQL de concurrence.

## 5. Tests d'acceptation

- Un utilisateur non-admin, un admin sans MFA et un compte désactivé reçoivent un refus.
- Les rôles inconnus et champs sensibles injectés sont rejetés.
- Un changement de rôle/désactivation/reset MFA incrémente `auth_version` et invalide les access tokens et refresh sessions.
- Une révocation de session seule invalide également les access tokens.
- L'échec de `enqueue_audit_event` annule la mutation et la révocation.
- Deux demandes concurrentes ne peuvent pas désactiver/rétrograder simultanément les deux derniers administrateurs actifs.
- Un administrateur ne peut pas se retirer lui-même le dernier accès administrateur.
- Les réponses n'exposent jamais les hashes de mot de passe, secret MFA ou hashes des codes de secours.
- Tests API unitaires et intégration PostgreSQL couvrant les scénarios positifs, refus, rollback et concurrence.

## 6. Critères de clôture

La première tranche est implémentée et possède des preuves CI/PostgreSQL sur le HEAD indiqué. Ce document ne constitue pas une preuve de préparation à la production ; la revue humaine, les contrôles opérationnels et les tests complémentaires restent requis.
