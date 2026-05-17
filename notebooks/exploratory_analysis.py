"""
Exploratory Data Analysis — UK Retail Supply Chain Disruption Tracker
======================================================================
This script produces all key analytical charts and insight summaries
used to validate the disruption score model and communicate findings.

Run this after all 8 scripts have completed successfully.
Output: charts printed to screen + saved to data/exports/
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import os

# ─── Setup ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS      = os.path.join(PROJECT_ROOT, "data", "exports")

# Dark theme for all charts — matches Power BI dashboard aesthetic
plt.rcParams.update({
    "figure.facecolor":  "#0d1b2a",
    "axes.facecolor":    "#0d1b2a",
    "axes.edgecolor":    "#334155",
    "axes.labelcolor":   "white",
    "text.color":        "white",
    "xtick.color":       "white",
    "ytick.color":       "white",
    "grid.color":        "#1e293b",
    "legend.facecolor":  "#1e293b",
    "legend.labelcolor": "white",
    "figure.figsize":    (14, 6)
})

# ─── Load Data ────────────────────────────────────────────────────────────────

print("Loading data...")
df = pd.read_csv(
    os.path.join(EXPORTS, "supply_chain_scored.csv"),
    parse_dates=["date"]
)
cat_df = pd.read_csv(
    os.path.join(EXPORTS, "category_disruption_scores.csv"),
    parse_dates=["date"]
)
forecast_df = pd.read_csv(
    os.path.join(EXPORTS, "arima_forecasts.csv"),
    parse_dates=["date"]
)

df = df.sort_values("date").reset_index(drop=True)
print(f"Main dataset: {df.shape[0]} months, {df.shape[1]} columns")
print(f"Date range: {df['date'].min().strftime('%b %Y')} to {df['date'].max().strftime('%b %Y')}")


# ─── Chart 1: Disruption Score Full Timeline ──────────────────────────────────

print("\n[1/7] Plotting disruption score timeline...")

fig, ax = plt.subplots(figsize=(16, 7))

ax.plot(df["date"], df["disruption_score"],
        color="#e53935", linewidth=2, label="Disruption Score")

ax.fill_between(df["date"], df["disruption_score"], 60,
                where=df["disruption_score"] > 60,
                alpha=0.3, color="#e53935", label="High Disruption Zone")

ax.axhline(60, color="#ff7043", linestyle="--", linewidth=1, label="High Threshold (60)")
ax.axhline(40, color="#ffca28", linestyle="--", linewidth=1, label="Moderate Threshold (40)")
ax.axhline(25, color="#66bb6a", linestyle="--", linewidth=1, label="Low Threshold (25)")

events = {
    "2020-03-01": "COVID\nLockdown",
    "2021-01-01": "Brexit\nEnd",
    "2021-09-01": "HGV\nCrisis",
    "2022-02-01": "Ukraine\nWar",
    "2022-10-01": "Energy\nPeak"
}
for date_str, label in events.items():
    event_date = pd.Timestamp(date_str)
    ax.axvline(event_date, color="#94a3b8", linestyle=":", linewidth=1, alpha=0.7)
    score_at = df.loc[df["date"] >= event_date, "disruption_score"].iloc[0]
    ax.text(event_date, score_at + 3, label,
            color="#94a3b8", fontsize=8, ha="center")

ax.set_title("UK Retail Supply Chain Disruption Score (2015–2024)",
             fontsize=14, fontweight="bold", pad=15)
ax.set_ylabel("Disruption Score (0–100)")
ax.set_xlabel("Date")
ax.set_ylim(0, 100)
ax.legend(loc="upper right", fontsize=9)
ax.grid(axis="y", alpha=0.3)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.xaxis.set_major_locator(mdates.YearLocator())

plt.tight_layout()
plt.savefig(os.path.join(EXPORTS, "eda_01_disruption_timeline.png"),
            dpi=150, bbox_inches="tight", facecolor="#0d1b2a")
plt.show()


# ─── Chart 2: Signal Components ───────────────────────────────────────────────

print("[2/7] Plotting signal components...")

fig, axes = plt.subplots(2, 2, figsize=(16, 10))
fig.suptitle("Individual Signal Components — Disruption Score Drivers",
             fontsize=14, fontweight="bold", y=1.01)

signals = {
    "signal_retail":         ("Retail Volume Deviation", "#42a5f5"),
    "signal_food_inflation":  ("Food Inflation Premium",  "#ffca28"),
    "signal_import_decline":  ("Import Volume Decline",   "#e53935"),
    "signal_hgv":             ("HGV Logistics Capacity",  "#66bb6a")
}

for ax, (col, (title, color)) in zip(axes.flatten(), signals.items()):
    ax.plot(df["date"], df[col], color=color, linewidth=1.8)
    ax.axhline(60, color="#ff7043", linestyle="--", linewidth=0.8, alpha=0.6)
    ax.axhline(40, color="#66bb6a", linestyle="--", linewidth=0.8, alpha=0.6)
    ax.set_title(title, fontweight="bold")
    ax.set_ylim(0, 100)
    ax.set_ylabel("Signal Score (0–100)")
    ax.grid(axis="y", alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_major_locator(mdates.YearLocator())

plt.tight_layout()
plt.savefig(os.path.join(EXPORTS, "eda_02_signal_components.png"),
            dpi=150, bbox_inches="tight", facecolor="#0d1b2a")
plt.show()


# ─── Chart 3: Era Comparison ──────────────────────────────────────────────────

print("[3/7] Plotting era comparison...")

era_stats = df.groupby("era").agg(
    avg_score    = ("disruption_score", "mean"),
    max_score    = ("disruption_score", "max"),
    month_count  = ("disruption_score", "count")
).round(2).sort_values("avg_score", ascending=True)

era_colors = {
    "Pre-COVID":             "#66bb6a",
    "COVID Period":          "#ffca28",
    "Post-Brexit / Recovery":"#ff7043",
    "High Inflation":        "#e53935",
    "Stabilisation":         "#42a5f5"
}

fig, ax = plt.subplots(figsize=(12, 6))
bars = ax.barh(
    era_stats.index,
    era_stats["avg_score"],
    color=[era_colors.get(e, "#94a3b8") for e in era_stats.index],
    edgecolor="#334155",
    height=0.6
)

for bar, val in zip(bars, era_stats["avg_score"]):
    ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
            f"{val:.1f}", va="center", fontsize=11, fontweight="bold")

ax.axvline(51.33, color="white", linestyle="--",
           linewidth=1, alpha=0.5, label="Overall Average (51.33)")
ax.set_title("Average Disruption Score by Era", fontsize=14, fontweight="bold")
ax.set_xlabel("Average Disruption Score")
ax.set_xlim(0, 70)
ax.legend(fontsize=9)
ax.grid(axis="x", alpha=0.3)

plt.tight_layout()
plt.savefig(os.path.join(EXPORTS, "eda_03_era_comparison.png"),
            dpi=150, bbox_inches="tight", facecolor="#0d1b2a")
plt.show()


# ─── Chart 4: Monthly Heatmap ────────────────────────────────────────────────

print("[4/7] Plotting monthly heatmap...")

heatmap_data = df.pivot_table(
    index="year",
    columns="month",
    values="disruption_score",
    aggfunc="mean"
)
heatmap_data.columns = ["Jan","Feb","Mar","Apr","May","Jun",
                         "Jul","Aug","Sep","Oct","Nov","Dec"]

fig, ax = plt.subplots(figsize=(16, 8))
sns.heatmap(
    heatmap_data,
    ax         = ax,
    cmap       = sns.diverging_palette(130, 10, as_cmap=True),
    center     = 50,
    vmin       = 0,
    vmax       = 100,
    annot      = True,
    fmt        = ".0f",
    linewidths = 0.5,
    linecolor  = "#0d1b2a",
    cbar_kws   = {"label": "Disruption Score"}
)
ax.set_title("Monthly Disruption Score Heatmap (2015–2024)",
             fontsize=14, fontweight="bold", pad=15)
ax.set_xlabel("Month")
ax.set_ylabel("Year")
ax.tick_params(axis="x", rotation=0)

plt.tight_layout()
plt.savefig(os.path.join(EXPORTS, "eda_04_monthly_heatmap.png"),
            dpi=150, bbox_inches="tight", facecolor="#0d1b2a")
plt.show()


# ─── Chart 5: Food CPI vs Import Decline ────────────────────────────────────

print("[5/7] Plotting food CPI vs import decline...")

fig, ax1 = plt.subplots(figsize=(16, 6))
ax2 = ax1.twinx()

valid_cpi = df[df["cpi_food_nonalcoholic_yoy"].notna()]
valid_imp = df[df["imports_food_and_live_animals_yoy"].notna()]

ax1.plot(valid_cpi["date"], valid_cpi["cpi_food_nonalcoholic_yoy"],
         color="#ffca28", linewidth=2, label="Food CPI YoY %")
ax1.axhline(0, color="white", linewidth=0.5, alpha=0.4)
ax1.set_ylabel("Food CPI YoY %", color="#ffca28")
ax1.tick_params(axis="y", colors="#ffca28")
ax1.set_ylim(-5, 15)

ax2.plot(valid_imp["date"], valid_imp["imports_food_and_live_animals_yoy"],
         color="#42a5f5", linewidth=2, linestyle="--",
         label="Food Imports YoY %")
ax2.axhline(0, color="white", linewidth=0.5, alpha=0.4)
ax2.set_ylabel("Food Imports YoY %", color="#42a5f5")
ax2.tick_params(axis="y", colors="#42a5f5")
ax2.set_ylim(-40, 40)

lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc="upper left")

ax1.set_title("Food CPI Inflation vs Food Import Volumes (YoY %)",
              fontsize=14, fontweight="bold")
ax1.set_xlabel("Date")
ax1.grid(axis="y", alpha=0.2)
ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax1.xaxis.set_major_locator(mdates.YearLocator())

plt.tight_layout()
plt.savefig(os.path.join(EXPORTS, "eda_05_cpi_vs_imports.png"),
            dpi=150, bbox_inches="tight", facecolor="#0d1b2a")
plt.show()


# ─── Chart 6: Category Disruption ────────────────────────────────────────────

print("[6/7] Plotting category disruption scores...")

cat_avg = cat_df.groupby("category")["category_disruption_score"].mean().sort_values()

cat_colors = {
    "Food & Drink":           "#e53935",
    "Clothing":               "#ff7043",
    "Energy & Fuels":         "#ffca28",
    "Machinery & Industrial": "#42a5f5",
    "Chemicals & Pharma":     "#66bb6a"
}

fig, ax = plt.subplots(figsize=(12, 6))
bars = ax.barh(
    cat_avg.index,
    cat_avg.values,
    color=[cat_colors.get(c, "#94a3b8") for c in cat_avg.index],
    edgecolor="#334155",
    height=0.6
)

for bar, val in zip(bars, cat_avg.values):
    ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
            f"{val:.1f}", va="center", fontsize=11, fontweight="bold")

ax.set_title("Average Disruption Score by Supply Chain Category",
             fontsize=14, fontweight="bold")
ax.set_xlabel("Average Disruption Score")
ax.set_xlim(0, 60)
ax.grid(axis="x", alpha=0.3)

plt.tight_layout()
plt.savefig(os.path.join(EXPORTS, "eda_06_category_scores.png"),
            dpi=150, bbox_inches="tight", facecolor="#0d1b2a")
plt.show()


# ─── Chart 7: ARIMA Forecast ─────────────────────────────────────────────────

print("[7/7] Plotting ARIMA forecast...")

total_forecast = forecast_df[
    forecast_df["series"] == "Total Retail Volume"
].copy()

hist = df[df["date"] >= "2022-01-01"][["date","retail_total_volume"]].dropna()

fig, ax = plt.subplots(figsize=(14, 6))

ax.plot(hist["date"], hist["retail_total_volume"],
        color="#42a5f5", linewidth=2.5, label="Historical (2022–2024)")

if len(total_forecast) > 0:
    ax.plot(total_forecast["date"], total_forecast["forecast_value"],
            color="#e53935", linewidth=2.5, linestyle="--",
            label="ARIMA Forecast (6 months)")
    ax.fill_between(
        total_forecast["date"],
        total_forecast["forecast_lower_95"],
        total_forecast["forecast_upper_95"],
        alpha=0.2, color="#e53935",
        label="95% Confidence Interval"
    )
    ax.axvline(total_forecast["date"].iloc[0],
               color="#94a3b8", linestyle=":", linewidth=1.5,
               label="Forecast Start", alpha=0.7)

ax.set_title("UK Total Retail Volume — Historical + 6-Month ARIMA Forecast",
             fontsize=14, fontweight="bold")
ax.set_xlabel("Date")
ax.set_ylabel("Retail Volume Index (2019 = 100)")
ax.legend(fontsize=9)
ax.grid(axis="y", alpha=0.3)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
plt.xticks(rotation=45)

plt.tight_layout()
plt.savefig(os.path.join(EXPORTS, "eda_07_arima_forecast.png"),
            dpi=150, bbox_inches="tight", facecolor="#0d1b2a")
plt.show()


# ─── Summary Statistics ───────────────────────────────────────────────────────

print("\n" + "="*60)
print("ANALYTICAL SUMMARY")
print("="*60)

print(f"\nDate range        : {df['date'].min().strftime('%b %Y')} – {df['date'].max().strftime('%b %Y')}")
print(f"Total months      : {len(df)}")
print(f"Avg score         : {df['disruption_score'].mean():.2f}")
print(f"Peak score        : {df['disruption_score'].max():.2f}")
print(f"Peak month        : {df.loc[df['disruption_score'].idxmax(), 'date'].strftime('%B %Y')}")
print(f"High/Critical     : {(df['disruption_level'].isin(['High','Critical'])).sum()} months")

print(f"\nDisruption levels:")
for level, count in df["disruption_level"].value_counts().items():
    pct = count / len(df) * 100
    print(f"  {level:<12}: {count:>3} months ({pct:.1f}%)")

print(f"\nAvg score by era:")
for era, score in df.groupby("era")["disruption_score"].mean().sort_values(ascending=False).items():
    print(f"  {era:<30}: {score:.2f}")

print(f"\nFood CPI YoY:")
valid = df["cpi_food_nonalcoholic_yoy"].dropna()
print(f"  Mean : {valid.mean():.2f}%")
print(f"  Max  : {valid.max():.2f}% ({df.loc[df['cpi_food_nonalcoholic_yoy'].idxmax(), 'date'].strftime('%B %Y')})")
print(f"  Min  : {valid.min():.2f}%")

print(f"\nCorrelation — Disruption Score vs:")
for col, label in [
    ("cpi_food_nonalcoholic_yoy", "Food CPI YoY"),
    ("imports_food_and_live_animals_yoy", "Food Imports YoY"),
    ("retail_total_volume_deviation", "Retail Deviation"),
    ("hgv_yoy", "HGV YoY Change")
]:
    if col in df.columns:
        corr = df[["disruption_score", col]].dropna().corr().iloc[0, 1]
        print(f"  {label:<30}: {corr:+.3f}")

print("\nAll charts saved to data/exports/")
print("EDA complete.")