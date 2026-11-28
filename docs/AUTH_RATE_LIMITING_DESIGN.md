# Limitation distribuée des tentatives d'authentification

Date : 2026-11-25  
Branche : `chore/phase0-stabilization`  
Statut : première implémentation PostgreSQL ajoutée ; validation CI et revue opérationnelle requises.

## Décision d'architecture

La plateforme utilise déjà PostgreSQL comme dépendance obligatoire et ne déploie pas Redis dans son profil Compose. La première version s'appuie donc sur des compteurs atomiques PostgreSQL (`INSERT ... ON CONFLICT DO UPDATE`) plutôt que d'introduire un service Redis supplémentaire.

Les lignes sont partagées par toutes les répliques backend qui utilisent la même base. L'incrément est atomique et sérialisé par la clé primaire du bucket. Si le stockage du limiteur est indisponible, les routes protégées échouent en mode fermé avec HTTP 503 ; aucune tentative n'est autorisée en contournement.

## Identifiants et confidentialité

- Deux dimensions sont suivies : adresse IP source et identifiant de compte normalisé.
- Les clés persistées sont des HMAC-SHA256 ; les adresses IP et emails bruts ne sont jamais stockés dans la table.
- En développement, une clé déterministe est dérivée du secret JWT uniquement pour faciliter le démarrage local.
- En staging/production, `AUTH_RATE_LIMIT_HMAC_KEY` est obligatoire, distincte du secret JWT et d'au moins 32 caractères.
- Sans proxy déclaré, l'adresse source provient exclusivement de `request.client.host` et tout `X-Forwarded-For` est ignoré.
- `AUTH_TRUSTED_PROXY_IPS` accepte une liste explicite d'adresses/CIDR. Le header transféré n'est lu que si le pair TCP immédiat appartient à cette liste ; la chaîne est parcourue de droite à gauche pour retenir le premier saut non approuvé. Un header mal formé est ignoré au profit du pair immédiat.
- En production derrière un reverse proxy, renseigner précisément ses IP/CIDR et configurer le proxy pour écraser ou compléter correctement la chaîne XFF. Ne jamais ajouter des plages publiques ou trop larges par facilité.
- Les buckets inactifs depuis 48 heures sont supprimés par un worker périodique.

## Politique initiale

Les limites sont des seuils de requêtes par fenêtre. Le nombre indiqué est autorisé ; la requête suivante déclenche HTTP 429 et un en-tête `Retry-After`.

| Opération | IP source | Compte | Fenêtre | Blocage |
|---|---:|---:|---:|---:|
| Connexion | 20 | 20 | 15 min | 15 min |
| Confirmation MFA | 30 | 10 | 15 min | 15 min |
| Démarrage enrôlement MFA | 10 | 5 | 15 min | 15 min |
| Changement obligatoire du mot de passe | 5 | 5 | 15 min | 15 min |
| Renouvellement refresh | 120 | 30 | 15 min | 5 min |

Ces seuils sont des valeurs initiales conservatrices, à surveiller et ajuster à partir des métriques et des usages réels. Le verrouillage de compte existant reste actif en complément ; le limiteur distribué ne le remplace pas.

## Routes protégées

- `POST /auth/login` : IP et email fournis.
- `POST /auth/start-enrollment` : IP avant décodage du pré-auth, puis compte après extraction du sujet.
- `POST /auth/confirm-mfa` : IP avant décodage, puis compte.
- `POST /auth/change-password` : IP avant vérification, puis compte après décodage du jeton.
- `POST /auth/refresh` : IP après contrôle Origin, puis compte après décodage du refresh cookie.
- Logout n'est pas limité dans cette tranche afin de ne pas empêcher la révocation d'une session compromise.

Le compteur est validé et commité avant la logique métier. Ainsi, une réponse 429 ou un rollback ultérieur ne supprime pas l'état du limiteur. Le compteur IP est vérifié en premier ; lorsqu'il bloque, le compteur compte n'est pas incrémenté inutilement.

## Validation attendue

- Tests unitaires : politiques, HMAC non réversible, absence de données personnelles en clair et échec fermé en cas d'indisponibilité DB.
- Tests PostgreSQL concurrents : appels simultanés depuis plusieurs sessions, exactement le nombre de requêtes autorisées, puis HTTP 429 et `Retry-After`.
- Migration `0026_auth_rate_limit_buckets` : table, clé primaire, contrainte non négative et index de rétention.
- CI backend, PostgreSQL, frontend et Compose entièrement verte sur le HEAD final.
- Revue humaine des seuils, de l'observabilité et de la politique proxy avant production.

Cette implémentation n'est pas considérée validée tant que les tests PostgreSQL et l'ensemble de la CI ne sont pas verts.


## Résultat CI — 2026-11-25

- Workflow `45586284593` : quatre jobs réussis sur le HEAD `91ec0cc` (backend 376 réussites/26 ignorés, PostgreSQL 26 réussites, frontend et Compose réussis).
- Backend : 375 tests réussis / 24 ignorés.
- PostgreSQL : 24 tests réussis, dont les deux scénarios de concurrence du limiteur.
- Frontend build et smoke test Docker Compose (health API + proxy frontend) réussis.
- La migration `0026_auth_rate_limit_buckets` a été appliquée avec succès sur PostgreSQL.
- Cette preuve valide l'implémentation sur le HEAD indiqué ; l'exploitation en production et le calibrage des seuils restent à valider.
