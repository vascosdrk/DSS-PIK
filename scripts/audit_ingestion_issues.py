import sys
sys.path.insert(0, '.')
import os
import pymysql
import pandas as pd
import json

from backend.data_service import get_spi_data, get_probability_data, get_daily_rainfall_data

print("=== 1. AUDIT SPI DATA RETRIEVAL (data_service.py) ===")
# Check SPI Bulanan
try:
    res_bul = get_spi_data(timescale='1M', period_id='2025-12', page=1, page_size=10)
    print("SPI 1M (Bulanan):")
    print(f"  Available Periods ({len(res_bul.get('available_periods', []))}): {res_bul.get('available_periods', [])[:10]}...")
    print(f"  Selected Period: {res_bul.get('period_id')}")
    print(f"  Total Stations: {res_bul.get('total')}")
    print(f"  Sample Item: {res_bul.get('items', [])[:2]}")
except Exception as e:
    print(f"  Error SPI 1M: {e}")

# Check SPI Dasarian 30D
try:
    res_das = get_spi_data(timescale='30D', period_id='2026-10-das1', page=1, page_size=10)
    print("\nSPI 30D (Dasarian):")
    print(f"  Available Periods ({len(res_das.get('available_periods', []))}): {res_das.get('available_periods', [])[-10:]}...")
    print(f"  Selected Period: {res_das.get('period_id')}")
    print(f"  Sample Item: {res_das.get('items', [])[:2]}")
except Exception as e:
    print(f"  Error SPI 30D: {e}")

# Check SPI Harian
try:
    res_har = get_spi_data(timescale='30D_HARIAN', period_id='2026-10-01', page=1, page_size=10)
    print("\nSPI Harian 30D:")
    print(f"  Available Periods ({len(res_har.get('available_periods', []))}): {res_har.get('available_periods', [])[-10:]}...")
    print(f"  Selected Period: {res_har.get('period_id')}")
    print(f"  Sample Item: {res_har.get('items', [])[:2]}")
except Exception as e:
    print(f"  Error SPI Harian: {e}")

print("\n=== 2. AUDIT PROBABILITY DATA RETRIEVAL (data_service.py) ===")
try:
    res_prob = get_probability_data(period_id='2026-11-das1', page=1, page_size=10)
    print("Probability 2026-11-das1:")
    print(f"  Available Vintages: {res_prob.get('available_vintages')}")
    print(f"  Selected Issue Date: {res_prob.get('selected_issue_date')}")
    print(f"  Total Items: {res_prob.get('total')}")
    print(f"  Sample Item: {res_prob.get('items', [])[:2]}")
except Exception as e:
    print(f"  Error Probability: {e}")

print("\n=== 3. AUDIT CH DATA RETRIEVAL (DailyRainfallTable baseline) ===")
try:
    res_ch = get_daily_rainfall_data(period_id='2026-10-das1', page=1, page_size=5)
    print("CH 2026-10-das1:")
    print(f"  Period ID: {res_ch.get('period_id')}")
    print(f"  Total Items: {res_ch.get('total')}")
    print(f"  Sample Item: {res_ch.get('items', [])[:1]}")
except Exception as e:
    print(f"  Error CH: {e}")

