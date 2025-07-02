import datetime
import sqlite3
import pandas as pd
import streamlit as st
from config import DB_PATH


# ----------------------------------------------------------------------
# 🔗  Convenience: add clickable links for Screener.in
# ----------------------------------------------------------------------
def add_screener_links(df: pd.DataFrame) -> pd.DataFrame:
    def link_bse(x):
        try:
            return f"[{int(x)}](https://www.screener.in/company/{int(x)}/)"
        except (ValueError, TypeError):
            return ""

    def link_nse(x):
        try:
            return f"[{x}](https://www.screener.in/company/{x}/)" if pd.notna(x) and str(x).strip() else ""
        except Exception:
            return ""

    if "bse_code" in df.columns:
        df["bse_code"] = df["bse_code"].apply(link_bse)

    if "nse_code" in df.columns:
        df["nse_code"] = df["nse_code"].apply(link_nse)

    return df


# ----------------------------------------------------------------------
# 📄  Cached data helpers
# ----------------------------------------------------------------------
@st.cache_data
def get_momentum_summary() -> pd.DataFrame:
    today = datetime.date.today()
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)

    def _hit_counts(days: int) -> pd.DataFrame:
        since = today - datetime.timedelta(days=days)
        q = f"""
            SELECT name, COUNT(*) AS hits_{days}
            FROM highs
            WHERE date >= ?
            GROUP BY name
        """
        return pd.read_sql(q, conn, params=(since,)).set_index("name")

    # rolling hit counts
    counts7  = _hit_counts(7)
    counts30 = _hit_counts(30)
    counts60 = _hit_counts(60)

    # most‑recent snapshot for each stock
    latest = pd.read_sql(
        """
        SELECT h1.*
        FROM highs h1
        JOIN (
            SELECT name, MAX(date) AS max_date
            FROM highs
            GROUP BY name
        ) h2 ON h1.name = h2.name AND h1.date = h2.max_date
        """,
        conn,
    ).set_index("name")

    latest["%_gain_mc"] = 100 * (
        latest["market_cap"] - latest["first_market_cap"]
    ) / latest["first_market_cap"]

    df = latest[
        [
            "nse_code",
            "bse_code",
            "industry",
            "market_cap",
            "first_market_cap",
            "first_seen_date",
            "%_gain_mc",
        ]
    ]
    df = df.join(counts7).join(counts30).join(counts60)

    # -- type hygiene ---------------------------------------------------
    if "bse_code" in df.columns:
        # NOTE: **no .dropna()** – keeps the index aligned
        df["bse_code"] = pd.to_numeric(df["bse_code"], errors="coerce").astype("Int64")

    if "nse_code" in df.columns:
        df["nse_code"] = df["nse_code"].astype("string")

    if "industry" in df.columns:
        df["industry"] = df["industry"].astype("string")

    conn.close()
    return df.reset_index()


@st.cache_data
def get_historical_market_cap() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    df = pd.read_sql(
        "SELECT date, name, nse_code, bse_code, industry, market_cap FROM highs", conn
    )
    df["date"] = pd.to_datetime(df["date"])

    if "bse_code" in df.columns:
        df["bse_code"] = pd.to_numeric(df["bse_code"], errors="coerce").astype("Int64")

    conn.close()
    return df


@st.cache_data
def get_all_dates() -> list[datetime.date]:
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    df = pd.read_sql("SELECT DISTINCT date FROM highs ORDER BY date", conn)
    conn.close()
    return pd.to_datetime(df["date"]).dt.date.tolist()


@st.cache_data
def get_data_for_date(selected_date: str | datetime.date) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    df = pd.read_sql("SELECT * FROM highs WHERE date = ?", conn, params=(selected_date,))
    conn.close()

    if "bse_code" in df.columns:
        df["bse_code"] = pd.to_numeric(df["bse_code"], errors="coerce").astype("Int64")

    for col in ["nse_code", "industry", "name"]:
        if col in df.columns:
            df[col] = df[col].astype("string")

    return df


@st.cache_data
def get_sparkline_data() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    df = pd.read_sql("SELECT name, date FROM highs", conn)
    conn.close()

    df["date"] = pd.to_datetime(df["date"])
    df["value"] = 1  # presence flag
    return df
