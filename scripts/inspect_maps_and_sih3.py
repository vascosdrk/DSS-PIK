import os
import glob
from datetime import datetime

print("--- data/operational/maps analysis ---")
maps_dir = 'data/operational/maps'
if os.path.exists(maps_dir):
    files = os.listdir(maps_dir)
    print(f"Total files in maps: {len(files)}")
    dates = {}
    prefixes = {}
    for f in files:
        fp = os.path.join(maps_dir, f)
        if os.path.isfile(fp):
            mtime = datetime.fromtimestamp(os.path.getmtime(fp)).strftime('%Y-%m-%d')
            dates[mtime] = dates.get(mtime, 0) + 1
            pref = f.split('_')[0] if '_' in f else 'other'
            prefixes[pref] = prefixes.get(pref, 0) + 1
    print("Files by modification date:")
    for d, c in sorted(dates.items()):
        print(f"  {d}: {c} files")
    print("Files by prefix:")
    for p, c in sorted(prefixes.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {p}: {c} files")

print("\n--- data/output/sih3 analysis ---")
sih3_dir = 'data/output/sih3'
if os.path.exists(sih3_dir):
    sfiles = os.listdir(sih3_dir)
    print(f"Total files in sih3: {len(sfiles)}")
    for f in sfiles:
        fp = os.path.join(sih3_dir, f)
        sz = os.path.getsize(fp)
        print(f"  {f} ({sz} bytes)")
else:
    print("sih3 dir does not exist")

