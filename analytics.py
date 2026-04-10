"""
analytics.py — Аналитический модуль
Считает медиану, среднее и премиум-ставку по направлениям (и транспорту)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

CSV_FILE = "logistics_data.csv"

def load_data(hours: int = 24) -> pd.DataFrame:
    try:
        df = pd.read_csv(CSV_FILE, parse_dates=["timestamp"])
    except FileNotFoundError:
        return pd.DataFrame(columns=[
            "timestamp", "chat", "from_city", "to_city",
            "volume_cbm", "weight_ton", "transport",
            "cargo", "price_usd", "price_kzt", "raw_text"
        ])
    cutoff = datetime.now() - timedelta(hours=hours)
    df = df[df["timestamp"] >= cutoff]
    return df

def get_route_stats(df: pd.DataFrame, currency: str = "usd") -> pd.DataFrame:
    price_col = f"price_{currency}"
    df_clean = df.dropna(subset=[price_col, "from_city", "to_city"]).copy()
    if df_clean.empty:
        return pd.DataFrame()
    df_clean["route"] = df_clean["from_city"] + " → " + df_clean["to_city"]
    stats = df_clean.groupby("route")[price_col].agg(
        count="count",
        mean="mean",
        median="median",
        min_price="min",
        max_price="max",
        p75=lambda x: np.percentile(x, 75),
    ).reset_index()
    stats["premium_rate"] = stats["p75"] * 1.10
    for col in ["mean", "median", "p75", "premium_rate", "min_price", "max_price"]:
        stats[col] = stats[col].round(0).astype(int)
    stats = stats.sort_values("count", ascending=False)
    return stats

def get_route_transport_stats(df: pd.DataFrame, currency: str = "usd") -> pd.DataFrame:
    price_col = f"price_{currency}"
    df_clean = df.dropna(subset=[price_col, "from_city", "to_city"]).copy()
    if df_clean.empty:
        return pd.DataFrame()
    df_clean["route"] = df_clean["from_city"] + " → " + df_clean["to_city"]
    df_clean["transport"] = df_clean["transport"].fillna("не указан")
    df_clean["transport"] = df_clean["transport"].apply(lambda x: x if str(x).strip() != "" else "не указан")
    stats = df_clean.groupby(["route", "transport"])[price_col].agg(
        count="count",
        mean="mean",
        median="median",
        min_price="min",
        max_price="max",
        p75=lambda x: np.percentile(x, 75),
    ).reset_index()
    stats["premium_rate"] = stats["p75"] * 1.10
    for col in ["mean", "median", "p75", "premium_rate", "min_price", "max_price"]:
        stats[col] = stats[col].round(0).astype(int)
    stats = stats.sort_values("count", ascending=False)
    return stats

def get_recent_entries(df: pd.DataFrame, limit: int = 50) -> pd.DataFrame:
    return df.tail(limit).sort_values("timestamp", ascending=False)

def get_summary(df: pd.DataFrame) -> dict:
    return {
        "total_records": len(df),
        "unique_routes": df.dropna(subset=["from_city", "to_city"])
                           .apply(lambda r: f"{r['from_city']}→{r['to_city']}", axis=1)
                           .nunique() if not df.empty else 0,
        "unique_chats": df["chat"].nunique() if not df.empty else 0,
        "last_update": df["timestamp"].max() if not df.empty else None,
    }