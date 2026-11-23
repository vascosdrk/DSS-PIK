import os
import glob

# Daftar file spesifik yang sudah tidak digunakan
files_to_remove = [
    'station_mapping_referensi_additional.xlsx', # File referensi lama yang dilarang
    '~$mapping_tambahan.xlsx', # File temporary excel
    'cleanup_temp_files.py', # Script debug
    'compare_hth.py', # Script debug
    'debug_merge.py', # Script debug
    'inspect_mapping.py', # Script debug
    'investigate_hth_diff.py', # Script debug
    'pipeline_error.txt', # Log error lama
    'SPI_PIPELINE_AUDIT_REPORT.md' # Report lama
]

# Daftar pola file (opsional, untuk parquet lama)
# files_to_remove.extend(glob.glob('spi_analysis_*.parquet'))

def clean():
    count = 0
    for f in files_to_remove:
        if os.path.exists(f):
            try:
                os.remove(f)
                print(f"🗑️ Deleted: {f}")
                count += 1
            except Exception as e:
                print(f"❌ Failed to delete {f}: {e}")
    
    print(f"\n✅ Total file dibersihkan: {count}")

if __name__ == '__main__':
    clean()
