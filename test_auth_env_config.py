"""
Targeted Security & Auth Tests for Per-Installation Env Password Configuration.
Covers:
1. Login with DSS_PIK_PASSWORD (bcrypt hashed once at startup, no re-hash on login).
2. Wrong password & wrong username rejected.
3. Empty username / empty password rejected safely (no active default password).
4. Legacy DSS_PIK_PASSWORD_HASH compatibility fallback works.
5. Both DSS_PIK_PASSWORD and DSS_PIK_PASSWORD_HASH set -> primary wins + warning.
6. Session token HMAC-SHA256 valid, tampered/expired rejected, no public fallback secret.
7. Zero plaintext passwords, bcrypt hashes, or session secrets printed in logs.
"""

import bcrypt
import pytest
import backend.auth as auth


class TestEnvBasedAuthentication:
    def test_01_primary_env_password_login_and_single_hash(self, monkeypatch, capsys):
        monkeypatch.setenv("DSS_PIK_USERNAME", "admin_test")
        monkeypatch.setenv("DSS_PIK_PASSWORD", "SuperSecret!Pass2026")
        monkeypatch.delenv("DSS_PIK_PASSWORD_HASH", raising=False)
        monkeypatch.setenv("DSS_PIK_SESSION_SECRET", "a" * 64)

        auth.reload_auth_config()
        initial_hash = auth.DSS_PIK_PASSWORD_HASH
        assert initial_hash.startswith("$2b$") or initial_hash.startswith("$2a$")
        assert auth.authenticate_user("admin_test", "SuperSecret!Pass2026") is True
        assert auth.authenticate_user("ADMIN_TEST", "SuperSecret!Pass2026") is True
        # Ensure hash is NOT regenerated during login
        assert auth.DSS_PIK_PASSWORD_HASH == initial_hash

        out = capsys.readouterr().out
        assert "SuperSecret!Pass2026" not in out
        assert initial_hash not in out
        assert ("a" * 64) not in out

    def test_02_wrong_password_and_wrong_username_rejected(self, monkeypatch):
        monkeypatch.setenv("DSS_PIK_USERNAME", "admin_test")
        monkeypatch.setenv("DSS_PIK_PASSWORD", "CorrectPass!99")
        monkeypatch.delenv("DSS_PIK_PASSWORD_HASH", raising=False)
        monkeypatch.setenv("DSS_PIK_SESSION_SECRET", "b" * 64)

        auth.reload_auth_config()
        assert auth.authenticate_user("admin_test", "WrongPass!00") is False
        assert auth.authenticate_user("other_user", "CorrectPass!99") is False
        assert auth.authenticate_user("", "CorrectPass!99") is False
        assert auth.authenticate_user("admin_test", "") is False

    def test_03_empty_env_fails_safely(self, monkeypatch, capsys):
        monkeypatch.delenv("DSS_PIK_USERNAME", raising=False)
        monkeypatch.delenv("DSS_PIK_PASSWORD", raising=False)
        monkeypatch.delenv("DSS_PIK_PASSWORD_HASH", raising=False)
        monkeypatch.delenv("DSS_PIK_SESSION_SECRET", raising=False)

        auth.reload_auth_config()
        assert auth.authenticate_user("klimatkepri", "") is False
        assert auth.authenticate_user("klimatkepri", "admin") is False
        assert auth.DSS_PIK_SESSION_SECRET != "dss_pik_secret_fallback_key"
        assert len(auth.DSS_PIK_SESSION_SECRET) == 64

        out = capsys.readouterr().out
        assert "AUTH CONFIG WARNING" in out

    def test_04_legacy_password_hash_fallback_still_works(self, monkeypatch, capsys):
        legacy_hash = bcrypt.hashpw(b"LegacyProdPass!2026", bcrypt.gensalt()).decode("utf-8")
        monkeypatch.setenv("DSS_PIK_USERNAME", "klimatkepri")
        monkeypatch.delenv("DSS_PIK_PASSWORD", raising=False)
        monkeypatch.setenv("DSS_PIK_PASSWORD_HASH", legacy_hash)
        monkeypatch.setenv("DSS_PIK_SESSION_SECRET", "c" * 64)

        auth.reload_auth_config()
        assert auth.authenticate_user("klimatkepri", "LegacyProdPass!2026") is True
        assert auth.authenticate_user("klimatkepri", "WrongLegacy") is False
        out = capsys.readouterr().out
        assert "legacy DSS_PIK_PASSWORD_HASH" in out
        assert legacy_hash not in out

    def test_05_both_set_prefers_primary_with_warning(self, monkeypatch, capsys):
        legacy_hash = bcrypt.hashpw(b"OldLegacyPass", bcrypt.gensalt()).decode("utf-8")
        monkeypatch.setenv("DSS_PIK_USERNAME", "operator1")
        monkeypatch.setenv("DSS_PIK_PASSWORD", "NewPrimaryPass!2026")
        monkeypatch.setenv("DSS_PIK_PASSWORD_HASH", legacy_hash)
        monkeypatch.setenv("DSS_PIK_SESSION_SECRET", "d" * 64)

        auth.reload_auth_config()
        assert auth.authenticate_user("operator1", "NewPrimaryPass!2026") is True
        assert auth.authenticate_user("operator1", "OldLegacyPass") is False
        out = capsys.readouterr().out
        assert "Both DSS_PIK_PASSWORD and legacy DSS_PIK_PASSWORD_HASH are set" in out
        assert "NewPrimaryPass!2026" not in out
        assert legacy_hash not in out

    def test_06_session_token_valid_tampered_and_expired(self, monkeypatch):
        monkeypatch.setenv("DSS_PIK_USERNAME", "operator1")
        monkeypatch.setenv("DSS_PIK_PASSWORD", "SessionPass!2026")
        monkeypatch.setenv("DSS_PIK_SESSION_SECRET", "e" * 64)

        auth.reload_auth_config()
        tok = auth.create_session_token("operator1")
        payload = auth.decode_session_token(tok)
        assert payload is not None and payload["sub"] == "operator1"

        # Tampered token rejected
        assert auth.decode_session_token(tok + "tamper") is None

        # Expired token rejected
        exp_tok = auth.create_session_token("operator1", expires_in=-10)
        assert auth.decode_session_token(exp_tok) is None
