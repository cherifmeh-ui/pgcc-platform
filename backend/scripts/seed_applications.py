# backend/scripts/seed_applications.py
import asyncio, sys, os
from uuid import uuid4
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.core.config import settings

APPS_DATA = [
    # (name, module, owner, direction, access_level, hosting_current, hosting_target, criticality, main_risk, treatment_plan, comment)
    ("IBM DOMINO", "Messagerie", "DI", "DI", "Utilisateur standard / Admin restreint", "On-Premise", "Cloud IaaS externe", "Critique", "Phishing / indisponibilité", "Migration Cloud + PRA", "Messagerie centrale de la CTF"),
    ("IBM DOMINO", "Annuaire", "DI", "DI", "Administrateur", "On-Premise", "Cloud IaaS externe", "Critique", "Phishing / indisponibilité", "Migration Cloud + PRA", "Gestion des comptes et identités"),
    ("Mail Manager", "Gestion courrier", "Responsable courrier", "DI", "Utilisateur / Admin", "On-Premise", "Cloud IaaS externe", "Élevée", None, None, "Archivage et traçabilité"),
    ("Open PGI", "Comptabilité", "Responsable Financier et Comptable", "DFC", "Utilisateur / Admin", "On-Premise", "Cloud IaaS externe", "Critique", "Obsolescence / Indisponibilité", "Migration Cloud + PRA", "Données financières sensibles"),
    ("Open PGI", "Gestion RH", "Responsable RH", "DRH", "Utilisateur / Admin", "On-Premise", "Cloud IaaS externe", "Critique", "Obsolescence / Indisponibilité", "Migration Cloud + PRA", "Données personnelles employés"),
    ("Open PGI", "Contrôle de gestion", "Responsable CG", "DCG", "Utilisateur / Admin", "On-Premise", "Cloud IaaS externe", "Élevée", "Obsolescence / Indisponibilité", "Migration Cloud + PRA", "Reporting financier"),
    ("COSWIN", "Maintenance", "Responsable MM", "DMM", "Utilisateur / Admin", "On-Premise", "Cloud IaaS externe", "Élevée", "Perte données / Arrêt activité", "Migration Cloud + PRA", "Gestion maintenance équipements"),
    ("COSWIN", "Approvisionnement", "Responsable AL", "DAL", "Utilisateur / Admin", "On-Premise", "Cloud IaaS externe", "Élevée", "Perte données / Arrêt activité", "Migration Cloud + PRA", "Gestion pièces et stocks"),
    ("AL QAZAR", "Pointage", "Responsable RH", "DRH / DI", "Utilisateur / Admin", "On-Premise", "Cloud IaaS externe", "Moyenne", None, None, "Données temps de travail"),
    ("Qualipro", None, None, None, None, "On-Premise", None, "Moyenne", None, None, None),
    ("Moodle", "Formation", "Responsable RH", "DRH", "Utilisateur / Admin", "On-Premise", None, "Faible", None, None, "Plateforme e-learning"),
    ("Big Blue Button", "Visioconférence", "Responsable RH", "DRH", "Utilisateur / Admin", "On-Premise", None, "Faible", None, None, "Réunions et formations"),
]

async def seed():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        # Créer la table si absente
        await conn.run_sync(lambda sync_conn: Application.metadata.create_all(sync_conn))
        
        res = await conn.execute(text("SELECT COUNT(*) FROM applications"))
        count = res.scalar()
        if count and count > 0:
            print(f"⚠️ Table 'applications' déjà peuplée ({count} lignes). Annulation.")
            return
        
        for row in APPS_DATA:
            stmt = text("""INSERT INTO applications 
                (id, name, module, owner, direction, access_level, hosting_current, hosting_target, criticality, main_risk, treatment_plan, comment, created_at, updated_at)
                VALUES (:id, :n, :m, :o, :d, :al, :hc, :ht, :c, :mr, :tp, :cm, NOW(), NOW())""")
            params = dict(zip(["id","n","m","o","d","al","hc","ht","c","mr","tp","cm"], [str(uuid4())] + list(row)))
            await conn.execute(stmt, params)
        print(f"✅ {len(APPS_DATA)} applications critiques injectées.")

from app.models.application import Application
if __name__ == "__main__":
    asyncio.run(seed())