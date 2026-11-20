# backend/scripts/build_knowledge_graph.py
import sys
import os
import asyncio

# ⬇️ FORÇAGE DU PYTHONPATH POUR TROUVER LE MODULE 'APP' DEPUIS /app/scripts
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.core.config import settings

# ✅ IMPORT CRUCIAL : Charger TOUS les modèles liés aux relations
# Même si on ne les utilise pas directement ici, cet import enregistre 
# leurs classes dans le registry global de SQLAlchemy.
from app.models.risk import Risk          # Contient relationship("ActionItem")
from app.models.action_item import ActionItem # La cible de la relation
from app.models.application import Application
from app.models.iso_control import IsoControl
from app.models.entity_link import EntityLink, EntityType, LinkType


async def build_links():
    engine = create_async_engine(settings.DATABASE_URL)
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    print("🕸️ Connexion à la base...")
    
    try:
        async with async_session_maker() as session:
            # 1. Charger toutes les entités
            risks_res = await session.execute(select(Risk))
            apps_res = await session.execute(select(Application))
            controls_res = await session.execute(select(IsoControl))
            
            risks = risks_res.scalars().all()
            apps = apps_res.scalars().all()
            controls = controls_res.scalars().all()
            
            if not risks or not apps:
                print("⚠️ Données insuffisantes (risques ou applications vides). Annulation.")
                return
                
            new_links = []
            
            # --- LOGIQUE DE LIAISON RISQUE <-> APP ---
            for risk in risks:
                r_text = f"{risk.title} {risk.threat or ''}".lower()
                
                for app in apps:
                    a_name = app.name.lower()
                    # Si le nom de l'app apparaît dans la description du risque
                    if a_name in r_text:
                        # Vérifier si le lien existe déjà pour éviter doublons
                        exists_q = await session.execute(
                            select(EntityLink).where(
                                EntityLink.source_id == risk.id, 
                                EntityLink.target_id == app.id
                            )
                        )
                        if not exists_q.scalar_one_or_none():
                            new_links.append(EntityLink(
                                source_id=risk.id, source_type=EntityType.RISK,
                                target_id=app.id, target_type=EntityType.APPLICATION,
                                link_type=LinkType.IMPACTS,
                                description=f"Le risque '{risk.ref}' impacte potentiellement l'application '{app.name}'."
                            ))

            # --- LOGIQUE DE LIAISON CONTRÔLE ISO <-> RISQUE ---
            KEYWORD_MAP = {
                "sauvegarde": ["A.8.2", "A.8.14"],
                "authentification": ["A.8.5", "A.8.56"],
                "chiffrement": ["A.8.24", "A.8.25"],
                "malware": ["A.8.7"],
                "incident": ["A.8.43"],
                "formation": ["A.6.3"],
            }

            for control in controls:
                c_ref_lower = control.ref_code.lower()
                c_title_lower = control.title.lower()
                
                for risk in risks:
                    matched_keywords = []
                    for keyword, iso_refs in KEYWORD_MAP.items():
                        if keyword in c_title_lower and any(ref.lower() == c_ref_lower for ref in iso_refs):
                             # Vérifier si le mot-clé est aussi dans le risque
                             if keyword in risk.title.lower() or keyword in (risk.treatment_plan or "").lower():
                                 matched_keywords.append(keyword)
                                 
                    if matched_keywords:
                        exists_q = await session.execute(
                            select(EntityLink).where(
                                EntityLink.source_id == control.id, 
                                EntityLink.target_id == risk.id
                            )
                        )
                        if not exists_q.scalar_one_or_none():
                            new_links.append(EntityLink(
                                source_id=control.id, source_type=EntityType.CONTROL_ISO,
                                target_id=risk.id, target_type=EntityType.RISK,
                                link_type=LinkType.MITIGATES,
                                description=f"Le contrôle {control.ref_code} aide à mitiger le risque via les concepts : {', '.join(matched_keywords)}."
                            ))

            # Sauvegarder tous les nouveaux liens
            if new_links:
                session.add_all(new_links)
                await session.commit()
                print(f"✅ Succès ! {len(new_links)} liens sémantiques créés.")
            else:
                print("ℹ️ Aucun nouveau lien détecté.")
                
    except Exception as e:
        print(f"\n💥 ERREUR CRITIQUE lors de la construction du graphe :\n{str(e)}")
        import traceback
        traceback.print_exc()
        
    finally:
        await engine.dispose()
        print("\n🔒 Connexion DB fermée.")

if __name__ == "__main__":
    asyncio.run(build_links())