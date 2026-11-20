# backend/scripts/init_db.py
import sys
import os
import asyncio

# ⬇️ FORÇAGE DU PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings
from app.core.database import Base

# ✅ IMPORT CRUCIAL : Charger TOUS les modèles pour qu'ils soient enregistrés dans Base.metadata
# Sans ces imports, SQLAlchemy ne sait pas quelles tables créer !
from app.models.risk import Risk
from app.models.application import Application
from app.models.user import User
from app.models.action_item import ActionItem
from app.models.iso_control import IsoControl
from app.models.entity_link import EntityLink  # ⬅️ LE MODÈLE MANQUANT
from app.models.document import Document        # Si tu as ajouté le modèle document aussi

async def init_database():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    
    print("🚀 Initialisation de la base de données...")
    print(f"   Target: {settings.DATABASE_URL.split('@')[1]}")
    
    try:
        async with engine.begin() as conn:
            # checkfirst=True évite de crasher si la table existe déjà
            await conn.run_sync(Base.metadata.create_all, checkfirst=True)
            
        print("✅ Succès ! Toutes les tables sont créées/vérifiées.")
        
    except Exception as e:
        print(f"\n💥 ERREUR lors de l'init DB :\n{str(e)}")
        import traceback
        traceback.print_exc()
        
    finally:
        await engine.dispose()
        print("\n🔒 Connexion fermée.")

if __name__ == "__main__":
    asyncio.run(init_database())