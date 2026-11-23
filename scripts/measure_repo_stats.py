import os
import json

def get_dir_stats(path):
    total_size = 0
    total_files = 0
    subdirs = {}
    
    for root, dirs, files in os.walk(path):
        rel = os.path.relpath(root, path)
        top_level = rel.split(os.sep)[0] if rel != '.' else '.'
        
        for f in files:
            fp = os.path.join(root, f)
            try:
                sz = os.path.getsize(fp)
            except OSError:
                sz = 0
            total_size += sz
            total_files += 1
            
            if top_level not in subdirs:
                subdirs[top_level] = {'files': 0, 'size': 0}
            subdirs[top_level]['files'] += 1
            subdirs[top_level]['size'] += sz
            
    return total_size, total_files, subdirs

total_size, total_files, subdirs = get_dir_stats('.')
print(f"Total Size: {total_size / (1024*1024):.2f} MB ({total_size:,} bytes)")
print(f"Total Files: {total_files}")
print("\nTop Directories:")
for d, s in sorted(subdirs.items(), key=lambda x: x[1]['size'], reverse=True):
    print(f"  {d:25s}: {s['files']:6d} files, {s['size'] / (1024*1024):8.2f} MB")

with open('reports/maintenance/repo_stats_pre_cleanup.json', 'w') as out:
    json.dump({'total_size': total_size, 'total_files': total_files, 'subdirs': subdirs}, out, indent=2)

