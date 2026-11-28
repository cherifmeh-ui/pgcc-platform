# Phase 0 — Runbook de sauvegarde et de restauration PostgreSQL

**Statut :** procédure proposée à faire approuver et à exécuter sur l'environnement cible.  
**Portée :** PostgreSQL du déploiement Docker Compose de PGCC.  
**Attention :** ce document ne constitue pas une preuve qu'une sauvegarde CTF/préproduction a été réalisée.

## 1. Objectifs et prérequis

Avant toute mise en exploitation, le propriétaire du service et le RSSI doivent approuver et renseigner :

- RPO cible : `[à approuver]`.
- RTO cible : `[à approuver]`.
- Fréquence des sauvegardes et durée de rétention : `[à approuver]`.
- Emplacement hors hôte / hors domaine d'administration : `[à renseigner]`.
- Responsable d'exécution, responsable de contrôle et astreinte : `[à renseigner]`.
- Détenteur de la clé privée de déchiffrement, procédure d'accès d'urgence et preuve de test de récupération de clé : `[à renseigner]`.

Prérequis techniques sur l'hôte d'exploitation :

- Docker Compose opérationnel et accès autorisé au projet PGCC.
- Outils `age`, `sha256sum`, `stat` et `date`.
- Un destinataire age public approuvé (`AGE_RECIPIENT`) pour le chiffrement ; la clé privée correspondante est conservée séparément, avec contrôle d'accès et procédure de secours.
- Stockage de sauvegarde chiffré, distant, à accès restreint, avec versioning/immutabilité si disponible.
- Horloge synchronisée et journalisation de l'opération.

Ne jamais committer les fichiers de sauvegarde, les clés, les certificats, les secrets ou le fichier `.env.production`.

## 2. Sauvegarde logique chiffrée

Exécuter depuis le répertoire de déploiement contenant `docker-compose.production.yaml` et `.env.production`. Utiliser un compte d'exploitation autorisé. Ne pas activer le traçage shell (`set -x`).

```bash
set -euo pipefail
set +x
umask 077

set -a
. ./.env.production
set +a

: "${POSTGRES_USER:?POSTGRES_USER requis}"
: "${POSTGRES_DB:?POSTGRES_DB requis}"
: "${AGE_RECIPIENT:?AGE_RECIPIENT doit être fourni par le gestionnaire de secrets}"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT
plain="$workdir/pgcc-${stamp}.dump"
roles="$workdir/pgcc-roles-${stamp}.sql"
encrypted="/secure-backup/pgcc-${stamp}.dump.age"
roles_encrypted="/secure-backup/pgcc-roles-${stamp}.sql.age"

docker compose -f docker-compose.production.yaml --env-file .env.production \
  exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom > "$plain"

docker compose -f docker-compose.production.yaml --env-file .env.production \
  exec -T postgres pg_dumpall -U "$POSTGRES_USER" --globals-only > "$roles"

test -s "$plain"
test -s "$roles"
age -r "$AGE_RECIPIENT" -o "$encrypted" "$plain"
age -r "$AGE_RECIPIENT" -o "$roles_encrypted" "$roles"

sha256sum "$encrypted" "$roles_encrypted" > "${encrypted}.sha256"
stat --printf='database_dump_bytes=%s\n' "$encrypted"
stat --printf='roles_dump_bytes=%s\n' "$roles_encrypted"
date -u +'%Y-%m-%dT%H:%M:%SZ'
```

Remplacer `/secure-backup` par le chemin d'un stockage distant approuvé, monté avec des droits restrictifs. Le répertoire temporaire doit être sur un volume chiffré et suffisamment protégé ; le nettoyage du répertoire temporaire ne remplace pas les contrôles de stockage sécurisé. Transférer les fichiers chiffrés et leur manifeste vers le dépôt distant, puis vérifier leur présence, leur taille et leur empreinte après transfert. Ne pas conserver le dump en clair au-delà de l'opération.

Le dump de base et le dump des rôles sont deux artefacts distincts. Les rôles et privilèges doivent être restaurés uniquement après validation de leur contenu et de leur compatibilité avec l'environnement cible.

## 3. Contrôles de sauvegarde

Pour chaque exécution, enregistrer dans le registre d'exploitation :

- identifiant d'exécution, date UTC, opérateur et approbateur ;
- environnement et version PGCC / version PostgreSQL ;
- nom logique, taille et empreinte SHA-256 des artefacts chiffrés ;
- destination distante, statut du transfert et politique de rétention appliquée ;
- identifiant/version de clé de chiffrement (jamais la clé elle-même) ;
- résultat de la vérification de déchiffrement dans un environnement isolé ;
- anomalies, durée et actions correctives.

Une sauvegarde n'est pas considérée valide sur la seule base du code de retour de `pg_dump`. Il faut vérifier l'intégrité de l'artefact transféré et réaliser des restaurations périodiques.

## 4. Restauration contrôlée dans un environnement isolé

La restauration doit être autorisée par le propriétaire du service. Ne jamais restaurer directement sur la base de production pour un exercice. Préparer une instance PostgreSQL isolée, avec accès réseau restreint, puis :

1. Vérifier l'empreinte SHA-256 des artefacts reçus.
2. Déchiffrer avec la clé privée autorisée, sans exposer le contenu dans les logs.
3. Inspecter le dump avec `pg_restore --list`.
4. Créer une base vide dédiée au test et restaurer le dump.
5. Restaurer les rôles uniquement après revue et adaptation des privilèges à l'environnement de test.
6. Vérifier les migrations Alembic, les tables essentielles, les volumes de données attendus et les contraintes.
7. Démarrer une instance applicative isolée et réaliser des tests de santé et de parcours métier en lecture/écriture contrôlée.
8. Mesurer le RTO réel, comparer le point de restauration au RPO, consigner les écarts.
9. Détruire l'environnement de test et les fichiers temporaires selon la procédure approuvée.

Exemple de restauration logique (après déchiffrement et vérification, avec variables de connexion de l'instance de test) :

```bash
set -euo pipefail
set +x
umask 077

: "${RESTORE_DATABASE_NAME:?Nom de la base isolée requis}"
: "${RESTORE_DATABASE_URL:?DATABASE_URL pointant vers la base isolée restaurée requis}"
: "${PGHOST:?Hôte PostgreSQL de test requis}"
: "${PGPORT:?Port PostgreSQL de test requis}"
: "${PGUSER:?Compte PostgreSQL de test requis}"

# Authentification par .pgpass temporaire mode 0600 ou secret manager ;
# ne pas placer le mot de passe dans les arguments de processus.
pg_restore --list /secure-restore/pgcc.dump >/dev/null
createdb --maintenance-db=postgres "$RESTORE_DATABASE_NAME"
pg_restore --exit-on-error --no-owner --no-privileges \
  --dbname="$RESTORE_DATABASE_NAME" /secure-restore/pgcc.dump

DATABASE_URL="$RESTORE_DATABASE_URL" alembic -c backend/alembic.ini upgrade head
DATABASE_URL="$RESTORE_DATABASE_URL" alembic -c backend/alembic.ini check
```

L'exemple suppose que RESTORE_DATABASE_URL est injectée par le gestionnaire de secrets dans l'environnement du processus et cible précisément la base isolée créée. Les commandes libpq utilisent PGHOST/PGPORT/PGUSER et un fichier `.pgpass` temporaire protégé (mode 0600), ou le mécanisme de secret manager approuvé. Ne pas placer de mot de passe dans les arguments de processus ou l'historique shell. Vérifier explicitement que PGHOST/RESTORE_DATABASE_URL pointent vers l'instance de test et non la production.

Les options `--no-owner --no-privileges` sont adaptées à une restauration de test sans reproduction des propriétaires/grants. Pour une reprise opérationnelle réelle, établir et valider séparément la stratégie de restauration des rôles, propriétaires, privilèges, extensions et paramètres PostgreSQL.

## 5. RPO, WAL et restauration à un instant donné

Le Compose de production versionné utilise un volume persistant `pgdata`, mais cette seule persistance n'est pas une sauvegarde. La configuration versionnée ne démontre pas la mise en place d'un archivage continu WAL, d'un dépôt WAL distant, ni d'une restauration PITR. En conséquence :

- ne pas annoncer de capacité de restauration à un instant donné ;
- ne pas considérer les dumps périodiques comme couvrant les transactions postérieures au dernier dump ;
- faire concevoir et approuver une stratégie WAL/PITR distincte si le RPO exigé le nécessite ;
- tester la restauration complète et, si retenue, la récupération à un instant précis sur un environnement isolé.

## 6. Critères de réussite d'un exercice

Un exercice est accepté uniquement si tous les points suivants sont documentés :

- [ ] artefacts chiffrés transférés hors hôte et empreintes vérifiées ;
- [ ] clé de récupération disponible via la procédure de secours approuvée ;
- [ ] restauration complète sur instance isolée sans erreur ;
- [ ] version Alembic attendue et contrôle `alembic check` cohérents ;
- [ ] contrôles applicatifs et échantillons métier validés par le propriétaire ;
- [ ] durée de restauration mesurée et RTO comparé à la cible ;
- [ ] perte de données mesurée et RPO comparé à la cible ;
- [ ] accès, logs, rétention et destruction de l'environnement de test vérifiés ;
- [ ] rapport d'exercice signé par l'exécutant, le vérificateur et le propriétaire du service.

## 7. État de preuve Phase 0

- La CI exécute un `pg_dump` au format custom, restaure dans une base PostgreSQL fraîche et vérifie la version Alembic ainsi qu'une donnée témoin.
- Cette CI est une preuve automatisée sur une base éphémère, non chiffrée, au sein du runner GitHub Actions.
- Elle ne prouve ni le chiffrement avec la clé d'exploitation, ni le transfert hors site, ni la restauration d'une sauvegarde CTF/préproduction, ni le RPO/RTO réel.
- La configuration Compose actuelle ne démontre pas l'archivage WAL/PITR.
- **Gate encore ouvert :** exercice opérationnel sur sauvegarde chiffrée de l'environnement cible, validation de la procédure de récupération des clés et approbation formelle du RPO/RTO.

