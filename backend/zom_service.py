import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

from config.paths import PATH_STATION_METADATA, PROJECT_ROOT
from backend.period_service import get_active_period

ROOT_DIR = PROJECT_ROOT
_ZOM_GEOJSON_PATH = ROOT_DIR / "data" / "reference" / "boundaries" / "kepri_zom.geojson"
_ZOM_ANALYSIS_CACHE: Optional[Dict[str, Any]] = None


def get_zom_spatial_analysis(period_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Performs spatial join and climate indicator aggregation of the 57 master stations
    across the 14 Zona Musim (ZOM) polygons of Kepulauan Riau.
    
    Principles:
    - 56 stations fall directly inside the 14 ZOM polygons.
    - Station Stamet Tarempa (21050101a / 21050101A) is located on a coastal island point
      outside the simplified ZOM boundary, and is explicitly classified as:
      'Belum terpetakan / Tidak masuk poligon ZOM'.
    - Aggregates station count, station list, HTH statistics, warning distribution,
      and seasonal characteristics (AMH, AMK, Puncak MH, Puncak MK) per ZOM.
    """
    if not _ZOM_GEOJSON_PATH.exists():
        raise FileNotFoundError(f"File layer Zona Musim tidak ditemukan di {_ZOM_GEOJSON_PATH}")

    # Load 57 master stations
    meta_df = pd.read_parquet(PATH_STATION_METADATA)
    meta_df["station_id_upper"] = meta_df["station_id"].astype(str).str.strip().str.upper()

    # Load current warning / snapshot data for current period to get real-time indicators
    from backend.main import get_period_snapshot
    snap = get_period_snapshot(period_id)
    period_label = snap.get("label") or period_id or "Dasarian Terpilih"

    stn_snap_map = {}
    for itm in snap.get("items", []):
        sid = str(itm.get("station_id", "")).strip().upper()
        stn_snap_map[sid] = itm

    # Load ZOM GeoJSON
    zom_gdf = gpd.read_file(_ZOM_GEOJSON_PATH)

    # Convert stations to GeoDataFrame
    points = [Point(float(r["longitude"]), float(r["latitude"])) for _, r in meta_df.iterrows()]
    stns_gdf = gpd.GeoDataFrame(meta_df.copy(), geometry=points, crs="EPSG:4326")

    # Spatial join (within)
    joined = gpd.sjoin(stns_gdf, zom_gdf[["NO_ZOM", "ZOM", "AMH", "AMK", "PUNCAK_MH", "PUNCAK_MK", "SIFAT_MH", "SIFAT_MK", "geometry"]], how="left", predicate="within")

    # Group stations by NO_ZOM
    zom_summary_list: List[Dict[str, Any]] = []

    for _, zom_row in zom_gdf.iterrows():
        nz = zom_row.get("NO_ZOM")
        zt = zom_row.get("ZOM") or "ZOM"
        amh = zom_row.get("AMH") or "—"
        amk = zom_row.get("AMK") or "—"
        pmh = zom_row.get("PUNCAK_MH") or "—"
        pmk = zom_row.get("PUNCAK_MK") or "—"
        smh = zom_row.get("SIFAT_MH") or "—"
        smk = zom_row.get("SIFAT_MK") or "—"

        stns_in_zom = joined[joined["NO_ZOM"] == nz]
        stn_items = []
        hth_vals = []
        warnings_count = {"WASPADA": 0, "SIAGA": 0, "AWAS": 0, "AMAN": 0, "INCOMPLETE": 0}

        for _, srow in stns_in_zom.iterrows():
            sid = srow["station_id_upper"]
            sname = srow["station_name"]
            kab = srow["regency"]
            snap_item = stn_snap_map.get(sid, {})

            hth = snap_item.get("hth_days_current") if "hth_days_current" in snap_item else snap_item.get("hth_days")
            w_lvl = str(snap_item.get("warning_level") or "NORMAL").upper()
            if "AWAS" in w_lvl:
                warnings_count["AWAS"] += 1
            elif "SIAGA" in w_lvl:
                warnings_count["SIAGA"] += 1
            elif "WASPADA" in w_lvl:
                warnings_count["WASPADA"] += 1
            elif "INCOMPLETE" in w_lvl or "PARSIAL" in w_lvl:
                warnings_count["INCOMPLETE"] += 1
            else:
                warnings_count["AMAN"] += 1

            if hth is not None:
                try:
                    hth_vals.append(int(hth))
                except Exception:
                    pass

            stn_items.append({
                "station_id": sid,
                "station_name": sname,
                "kabupaten": kab,
                "hth_days": hth,
                "warning_level": w_lvl,
                "is_arg": srow.get("is_arg", False),
            })

        avg_hth = round(sum(hth_vals) / len(hth_vals), 1) if hth_vals else None
        max_hth = max(hth_vals) if hth_vals else None

        zom_summary_list.append({
            "no_zom": nz,
            "zom_type": zt,
            "amh": amh,
            "amk": amk,
            "puncak_mh": pmh,
            "puncak_mk": pmk,
            "sifat_mh": smh,
            "sifat_mk": smk,
            "station_count": len(stn_items),
            "stations": stn_items,
            "hth_statistics": {
                "count": len(hth_vals),
                "avg_hth": avg_hth,
                "max_hth": max_hth,
            },
            "warning_distribution": warnings_count,
        })

    # Find unmapped stations (e.g. Stamet Tarempa 21050101a)
    unmapped_rows = joined[joined["NO_ZOM"].isnull()]
    unmapped_items = []
    for _, srow in unmapped_rows.iterrows():
        sid = srow["station_id_upper"]
        sname = srow["station_name"]
        kab = srow["regency"]
        snap_item = stn_snap_map.get(sid, {})
        hth = snap_item.get("hth_days_current") if "hth_days_current" in snap_item else snap_item.get("hth_days")
        w_lvl = str(snap_item.get("warning_level") or "NORMAL").upper()

        unmapped_items.append({
            "station_id": sid,
            "station_name": sname,
            "kabupaten": kab,
            "hth_days": hth,
            "warning_level": w_lvl,
            "is_arg": srow.get("is_arg", False),
            "status_note": "Belum terpetakan / Tidak masuk poligon ZOM (Lokasi pesisir kepulauan)",
            "official_nozom_ref": srow.get("NOZOM_PROV", "KEPRI_12"),
        })

    return {
        "status": "SUCCESS",
        "period_id": snap.get("period_id", period_id),
        "period_label": period_label,
        "total_zom_polygons": len(zom_gdf),
        "total_master_stations": len(meta_df),
        "mapped_stations_count": len(joined[joined["NO_ZOM"].notnull()]),
        "unmapped_stations_count": len(unmapped_items),
        "zom_polygons": zom_summary_list,
        "unmapped_stations": unmapped_items,
    }
