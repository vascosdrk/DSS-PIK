from pathlib import Path

from pandas import Series, read_csv
from scipy.stats import gamma

from spei.si import spi


def load_example_precipitation() -> Series:
    csv_path = Path(__file__).parent.parent / "docs" / "data" / "example.csv"
    if csv_path.exists():
        example = read_csv(
            csv_path,
            index_col=0,
            sep=";",
            parse_dates=True,
            date_format="%Y-%m-%d %H.%M.%S",
        )
        return example.iloc[:, 0].astype(float)
    else:
        # Fallback to packaged test data
        b11_path = Path(__file__).parent / "data" / "B11C0329_EAGMARYP.csv"
        df = read_csv(b11_path, index_col=0, sep=";", parse_dates=True)
        return df["Prec [m/d] 081_JOURE"].dropna().multiply(1e3).astype(float)



def test_spi_centroid_vs_median_example_csv() -> None:
    prec = load_example_precipitation()
    prec = prec.rename("precipitation")

    spi_centroid = spi(
        prec,
        dist=gamma,
        fit_freq="MS",
        prob_zero=True,
        method="centroid",
    )
    spi_median = spi(
        prec,
        dist=gamma,
        fit_freq="MS",
        prob_zero=True,
        method="median",
    )

    assert len(spi_centroid) == len(spi_median)
    assert not spi_centroid.equals(spi_median), (
        "SPI centroid and M-SPI median should differ for skewed example data"
    )
    assert spi_centroid.index.equals(spi_median.index)
    assert spi_centroid.notna().all() and spi_median.notna().all()
    assert any(spi_centroid != spi_median)
