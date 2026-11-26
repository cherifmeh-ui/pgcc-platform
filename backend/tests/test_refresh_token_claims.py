from app.core.security import create_refresh_token, decode_token


def test_refresh_token_contains_normalized_role_and_mfa_state_snapshot():
    token = create_refresh_token(
        subject="refresh-snapshot@example.test",
        role=" ADMIN ",
        mfa_enabled=False,
        mfa_confirmed_at=1_800_000_000,
    )

    payload = decode_token(token, expected_type="refresh")
    assert payload["sub"] == "refresh-snapshot@example.test"
    assert payload["role"] == "admin"
    assert payload["mfa_enabled"] is False
    assert payload["mfa_confirmed_at"] == 1_800_000_000


def test_pre_auth_and_password_change_tokens_bind_normalized_role_and_auth_version():
    from app.core.security import create_pre_auth_token, create_change_password_token

    pre_auth = decode_token(
        create_pre_auth_token("claims@example.test", " ADMIN ", auth_version=7),
        expected_type="pre_auth",
    )
    password_change = decode_token(
        create_change_password_token("claims@example.test", " EXECUTIVE ", auth_version=9),
        expected_type="change_password",
    )

    assert pre_auth["role"] == "admin"
    assert pre_auth["auth_version"] == 7
    assert password_change["role"] == "executive"
    assert password_change["auth_version"] == 9
