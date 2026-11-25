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
