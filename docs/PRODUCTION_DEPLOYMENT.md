# Déploiement de production — profil Docker Compose

## Périmètre

Le fichier docker-compose.production.yaml est distinct du stack de développement. Il fournit :

- PostgreSQL sans port publié sur l'hôte, sur un réseau interne dédié.
- Backend FastAPI sans port publié, sans montage du code source, en lecture seule avec /tmp borné, utilisateur non privilégié, capacités supprimées et limites CPU/mémoire/PID.
- Parseur PDF/DOCX isolé sur son propre réseau interne, sans accès à PostgreSQL, ClamAV ou au réseau public.
- ClamAV sur un réseau interne partagé uniquement avec le backend, plus un réseau de sortie réservé aux mises à jour de signatures.
- Frontend Vue compilé et servi par Nginx non privilégié, avec terminaison TLS, redirection HTTP vers HTTPS et proxy API same-origin.
- Aucun port PostgreSQL, parser, ClamAV ou backend publié ; seuls les ports HTTP/HTTPS du frontend sont exposés.

Le backend fait confiance uniquement à l'adresse statique du proxy Nginx (172.31.10.10/32). Nginx remplace X-Forwarded-For par l'adresse source observée et ne relaie pas une valeur fournie arbitrairement par le client.

## Préparation des secrets

1. Copier .env.production.example vers .env.production.
2. Remplacer toutes les valeurs CHANGE_ME par des secrets générés indépendamment.
3. Générer une clé JWT d'au moins 32 caractères, une clé Fernet valide pour MFA_ENCRYPTION_KEYS, une clé HMAC dédiée pour AUTH_RATE_LIMIT_HMAC_KEY et un secret aléatoire d'au moins 32 caractères pour PARSER_SHARED_TOKEN.
4. Utiliser un mot de passe PostgreSQL URL-encodé dans DATABASE_URL ; le mot de passe doit correspondre à POSTGRES_PASSWORD.
5. Définir CORS_ORIGINS avec l'origine HTTPS exacte, sans joker.
6. Conserver .env.production hors Git et limiter ses permissions au compte de déploiement.
7. Installer le certificat TLS et la clé privée dans certs/fullchain.pem et certs/privkey.pem. Le dossier certs est monté en lecture seule dans le frontend. L'image nginx-unprivileged exécute Nginx avec l'UID/GID 101 : rendre la chaîne publique lisible et la clé privée accessible uniquement au groupe 101.

Ne pas utiliser les valeurs d'exemple. Le backend refuse les placeholders et les paramètres de sécurité incomplets en environnement de production.

Pour les permissions des certificats, exécuter en tant que root (adapter le chemin si nécessaire) :

```bash
chown root:101 certs/privkey.pem
chmod 640 certs/privkey.pem
chmod 644 certs/fullchain.pem
```

Ne pas rendre la clé privée lisible par tous (`0644`). Le contrôle CI valide Nginx avec une clé `root:101` en `0640`.

## Déploiement initial

Depuis la racine du dépôt :

```bash
cp .env.production.example .env.production
# Éditer .env.production et installer les certificats TLS dans ./certs/

docker compose --env-file .env.production -f docker-compose.production.yaml config --quiet

# Construire les images et démarrer les dépendances nécessaires à la migration
docker compose --env-file .env.production -f docker-compose.production.yaml build

docker compose --env-file .env.production -f docker-compose.production.yaml run --rm backend alembic upgrade head

docker compose --env-file .env.production -f docker-compose.production.yaml up -d

docker compose --env-file .env.production -f docker-compose.production.yaml ps
```

Les migrations doivent être exécutées explicitement avant la mise à disposition de l'application. L'image backend contient alembic.ini et le répertoire migrations.

## Vérifications après démarrage

- Vérifier que seuls les ports 80 et 443 du frontend sont publiés.
- Vérifier que PostgreSQL, le backend, ClamAV et le parseur ne possèdent aucun port hôte publié.
- Vérifier que le backend est uniquement sur les réseaux applicatifs nécessaires.
- Vérifier que le parseur n'est présent que sur parser_internal.
- Vérifier que le frontend redirige HTTP vers HTTPS et que les cookies de renouvellement sont Secure, HttpOnly et SameSite=Strict.
- Tester une requête API non authentifiée, un dépôt documentaire sain et un dépôt EICAR dans un environnement de recette.
- Vérifier les journaux, les alertes, les mises à jour ClamAV et la rotation des secrets.

## Limites et conditions de mise en production

Ce profil est une base de déploiement durcie, pas une homologation automatique. La CI valide la syntaxe Compose et construit l'image frontend ; elle ne remplace pas un déploiement de recette avec certificats réels, vérification réseau effective, test de charge, sauvegarde chiffrée, restauration/WAL et mesure RPO/RTO.

Avant exposition publique, faire valider par l'équipe d'exploitation :
- l'origine et la chaîne de confiance des certificats TLS ;
- les règles pare-feu, DNS, ports entrants et mises à jour des images ;
- la supervision centralisée, les alertes de sécurité et les seuils de limitation d'authentification ;
- la stratégie de sauvegarde chiffrée, la rétention WAL et la procédure de restauration ;
- les capacités CPU/mémoire selon la charge réelle ;
- la revue de sécurité humaine et l'acceptation formelle des risques résiduels.
