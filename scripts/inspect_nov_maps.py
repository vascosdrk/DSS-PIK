import os
from datetime import datetime

maps_dir = 'data/operational/maps'
nov_files = []
for f in os.listdir(maps_dir):
    fp = os.path.join(maps_dir, f)
    mtime = datetime.fromtimestamp(os.path.getmtime(fp)).strftime('%Y-%m-%d')
    if mtime >= '2026-11-01':
        nov_files.append((f, os.path.getsize(fp), mtime))

print(f"Total Nov files: {len(nov_files)}, size: {sum(s for _, s, _ in nov_files)/(1024*1024):.2f} MB")
# Let's inspect the names
prefixes = {}
for f, s, m in nov_files:
    pref = f.split('_')[0]
    prefixes[pref] = prefixes.get(pref, 0) + 1
print("Nov files by prefix:", prefixes)

# Check for scenario outputs and latest official files
key_files = [f for f, _, _ in nov_files if 'Scenario' in f or 'PETA_PDKM' in f or 'PETA_PDCHT' in f or 'latest' in f]
print("Key files sample:", key_files[:15])

