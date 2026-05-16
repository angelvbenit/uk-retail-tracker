"""
Script 03: Precision ONS Table 38 CPI Archive Parser
Targets the master historical time-series sheet (Table 38) to extract
complete monthly CPI records from 2015 to the present day seamlessly.
"""

import pandas as pd
import os
import sys

# Ensure config paths work cleanly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RAW_DATA_PATH, PROCESSED_DATA_PATH


def build_clean_cpi_dataframe():
    # Force Python to find the absolute path of the project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    filepath = os.path.join(project_root, RAW_DATA_PATH, "ons_cpi.xlsx")

    if not os.path.exists(filepath):
        print(f"ERROR: Local file not found at {filepath}")
        return None

    print(f"Opening local master archive workbook: {filepath}")

    # Target the true historical database tab
    target_sheet = 'Table 38'
    print(f"Extracting historical data matrix from: '{target_sheet}'")

    # Read sheet raw to avoid assumption errors with merged header blocks
    df = pd.read_excel(filepath, sheet_name=target_sheet, header=None)

    # Slice rows from index 7 downwards where the raw data values start
    df_data = df.iloc[7:].copy()

    # Isolate targets directly by their verified positional column indexes:
    # Col 1 = Datetime String, Col 3 = Food, Col 23 = Clothing, Col 63 = Transport
    df_clean = pd.DataFrame({
        'date_raw': df_data[1].astype(str).str.strip(),
        'cpi_food_nonalcoholic': df_data[3],
        'cpi_clothing_footwear': df_data[23],
        'cpi_transport': df_data[63]
    })

    # Standardize time dimension records
    df_clean['date'] = pd.to_datetime(df_clean['date_raw'], errors='coerce')
    df_clean = df_clean.dropna(subset=['date'])

    # Generate calendar markers for modeling scripts later
    df_clean['year'] = df_clean['date'].dt.year
    df_clean['month'] = df_clean['date'].dt.month

    # Filter strictly for our project baseline scope window
    df_clean = df_clean[df_clean['year'] >= 2015]

    # Ensure value columns are clean decimal numbers (floats)
    for col in ['cpi_food_nonalcoholic', 'cpi_clothing_footwear', 'cpi_transport']:
        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')

    # Reorder into clean tabular layout schema
    final_cols = ['date', 'year', 'month', 'cpi_food_nonalcoholic', 'cpi_clothing_footwear', 'cpi_transport']
    df_final = df_clean[final_cols].sort_values('date').reset_index(drop=True)

    # Save the output file safely inside the processed data folder
    target_dir = os.path.join(project_root, PROCESSED_DATA_PATH)
    os.makedirs(target_dir, exist_ok=True)
    output_path = os.path.join(target_dir, "cpi_clean.csv")
    df_final.to_csv(output_path, index=False)

    print(f"\nSUCCESS: Saved clean local CPI schema ({len(df_final)} rows) to: {output_path}")
    return df_final


if __name__ == "__main__":
    print("=" * 60)
    print("Local ONS Master Archive Processing Engine")
    print("=" * 60)
    df = build_clean_cpi_dataframe()
    if df is not None and not df.empty:
        print("\n--- Processed Data Sample Preview ---")
        print(df.head(12))
        print(
            f"\nVerified Timeline Scope: {df['date'].min().strftime('%Y-%m')} to {df['date'].max().strftime('%Y-%m')}")