# PHASE 6.14 — DEPENDENCY LOCK & ENVIRONMENT REPRODUCIBILITY
**Sistem:** DSS-PIK BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang  
**Target Python Runtime:** Python `3.12.10` (64-bit AMD64, kompatibel `3.10` – `3.12`)  

---

## 1. Strategi Penguncian Dependency (`requirements.txt` vs `requirements-lock.txt`)
- **[`requirements.txt`](file:///c:/LATSAR/ASLI2/requirements.txt)** (`20` paket utama): Mendefinisikan rentang versi minimum kompatibel untuk paket langsung yang di-import oleh `backend/`, `config/`, `SPEI/src/`, `pipeline/`, dan `scripts/`.
- **[`requirements-lock.txt`](file:///c:/LATSAR/ASLI2/requirements-lock.txt)** (`45` paket terkunci): Mengunci versi eksak (`==`) seluruh dependency langsung maupun transitive dependency berdasarkan lingkungan yang telah lulus `29/29` regression test pada Python `3.12.10`.

## 2. Daftar Paket Inti Terkunci (`requirements-lock.txt`)
| Kategori | Paket & Versi Teruji |
|---|---|
| **Web Framework & ASGI** | `fastapi==0.162.0`, `starlette`, `uvicorn==0.54.0`, `pydantic==2.14.2`, `python-multipart==0.0.33` |
| **Database & Security** | `pymysql==1.2.3`, `bcrypt==5.0.0`, `python-dotenv==1.2.4` |
| **Data Science & SPI (`SPEI/src`)** | `pandas==3.1.0`, `numpy==2.5.4`, `scipy==1.18.1`, `pyarrow==26.0.1`, `joblib==1.6.0` |
| **GIS & Official Map Generator** | `geopandas==1.2.0`, `shapely==2.2.0`, `pyogrio`, `pyproj`, `Pillow==13.0.0`, `matplotlib` |
| **Excel, Validation & Process** | `openpyxl==3.1.5`, `jsonschema`, `psutil`, `packaging`, `requests==2.34.2`, `pytest==9.2.0` |

## 3. Integrasi `SPEI/src` Lokal
- Modul kalkulasi SPI (`SPEI/src/spei`) dimuat secara langsung melalui `sys.path.insert(0, str(PROJECT_ROOT / "SPEI" / "src"))` pada `backend/spi_calculation_worker.py` dan `backend/spi_distribution_registry.py`.
- Tidak memerlukan `pip install spei` dari PyPI internet karena kode sumber `SPEI/src` yang telah disesuaikan dengan distribusi BestDist BMKG sudah terbundel di dalam repository.

## 4. Kebutuhan Frontend (`Node.js` / `npm`)
- **Runtime Produksi LAN**: **TIDAK membutuhkan Node.js atau `node_modules/`**. Seluruh bundle produksi React + Leaflet + Cobalt Theme telah dikompilasi ke dalam `frontend/dist/` dan disajikan langsung oleh FastAPI (`CEWS_SERVE_FRONTEND=true`).
- **Rebuild Development**: Hanya jika kode `frontend/src/` diubah, diperlukan Node.js `v20+` / `v22+` dan npm `10+` (`npm --prefix frontend ci && npm --prefix frontend run build`).

