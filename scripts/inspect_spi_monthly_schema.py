import pandas as pd

df = pd.read_parquet('data/raw/spi/bulanan/SPI_monthly.parquet')
print("SPI_monthly.parquet shape:", df.shape)
print("Index:", type(df.index), df.index[:5])
print("Columns count:", len(df.columns))
print("Columns sample:", list(df.columns)[:5])
print("Sample values:\n", df.iloc[:3, :3])

