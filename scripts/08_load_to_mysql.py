"""
Script 08: Load All Processed Data to MySQL (Special Character Fix)
Reads password from .env file securely and URL-encodes it to prevent
symbols like '@' or '#' from breaking the connection string.
"""

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
from urllib.parse import quote_plus  # <--- THIS IS THE MAGIC FIX

# ─── Load credentials from .env ───────────────────────────────────────────────

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv_path = os.path.join(PROJECT_ROOT, ".env")
load_dotenv(dotenv_path)

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "uk_supply_chain")

EXPORTS = os.path.join(PROJECT_ROOT, "data", "exports")


# ─── Step 1: Verify .env loaded correctly ─────────────────────────────────────

def verify_env():
    print("Checking .env configuration...")
    if not DB_PASS:
        print("\nERROR: DB_PASSWORD not found in .env file.")
        exit(1)
    print("  .env loaded correctly.\n")


# ─── Step 2: Create engine ────────────────────────────────────────────────────

def get_engine():
    # We use quote_plus to safely encode any @, #, or ! symbols in your password
    safe_pass = quote_plus(DB_PASS)
    connection_string = (
        f"mysql+pymysql://{DB_USER}:{safe_pass}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    engine = create_engine(connection_string, echo=False)
    return engine


def test_connection(engine):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("MySQL connection successful.")
    except Exception as e:
        print(f"\nERROR: Could not connect to MySQL.")
        print(f"Details: {e}")
        exit(1)


# ─── Step 3: Create database if it doesn't exist ─────────────────────────────

def ensure_database():
    try:
        safe_pass = quote_plus(DB_PASS)
        temp_engine = create_engine(
            f"mysql+pymysql://{DB_USER}:{safe_pass}@{DB_HOST}:{DB_PORT}/",
            echo=False
        )
        with temp_engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}"))
            conn.commit()
        print(f"Database '{DB_NAME}' confirmed/created.")
    except Exception as e:
        print(f"Could not create database: {e}")


# ─── Step 4: Load a CSV into a MySQL table ───────────────────────────────────

def load_table(engine, filepath, table_name):
    if not os.path.exists(filepath):
        print(f"  SKIPPED: {filepath} not found.")
        return

    df = pd.read_csv(filepath)

    for col in df.columns:
        if "date" in col.lower():
            df[col] = pd.to_datetime(df[col], errors="coerce")

    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str[:255]

    try:
        df.to_sql(
            name=table_name,
            con=engine,
            if_exists="replace",
            index=False,
            chunksize=500
        )
        print(f"  Loaded: {table_name} — {len(df)} rows, {df.shape[1]} columns")
    except Exception as e:
        print(f"  ERROR loading {table_name}: {e}")


# ─── Step 5: Run validation queries ──────────────────────────────────────────

def validate(engine):
    print("\n" + "=" * 55)
    print("VALIDATION QUERIES")
    print("=" * 55)

    queries = {
        "Row counts per table": """
            SELECT 'fact_monthly'    AS tbl, COUNT(*) AS rows FROM fact_monthly
            UNION ALL
            SELECT 'fact_category',          COUNT(*) FROM fact_category
            UNION ALL
            SELECT 'fact_master',            COUNT(*) FROM fact_master
        """
    }

    with engine.connect() as conn:
        for query_name, sql in queries.items():
            print(f"\n{query_name}:")
            try:
                result = pd.read_sql(text(sql), conn)
                print(result.to_string(index=False))
            except Exception as e:
                print(f"  Query failed: {e}")


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Script 08: Load Data to MySQL (Safe Parse)")
    print("=" * 60)

    verify_env()
    ensure_database()

    engine = get_engine()
    test_connection(engine)

    print("\nLoading tables...")
    load_table(engine, os.path.join(EXPORTS, "supply_chain_scored.csv"), "fact_monthly")
    load_table(engine, os.path.join(EXPORTS, "category_disruption_scores.csv"), "fact_category")
    load_table(engine, os.path.join(EXPORTS, "master_supply_chain.csv"), "fact_master")

    # If you successfully generated forecasts from script 07, load them too!
    forecast_path = os.path.join(EXPORTS, "arima_forecasts.csv")
    if os.path.exists(forecast_path):
        load_table(engine, forecast_path, "fact_forecasts")

    validate(engine)

    print("\nSUCCESS: Script 08 complete.")
    print("Your MySQL database is ready for Power BI.")