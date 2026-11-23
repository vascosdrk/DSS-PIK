# PHASE 6.12 — DEPENDENCY & PORTABILITY INVENTORY

---

## 1. Python Dependencies (`requirements.txt`)
| Paket | Fungsi Utama dalam DSS-PIK |
|---|---|
| `fastapi`, `uvicorn`, `pydantic`, `python-multipart` | REST API server, validasi skema, upload file Excel/Parquet, dan SPA static serving |
| `pymysql`, `python-dotenv`, `bcrypt` | Koneksi MariaDB (`cews_db`), pembacaan `.env`, dan autentikasi password + HMAC session |
| `pandas`, `numpy`, `scipy`, `pyarrow`, `joblib` | Mesin perhitungan SPI (`SPEI/src`), pembacaan/penulisan Parquet, dan eksekusi paralel |
| `openpyxl` | Parsing dan ekspor file Excel CH, SPI, Probabilitas ECMWF, dan `cews_rules.xlsx` |
| `Pillow`, `geopandas`, `shapely`, `matplotlib` | Rasterisasi poligon 59 kecamatan (`KEPRI.shp` / GeoJSON) dan generator peta resmi BMKG JPG/PDF |
| `jsonschema`, `psutil`, `packaging`, `requests`, `pytest` | Validasi skema JSON SIH3, supervisi proses `launcher.py`, dan regression test suite |

---

## 2. Frontend Dependencies (`frontend/package.json`)
- **Runtime**: `react` (`18.3.1`), `react-dom` (`18.3.1`), `leaflet` (`1.9.4`), `lucide-react` (`0.453.0`).
- **Build Tool**: `vite` (`5.4.21`), `@vitejs/plugin-react`.
- **Catatan Portabilitas**: Folder `frontend/dist/` sudah berisi bundle produksi yang bebas dari hardcode `localhost`/`127.0.0.1`, sehingga komputer server baru **tidak wajib** menjalankan Vite dev server maupun menyimpan `node_modules/` untuk keperluan runtime.

---

## 3. Portabilitas Path (`config/paths.py` & `pipeline/`)
- Seluruh path aplikasi di-resolve secara dinamis terhadap lokasi file menggunakan `Path(__file__).resolve().parent.parent` (`PROJECT_ROOT`).
- Enam script utilitas/pipeline lama yang sebelumnya memiliki referensi `F:\TNJ\...` (`pipeline/generate_hth_pipeline.py`, `pipeline/generate_spi_pipeline.py`, `pipeline/prepare_cews_data.py`, `scripts/utilities/audit_cews.py`, `scripts/utilities/check_cols.py`, `scripts/utilities/generate_audit_report.py`) telah direfaktor menggunakan `os.path.dirname(__file__)`.

