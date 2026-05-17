"""
Script 07: ARIMA Forecasting
Forecasts 6 months ahead for 3 retail series.
Output: data/exports/arima_forecasts.csv
        data/exports/forecast_*.png
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import warnings
import os

warnings.filterwarnings("ignore")

# ─── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS      = os.path.join(PROJECT_ROOT, "data", "exports")

os.makedirs(EXPORTS, exist_ok=True)


# ─── Step 1: Load ─────────────────────────────────────────────────────────────

def load_scored():
    path = os.path.join(EXPORTS, "supply_chain_scored.csv")
    df   = pd.read_csv(path, parse_dates=["date"])
    df   = df.sort_values("date").reset_index(drop=True)
    print(f"Scored data loaded: {df.shape}")
    print(f"Date range: {df['date'].min().date()} to {df['date'].max().date()}")
    return df


# ─── Step 2: Stationarity test ────────────────────────────────────────────────

def check_stationarity(series, name):
    """
    ADF (Augmented Dickey-Fuller) test.
    If p-value > 0.05 the series is NON-stationary — needs differencing (d=1).
    If p-value <= 0.05 the series IS stationary — no differencing needed (d=0).
    """
    from statsmodels.tsa.stattools import adfuller
    result = adfuller(series.dropna())
    p_value = result[1]
    stationary = p_value <= 0.05
    print(f"  ADF test — {name}: p={p_value:.4f} → {'stationary' if stationary else 'non-stationary (will use d=1)'}")
    return 0 if stationary else 1


# ─── Step 3: Fit ARIMA and forecast ──────────────────────────────────────────

def fit_and_forecast(series, series_name, forecast_months=6):
    """
    Fits ARIMA models with 3 different (p,d,q) combinations.
    Picks the one with the lowest AIC score.
    AIC = Akaike Information Criterion — lower is better fit.
    Then forecasts forward by forecast_months.
    """
    from statsmodels.tsa.arima.model import ARIMA

    # Drop nulls and keep only values
    clean = series.dropna()

    if len(clean) < 24:
        print(f"  Not enough data for {series_name} ({len(clean)} rows). Skipping.")
        return None

    print(f"\n  Fitting ARIMA for: {series_name} ({len(clean)} data points)")

    # Check stationarity to decide d
    d = check_stationarity(clean, series_name)

    # Try 3 model configurations, pick best AIC
    candidates = [
        (1, d, 1),
        (2, d, 1),
        (1, d, 2),
    ]

    best_aic    = np.inf
    best_model  = None
    best_order  = None

    for order in candidates:
        try:
            model  = ARIMA(clean, order=order)
            fitted = model.fit()
            if fitted.aic < best_aic:
                best_aic   = fitted.aic
                best_model = fitted
                best_order = order
            print(f"    ARIMA{order} AIC: {fitted.aic:.2f}")
        except Exception as e:
            print(f"    ARIMA{order} failed: {e}")

    if best_model is None:
        print(f"  All models failed for {series_name}.")
        return None

    print(f"  Best model: ARIMA{best_order} (AIC={best_aic:.2f})")

    # Forecast
    forecast_result = best_model.get_forecast(steps=forecast_months)
    forecast_mean   = forecast_result.predicted_mean
    forecast_ci     = forecast_result.conf_int(alpha=0.05)

    # Build date index for forecast period
    last_date      = series.index[-1]
    forecast_dates = pd.date_range(
        start  = last_date + pd.DateOffset(months=1),
        periods= forecast_months,
        freq   = "MS"
    )

    forecast_df = pd.DataFrame({
        "date":               forecast_dates,
        "forecast_value":     forecast_mean.values,
        "forecast_lower_95":  forecast_ci.iloc[:, 0].values,
        "forecast_upper_95":  forecast_ci.iloc[:, 1].values,
        "series":             series_name,
        "arima_order":        str(best_order),
        "is_forecast":        True
    })

    return forecast_df


# ─── Step 4: Plot each forecast ───────────────────────────────────────────────

def plot_forecast(df_full, forecast_df, col, series_name):
    """
    Plots the last 3 years of historical data + 6 month forecast
    with a shaded 95% confidence interval band.
    """
    fig, ax = plt.subplots(figsize=(14, 6))
    fig.patch.set_facecolor("#0d1b2a")
    ax.set_facecolor("#0d1b2a")
    ax.tick_params(colors="white")
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")
    ax.title.set_color("white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#334155")

    # Historical — last 3 years for clarity
    hist = df_full[df_full["date"] >= "2022-01-01"][["date", col]].dropna()
    ax.plot(hist["date"], hist[col],
            color="#42a5f5", linewidth=2.5, label="Historical", zorder=3)

    if forecast_df is not None:
        # Forecast line
        ax.plot(forecast_df["date"], forecast_df["forecast_value"],
                color="#e53935", linewidth=2.5, linestyle="--",
                label="Forecast (6 months)", zorder=3)

        # Confidence interval shading
        ax.fill_between(
            forecast_df["date"],
            forecast_df["forecast_lower_95"],
            forecast_df["forecast_upper_95"],
            alpha=0.25, color="#e53935", label="95% Confidence Interval"
        )

        # Vertical line marking forecast start
        ax.axvline(forecast_df["date"].iloc[0],
                   color="#94a3b8", linestyle=":", linewidth=1.5,
                   label="Forecast Start", alpha=0.7)

        # Annotate the last forecast value
        last_val  = forecast_df["forecast_value"].iloc[-1]
        last_date = forecast_df["date"].iloc[-1]
        ax.annotate(
            f"{last_val:.1f}",
            xy=(last_date, last_val),
            xytext=(last_date, last_val + 2),
            color="white", fontsize=9,
            arrowprops=dict(arrowstyle="->", color="white", lw=1)
        )

    ax.set_title(
        f"UK {series_name.replace('_', ' ').title()} — Historical + 6-Month ARIMA Forecast",
        fontweight="bold", fontsize=13
    )
    ax.set_xlabel("Date")
    ax.set_ylabel("Index Value (2019 = 100)")
    ax.legend(fontsize=9, facecolor="#1e293b", labelcolor="white")
    ax.grid(axis="y", alpha=0.15, color="white")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.xticks(rotation=45)
    plt.tight_layout()

    chart_path = os.path.join(EXPORTS, f"forecast_{col}.png")
    plt.savefig(chart_path, dpi=150, bbox_inches="tight", facecolor="#0d1b2a")
    print(f"  Chart saved: {chart_path}")
    plt.show()


# ─── Step 5: Run all forecasts ────────────────────────────────────────────────

def run_all_forecasts(df):
    """
    Runs ARIMA for 3 retail series + the disruption score itself.
    Each uses the date column as the index.
    """

    targets = {
        "retail_total_volume":   "Total Retail Volume",
        "retail_food_volume":    "Food Retail Volume",
        "retail_non_food_volume":"Non-Food Retail Volume",
        "disruption_score":      "Supply Chain Disruption Score"
    }

    all_forecasts = []

    for col, series_name in targets.items():
        if col not in df.columns:
            print(f"Column '{col}' not in data — skipping.")
            continue

        # Build a clean series with date as index
        series = df.set_index("date")[col].dropna()
        series.index = pd.DatetimeIndex(series.index)

        forecast_df = fit_and_forecast(series, series_name, forecast_months=6)

        plot_forecast(df, forecast_df, col, series_name)

        if forecast_df is not None:
            all_forecasts.append(forecast_df)

    if all_forecasts:
        combined = pd.concat(all_forecasts, ignore_index=True)
        return combined
    return None


# ─── Step 6: Print forecast summary ──────────────────────────────────────────

def print_forecast_summary(combined):
    print("\n" + "="*55)
    print("FORECAST SUMMARY — Next 6 Months")
    print("="*55)

    for series_name in combined["series"].unique():
        subset = combined[combined["series"] == series_name]
        print(f"\n{series_name}:")
        print(subset[["date","forecast_value","forecast_lower_95","forecast_upper_95"]].to_string(index=False))


# ─── Step 7: Save ─────────────────────────────────────────────────────────────

def save_forecasts(combined):
    path = os.path.join(EXPORTS, "arima_forecasts.csv")
    combined.to_csv(path, index=False)
    print(f"\nAll forecasts saved: {path} ({combined.shape})")


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("="*60)
    print("Script 07: ARIMA Forecasting")
    print("="*60)

    df       = load_scored()
    combined = run_all_forecasts(df)

    if combined is not None:
        print_forecast_summary(combined)
        save_forecasts(combined)
        print("\nSUCCESS: Script 07 complete. Run script 08 next.")
    else:
        print("\nERROR: No forecasts generated. Check output above.")