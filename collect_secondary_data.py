
from __future__ import annotations

import requests
import pandas as pd
import numpy as np
from pathlib import Path

COUNTRY = "VNM"
START_YEAR = 1995
REQUESTED_END_YEAR = 2025

GDP_IN_BILLIONS = True
ROUND_DIGITS = 3

OUTPUT_DIR = Path(".")
OUTPUT_ANNUAL_CSV = OUTPUT_DIR / "secondary_data_annual.csv"
OUTPUT_ANNUAL_XLSX = OUTPUT_DIR / "secondary_data_annual.xlsx"
OUTPUT_QUARTERLY_CSV = OUTPUT_DIR / "secondary_data_cleaned.csv"
OUTPUT_QUARTERLY_XLSX = OUTPUT_DIR / "secondary_data_cleaned.xlsx"

INDICATOR_MAP = {
    "NY.GDP.MKTP.CD": "GDP_Raw",
    "FP.CPI.TOTL.ZG": "Inflation",
    "FR.INR.LEND": "Interest_Rate",
    "BX.KLT.DINV.WD.GD.ZS": "FDI_pct_GDP",
    "NE.GDI.TOTL.ZS": "Investment_pct_GDP",
    "NE.EXP.GNFS.ZS": "Export_pct_GDP",
    "SL.UEM.TOTL.ZS": "Unemployment_Rate",
    "NE.CON.GOVT.ZS": "Gov_Spending_pct_GDP",
    "NY.GDP.MKTP.KD.ZG": "GDP_Growth",
}

FINAL_COLUMNS = [
    "Year",
    "GDP_Raw",
    "Inflation",
    "Interest_Rate",
    "FDI_pct_GDP",
    "Investment_pct_GDP",
    "Export_pct_GDP",
    "Unemployment_Rate",
    "Gov_Spending_pct_GDP",
    "GDP_Growth",
]


def fetch_world_bank_indicators(
    country: str,
    indicator_map: dict[str, str],
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    indicators = ";".join(indicator_map.keys())
    url = (
        f"https://api.worldbank.org/v2/country/{country}/indicator/{indicators}"
        f"?source=2&format=json&per_page=20000"
    )

    response = requests.get(url, timeout=60)
    response.raise_for_status()

    payload = response.json()
    if not isinstance(payload, list) or len(payload) < 2:
        raise ValueError("World Bank API trả về dữ liệu không đúng định dạng.")

    rows = []
    for item in payload[1]:
        year = item.get("date")
        indicator = item.get("indicator", {}).get("id")
        value = item.get("value")

        if year is None or indicator is None:
            continue

        try:
            year = int(year)
        except Exception:
            continue

        if start_year <= year <= end_year:
            rows.append(
                {
                    "Year": year,
                    "indicator": indicator,
                    "value": value,
                }
            )

    if not rows:
        raise ValueError("Không lấy được dữ liệu từ World Bank trong khoảng năm đã chọn.")

    df = pd.DataFrame(rows)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    df = (
        df.pivot_table(index="Year", columns="indicator", values="value", aggfunc="first")
        .reset_index()
        .rename(columns=indicator_map)
    )

    for col in FINAL_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan

    df = df[FINAL_COLUMNS].sort_values("Year").reset_index(drop=True)

    if GDP_IN_BILLIONS:
        df["GDP_Raw"] = df["GDP_Raw"] / 1e9

    return df


def linear_extrapolate_by_time(series: pd.Series, target_index: pd.DatetimeIndex) -> pd.Series:
    s = series.copy()
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()

    valid = s.dropna()
    out = pd.Series(index=target_index, dtype=float)

    if len(valid) == 0:
        return out

    if len(valid) == 1:
        out[:] = float(valid.iloc[0])
        return out

    all_index = valid.index.union(target_index).sort_values()
    temp = valid.reindex(all_index).astype(float)
    temp = temp.interpolate(method="time", limit_area="inside")
    out = temp.reindex(target_index).astype(float)

    first_idx, second_idx = valid.index[0], valid.index[1]
    last_idx, prev_idx = valid.index[-1], valid.index[-2]
    first_val, second_val = float(valid.iloc[0]), float(valid.iloc[1])
    last_val, prev_val = float(valid.iloc[-1]), float(valid.iloc[-2])

    first_days = max((second_idx - first_idx).days, 1)
    last_days = max((last_idx - prev_idx).days, 1)

    first_slope = (second_val - first_val) / first_days
    last_slope = (last_val - prev_val) / last_days

    for idx in out.index:
        if pd.isna(out.loc[idx]):
            if idx < first_idx:
                out.loc[idx] = first_val - first_slope * (first_idx - idx).days
            elif idx > last_idx:
                out.loc[idx] = last_val + last_slope * (idx - last_idx).days

    return out


def repair_artificial_trailing_flats(
    quarterly: pd.DataFrame,
    annual: pd.DataFrame,
    value_columns: list[str],
) -> pd.DataFrame:
    fixed = quarterly.copy()

    for col in value_columns:
        annual_valid = annual[col].dropna()
        if len(annual_valid) < 2:
            continue

        last_real_idx = annual_valid.index[-1]
        prev_real_idx = annual_valid.index[-2]
        last_real_val = float(annual_valid.iloc[-1])
        prev_real_val = float(annual_valid.iloc[-2])

        days = max((last_real_idx - prev_real_idx).days, 1)
        slope = (last_real_val - prev_real_val) / days

        series = fixed[col].astype(float).copy()
        if len(series) < 2:
            continue

        tail_value = float(series.iloc[-1])
        start_pos = len(series) - 1
        while start_pos > 0 and np.isclose(series.iloc[start_pos - 1], tail_value, equal_nan=False):
            start_pos -= 1

        if start_pos == len(series) - 1:
            continue

        tail_dates = fixed.index[start_pos:]
        if len(tail_dates) < 2:
            continue

        if tail_dates[0] < last_real_idx:
            continue

        for dt in tail_dates:
            delta_days = (dt - last_real_idx).days
            fixed.loc[dt, col] = last_real_val + slope * delta_days

    return fixed


def annual_to_quarterly_like_mock(
    annual_df: pd.DataFrame,
    start_year: int,
    requested_end_year: int,
) -> pd.DataFrame:
    annual = annual_df.copy()
    annual["Year"] = pd.to_datetime(annual["Year"].astype(str) + "-01-01")
    annual = annual.set_index("Year").sort_index()

    quarterly_index = pd.date_range(
        start=f"{start_year}-01-01",
        end=f"{requested_end_year}-01-01",
        freq="QS"
    )

    quarterly = pd.DataFrame(index=quarterly_index)

    value_columns = [c for c in annual.columns if c != "Year"]

    for col in value_columns:
        quarterly[col] = linear_extrapolate_by_time(annual[col], quarterly_index)

    quarterly = repair_artificial_trailing_flats(
        quarterly=quarterly,
        annual=annual,
        value_columns=value_columns,
    )

    quarterly = quarterly.reset_index().rename(columns={"index": "Year"})
    quarterly["Year"] = quarterly["Year"].dt.strftime("%Y-%m-%d")

    quarterly = quarterly[quarterly["Year"] >= f"{start_year}-04-01"]
    quarterly = quarterly[["Year"] + [c for c in FINAL_COLUMNS if c != "Year"]]

    num_cols = [c for c in quarterly.columns if c != "Year"]
    quarterly[num_cols] = quarterly[num_cols].round(ROUND_DIGITS)

    return quarterly.reset_index(drop=True)


def save_outputs(annual_df: pd.DataFrame, quarterly_df: pd.DataFrame) -> None:
    annual_to_save = annual_df.copy()
    annual_to_save = annual_to_save[FINAL_COLUMNS]
    num_cols_annual = [c for c in annual_to_save.columns if c != "Year"]
    annual_to_save[num_cols_annual] = annual_to_save[num_cols_annual].round(ROUND_DIGITS)

    annual_to_save.to_csv(OUTPUT_ANNUAL_CSV, index=False)
    annual_to_save.to_excel(OUTPUT_ANNUAL_XLSX, index=False)

    quarterly_df.to_csv(OUTPUT_QUARTERLY_CSV, index=False)
    quarterly_df.to_excel(OUTPUT_QUARTERLY_XLSX, index=False)


def main() -> None:
    annual_df = fetch_world_bank_indicators(
        country=COUNTRY,
        indicator_map=INDICATOR_MAP,
        start_year=START_YEAR,
        end_year=REQUESTED_END_YEAR,
    )

    quarterly_df = annual_to_quarterly_like_mock(
        annual_df=annual_df,
        start_year=START_YEAR,
        requested_end_year=REQUESTED_END_YEAR,
    )

    save_outputs(annual_df, quarterly_df)

    print("Đã tạo xong các file:")
    print(f"- {OUTPUT_ANNUAL_CSV}")
    print(f"- {OUTPUT_ANNUAL_XLSX}")
    print(f"- {OUTPUT_QUARTERLY_CSV}")
    print(f"- {OUTPUT_QUARTERLY_XLSX}")


if __name__ == "__main__":
    main()