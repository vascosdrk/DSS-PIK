# Legacy Single-Container Docker Configurations (`v1.0.0`)

File di dalam folder ini adalah konfigurasi **single-container legacy** (FastAPI + SPA dalam satu container) yang dipertahankan semata-mata untuk referensi historis `v1.0.0`.

**Konfigurasi utama yang direkomendasikan untuk deployment server BMKG adalah `compose.yaml` di root repository** (arsitektur split 3-container: `frontend` Nginx -> `backend` FastAPI -> `mariadb` 11.4).
