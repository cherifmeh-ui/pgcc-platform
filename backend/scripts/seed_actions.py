# backend/scripts/seed_actions.py
import asyncio, sys, os
from uuid import uuid4
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.core.config import settings
from datetime import datetime, timedelta

SEED_ACTIONS = [
    # (risk_ref, title, description, priority, assigned_to, days_offset)
    ("M-EXT-01", "Déployer IDS/IPS périmétrique", "Installer Fortinet/FortiGate sur DMZ siège.", "CRITICAL", "DI", 30),
    ("M-EXT-01", "Sensibilisation Phishing mensuelle", "Lancer campagne KnowBe4 tous les mois.", "HIGH", "DRH", 7),
    ("NC-POL-01", "Activer MFA sur Open PGI", "Configurer TOTP pour tous les admins comptables.", "CRITICAL", "DFC", 14),
    ("T-APP-01", "Audit sécurité IBM Domino", "Scan vulnérabilités serveur messagerie.", "HIGH", "DI", 21),
    ("E-HUM-01", "Rotation mots de passe Admin", "Force change password every 90 days policy.", "MEDIUM", "DI", 10),
]

async def seed():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        # Check if table exists first? Assuming models are loaded by main.py startup usually.
        # But here we rely on raw SQL insert because importing ORM might be heavy/slow in script context without full app init.
        # However, safer to use ORM if possible. Let's stick to raw SQL for simplicity in this standalone script logic 
        # OR better: assume the user runs this AFTER restarting backend so tables exist.
        
        print("⏳ Préparation insertion actions...")
        
        # We need risk IDs. Since we don't have easy access to ORM objects here easily without booting FastAPI app fully,
        # we will fetch them via SQL join based on 'ref'.
        
        for item in SEED_ACTIONS:
            r_ref, title, desc, prio, owner, offset_days = item
            
            # Find risk ID
            res = await conn.execute(text("SELECT id FROM risks WHERE ref = :r_ref"), {"r_ref": r_ref})
            row = res.fetchone()
            if not row:
                print(f"⚠️ Risque {r_ref} non trouvé. Ignoré.")
                continue
                
            risk_id = row[0]
            due_dt = datetime.utcnow() + timedelta(days=offset_days)
            
            stmt = text("""
                INSERT INTO action_items (id, risk_id, title, description, status, priority, assigned_to, due_date, created_at, updated_at)
                VALUES (:id, :rid, :t, :d, 'TODO', :p, :o, :dd, NOW(), NOW())
            """)
            
            params = {
                "id": str(uuid4()),
                "rid": risk_id,
                "t": title,
                "d": desc,
                "p": prio.upper(), # Match enum values if stored as strings or check DB schema
                "o": owner,
                "dd": due_dt.isoformat()
            }
            
            await conn.execute(stmt, params)
            print(f"✅ Action '{title}' créée pour risque {r_ref}.")

if __name__ == "__main__":
    asyncio.run(seed())