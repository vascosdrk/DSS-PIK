import os
from datetime import datetime

maps_dir = 'data/operational/maps'
old_files = []
for f in os.listdir(maps_dir):
    fp = os.path.join(maps_dir, f)
    mtime = datetime.fromtimestamp(os.path.getmtime(fp)).strftime('%Y-%m-%d')
    if mtime < '2026-11-01':
        old_files.append((f, os.path.getsize(fp), mtime))

print(f"Total old files (before Nov 1): {len(old_files)}, total size: {sum(s for _, s, _ in old_files)/(1024*1024):.2f} MB")
for f, s, m in old_files[:20]:
    print(f"  {m} | {s:8d} B | {f}")

