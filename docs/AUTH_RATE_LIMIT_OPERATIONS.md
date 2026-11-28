# Exploitation — limitation des tentatives d'authentification

## Politique appliquée

Les limites sont partagées entre toutes les répliques backend via des compteurs atomiques PostgreSQL. Les identifiants de compte et les adresses IP sont transformés par HMAC avant persistance ; les valeurs brutes ne sont pas stockées dans la table des compteurs.

| Parcours | Seuil IP | Seuil compte | Fenêtre | Blocage |
|---|---:|---:|---:|---:|
| Connexion | 20 | 20 | 15 min | 15 min |
| Confirmation MFA | 30 | 10 | 15 min | 15 min |
| Enrôlement MFA | 10 | 5 | 15 min | 15 min |
| Changement de mot de passe | 5 | 5 | 15 min | 15 min |
| Renouvellement de session | 120 | 30 | 15 min | 5 min |

Les compteurs inactifs sont supprimés après 48 heures. Le nettoyage est exécuté par le worker applicatif.

## Adresse IP et reverse proxy

- AUTH_TRUSTED_PROXY_IPS doit contenir uniquement les adresses ou CIDR des proxys réellement administrés.
- X-Forwarded-For est ignoré si le pair TCP immédiat n'appartient pas à cette liste.
- Si le pair est approuvé, la chaîne est parcourue de droite à gauche pour retenir le premier saut non approuvé.
- Une chaîne malformée ou entièrement constituée de proxys approuvés retombe sur l'adresse du pair immédiat.
- En production, le proxy doit écraser X-Forwarded-For avec l'adresse client qu'il a lui-même observée. Ne jamais approuver un réseau client large ou non maîtrisé.

## Réponses et dégradation

- Seuil dépassé : HTTP 429 avec Retry-After en secondes.
- PostgreSQL ou persistance des compteurs indisponible : HTTP 503, sans autoriser le parcours protégé (refus fermé).
- Les événements de dépassement sont journalisés avec les champs structurés security_event=auth_rate_limit_exceeded, auth_action, bucket_scope et retry_after_seconds. Aucun identifiant de compte, adresse IP ou clé HMAC n'est ajouté à cet événement.
- Le nettoyage journalise les volumes supprimés ; les erreurs de nettoyage sont consignées sans interrompre le service.

## Exploitation et critères avant production

1. Vérifier la topologie réelle du proxy et renseigner les adresses exactes dans AUTH_TRUSTED_PROXY_IPS.
2. Agréger les événements auth_rate_limit_exceeded dans la supervision centralisée et créer des alertes par parcours et portée (IP/compte).
3. Définir les tableaux de bord et indicateurs à partir des journaux : nombre de blocages, distribution par parcours/portée, taux HTTP 429/503, erreurs PostgreSQL du limiteur et âge du dernier nettoyage.
4. Mesurer le trafic réel puis ajuster les seuils avec une procédure de changement approuvée ; les valeurs du tableau sont des valeurs initiales, pas une calibration de production.
5. Tester l'impact sur les utilisateurs légitimes, les NAT partagés, les VPN et les opérations de support avant mise en service.

## État de validation

Les tests unitaires vérifient le refus fermé, la confiance limitée aux proxys explicitement configurés, le comportement de Retry-After et l'événement structuré sans donnée personnelle. Les tests PostgreSQL vérifient l'atomicité entre sessions concurrentes et la portée partagée entre plusieurs adresses IP.

Aucun exporteur Prometheus/OpenTelemetry n'est actuellement intégré au backend. Les journaux structurés permettent une agrégation externe, mais la connexion à la plateforme de supervision, les alertes, le choix définitif des seuils et la validation de la topologie proxy restent des tâches opérationnelles obligatoires.
