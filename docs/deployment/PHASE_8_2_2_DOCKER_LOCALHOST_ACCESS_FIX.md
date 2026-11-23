# PHASE 8.2.2 — DOCKER LOCALHOST ACCESS FIX REPORT

**Project**: Decision Support System Peringatan Iklim (DSS-PIK) Kepulauan Riau  
**Date**: 2026-11-23  
**Status**: **COMPLETE & VERIFIED (42/42 TESTS PASSED, HOST `:18000` HTTP 200)**

---

## 1. Root Cause
- When a Windows/WSL2 host browser accesses `http://127.0.0.1:18000`, Docker's bridge NAT forwards the packet to `dss_pik_dev_app:8000` with source IP equal to the Docker bridge gateway (`172.19.0.1` on `dss_pik_dev_internal`).
- `lan_access_guard_middleware` (`backend/main.py` -> `backend/lan_firewall_service.py:is_client_ip_allowed`) rejected `172.19.0.1` with `HTTP 403` because `config/lan_access_policy.json` has `lan_enabled: false`.

---

## 2. Exact Implementation & Trusted Gateway Mechanism
- Added `detect_docker_host_gateway()` and `is_docker_local_only_mode()` in `backend/lan_firewall_service.py`:
  - Controlled exclusively by `CEWS_DOCKER_LOCAL_ONLY=true` (set only in `.env.docker` / `compose.yaml`; unset in native `.env`).
  - Dynamically reads the container's single exact IPv4 default gateway from Linux `/proc/net/route` (destination `00000000` -> `172.19.0.1`, cached once).
  - Allows **only** exact equality with that single private gateway IP (`docker_local_gateway:172.19.0.1`) — **never** the entire Docker subnet, **never** arbitrary Docker IPs, and **never** `X-Forwarded-For` headers.
  - `config/lan_access_policy.json` remains `lan_enabled: false`.
  - `compose.yaml` keeps host port strictly bound to `127.0.0.1:18000:8000` and MariaDB internal-only (`3306/tcp` not published).

---

## 3. Security & Regression Test Results (`42/42 PASSED`)
- **New Security Suite** (`test_phase822_docker_local_security.py`): **6/6 PASSED** (verified both on native Windows `.venv` and inside `dss_pik_dev_app`):
  - Native mode: loopback allowed; Docker gateway & LAN IPs blocked (`403`).
  - Docker local-only mode: exact Docker gateway allowed; other Docker subnet IPs (`172.18.0.2`, `172.18.0.254`), LAN IPs, and public IPs blocked (`403`); spoofed `X-Forwarded-For: 127.0.0.1` blocked (`403`); `lan_enabled` remains `false`.
- **Full Regression Suite Inside `dss_pik_dev_app`**: **42 passed in 75.81s** (`36` existing + `6` new security tests; `0` failed, `0` skipped).

---

## 4. Verified HTTP Endpoints (From Windows Host)
| Endpoint | Status | Result |
|---|---|---|
| `GET http://127.0.0.1:18000/health` | **HTTP 200** | `{"status":"ok","service":"cews-api","database":"connected"}` |
| `GET http://127.0.0.1:18000/` | **HTTP 200** | `1,370` bytes (`id="root"` present) |
| `GET http://127.0.0.1:18000/assets/index-BRK1kGL_.js` | **HTTP 200** | `692,775` bytes |
| `GET http://127.0.0.1:18000/assets/index-C4PvWgH1.css` | **HTTP 200** | `202,521` bytes |
| `GET http://127.0.0.1:18000/api/v1/geo/layers/kabkot` | **HTTP 200** | `1,013,227` bytes |
| `GET http://127.0.0.1:8000/health` (Native) | **HTTP 200** | `{"status":"ok","service":"cews-api","database":"connected"}` |

---

## 5. Database Integrity & Native Application Health
- Only `dss_pik_dev_app` was recreated (`docker compose -p dss-pik-dev --env-file .env.docker up -d --no-deps --build app`).
- `dss_pik_dev_mariadb` remained continuously `Up 2 hours (healthy)` with all persistent data intact (`stations=57`, `cews_rainfall_daily=287,189`, `cews_forecast_snapshot=3,244`, `cews_regional_warning_decisions=42`, `cews_regional_decision_audit_log=462`).
- Native Windows DSS-PIK (`:8000`) and native MariaDB remained completely untouched.
