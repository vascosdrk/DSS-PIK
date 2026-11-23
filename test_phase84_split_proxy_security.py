"""
Phase 8.4 — Security Regression Tests for Split-Container Trusted Reverse Proxy.
"""

import asyncio
from types import SimpleNamespace

from backend.lan_firewall_service import is_client_ip_allowed
from backend.main import lan_access_guard_middleware

LOCKED_POLICY = {"lan_enabled": False, "approved_remote_addresses": []}
LAN_POLICY = {"lan_enabled": True, "approved_remote_addresses": ["192.168.110.0/24"]}


class TestSplitContainerTrustedProxySecurity:
    def test_trusted_proxy_with_loopback_client_allowed(self, monkeypatch):
        monkeypatch.setenv("CEWS_TRUSTED_PROXY_CIDRS", "172.20.0.0/16")
        monkeypatch.delenv("CEWS_DOCKER_LOCAL_ONLY", raising=False)
        ok, reason = is_client_ip_allowed("172.20.0.3", policy=LOCKED_POLICY, forwarded_real_ip="127.0.0.1")
        assert ok is True and reason == "loopback"

    def test_trusted_proxy_with_unauthorized_client_blocked(self, monkeypatch):
        monkeypatch.setenv("CEWS_TRUSTED_PROXY_CIDRS", "172.20.0.0/16")
        monkeypatch.delenv("CEWS_DOCKER_LOCAL_ONLY", raising=False)
        ok, _ = is_client_ip_allowed("172.20.0.3", policy=LOCKED_POLICY, forwarded_real_ip="192.168.1.99")
        assert ok is False

    def test_untrusted_proxy_cannot_spoof_x_real_ip(self, monkeypatch):
        monkeypatch.setenv("CEWS_TRUSTED_PROXY_CIDRS", "172.20.0.0/16")
        monkeypatch.delenv("CEWS_DOCKER_LOCAL_ONLY", raising=False)
        fake_req = SimpleNamespace(
            client=SimpleNamespace(host="192.168.1.99"),
            headers={"x-real-ip": "127.0.0.1", "x-forwarded-for": "127.0.0.1"},
        )

        async def _call_next(_req):
            return SimpleNamespace(status_code=200)

        resp = asyncio.run(lan_access_guard_middleware(fake_req, _call_next))
        assert resp.status_code == 403

    def test_trusted_proxy_with_approved_lan_client_allowed(self, monkeypatch):
        monkeypatch.setenv("CEWS_TRUSTED_PROXY_CIDRS", "172.20.0.0/16")
        ok, reason = is_client_ip_allowed("172.20.0.3", policy=LAN_POLICY, forwarded_real_ip="192.168.110.42")
        assert ok is True and "192.168.110.0/24" in reason

    def test_trusted_proxy_with_unapproved_lan_client_blocked(self, monkeypatch):
        monkeypatch.setenv("CEWS_TRUSTED_PROXY_CIDRS", "172.20.0.0/16")
        ok, _ = is_client_ip_allowed("172.20.0.3", policy=LAN_POLICY, forwarded_real_ip="10.99.0.5")
        assert ok is False
