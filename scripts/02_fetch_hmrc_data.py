"""
Script 02: Fetch & Process HMRC Trade Data via Checkpoints
API Docs: https://api.uktradeinfo.com
Reprocesses downloaded data using sitc_reference.csv to fix leading-zero mapping issues.
"""

import pandas as pd
import json
import os
import sys

# ─── Constants & Configurations ───────────────────────────────────────────────

START_YEAR = 2015
END_YEAR = 2024

SITC_LABELS = {
    0: "Food_and_Live_Animals",
    1: "Beverages_and_Tobacco",
    2: "Crude_Materials",
    3: "Mineral_Fuels",
    4: "Animal_Vegetable_Oils",
    5: "Chemicals",
    6: "Manufactured_Goods",
    7: "Machinery_and_Transport",
    8: "Miscellaneous_Manufactures",
    9: "Other"
}

# Set up clean absolute project root pathways
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DATA_PATH = os.path.join(PROJECT_ROOT, "data", "raw")
PROCESSED_DATA_PATH = os.path.join(PROJECT_ROOT, "data", "processed")


# ─── Data Core Processing Logic ────────────────────────────────────────────────

def process_ots_data(raw_records, sitc_df=None):
    if not raw_records:
        print("No records to process.")
        return None

    df = pd.DataFrame(raw_records)
    print(f"\nRaw checkpoint data shape: {df.shape}")

    # Standardize column headers from API response formats
    rename_map = {}
    for col in df.columns:
        if col.lower() == 'monthid':
            rename_map[col] = 'month_id'
        elif col.lower() == 'commoditysitcid':
            rename_map[col] = 'sitc_id'
        elif col.lower() == 'totalvalue' or col.lower() == 'value':
            rename_map[col] = 'import_value_gbp'

    df = df.rename(columns=rename_map)

    # Parse MonthId (YYYYMM format) into clean date objects
    df['month_id'] = df['month_id'].astype(str)
    df['year'] = df['month_id'].str[:4].astype(int)
    df['month'] = df['month_id'].str[4:6].astype(int)
    df['date'] = pd.to_datetime(
        df['year'].astype(str) + '-' + df['month'].astype(str).str.zfill(2) + '-01'
    )

    # Filter out internal system codes (negative values)
    df = df[df['sitc_id'] >= 0].copy()

    # FIX: Use reference table if available to preserve leading zeros for Section 0 (Food)
    if sitc_df is not None:
        print("Reference mapping archive loaded. Aligning true structural categories...")
        # Standardize reference columns
        sitc_df_clean = sitc_df.copy()
        sitc_df_clean.columns = [str(c).lower().strip() for c in sitc_df_clean.columns]

        id_col = 'id' if 'id' in sitc_df_clean.columns else sitc_df_clean.columns[0]
        code_col = 'code' if 'code' in sitc_df_clean.columns else sitc_df_clean.columns[1]

        sitc_mapping = dict(zip(sitc_df_clean[id_col].astype(int), sitc_df_clean[code_col].astype(str).str.strip()))

        # Map IDs to actual character code strings to capture text structural zeros
        df['sitc_code'] = df['sitc_id'].astype(int).map(sitc_mapping).fillna('')

        # Pull the first character digit safely to find the true section
        df['sitc_section'] = df['sitc_code'].apply(
            lambda x: int(x[0]) if (x and x[0].isdigit()) else 9
        )
    else:
        # Fallback positional lambda if reference file is unreadable
        df['sitc_section'] = df['sitc_id'].apply(
            lambda x: x if x < 10 else int(str(int(x))[0])
        )

    df['commodity_category'] = df['sitc_section'].map(SITC_LABELS).fillna('Unknown')
    df['import_value_gbp'] = pd.to_numeric(df['import_value_gbp'], errors='coerce')

    # Keep valid dates and baseline timelines
    df = df[(df['year'] >= START_YEAR) & (df['year'] <= END_YEAR)]
    df = df.dropna(subset=['date', 'import_value_gbp'])

    print(f"Cleaned database shape: {df.shape}")
    print(f"Categories detected: {df['commodity_category'].unique().tolist()}")

    print(f"\nTotal import value by category (£ billions):")
    category_totals = df.groupby('commodity_category')['import_value_gbp'].sum() / 1e9
    print(category_totals.sort_values(ascending=False).round(2))

    return df


def build_monthly_pivot(df):
    pivot = df.pivot_table(
        index='date',
        columns='commodity_category',
        values='import_value_gbp',
        aggfunc='sum'
    ).reset_index()

    pivot.columns.name = None

    # Standardize column headers with prefix tags
    new_cols = {'date': 'date'}
    for col in pivot.columns:
        if col != 'date':
            clean = col.lower().replace(' ', '_').replace('&', 'and').replace(',', '')
            new_cols[col] = f"imports_{clean}"
    pivot = pivot.rename(columns=new_cols)

    # Inject Year-on-Year tracking indicators
    for col in pivot.columns:
        if col.startswith('imports_'):
            pivot[f"{col}_yoy"] = pivot[col].pct_change(periods=12) * 100

    print(f"\nMonthly pivot dimensions: {pivot.shape}")
    return pivot


def save_outputs(df_long, df_pivot):
    os.makedirs(RAW_DATA_PATH, exist_ok=True)
    os.makedirs(PROCESSED_DATA_PATH, exist_ok=True)

    long_path = os.path.join(RAW_DATA_PATH, "hmrc_ots_imports_long.csv")
    df_long.to_csv(long_path, index=False)
    print(f"Long format saved directly: {long_path}")

    pivot_path = os.path.join(PROCESSED_DATA_PATH, "hmrc_imports_monthly.csv")
    df_pivot.to_csv(pivot_path, index=False)
    print(f"Monthly analysis framework saved: {pivot_path}")


# ─── Main Execution Pipeline ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("HMRC — Reprocessing Data Frame from Saved Local Checkpoints")
    print("=" * 60)

    checkpoint_dir = os.path.join(RAW_DATA_PATH, "hmrc_checkpoints")
    all_records = []

    for year in range(START_YEAR, END_YEAR + 1):
        checkpoint_file = os.path.join(checkpoint_dir, f"ots_imports_{year}.json")
        if os.path.exists(checkpoint_file):
            with open(checkpoint_file, 'r') as f:
                records = json.load(f)
            all_records.extend(records)
            print(f"Year {year}: loaded {len(records)} records from archive checkpoint")
        else:
            print(f"Year {year}: checkpoint file missing — skipping step")

    print(f"\nTotal structural rows loaded: {len(all_records)}")

    # Load reference mapping tab file safely
    sitc_path = os.path.join(RAW_DATA_PATH, "sitc_reference.csv")
    sitc_df = pd.read_csv(sitc_path) if os.path.exists(sitc_path) else None

    # Run processing functions
    df_long = process_ots_data(all_records, sitc_df)

    if df_long is not None:
        df_pivot = build_monthly_pivot(df_long)
        save_outputs(df_long, df_pivot)
        print("\nSUCCESS: HMRC processing sequence complete. Ready for script 05.")
    else:
        print("\nERROR: Compilation sequences aborted.")