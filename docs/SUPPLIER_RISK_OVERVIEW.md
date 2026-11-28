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


## Historisation mensuelle

La migration `0019_supplier_risk_snapshots` crée une table d'instantanés immuables, avec une contrainte d'unicité sur le premier jour du mois.

- `POST /api/v1/suppliers/overview/snapshots/capture` : capture l'état courant une fois par mois; permission `suppliers:manage_risks` (RSSI / administrateur).
- `GET /api/v1/suppliers/overview/snapshots?limit=24` : restitue les instantanés historiques; permissions `suppliers:read` et `risks:read`.
- Une seconde capture du même mois est refusée avec HTTP 409; les instantanés ne sont pas écrasés.
- Chaque enregistrement conserve les indicateurs JSON calculés, la date du mois, l'utilisateur ayant capturé et l'horodatage.
- Cette historisation est déclenchée explicitement par un utilisateur autorisé; elle ne prétend pas être une tâche planifiée automatique.


## Comparaison mensuelle et détection des évolutions

**Endpoint :** `GET /api/v1/suppliers/overview/trends?limit=12`

- Compare les deux derniers instantanés mensuels disponibles, quel que soit leur espacement.
- Les indicateurs à sens défavorable explicite sont classés en amélioration, stabilité ou dégradation : fournisseurs critiques sans évaluation à jour, évaluations en retard, revues d'accès en retard et contrats avec clauses SSI manquantes.
- Les échéances contractuelles, les accès privilégiés actifs et le nombre de risques liés sont affichés comme variations à analyser. Leur hausse n'est pas automatiquement assimilée à une dégradation.
- Si l'historique ou une valeur manque, la comparaison affiche des données insuffisantes plutôt que de fabriquer un delta.
- La comparaison ne calcule aucun score fournisseur et n'entraîne aucune modification automatique du registre central des risques.

## Concentration des risques fournisseurs

**Endpoint :** `GET /api/v1/suppliers/overview/concentration?limit=10`

- Classe les fournisseurs actifs selon le niveau maximal des risques centraux qui leur sont associés, le nombre de risques distincts liés et le nombre d'autorisations privilégiées actives.
- Présente la répartition des risques liés par niveau, sans recalculer les niveaux.
- Un même risque lié plusieurs fois au même fournisseur n'est compté qu'une fois.
- Les autorisations prises en compte sont approuvées et couvrent la date courante.
- Ce classement est un outil de priorisation RSSI : il ne constitue pas une note globale de risque du fournisseur ni une décision automatique.
- Permissions : `suppliers:read` et `risks:read`.


## Pilotage RSSI / Direction Générale et rapport PDF

- Le tableau de bord stratégique consomme les indicateurs consolidés TPRM, les tendances mensuelles et le classement des fournisseurs concentrant les risques.
- Les rôles RSSI/administrateur et Direction Générale accèdent à cette vue selon les permissions serveur `suppliers:read` et `risks:read`.
- Le bouton **Exporter le rapport PDF** ouvre la fonction d'impression du navigateur, avec une feuille de style dédiée qui isole la synthèse TPRM. L'utilisateur peut choisir « Enregistrer au format PDF » dans la boîte de dialogue d'impression.
- Il s'agit d'une génération côté navigateur via impression, et non d'un fichier PDF produit par le serveur. Aucun service ou paquet PDF supplémentaire n'est requis.
