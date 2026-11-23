import geopandas as gpd
from shapely.ops import transform
from pathlib import Path

out_dir = Path("data/reference/boundaries")
out_dir.mkdir(parents=True, exist_ok=True)

print("Reading Kepri__ZOM9120.shp...")
gdf_zom = gpd.read_file("data/reference/PETA/Kepri__ZOM9120.shp")

def to_2d(geom):
    return transform(lambda x, y, z=None: (x, y), geom)

gdf_zom["geometry"] = gdf_zom["geometry"].apply(to_2d)
gdf_zom["geometry"] = gdf_zom["geometry"].simplify(tolerance=0.0005, preserve_topology=True)

dst = out_dir / "kepri_zom.geojson"
gdf_zom.to_file(dst, driver="GeoJSON")
print(f"Exported {dst.name}: size = {dst.stat().st_size / 1024:.1f} KB, count = {len(gdf_zom)}")

