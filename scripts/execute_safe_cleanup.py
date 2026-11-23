import os
import shutil
import glob
import sys
from datetime import datetime

DRY_RUN = "--execute" not in sys.argv

print(f"=== DSS-PIK SAFE CLEANUP SCRIPT (MODE: {'DRY RUN' if DRY_RUN else 'EXECUTE'}) ===")

removed_files = []
removed_dirs = []
bytes_freed = 0

def safe_remove_file(path, reason):
    global bytes_freed
    if os.path.isfile(path) or os.path.islink(path):
        sz = os.path.getsize(path)
        bytes_freed += sz
        removed_files.append((path, sz, reason))
        if not DRY_RUN:
            try:
                os.remove(path)
            except Exception as e:
                print(f"[ERROR] Could not remove {path}: {e}")

def safe_remove_dir(path, reason):
    global bytes_freed
    if os.path.isdir(path):
        sz = 0
        for root, _, files in os.walk(path):
            for f in files:
                sz += os.path.getsize(os.path.join(root, f))
        bytes_freed += sz
        removed_dirs.append((path, sz, reason))
        if not DRY_RUN:
            try:
                shutil.rmtree(path)
            except Exception as e:
                print(f"[ERROR] Could not remove dir {path}: {e}")

# 1. Root zero-byte stray files
root_strays = ["console.error('Frontend", "console.log(i", "{"]
for rs in root_strays:
    if os.path.exists(rs):
        safe_remove_file(rs, "Accidental 0-byte root stray file")

# 2. Python __pycache__, .pytest_cache, .vite
for root, dirs, files in os.walk('.', topdown=False):
    # Avoid walking inside node_modules or .git
    if 'node_modules' in root or '.git' in root:
        continue
    for d in dirs:
        if d in ('__pycache__', '.pytest_cache', '.vite'):
            dp = os.path.join(root, d)
            safe_remove_dir(dp, f"Framework / bytecode cache ({d})")

# 3. Scratch directory cleanup
scratch_dir = 'scratch'
if os.path.isdir(scratch_dir):
    for item in os.listdir(scratch_dir):
        if item in ('.gitkeep', 'canonical_baseline_sha256.json'):
            continue
        ip = os.path.join(scratch_dir, item)
        if os.path.isfile(ip):
            safe_remove_file(ip, "Temporary test scratch file")
        elif os.path.isdir(ip):
            safe_remove_dir(ip, "Temporary test scratch directory")

    if not DRY_RUN:
        with open(os.path.join(scratch_dir, '.gitkeep'), 'w') as f:
            f.write('')

# 4. data/operational/maps/ cleanup
# - Remove pre-Nov-1 test renders (Oct 27-31)
# - Remove obsolete PETA_UNIFIED_* files from Nov 1
# - Preserve canonical PDKM, PDCHT, Scenarios, and latest official outputs
maps_dir = 'data/operational/maps'
if os.path.isdir(maps_dir):
    for item in os.listdir(maps_dir):
        ip = os.path.join(maps_dir, item)
        if not os.path.isfile(ip):
            continue
        
        # Check date
        mtime = datetime.fromtimestamp(os.path.getmtime(ip)).strftime('%Y-%m-%d')
        
        # Rule 1: pre-Nov-1 intermediate renders
        if mtime < '2026-11-01':
            safe_remove_file(ip, "Obsolete intermediate map render (Oct 2026 development iteration)")
            continue
            
        # Rule 2: PETA_UNIFIED_* renders
        if item.startswith('PETA_UNIFIED_'):
            safe_remove_file(ip, "Obsolete multi-hazard unified map render (concept deprecated in favor of separate PDKM/PDCHT)")
            continue

# 5. data/output/sih3/ cleanup
# Retain canonical baseline and latest runs, remove intermediate rapid-iteration test files
sih3_dir = 'data/output/sih3'
if os.path.isdir(sih3_dir):
    # Files to strictly keep:
    canonical_sih3 = {
        'sih3_regional_warning_latest.json',
        'sih3_warning_2026-09-das1_gabungan.json',
        'sih3_warning_2026-09-das2_gabungan.json',
        'sih3_warning_2026-09-das2_pdcht.json',
        'sih3_warning_2026-09-das2_pdkm.json',
        'sih3_warning_2026-11-das1_gabungan.json',
        'sih3_warning_2026-11-das1_pdcht.json',
    }
    
    # Get all PERINGATAN_DINI_KEPRI files sorted by time
    pdk_files = [f for f in os.listdir(sih3_dir) if f.startswith('PERINGATAN_DINI_KEPRI_')]
    pdk_files.sort()
    # Keep the latest 5 files for historical review
    keep_pdk = set(pdk_files[-5:])
    
    for item in os.listdir(sih3_dir):
        ip = os.path.join(sih3_dir, item)
        if not os.path.isfile(ip):
            continue
        if item in canonical_sih3 or item in keep_pdk:
            continue
        safe_remove_file(ip, "Redundant test iteration JSON export")

print(f"\n--- SUMMARY OF {'DRY RUN' if DRY_RUN else 'EXECUTION'} ---")
print(f"Files to remove: {len(removed_files)}")
print(f"Directories to remove: {len(removed_dirs)}")
print(f"Total storage to reclaim: {bytes_freed / (1024*1024):.2f} MB ({bytes_freed:,} bytes)")

import json
os.makedirs('reports/maintenance', exist_ok=True)
record_path = 'reports/maintenance/cleanup_preview.json' if DRY_RUN else 'reports/maintenance/cleanup_executed.json'
with open(record_path, 'w') as f:
    json.dump({
        'mode': 'dry-run' if DRY_RUN else 'executed',
        'timestamp': datetime.now().isoformat(),
        'total_bytes_freed': bytes_freed,
        'removed_files_count': len(removed_files),
        'removed_dirs_count': len(removed_dirs),
        'removed_files': removed_files,
        'removed_dirs': removed_dirs
    }, f, indent=2)
print(f"Saved record to {record_path}")

