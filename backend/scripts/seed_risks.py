# backend/scripts/seed_risks.py
"""
Script de peuplement initial du Registre des Risques PGCC.
Basé sur CTF_GRC_Data.xlsx (Menaces + Apps Critiques).
Exécution : docker-compose exec backend python scripts/seed_risks.py
"""
import asyncio
import sys
import os
from uuid import uuid4

# Ajouter le parent au path pour importer app.*
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# Importer la config pour récupérer DATABASE_URL
try:
    from app.core.config import settings
except ImportError:
    print("⚠️ Impossible d'importer settings depuis app.core.config. Utilisation fallback env var.")
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@db:5432/pgcc_db")
else:
    DATABASE_URL = settings.DATABASE_URL

# --- DONNÉES EXTRAITES DE L'EXCEL ---
RISKS_DATA = [
    # MALVEILLANCE EXTERNE
    ("M-EXT-01", "Cyberattaque ciblée (APT) contre infrastructure critique", 
     "Une attaque avancée persistante visant les systèmes SCADA ou ERP de la CTF pourrait compromettre la continuité opérationnelle des forages.",
     "Cyberattaque ciblée", 5, 4, "Siège Tunis / Rigs Offshore", "Ouvert"),
     
    ("M-EXT-02", "Intrusion réseau non autorisée dans VLAN administratifs",
     "Pénétration potentielle du réseau interne via des vulnérabilités WiFi ou ports physiques accessibles sur sites chantiers.",
     "Intrusion réseau", 5, 3, "Tous Sites", "Ouvert"),
     
    ("M-EXT-03", "Campagne de Phishing massive ciblant les dirigeants",
     "Envois massifs d'emails frauduleux imitant la DG ou ANCS pour voler identifiants O365/Domino ou installer ransomware.",
     "Hameçonnage (Phishing)", 4, 5, "Siège Tunis", "Ouvert"),
     
    ("M-EXT-04", "Ransomware bloquant accès aux données RH et Financières",
     "Chiffrement accidentel ou malveillant des bases Open PGI (Compta/RH) rendant impossible toute paie ou clôture comptable.",
     "Logiciel rançonneur", 5, 3, "Datacenter Siège", "Ouvert"),
     
    ("M-EXT-05", "Déni de service (DDoS) paralysant portail client/fournisseur",
     "Attaque volumétrique saturant la bande passante VSAT/Satellite des rig offshore, coupant communication satellite.",
     "Déni de service (DDoS)", 3, 2, "Rigs Offshore", "Ouvert"),

    # PANNE TECHNIQUE & OBSOLESCENCE (Apps Critiques)
    ("T-APP-01", "Obsolescence critique Serveur IBM Domino (Messagerie/Annuaire)",
     "Version non patchée depuis >5 ans. Vulnérable CVE connues. Pas de support éditeur. Risque majeur indisponibilité mail global.",
     "Panne technique / Obsolescence", 5, 4, "Datacenter Siège", "En traitement"),
     
    ("T-APP-02", "Single Point of Failure sur Application COSWIN (Maintenance)",
     "Pas de redondance active. Si serveur tombe, plus aucun ordre de travail ni suivi pièces détachées disponible pour DMM/DAL.",
     "Panne technique", 4, 3, "Datacenter Siège", "Ouvert"),
     
    ("T-APP-03", "Corruption potentielle Base de Données Open PGI (Finances/RH)",
     "Absence de vérification intégrité quotidienne. Risque perte irrémédiable données comptables légales si corruption silencieuse.",
     "Corruption base de données", 5, 2, "Datacenter Siège", "Ouvert"),
     
    ("T-INF-01", "Coupure Liaison VSAT Chantier sans Failover 4G/Starlink",
     "Les rigs dépendent uniquement du lien satellite principal. Toute panne météo/matérielle isole complètement le chantier.",
     "Panne liaison VSAT", 4, 4, "Rigs Offshore", "Ouvert"),
     
    ("T-INF-02", "Défaillance Stockage SAN sans RAID fonctionnel",
     "Disques anciens sans monitoring SMART actif. Panne simultanée possible entraînant perte totale archives projets.",
     "Défaillance stockage", 5, 2, "Datacenter Siège", "Ouvert"),

    # ERREUR HUMAINE & PROCESSUS
    ("E-HUM-01", "Partage généralisé de comptes Admin locaux sur postes techniques",
     "Techniciens maintenance partagent mot de passe 'admin123' sur tous les PC atelier. Impossible tracer qui a fait quoi.",
     "Partage d'identifiants", 4, 5, "Ateliers / Sites", "Ouvert"),
     
    ("E-HUM-02", "Installation logiciels non agréés par employés (Shadow IT)",
     "Téléchargement outils gratuits ou cracked sur postes bureautiques introduisant malwares ou failles sécurité majeures.",
     "Installation logiciel non autorisé", 3, 5, "Siège Tunis", "Ouvert"),
     
    ("E-HUM-03", "Erreur manipulation suppression accidentelle fichiers partagés",
     "Suppression involontaire dossiers projets/archives suite à mauvaise compréhension arborescence réseau.",
     "Erreur de manipulation", 3, 4, "Serveurs Fichiers", "Traité"),
     
    ("E-HUM-04", "Perte équipement mobile contenant données clients sensibles",
     "Smartphones/Tablettes perdus/volés hors bureau sans chiffrement complet ni MDM effacement distance.",
     "Perte équipement mobile", 4, 3, "Terrain / Commercial", "Ouvert"),

    # NON-CONFORMITÉ RÉGLEMENTAIRE
    ("NC-REG-01", "Non-respect Décret-Loi Cybersécurité Tunisie (ANCS)",
     "Absence déclaration incidents obligatoires sous 24h et manque registre formalisé des traitements données personnelles.",
     "Manquement réglementaire", 5, 3, "Global Entreprise", "Ouvert"),
     
    ("NC-POL-01", "Violation Politique Sécurité SI (PSSI) - Absence MFA généralisée",
     "Beaucoup d'applications internes encore protégées seulement par login/password simple malgré directive RSSI récente.",
     "Non-respect PSSI", 4, 5, "SI Interne", "En traitement"),
     
    ("NC-AUD-01", "Impossibilité prouver conformité lors audit ISO 27001 externe",
     "Traces journalisation insuffisantes ou conservées trop peu (<6 mois), empêchant reconstruction événements sécuritaires.",
     "Absence de preuve de conformité", 3, 4, "Audit / Compliance", "Ouvert"),

    # ENVIRONNEMENTAL
    ("ENV-01", "Incendie Datacenter Siège détruisant serveurs physiques",
     "Protection incendie gaz obsolète ou absence détection précoce fumée haute sensibilité salle serveurs.",
     "Incendie locaux", 5, 1, "Datacenter Siège", "Accepté"), 
     
    ("ENV-02", "Inondation sous-sol affectant câblage réseau vital",
     "Remontée nappe phréatique ou rupture canalisation proche baies réseaux souterraines.",
     "Inondation", 4, 2, "Bâtiment Technique", "Ouvert"),
]

async def seed_database():
    print(f"🌱 Démarrage du seeding... Connexion à {DATABASE_URL.split('@')[1]}")
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Vérifier si déjà peuplé
        result = await session.execute(text("SELECT COUNT(*) FROM risks"))
        count = result.scalar()
        
        if count and count > 0:
            print(f"⚠️ La table 'risks' contient déjà {count} entrées. Annulation pour éviter doublons.")
            return

        inserted = 0
        for ref, title, desc, threat, imp, lik, site, status in RISKS_DATA:
            risk_level = imp * lik
            
            # Insertion SQL brute pour maximiser compatibilité et rapidité
            stmt = text("""
                INSERT INTO risks (id, ref, title, description, threat, impact, likelihood, risk_level, site, status, created_at, updated_at)
                VALUES (:id, :ref, :title, :desc, :threat, :imp, :lik, :lvl, :site, :status, NOW(), NOW())
            """)
            
            params = {
                "id": str(uuid4()),
                "ref": ref,
                "title": title,
                "desc": desc,
                "threat": threat,
                "imp": imp,
                "lik": lik,
                "lvl": risk_level,
                "site": site,
                "status": status
            }
            
            try:
                await session.execute(stmt, params)
                inserted += 1
            except Exception as e:
                print(f"❌ Erreur insertion {ref}: {e}")

        await session.commit()
        print(f"✅ Succès ! {inserted} risques injectés dans la base de données.")

if __name__ == "__main__":
    try:
        asyncio.run(seed_database())
    except Exception as e:
        print(f"❌ Erreur fatale pendant le seed : {e}")
        sys.exit(1)