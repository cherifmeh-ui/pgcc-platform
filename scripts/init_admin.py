# scripts/init_admin.py
import asyncio
import os
import secrets
import sys

# Rendre le package `app` importable quel que soit le cwd du conteneur
_HERE = os.path.dirname(os.path.abspath(__file__))      # /app/scripts
_ROOT = os.path.dirname(_HERE)                          # /app
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sqlalchemy import select  # noqa: E402

from app.core.database import AsyncSessionLocal, Base, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.user import User  # noqa: E402

ADMINS = [
    {
        "email": "rssi@ctf.com.tn",
        "full_name": "Responsable Sécurité Informatique (RSSI)",
        "department": "DSI",
        "role": "admin",
    },
    {
        "email": "dg@ctf.com.tn",
        "full_name": "Direction Générale (PDG)",
        "department": "Direction Générale",
        "role": "executive",
    },
]


async def main():
    # Idempotent : garantir les tables même si le serveur n'a pas encore tourné
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    created, skipped = [], []

    async with AsyncSessionLocal() as session:
        for spec in ADMINS:
            res = await session.execute(select(User).where(User.email == spec["email"]))
            if res.scalar_one_or_none():
                skipped.append(spec["email"])
                continue

            temp_pwd = secrets.token_urlsafe(16)
            session.add(
                User(
                    email=spec["email"],
                    full_name=spec["full_name"],
                    department=spec["department"],
                    role=spec["role"],
                    password_hash=hash_password(temp_pwd),
                    must_change_password=True,
                    is_active=True,
                    mfa_enabled=False,
                    failed_login_attempts=0,
                )
            )
            created.append((spec["email"], spec["role"], temp_pwd))

        await session.commit()

    print("=" * 64)
    print("INIT ADMIN PGCC — RÉSULTAT")
    print("=" * 64)
    if created:
        print("Comptes CRÉÉS (mot de passe temporaire à changer 1ère connexion) :")
        for email, role, pwd in created:
            print(f"  • {email}  [{role}]  temp = {pwd}")
        print()
        print("⚠️  Ces mots de passe s'affichent UNE SEULE FOIS.")
        print("    Transmets-les via un canal sûr ; changement + MFA obligatoires")
        print("    à la première connexion (flux Phase 3).")
    if skipped:
        print("Comptes DÉJÀ PRÉSENTS (non touchés) : " + ", ".join(skipped))
    print("=" * 64)


if __name__ == "__main__":
    asyncio.run(main())