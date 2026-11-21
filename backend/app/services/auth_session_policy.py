"""Authentication session eligibility policy helpers."""

from datetime import datetime


def refresh_denial_reason(
    *,
    is_active: bool,
    is_locked: bool,
    must_change_password: bool,
    password_changed_at: datetime | None,
    token_issued_at: int | None,
) -> str | None:
    """Return a denial reason for refresh, or None when eligible.

    The caller must separately validate the token signature, type and subject.
    """
    if not is_active:
        return "Compte désactivé."
    if is_locked:
        return "Compte temporairement verrouillé. Réessayez plus tard."
    if must_change_password:
        return "Changement de mot de passe obligatoire avant renouvellement de session."
    if password_changed_at and token_issued_at:
        if token_issued_at < int(password_changed_at.timestamp()):
            return "Refresh token révoqué."
    return None
