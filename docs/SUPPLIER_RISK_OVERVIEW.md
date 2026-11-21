# Analyse consolidée des risques fournisseurs

**Endpoint :** `GET /api/v1/suppliers/overview/risk`  
**Architecture :** monolithe modulaire FastAPI / PostgreSQL.  
**Principe :** cette synthèse agrège les données du registre fournisseurs, des risques, des évaluations, des autorisations et des contrats. Elle ne modifie jamais les scores ni les décisions du registre central des risques.

## Indicateurs exposés

- Fournisseurs actifs et fournisseurs de criticité élevée ou critique.
- Fournisseurs critiques/élevés sans évaluation validée encore valable.
- Nombre d'évaluations validées et revues échues.
- Nombre de risques distincts liés à des fournisseurs, répartis par score et statut.
- Autorisations fournisseurs actuellement approuvées et dans leur période de validité.
- Accès privilégiés actifs et revues d'accès en retard.
- Contrats actifs ou à renouveler arrivant à échéance dans les 90 jours.

## Règles de calcul

- Les fournisseurs archivés sont exclus.
- Les risques sont dédupliqués par identifiant de risque : un risque lié à plusieurs fournisseurs ne gonfle pas le nombre de risques distincts.
- Seules les évaluations au statut `Validée` sont considérées comme évaluations valides; une échéance absente ou dépassée ne vaut pas conformité.
- Seules les autorisations au statut `Approuvé` et dont la période couvre la date du calcul sont comptées comme actives.
- Les contrats ne sont considérés comme échéant que s'ils sont au statut `Actif` ou `À renouveler` et leur date de fin se situe dans les 90 prochains jours.
- Les niveaux de risques sont dérivés du score existant (1–4 faible, 5–9 modéré, 10–14 élevé, 15–19 critique, 20–25 inacceptable); aucune cotation n'est recalculée.

## Sécurité

- L'accès exige `suppliers:read` et `risks:read`.
- L'endpoint ne retourne pas les noms des fournisseurs, les références de contrats, les identifiants de comptes tiers, les coordonnées de contacts ou les détails individuels des risques.
- Les données sont agrégées côté serveur.
- Les contrôles de permissions restent appliqués côté API; masquer un widget frontend ne constitue pas un contrôle d'accès.

## Limites et prochaines étapes

Cette première version est un instantané calculé à la demande, non un moteur d'alertes planifiées. Les dates sont évaluées selon la date locale du serveur applicatif; le déploiement devra fixer explicitement le fuseau métier de référence. Une prochaine tranche pourra ajouter un tableau de bord, les filtres organisationnels, les seuils configurables et des tests d'intégration PostgreSQL.
