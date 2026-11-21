from datetime import datetime, timezone

import pytest

from app.services.auth_session_policy import refresh_denial_reason


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({"is_active": False, "is_locked": False, "must_change_password": False, "role": "viewer", "mfa_enabled": False, "password_changed_at": None, "token_issued_at": 100}, "Compte désactivé."),
        ({"is_active": True, "is_locked": True, "must_change_password": False, "role": "viewer", "mfa_enabled": False, "password_changed_at": None, "token_issued_at": 100}, "Compte temporairement verrouillé. Réessayez plus tard."),
        ({"is_active": True, "is_locked": False, "must_change_password": True, "role": "viewer", "mfa_enabled": False, "password_changed_at": None, "token_issued_at": 100}, "Changement de mot de passe obligatoire avant renouvellement de session."),
        ({"is_active": True, "is_locked": False, "must_change_password": False, "role": "viewer", "mfa_enabled": False, "password_changed_at": datetime.fromtimestamp(200, timezone.utc), "token_issued_at": 100}, "Refresh token révoqué."),
    ],
)
def test_refresh_denied_for_ineligible_user(kwargs, expected):
    assert refresh_denial_reason(**kwargs) == expected


def test_refresh_allowed_for_active_unlocked_user_with_current_password():
    assert refresh_denial_reason(
        is_active=True,
        is_locked=False,
        must_change_password=False,
        role="viewer",
        mfa_enabled=False,
        password_changed_at=datetime.fromtimestamp(100, timezone.utc),
        token_issued_at=101,
    ) is None


def test_refresh_allowed_when_no_password_change_timestamp():
    assert refresh_denial_reason(
        is_active=True,
        is_locked=False,
        must_change_password=False,
        role="viewer",
        mfa_enabled=False,
        password_changed_at=None,
        token_issued_at=101,
    ) is None


def test_refresh_denied_for_privileged_role_without_mfa():
    assert refresh_denial_reason(
        is_active=True,
        is_locked=False,
        must_change_password=False,
        role="admin",
        mfa_enabled=False,
        password_changed_at=None,
        token_issued_at=101,
    ) == "MFA obligatoire pour ce rôle."


def test_refresh_allowed_for_privileged_role_with_mfa():
    assert refresh_denial_reason(
        is_active=True,
        is_locked=False,
        must_change_password=False,
        role="executive",
        mfa_enabled=True,
        password_changed_at=None,
        token_issued_at=101,
    ) is None
