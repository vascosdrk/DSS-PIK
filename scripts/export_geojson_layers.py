import os
from pathlib import Path
import geopandas as gpd
from shapely.ops import transform

out_dir = Path("data/reference/boundaries")
out_dir.mkdir(parents=True, exist_ok=True)

# 1. Regency boundaries (Kabupaten / Kota)
print("Processing KEPRI.shp regency boundaries...")
gdf = gpd.read_file("data/reference/PETA/KEPRI.shp")

# Canonical names mapping
name_map = {
    "BINTAN": "BINTAN",
    "KARIMUN": "KARIMUN",
    "NATUNA": "NATUNA",
    "LINGGA": "LINGGA",
    "KEPULAUAN ANAMBAS": "KEPULAUAN ANAMBAS",
    "BATAM": "KOTA BATAM",
    "TANJUNGPINANG": "KOTA TANJUNGPINANG"
}

code_map = {
    "BINTAN": "21.01",
    "KARIMUN": "21.02",
    "NATUNA": "21.03",
    "LINGGA": "21.04",
    "KEPULAUAN ANAMBAS": "21.05",
    "BATAM": "21.71",
    "TANJUNGPINANG": "21.72"
}

kabkot = gdf.dissolve(by="KABKOT", as_index=False)
kabkot["region_code"] = kabkot["KABKOT"].map(code_map)
kabkot["region_name"] = kabkot["KABKOT"].map(name_map)
kabkot["name"] = kabkot["region_name"]
kabkot_out = kabkot[["region_code", "region_name", "name", "KABKOT", "geometry"]]
kabkot_out.to_file(out_dir / "kepri_kabkot.geojson", driver="GeoJSON")
print(f"Exported kepri_kabkot.geojson with {len(kabkot_out)} features.")

# 2. Kecamatan boundaries
print("Processing KEPRI.shp kecamatan boundaries...")
kec = gdf.dissolve(by=["KABKOT", "KECAMATAN"], as_index=False)
kec["region_name"] = kec["KABKOT"].map(name_map)
kec_out = kec[["region_name", "KABKOT", "KECAMATAN", "geometry"]]
kec_out.to_file(out_dir / "kepri_kecamatan.geojson", driver="GeoJSON")
print(f"Exported kepri_kecamatan.geojson with {len(kec_out)} features.")

# 3. ZOM boundaries
print("Processing Kepri__ZOM9120.shp boundaries...")
gdf_zom = gpd.read_file("data/reference/PETA/Kepri__ZOM9120.shp")
def to_2d(geom):
    return transform(lambda x, y, z=None: (x, y), geom)
gdf_zom["geometry"] = gdf_zom["geometry"].apply(to_2d)
gdf_zom.to_file(out_dir / "kepri_zom.geojson", driver="GeoJSON")
print(f"Exported kepri_zom.geojson with {len(gdf_zom)} features.")

print("All GeoJSON layers generated successfully!")

