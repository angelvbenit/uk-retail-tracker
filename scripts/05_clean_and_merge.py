"""
Script 05: Clean and Merge All Data Sources
Joins Retail Sales + CPI + HMRC Imports + HGV into one master table.
Output: data/processed/master_supply_chain.csv
        data/exports/master_supply_chain.csv
"""

import pandas as pd
import numpy as np
import os

# ─── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED = os.path.join(PROJECT_ROOT, "data", "processed")
EXPORTS   = os.path.join(PROJECT_ROOT, "data", "exports")

os.makedirs(EXPORTS, exist_ok=True)


# ─── Step 1: Load all 4 files ─────────────────────────────────────────────────

def load_all():
    print("Loading all 4 source files...")

    retail = pd.read_csv(os.path.join(PROCESSED, "ons_retail_clean.csv"),    parse_dates=["date"])
    cpi    = pd.read_csv(os.path.join(PROCESSED, "cpi_clean.csv"),            parse_dates=["date"])
    hmrc   = pd.read_csv(os.path.join(PROCESSED, "hmrc_imports_monthly.csv"), parse_dates=["date"])
    hgv    = pd.read_csv(os.path.join(PROCESSED, "hgv_clean.csv"),            parse_dates=["date"])

    print(f"  Retail : {retail.shape}")
    print(f"  CPI    : {cpi.shape}")
    print(f"  HMRC   : {hmrc.shape}")
    print(f"  HGV    : {hgv.shape}")

    return retail, cpi, hmrc, hgv


# ─── Step 2: Build the monthly spine ─────────────────────────────────────────
# The spine is every month from Jan 2015 to Dec 2024.
# Every other table gets left-joined onto this so there are no gaps.

def build_spine():
    dates = pd.date_range(start="2015-01-01", end="2024-12-01", freq="MS")
    spine = pd.DataFrame({"date": dates})
    spine["year"]       = spine["date"].dt.year
    spine["month"]      = spine["date"].dt.month
    spine["month_name"] = spine["date"].dt.strftime("%B")
    spine["quarter"]    = spine["date"].dt.quarter
    spine["year_month"] = spine["date"].dt.strftime("%Y-%m")

    # ── UK event flags (used in Power BI for annotations) ──
    spine["post_brexit"]      = (spine["date"] >= "2021-01-01").astype(int)
    spine["covid_period"]     = ((spine["date"] >= "2020-03-01") & (spine["date"] <= "2021-03-01")).astype(int)
    spine["hgv_crisis"]       = ((spine["date"] >= "2021-06-01") & (spine["date"] <= "2022-03-01")).astype(int)
    spine["ukraine_war"]      = ((spine["date"] >= "2022-02-01") & (spine["date"] <= "2022-12-01")).astype(int)
    spine["energy_crisis"]    = ((spine["date"] >= "2022-06-01") & (spine["date"] <= "2023-03-01")).astype(int)

    spine["era"] = "Pre-COVID"
    spine.loc[spine["date"] >= "2020-03-01", "era"] = "COVID Period"
    spine.loc[spine["date"] >= "2021-01-01", "era"] = "Post-Brexit / Recovery"
    spine.loc[spine["date"] >= "2022-02-01", "era"] = "High Inflation"
    spine.loc[spine["date"] >= "2023-06-01", "era"] = "Stabilisation"

    print(f"\nSpine built: {len(spine)} months ({spine['date'].min().date()} to {spine['date'].max().date()})")
    return spine


# ─── Step 3: Prepare each table for merging ───────────────────────────────────

def prep_retail(retail):
    # Keep only the columns we need — drop year/month (spine provides these)
    cols = ["date", "retail_total_volume", "retail_food_volume",
            "retail_non_food_volume", "retail_online_volume"]
    df = retail[cols].copy()

    # Filter to spine date range only
    df = df[(df["date"] >= "2015-01-01") & (df["date"] <= "2024-12-01")]
    return df


def prep_cpi(cpi):
    cols = ["date", "cpi_food_nonalcoholic", "cpi_clothing_footwear", "cpi_transport"]
    df = cpi[cols].copy()
    df = df[(df["date"] >= "2015-01-01") & (df["date"] <= "2024-12-01")]
    return df


def prep_hmrc(hmrc):
    # Keep raw import value columns + the 3 YoY columns most useful for scoring
    value_cols = [
        "date",
        "imports_food_and_live_animals",
        "imports_machinery_and_transport",
        "imports_manufactured_goods",
        "imports_chemicals",
        "imports_mineral_fuels",
        "imports_food_and_live_animals_yoy",
        "imports_machinery_and_transport_yoy",
        "imports_manufactured_goods_yoy"
    ]
    # Only keep columns that actually exist
    existing = [c for c in value_cols if c in hmrc.columns]
    df = hmrc[existing].copy()
    df = df[(df["date"] >= "2015-01-01") & (df["date"] <= "2024-12-01")]
    return df


def prep_hgv(hgv):
    df = hgv[["date", "total_hgv_licensed"]].copy()
    df = df[(df["date"] >= "2015-01-01") & (df["date"] <= "2024-12-01")]
    return df


# ─── Step 4: Merge everything onto the spine ─────────────────────────────────

def merge_all(spine, retail, cpi, hmrc, hgv):
    print("\nMerging all tables onto spine...")

    master = spine.copy()

    master = master.merge(retail, on="date", how="left")
    print(f"  After retail join  : {master.shape}")

    master = master.merge(cpi, on="date", how="left")
    print(f"  After CPI join     : {master.shape}")

    master = master.merge(hmrc, on="date", how="left")
    print(f"  After HMRC join    : {master.shape}")

    master = master.merge(hgv, on="date", how="left")
    print(f"  After HGV join     : {master.shape}")

    return master


# ─── Step 5: Calculate derived columns ───────────────────────────────────────
# These are the calculated fields that the disruption score (script 06) will use.

def calculate_derived(df):
    print("\nCalculating derived columns...")

    # ── Retail: deviation from 12-month rolling average ──
    # If actual sales drop below the rolling average, that signals disruption.
    for col in ["retail_total_volume", "retail_food_volume", "retail_non_food_volume"]:
        if col in df.columns:
            rolling_avg = df[col].rolling(window=12, min_periods=6).mean()
            df[f"{col}_rolling_avg"] = rolling_avg
            # Deviation in percentage points: negative = below trend = bad
            df[f"{col}_deviation"] = ((df[col] - rolling_avg) / rolling_avg * 100).round(4)

    # ── CPI: year-on-year % change ──
    for col in ["cpi_food_nonalcoholic", "cpi_clothing_footwear", "cpi_transport"]:
        if col in df.columns:
            df[f"{col}_yoy"] = (df[col].pct_change(periods=12) * 100).round(4)

    # ── CPI: food inflation premium over transport (proxy for general goods) ──
    if "cpi_food_nonalcoholic_yoy" in df.columns and "cpi_transport_yoy" in df.columns:
        df["cpi_food_premium"] = (df["cpi_food_nonalcoholic_yoy"] - df["cpi_transport_yoy"]).round(4)

    # ── HGV: year-on-year change ──
    if "total_hgv_licensed" in df.columns:
        df["hgv_yoy"] = (df["total_hgv_licensed"].pct_change(periods=12) * 100).round(4)
        # Flag: is HGV count below the 2019 average (pre-crisis baseline)?
        baseline_2019 = df[df["year"] == 2019]["total_hgv_licensed"].mean()
        df["hgv_below_2019"] = (df["total_hgv_licensed"] < baseline_2019).astype(int)
        print(f"  HGV 2019 baseline: {baseline_2019:,.0f} vehicles")

    # ── HMRC: fill small nulls in import columns using linear interpolation ──
    import_cols = [c for c in df.columns if c.startswith("imports_") and "_yoy" not in c]
    for col in import_cols:
        df[col] = df[col].interpolate(method="linear", limit=3)

    return df


# ─── Step 6: Final quality check ─────────────────────────────────────────────

def quality_check(df):
    print("\n" + "="*50)
    print("QUALITY CHECK")
    print("="*50)
    print(f"Shape       : {df.shape}")
    print(f"Date range  : {df['date'].min().date()} to {df['date'].max().date()}")
    print(f"Columns     : {df.columns.tolist()}")
    print(f"\nNull counts (columns with any nulls):")
    nulls = df.isnull().sum()
    nulls = nulls[nulls > 0]
    if len(nulls) == 0:
        print("  None — all columns fully populated.")
    else:
        for col, count in nulls.items():
            print(f"  {col}: {count}")

    print(f"\nEra breakdown:")
    print(df.groupby("era")["date"].count().rename("months").to_string())

    print(f"\nSample rows:")
    print(df[["date","era","retail_total_volume","cpi_food_nonalcoholic",
              "imports_food_and_live_animals","total_hgv_licensed"]].tail(6).to_string(index=False))


# ─── Step 7: Save ────────────────────────────────────────────────────────────

def save(df):
    p1 = os.path.join(PROCESSED, "master_supply_chain.csv")
    p2 = os.path.join(EXPORTS,   "master_supply_chain.csv")
    df.to_csv(p1, index=False)
    df.to_csv(p2, index=False)
    print(f"\nSaved to: {p1}")
    print(f"Saved to: {p2}")


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("="*60)
    print("Script 05: Clean and Merge")
    print("="*60)

    retail, cpi, hmrc, hgv = load_all()
    spine   = build_spine()
    retail  = prep_retail(retail)
    cpi     = prep_cpi(cpi)
    hmrc    = prep_hmrc(hmrc)
    hgv     = prep_hgv(hgv)
    master  = merge_all(spine, retail, cpi, hmrc, hgv)
    master  = calculate_derived(master)
    quality_check(master)
    save(master)

    print("\nSUCCESS: Script 05 complete. Run script 06 next.")