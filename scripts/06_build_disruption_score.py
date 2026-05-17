"""
Script 06: Build the Supply Chain Disruption Score
Produces a composite 0-100 score per month from 4 signals.
Output: data/exports/supply_chain_scored.csv
        data/exports/category_disruption_scores.csv
        data/exports/disruption_timeline.png
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os

# ─── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED = os.path.join(PROJECT_ROOT, "data", "processed")
EXPORTS = os.path.join(PROJECT_ROOT, "data", "exports")

os.makedirs(EXPORTS, exist_ok=True)


# ─── Step 1: Load master table ────────────────────────────────────────────────

def load_master():
    path = os.path.join(PROCESSED, "master_supply_chain_data.csv")
    if not os.path.exists(path):
        # Fallback in case it was saved differently
        path = os.path.join(PROCESSED, "master_supply_chain.csv")

    df = pd.read_csv(path, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)
    print(f"Master loaded: {df.shape}")
    return df


# ─── Step 2: Normalise helper ─────────────────────────────────────────────────

def normalise(series, invert=False):
    s = series.copy().astype(float)
    s_min = s.min()
    s_max = s.max()
    if s_max == s_min:
        return pd.Series([50.0] * len(s), index=s.index)
    scaled = (s - s_min) / (s_max - s_min) * 100
    if invert:
        scaled = 100 - scaled
    return scaled.round(2)


# ─── Step 3: Build the 4 signals ─────────────────────────────────────────────

def signal_retail(df):
    col = "retail_total_volume_deviation"
    if col not in df.columns:
        # If deviation isn't pre-calculated, calculate it here
        rolling_avg = df["retail_total_volume"].rolling(window=12, min_periods=1).mean()
        df[col] = ((df["retail_total_volume"] - rolling_avg) / rolling_avg * 100).round(4)

    raw = df[col].fillna(0)
    return normalise(-raw)


def signal_food_inflation(df):
    col = "cpi_food_premium"
    if col not in df.columns:
        if "cpi_food_nonalcoholic_yoy" in df.columns and "cpi_transport_yoy" in df.columns:
            df[col] = df["cpi_food_nonalcoholic_yoy"] - df["cpi_transport_yoy"]
        else:
            df[col] = df.get("cpi_food_nonalcoholic", pd.Series([0] * len(df)))

    raw = df[col].fillna(0)
    return normalise(raw)


def signal_import_decline(df):
    col = "imports_food_and_live_animals_yoy"
    if col not in df.columns:
        # Fall back to general imports if food specific isn't there
        col = "imports_food_and_live_animals"
        if col in df.columns:
            df[col + "_yoy"] = df[col].pct_change(periods=12) * 100
            col = col + "_yoy"

    raw = df.get(col, pd.Series([0] * len(df))).fillna(0)
    raw = raw.clip(lower=-50, upper=50)
    return normalise(-raw)


def signal_hgv(df):
    col = "total_hgv_licensed"
    if col not in df.columns:
        print(f"  WARNING: {col} not found. Signal 4 = 50 (neutral).")
        return pd.Series([50.0] * len(df), index=df.index)

    # MODERN FIX: Used .ffill() and .bfill() directly
    raw = df[col].ffill().bfill()
    return normalise(raw, invert=True)


# ─── Step 4: Composite score ──────────────────────────────────────────────────

WEIGHTS = {
    "signal_retail": 0.30,
    "signal_food_inflation": 0.25,
    "signal_import_decline": 0.30,
    "signal_hgv": 0.15,
}


def build_composite(df):
    print("\nBuilding signals...")

    df = df.copy()

    # Check if 'era' exists, if not, create it for the timeline
    if "era" not in df.columns:
        df["era"] = "Pre-COVID"
        df.loc[df["date"] >= "2020-03-01", "era"] = "COVID Period"
        df.loc[df["date"] >= "2021-01-01", "era"] = "Post-Brexit / Recovery"
        df.loc[df["date"] >= "2022-02-01", "era"] = "High Inflation"
        df.loc[df["date"] >= "2023-06-01", "era"] = "Stabilisation"

    # Check if 'year_month' exists
    if "year_month" not in df.columns:
        df["year_month"] = df["date"].dt.strftime("%Y-%m")

    df["signal_retail"] = signal_retail(df)
    df["signal_food_inflation"] = signal_food_inflation(df)
    df["signal_import_decline"] = signal_import_decline(df)
    df["signal_hgv"] = signal_hgv(df)

    df["disruption_score"] = (
            df["signal_retail"] * WEIGHTS["signal_retail"] +
            df["signal_food_inflation"] * WEIGHTS["signal_food_inflation"] +
            df["signal_import_decline"] * WEIGHTS["signal_import_decline"] +
            df["signal_hgv"] * WEIGHTS["signal_hgv"]
    ).round(2)

    df["disruption_level"] = pd.cut(
        df["disruption_score"],
        bins=[0, 25, 40, 60, 75, 100],
        labels=["Very Low", "Low", "Moderate", "High", "Critical"],
        include_lowest=True
    ).astype(str)

    print(f"\nDisruption Score Summary:")
    print(df[["date", "disruption_score", "disruption_level"]].describe())

    return df


# ─── Step 5: Top/Bottom months ───────────────────────────────────────────────

def print_insights(df):
    print("\n" + "=" * 55)
    print("TOP 10 HIGHEST DISRUPTION MONTHS")
    print("=" * 55)
    top10 = df.nlargest(10, "disruption_score")[
        ["date", "year_month", "disruption_score", "disruption_level", "era"]
    ]
    print(top10.to_string(index=False))


# ─── Step 6: Chart ───────────────────────────────────────────────────────────

def plot_timeline(df):
    fig, axes = plt.subplots(3, 1, figsize=(16, 14))
    fig.patch.set_facecolor("#0d1b2a")

    for ax in axes:
        ax.set_facecolor("#0d1b2a")
        ax.tick_params(colors="white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        ax.title.set_color("white")
        for spine in ax.spines.values():
            spine.set_edgecolor("#334155")

    # ── Panel 1: Composite disruption score ──
    ax1 = axes[0]
    ax1.plot(df["date"], df["disruption_score"], color="#e53935", linewidth=2.5, label="Disruption Score")
    ax1.fill_between(df["date"], df["disruption_score"], 60,
                     where=df["disruption_score"] > 60,
                     alpha=0.25, color="#e53935", label="High Zone")
    ax1.axhline(60, color="#ff7043", linestyle="--", linewidth=1, alpha=0.7, label="High threshold (60)")
    ax1.axhline(40, color="#66bb6a", linestyle="--", linewidth=1, alpha=0.7, label="Low threshold (40)")
    ax1.set_ylim(0, 100)
    ax1.set_ylabel("Score (0–100)", color="white")
    ax1.set_title("UK Supply Chain Disruption Score — Composite (2015–2024)", fontweight="bold")
    ax1.legend(fontsize=8, facecolor="#1e293b", labelcolor="white")
    ax1.grid(axis="y", alpha=0.15, color="white")

    # ── Panel 2: Individual signals ──
    ax2 = axes[1]
    signal_colors = {
        "signal_retail": "#42a5f5",
        "signal_food_inflation": "#ffca28",
        "signal_import_decline": "#ef5350",
        "signal_hgv": "#66bb6a"
    }
    signal_labels = {
        "signal_retail": "Retail Volume Deviation",
        "signal_food_inflation": "Food Inflation Premium",
        "signal_import_decline": "Import Volume Decline",
        "signal_hgv": "HGV Shortage"
    }
    for col, color in signal_colors.items():
        if col in df.columns:
            ax2.plot(df["date"], df[col], color=color,
                     linewidth=1.5, alpha=0.85, label=signal_labels[col])
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("Signal Score (0–100)", color="white")
    ax2.set_title("Individual Signal Components", fontweight="bold")
    ax2.legend(fontsize=8, facecolor="#1e293b", labelcolor="white")
    ax2.grid(axis="y", alpha=0.15, color="white")

    # ── Panel 3: Food CPI YoY vs HGV ──
    ax3 = axes[2]
    ax3b = ax3.twinx()

    if "cpi_food_nonalcoholic" in df.columns:
        ax3.plot(df["date"], df["cpi_food_nonalcoholic"],
                 color="#ffca28", linewidth=2, label="Food CPI")
        ax3.set_ylabel("Food CPI", color="#ffca28")
        ax3.tick_params(axis="y", colors="#ffca28")

    if "total_hgv_licensed" in df.columns:
        ax3b.plot(df["date"], df["total_hgv_licensed"] / 1000,
                  color="#66bb6a", linewidth=2, linestyle="--", label="HGV Licensed (000s)")
        ax3b.set_ylabel("HGV Licensed (000s)", color="#66bb6a")
        ax3b.tick_params(axis="y", colors="#66bb6a")

    ax3.set_title("Food Inflation vs HGV Capacity", fontweight="bold")
    lines1, labels1 = ax3.get_legend_handles_labels()
    lines2, labels2 = ax3b.get_legend_handles_labels()
    ax3.legend(lines1 + lines2, labels1 + labels2,
               fontsize=8, facecolor="#1e293b", labelcolor="white")
    ax3.grid(axis="y", alpha=0.15, color="white")
    ax3b.spines["right"].set_edgecolor("#334155")

    # Format x-axis dates
    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.xaxis.set_major_locator(mdates.YearLocator())

    plt.tight_layout(pad=2.0)
    chart_path = os.path.join(EXPORTS, "disruption_timeline.png")
    plt.savefig(chart_path, dpi=150, bbox_inches="tight", facecolor="#0d1b2a")
    print(f"\nChart saved: {chart_path}")

    # This will actually pop open a window showing your chart!
    plt.show()


# ─── Step 8: Save ─────────────────────────────────────────────────────────────

def save_all(df_scored):
    p1 = os.path.join(EXPORTS, "supply_chain_scored.csv")
    df_scored.to_csv(p1, index=False)
    print(f"\nScored master saved : {p1} ({df_scored.shape})")


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Script 06: Build Disruption Score")
    print("=" * 60)

    df = load_master()
    df_scored = build_composite(df)
    print_insights(df_scored)
    save_all(df_scored)

    # Put this last so the script finishes saving before opening the image
    plot_timeline(df_scored)

    print("\nSUCCESS: Script 06 complete. Run script 07 next.")