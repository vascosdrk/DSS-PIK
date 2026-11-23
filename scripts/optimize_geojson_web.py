import geopandas as gpd
from pathlib import Path

out_dir = Path("data/reference/boundaries")

for name in ["kepri_kabkot", "kepri_kecamatan", "kepri_zom"]:
    src = out_dir / f"{name}.geojson"
    if src.exists():
        gdf = gpd.read_file(src)
        # Simplify slightly (0.0005 deg is ~50m, perfect for province-wide web map)
        gdf["geometry"] = gdf["geometry"].simplify(tolerance=0.0005, preserve_topology=True)
        dst = out_dir / f"{name}.geojson"
        gdf.to_file(dst, driver="GeoJSON")
        print(f"Optimized {dst.name}: size = {dst.stat().st_size / 1024:.1f} KB")

print("Done optimizing GeoJSON layers.")

