# backend/services/knowledge_graph_service.py
import re
from typing import List, Tuple
from app.models.risk import Risk
from app.models.application import Application
from app.models.iso_control import IsoControl
from app.models.entity_link import EntityLink, EntityType, LinkType

class KnowledgeGraphService:
    
    @staticmethod
    async def build_initial_links(db_session):
        """
        Analyse les textes pour créer des liens automatiques entre Entités.
        À lancer après le seed initial ou périodiquement.
        """
        print("🕸️ Construction du Graphe de Connaissances...")
        
        # 1. Charger toutes les entités pertinentes
        risks_res = await db_session.execute(select(Risk))
        apps_res = await db_session.execute(select(Application))
        controls_res = await db_session.execute(select(IsoControl))
        
        risks = risks_res.scalars().all()
        apps = apps_res.scalars().all()
        controls = controls_res.scalars().all()
        
        new_links = []
        
        # --- LOGIQUE DE LIAISON RISQUE <-> APP ---
        for risk in risks:
            r_text = f"{risk.title} {risk.threat or ''}".lower()
            
            for app in apps:
                a_name = app.name.lower()
                # Si le nom de l'app apparaît dans la description du risque
                if a_name in r_text or any(kw in r_name for kw in ["domino", "pgi", "coswin"]):
                    # Éviter les doublons simples
                    exists = await db_session.query(EntityLink).filter_by(source_id=risk.id, target_id=app.id).first()
                    if not exists:
                        new_links.append(EntityLink(
                            source_id=risk.id, source_type=EntityType.RISK,
                            target_id=app.id, target_type=EntityType.APPLICATION,
                            link_type=LinkType.IMPACTS,
                            description=f"Le risque '{risk.ref}' impacte potentiellement l'application '{app.name}'."
                        ))

        # --- LOGIQUE DE LIAISON CONTRÔLE ISO <-> RISQUE ---
        # Basé sur les mots-clés communs (ex: "backup", "authentification", "chiffrement")
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
                    exists = await db_session.query(EntityLink).filter_by(source_id=control.id, target_id=risk.id).first()
                    if not exists:
                        new_links.append(EntityLink(
                            source_id=control.id, source_type=EntityType.CONTROL_ISO,
                            target_id=risk.id, target_type=EntityType.RISK,
                            link_type=LinkType.MITIGATES,
                            description=f"Le contrôle {control.ref_code} aide à mitiger le risque via les concepts : {', '.join(matched_keywords)}."
                        ))

        # Sauvegarder tous les nouveaux liens
        if new_links:
            db_session.add_all(new_links)
            await db_session.commit()
            print(f"✅ {len(new_links)} liens sémantiques créés.")
        else:
            print("ℹ️ Aucun nouveau lien détecté.")