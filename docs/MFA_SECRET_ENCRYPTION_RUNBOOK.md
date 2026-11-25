# MFA Secret Encryption Runbook

## Objective

Protect TOTP shared secrets at rest. New enrollment secrets are encrypted before persistence; verification decrypts them only in application memory. The users.mfa_secret column stores a fernet:v1: ciphertext, never a plaintext TOTP secret.

## Configuration

- MFA_ENCRYPTION_KEYS is a comma-separated Fernet key ring.
- The first key is active for encryption.
- Remaining keys are accepted for decryption during rotation.
- The setting is mandatory in staging and production. Development derives a deterministic development-only key from JWT_SECRET.
- Do not commit keys, put them in .env.example, or log them.
- Store the active key in the deployment secret manager and maintain a protected backup. Losing every decryption key makes enrolled MFA accounts unrecoverable.

Generate a key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Existing plaintext data migration

Before deploying the non-development version to a database that may contain legacy plaintext MFA secrets:

1. Set MFA_ENCRYPTION_KEYS in the backend environment.
2. Run a dry run:

   ```bash
   cd backend
   python scripts/encrypt_mfa_secrets.py --dry-run
   ```

3. Review the count, then run the migration:

   ```bash
   python scripts/encrypt_mfa_secrets.py
   ```

4. Verify the output count and deploy the application.
5. Non-development startup checks the users table and refuses to start if any non-null MFA secret is not prefixed fernet:v1:.

The migration script does not print secret values. It encrypts legacy plaintext and rotates ciphertext encrypted with a previous key to the first key in the configured ring.

## Key rotation

1. Generate a new Fernet key and put it first in MFA_ENCRYPTION_KEYS; keep the old key after it, e.g. new_key,old_key.
2. Deploy the new key ring to all application instances.
3. Run python scripts/encrypt_mfa_secrets.py --dry-run, then run it without --dry-run.
4. Verify the script reports no remaining updates on a second dry run.
5. Back up the new key securely. Only then remove the old key from the ring.
6. Keep a controlled recovery procedure for restoring a previous key if rollback is required.

## Automated controls

- Unit tests cover ciphertext-at-rest, legacy plaintext conversion, key rotation, invalid ciphertext fail-closed behavior and production configuration validation.
- Startup tests verify plaintext secrets block non-development startup.
- The CI pipeline must pass before this control is considered validated.
