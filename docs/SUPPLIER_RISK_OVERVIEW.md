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
- Contrats actifs ou à renouveler présentant au moins une clause SSI essentielle manquante parmi les huit clauses suivies (confidentialité, notification d’incident, droit d’audit, continuité, réversibilité, localisation, sous-traitance, restitution/destruction).

## Règles de calcul

- Les fournisseurs archivés ou au statut `Terminé` sont exclus.
- Les risques sont dédupliqués par identifiant de risque : un risque lié à plusieurs fournisseurs ne gonfle pas le nombre de risques distincts.
- Seules les évaluations au statut `Validée` sont considérées comme évaluations valides; une échéance absente ou dépassée ne vaut pas conformité.
- Seules les autorisations au statut `Approuvé` et dont la période couvre la date du calcul sont comptées comme actives.
- Les contrats ne sont considérés comme échéant que s'ils sont au statut `Actif` ou `À renouveler` et leur date de fin se situe dans les 90 prochains jours.
- Les niveaux de risques sont dérivés du score existant (1–4 faible, 5–9 modéré, 10–14 élevé, 15–19 critique, 20–25 inacceptable); aucune cotation n'est recalculée.
- Les lacunes contractuelles sont calculées sur les contrats `Actif` ou `À renouveler`; un contrat est signalé dès qu’une des huit clauses SSI suivies est absente.

## Sécurité

- L'accès exige `suppliers:read` et `risks:read`.
- L'endpoint ne retourne pas les noms des fournisseurs, les références de contrats, les identifiants de comptes tiers, les coordonnées de contacts ou les détails individuels des risques.
- Les données sont agrégées côté serveur.
- Les contrôles de permissions restent appliqués côté API; masquer un widget frontend ne constitue pas un contrôle d'accès.

## Limites et prochaines étapes

La synthèse est un instantané calculé à la demande. Les dates utilisent la date du serveur applicatif; le fuseau métier devra être fixé explicitement au déploiement. Les dépendances fournisseurs sont également intégrées à l'analyse d'impact des actifs, sous réserve de la permission `suppliers:read_assets`.
