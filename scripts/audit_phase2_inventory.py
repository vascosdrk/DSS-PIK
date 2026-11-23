import os

print("=== TAMBAHAN DIRECTORY INVENTORY ===")
for root, dirs, files in os.walk('tambahan'):
    if files:
        print(f"\n[{root}] ({len(files)} files)")
        for f in sorted(files)[:10]:
            fp = os.path.join(root, f)
            print(f"  {f} ({os.path.getsize(fp):,} B)")
        if len(files) > 10:
            print(f"  ... and {len(files) - 10} more")

print("\n=== DATA/RAW DIRECTORY INVENTORY ===")
for root, dirs, files in os.walk('data/raw'):
    if files:
        print(f"\n[{root}] ({len(files)} files)")
        for f in sorted(files):
            fp = os.path.join(root, f)
            print(f"  {f} ({os.path.getsize(fp):,} B)")

