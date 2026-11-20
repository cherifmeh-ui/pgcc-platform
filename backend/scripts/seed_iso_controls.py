# backend/scripts/seed_iso_controls.py
import sys
import os
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.core.config import settings
from app.models.iso_control import IsoControl

# LISTE COMPLÈTE DES 93 CONTRÔLES ISO 27002:2022
# Répartis en 4 Domaines Officiels : Organisationnels, Personnes, Physique, Technologique
SEED_DATA = [
    # --- A.5 ORGANISATIONNELS (37 Contrôles) ---
    ("A.5.1", "Politiques de sécurité de l'information", "Définir et revoir périodiquement les politiques.", "Organisationnels"),
    ("A.5.2", "Rôles et responsabilités de la sécurité de l'information", "Attribuer les rôles SI aux managers et employés.", "Organisationnels"),
    ("A.5.3", "Séparation des tâches", "Diviser les tâches incompatibles pour réduire les risques de fraude ou d'erreur.", "Organisationnels"),
    ("A.5.4", "Responsabilités des autorités déléguées", "Gérer les accès tiers via contrats et délégations formelles.", "Organisationnels"),
    ("A.5.5", "Contact avec les autorités", "Établir des contacts prioritaires avec les autorités légales/réglementaires.", "Organisationnels"),
    ("A.5.6", "Contact avec des groupes spéciaux", "Contacter des experts en sécurité informatique spécialisés.", "Organisationnels"),
    ("A.5.7", "Veille sur les menaces et vulnérabilités", "Surveiller activement les sources d'information relatives aux menaces.", "Organisationnels"),
    ("A.5.8", "Exigences de sécurité de l'information dans les processus de gestion des actifs", "Identifier et protéger les actifs critiques dès leur acquisition.", "Organisationnels"),
    ("A.5.9", "Inventaire des actifs", "Développer et maintenir un inventaire complet des actifs informationnels.", "Organisationnels"),
    ("A.5.10", "Utilisation acceptable des actifs", "Définir des règles d'utilisation acceptable pour tous les actifs.", "Organisationnels"),
    ("A.5.11", "Retour des actifs", "Procéder au retour sécurisé des actifs lors du départ d'un employé ou changement de rôle.", "Organisationnels"),
    ("A.5.12", "Classification des informations", "Classer les informations selon leur niveau de sensibilité (Publique, Interne, Confidentielle).", "Organisationnels"),
    ("A.5.13", "Étiquetage des informations", "Appliquer des étiquettes visibles aux documents/informations classifiées.", "Organisationnels"),
    ("A.5.14", "Transmission des informations", "Définir des procédures et mesures pour la transmission sécurisée des données.", "Organisationnels"),
    ("A.5.15", "Accès à l'information", "Restreindre l'accès aux informations aux seuls utilisateurs autorisés.", "Organisationnels"),
    ("A.5.16", "Gestion des identités", "Gérer le cycle de vie complet des identités numériques (création, modification, suppression).", "Organisationnels"),
    ("A.5.17", "Vérification des droits d'accès", "Revoir régulièrement les droits d'accès attribués aux utilisateurs.", "Organisationnels"),
    ("A.5.18", "Accès privilégiés", "Limiter strictement et surveiller l'accès aux comptes administrateurs/root.", "Organisationnels"),
    ("A.5.19", "Documentations relatives à la sécurité de l'information", "Produire et maintenir une documentation technique et procédurale claire.", "Organisationnels"),
    ("A.5.20", "Mesures correctives suite à une violation de politique", "Mettre en œuvre des actions disciplinaires ou correctrices immédiates.", "Organisationnels"),
    ("A.5.21", "Management de la continuité de l'activité", "Assurer la résilience des opérations critiques face aux perturbations majeures.", "Organisationnels"),
    ("A.5.22", "Planification de la disponibilité des systèmes d'information", "Garantir la capacité à reprendre les activités essentielles rapidement.", "Organisationnels"),
    ("A.5.23", "Cybersécurité de l'organisation", "Intégrer la cybersécurité dans la stratégie globale de l'entreprise.", "Organisationnels"),
    ("A.5.24", "Planification de la gestion des incidents de sécurité de l'information", "Préparer des plans de réponse structurés avant qu'un incident ne survienne.", "Organisationnels"),
    ("A.5.25", "Évaluation et analyse post-incident", "Analyser les causes profondes après chaque événement significatif.", "Organisationnels"),
    ("A.5.26", "Collecte de preuves", "Recueillir et préserver légalement les preuves numériques lors d'enquêtes.", "Organisationnels"),
    ("A.5.27", "Gestion des intérêts parties prenantes", "Identifier et gérer les attentes des parties intéressées externes.", "Organisationnels"),
    ("A.5.28", "Conformité aux exigences légales, statutaires, réglementaires et contractuelles", "Vérifier le respect constant des lois locales/internationales applicables.", "Organisationnels"),
    ("A.5.29", "Conformité aux politiques, normes et pratiques de sécurité de l'information", "Auditer internement la conformité aux standards définis.", "Organisationnels"),
    ("A.5.30", "Préparation des revues d'audit", "Faciliter les audits externes en préparant les éléments probants nécessaires.", "Organisationnels"),
    ("A.5.31", "Signatures électroniques", "Utiliser des mécanismes fiables pour authentifier les transactions digitales.", "Organisationnels"),
    ("A.5.32", "Confidentialité ou accords de non-divulgation", "Faire signer des NDA aux partenaires, fournisseurs et employés sensibles.", "Organisationnels"),
    ("A.5.33", "Protection des dossiers", "Sauvegarder et archiver les registres juridiques importants durablement.", "Organisationnels"),
    ("A.5.34", "Privacy et protection des PII", "Respecter scrupuleusement les règlements RGPD/local sur les données personnelles.", "Organisationnels"),
    ("A.5.35", "Revue indépendante de la sécurité de l'information", "Commander des audits externes périodiques par des tiers certifiés.", "Organisationnels"),
    ("A.5.36", "Conformité aux politiques de sécurité de l'information", "Contrôler techniquement l'adhésion aux règles établies.", "Organisationnels"),
    ("A.5.37", "Documents de procédure opérationnelle", "Standardiser les modes opératoires quotidiens IT/SI.", "Organisationnels"),

    # --- A.6 PERSONNES (8 Contrôles) ---
    ("A.6.1", "Screening", "Effectuer des vérifications préalables d'identité et casier judiciaire avant embauche.", "Personnes"),
    ("A.6.2", "Conditions d'emploi", "Inclure des clauses explicites de responsabilité SI dans les contrats de travail.", "Personnes"),
    ("A.6.3", "Sensibilisation, éducation et formation en sécurité de l'information", "Former continuellement le personnel aux bonnes pratiques cyber.", "Personnes"),
    ("A.6.4", "Discipline procédurale", "Appliquer des sanctions graduées en cas de manquements répétés aux politiques SI.", "Personnes"),
    ("A.6.5", "Responsabilités après cessation ou changement de fonction", "Révoquer immédiatement tous les accès logiques et physiques au départ.", "Personnes"),
    ("A.6.6", "Accords de confidentialité ou de non-divulgation", "Renforcer les obligations légales post-départ concernant les secrets industriels.", "Personnes"),
    ("A.6.7", "Évaluation de la performance", "Intégrer des indicateurs de conformité SI dans les entretiens annuels.", "Personnes"),
    ("A.6.8", "Incitation à signaler les événements de sécurité de l'information", "Encourager culturellement le reporting spontané des failles observées.", "Personnes"),

    # --- A.7 SÉCURITÉ PHYSIQUE (14 Contrôles) ---
    ("A.7.1", "Périmètres physiques de sécurité", "Délimiter clairement les zones protégées (Datacenter, Salles serveurs).", "Physique"),
    ("A.7.2", "Contrôle physique des points d'entrée", "Restreindre l'accès via badges biométriques ou cartes magnétiques actives.", "Physique"),
    ("A.7.3", "Sécurisation des bureaux", "Verrouiller systématiquement les locaux contenant des infos confidentielles.", "Physique"),
    ("A.7.4", "Surveillance de la sécurité physique", "Installer CCTV et rondes humaines dissuasives dans les zones critiques.", "Physique"),
    ("A.7.5", "Protection contre les menaces environnementales", "Anticiper incendies, inondations, tempêtes solaires affectant l'infrastructure.", "Physique"),
    ("A.7.6", "Travaux dans les installations", "Superviser strictement toute intervention extérieure modifiant l'environnement IT.", "Physique"),
    ("A.7.7", "Sécurisation des armoires et équipements", "Ancrer physiquement les racks/servers contre vol ou déplacement malveillant.", "Physique"),
    ("A.7.8", "Marquage des assets", "Étiqueter chaque équipement matériel avec numéro unique traçable.", "Physique"),
    ("A.7.9", "Politique relative aux supports vierges", "Interdire l'introduction de clés USB/disques non homologués dans le périmètre sécurisé.", "Physique"),
    ("A.7.10", "Stockage des supports", "Conserver les archives papier/digitales dans des coffres ignifugés climatisés.", "Physique"),
    ("A.7.11", "Transport des supports", "Chiffrer et escorter obligatoirement tout transfert physique de données sensibles.", "Physique"),
    ("A.7.12", "Stockage des informations", "Isoler géographiquement les copies de sauvegarde distantes (DR Site).", "Physique"),
    ("A.7.13", "Destruction des supports", "Broyer ou démagnétiser définitivement les médias usagés avant mise au rebut.", "Physique"),
    ("A.7.14", "Sûreté des équipements hors site", "Protéger les laptops/téléphones professionnels utilisés hors bureau.", "Physique"),

    # --- A.8 TECHNOLOGIQUES (34 Contrôles) ---
    ("A.8.1", "User endpoint devices", "Gérer centrairement les postes clients (MDM/EPP).", "Technologiques"),
    ("A.8.2", "Privileged access rights", "Audit journalisé exhaustif des actions root/admin sudo.", "Technologiques"),
    ("A.8.3", "Information access restriction", "Implémenter le principe du moindre privilège partout.", "Technologiques"),
    ("A.8.4", "Access to source code", "Protéger les repositories Git contre lecture/write non autorisée.", "Technologiques"),
    ("A.8.5", "Secure authentication", "Déployer MFA/TOTP obligatoire pour tous les accès distants.", "Technologiques"),
    ("A.8.6", "Capacity management", "Alertes proactives CPU/RAM/Disk basées seuils dynamiques.", "Technologiques"),
    ("A.8.7", "Malware", "AV/Antimalware temps réel endpoints + gateways mail/web.", "Technologiques"),
    ("A.8.8", "Management of technical vulnerabilities", "Scans mensuels Nessus/OpenVAS + patching SLA défini.", "Technologiques"),
    ("A.8.9", "Configuration management", "Baselines hardening CIS Benchmarks appliqués uniformément.", "Technologiques"),
    ("A.8.10", "Information deletion", "Effacement cryptographique sécurisé bases/logs expirés.", "Technologiques"),
    ("A.8.11", "Data masking", "Anonymisation automatique rapports BI/statistiques publiques.", "Technologiques"),
    ("A.8.12", "Data leakage prevention", "Filtres DLP réseaux smtp/fileshare/cloud storage.", "Technologiques"),
    ("A.8.13", "Information backup", "Backups incrémentaux chiffrés testés restauration trimestrielle.", "Technologiques"),
    ("A.8.14", "Redundancy of information processing facilities", "Cluster HA Active-Passive/Failover transparent rigs offshore.", "Technologiques"),
    ("A.8.15", "Logging", "Centralisation syslog immutable retention >1 an minimum.", "Technologiques"),
    ("A.8.16", "Monitoring activities", "Dashboards SOC Grafana/Prometheus anomalies detection ML.", "Technologiques"),
    ("A.8.17", "Clock synchronization", "NTP stratum 2 synchronisé globally across sites/timezones.", "Technologiques"),
    ("A.8.18", "Use of privileged utility programs", "Whitelist outils admin diagnostics restricted execution context.", "Technologiques"),
    ("A.8.19", "Installation of software on operational systems", "Change Advisory Board CAB approval mandatory production deploys.", "Technologiques"),
    ("A.8.20", "Networks security", "Segmentation VLAN micro-perimeters zero trust architecture rollout.", "Technologiques"),
    ("A.8.21", "Security of network services", "TLS 1.3 mutual auth certificates rotation automated PKI infra.", "Technologiques"),
    ("A.8.22", "Segregation of networks", "DMZ isolation web/app/db tiers firewall rules granular control.", "Technologiques"),
    ("A.8.23", "Web filtering", "DNS sinkhole block categories gambling/adult/malware domains.", "Technologiques"),
    ("A.8.24", "Use of cryptography", "AES-256-GCM encryption at rest/transit key escrow HSM managed.", "Technologiques"),
    ("A.8.25", "Lifecycle management", "SDLC secure coding standards OWASP Top 10 compliance enforced.", "Technologiques"),
    ("A.8.26", "Application security requirements", "Threat modeling STRIDE applied during design phase new features.", "Technologiques"),
    ("A.8.27", "Secure system architecture and engineering principles", "Defense-in-depth layered controls assume breach mindset adopted.", "Technologiques"),
    ("A.8.28", "Secure coding", "Static analysis SAST integrated CI/CD pipeline blocking merges.", "Technologiques"),
    ("A.8.29", "Penetration testing", "Red team exercises annual scope covering external/internal vectors.", "Technologiques"),
    ("A.8.30", "Outsourced development", "Code review contractual obligation vendor deliverables quality gates.", "Technologiques"),
    ("A.8.31", "Separation of development, test and production environments", "Environment parity checks prevent config drift impacting prod stability.", "Technologiques"),
    ("A.8.32", "Change management", "Rollback procedures documented tested prior deployment window opening.", "Technologiques"),
    ("A.8.33", "Test information", "Synthetic datasets used exclusively avoiding real customer data exposure.", "Technologiques"),
    ("A.8.34", "Protected system test data", "Masked/anonymized records stored encrypted isolated sandbox zones.", "Technologiques"),
]

def validate_seed_data():
    refs = [item[0].strip() for item in SEED_DATA]
    if len(refs) != len(set(refs)):
        raise ValueError("Le seed contient des références de contrôle dupliquées.")
    expected = {"Organisationnels": 37, "Personnes": 8, "Physique": 14, "Technologiques": 34}
    counts = {}
    for _, _, _, domain in SEED_DATA:
        counts[domain] = counts.get(domain, 0) + 1
    if counts != expected:
        raise ValueError(f"Répartition ISO 27002:2022 invalide: {counts}; attendu: {expected}")
    if len(SEED_DATA) != 93:
        raise ValueError(f"Le seed doit contenir 93 contrôles, trouvé: {len(SEED_DATA)}")


async def seed():
    validate_seed_data()
    engine = create_async_engine(settings.DATABASE_URL)
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("Connexion à la base...")
    try:
        async with async_session_maker() as session:
            existing_result = await session.execute(select(IsoControl))
            existing = {control.ref_code: control for control in existing_result.scalars().all()}
            inserted = updated = 0
            for ref_code, title, desc, domain in SEED_DATA:
                ref_code = ref_code.strip()
                obj = existing.get(ref_code)
                if obj is None:
                    obj = IsoControl(
                        ref_code=ref_code,
                        title=title.strip(),
                        description=desc.strip(),
                        domain=domain.strip(),
                        category="ISO_27002_v2022",
                        is_manually_covered=False,
                    )
                    session.add(obj)
                    inserted += 1
                else:
                    # Update reference metadata only; preserve assessment/coverage fields.
                    obj.title = title.strip()
                    obj.description = desc.strip()
                    obj.domain = domain.strip()
                    obj.category = "ISO_27002_v2022"
                    updated += 1
            await session.commit()
            print(f"Seed terminé: {inserted} ajoutés, {updated} mis à jour.")
            print("Aucun contrôle existant n'a été supprimé.")
    except Exception:
        await engine.dispose()
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed())