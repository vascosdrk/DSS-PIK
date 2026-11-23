"""
Phase 8.2.2 — Automated Security Tests for CEWS_DOCKER_LOCAL_ONLY & LAN Access Guard.

Verifies:
A. Native mode (CEWS_DOCKER_LOCAL_ONLY unset/false):
   - Loopback (127.0.0.1, ::1) allowed.
   - Docker gateway IP (e.g. 172.18.0.1) and LAN IPs blocked (403) when lan_enabled=False.
B. Docker local-only mode (CEWS_DOCKER_LOCAL_ONLY=true):
   - Verified exact Docker host gateway IP allowed.
   - Other IPs in the same Docker subnet (e.g. 172.18.0.2, 172.18.0.99) remain blocked (403).
   - Arbitrary remote LAN/public IPs remain blocked (403).
   - Arbitrary X-Forwarded-For headers cannot bypass the guard (middleware uses request.client.host only).
   - lan_enabled remains False.
"""

import asyncio
from types import SimpleNamespace
import pytest

from backend.lan_firewall_service import is_client_ip_allowed, load_lan_policy
from backend.main import lan_access_guard_middleware


LOCKED_POLICY = {
    "lan_enabled": False,
    "approved_remote_addresses": [],
}


class TestNativeModeSecurity:
    def test_loopback_allowed_in_native_mode(self, monkeypatch):
        monkeypatch.delenv("CEWS_DOCKER_LOCAL_ONLY", raising=False)
        ok4, reason4 = is_client_ip_allowed("127.0.0.1", policy=LOCKED_POLICY, docker_gateway_override="172.18.0.1")
        ok6, reason6 = is_client_ip_allowed("::1", policy=LOCKED_POLICY, docker_gateway_override="172.18.0.1")
        assert ok4 is True and reason4 == "loopback"
        assert ok6 is True and reason6 == "loopback"

    def test_unapproved_lan_and_docker_gw_blocked_in_native_mode(self, monkeypatch):
        monkeypatch.delenv("CEWS_DOCKER_LOCAL_ONLY", raising=False)
        for ip in ("172.18.0.1", "192.168.110.50", "10.0.0.5", "8.8.8.8"):
            ok, _ = is_client_ip_allowed(ip, policy=LOCKED_POLICY, docker_gateway_override="172.18.0.1")
            assert ok is False, f"Expected {ip} to be blocked in native mode"


class TestDockerLocalOnlyModeSecurity:
    def test_exact_docker_gateway_allowed(self, monkeypatch):
        monkeypatch.setenv("CEWS_DOCKER_LOCAL_ONLY", "true")
        ok, reason = is_client_ip_allowed("172.18.0.1", policy=LOCKED_POLICY, docker_gateway_override="172.18.0.1")
        assert ok is True
        assert reason == "docker_local_gateway:172.18.0.1"

    def test_other_docker_subnet_and_remote_ips_blocked(self, monkeypatch):
        monkeypatch.setenv("CEWS_DOCKER_LOCAL_ONLY", "true")
        for ip in ("172.18.0.2", "172.18.0.254", "172.17.0.1", "192.168.1.20", "8.8.8.8"):
            ok, _ = is_client_ip_allowed(ip, policy=LOCKED_POLICY, docker_gateway_override="172.18.0.1")
            assert ok is False, f"Expected {ip} to remain blocked in Docker local-only mode"

    def test_x_forwarded_for_cannot_bypass_middleware(self, monkeypatch):
        monkeypatch.setenv("CEWS_DOCKER_LOCAL_ONLY", "true")
        fake_req = SimpleNamespace(
            client=SimpleNamespace(host="192.168.1.99"),
            headers={"x-forwarded-for": "127.0.0.1"},
        )

        async def _call_next(_req):
            return SimpleNamespace(status_code=200)

        resp = asyncio.run(lan_access_guard_middleware(fake_req, _call_next))
        assert resp.status_code == 403

    def test_lan_policy_file_remains_disabled(self):
        pol = load_lan_policy(use_cache=False)
        assert pol.get("lan_enabled") is False
