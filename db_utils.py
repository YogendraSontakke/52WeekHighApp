import pandas as pd
import sqlite3
import datetime
from config import DB_PATH
import streamlit as st

@st.cache_data
def get_momentum_summary():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    today = datetime.date.today()

    def get_counts(days):
        since = today - datetime.timedelta(days=days)
        query = f"""
            SELECT name, COUNT(*) as hits_{days}
            FROM highs
            WHERE date >= ?
            GROUP BY name
        """
        return pd.read_sql(query, conn, params=(since,)).set_index("name")

    df7 = get_counts(7)
    df30 = get_counts(30)
    df60 = get_counts(60)

    latest = pd.read_sql("""
        SELECT h1.* FROM highs h1
        JOIN (
            SELECT name, MAX(date) as max_date
            FROM highs
            GROUP BY name
        ) h2
        ON h1.name = h2.name AND h1.date = h2.max_date
    """, conn).set_index("name")

    latest["%_gain_mc"] = 100 * (latest["market_cap"] - latest["first_market_cap"]) / latest["first_market_cap"]

    df = latest[[
        "nse_code", "industry", "market_cap", "first_market_cap", "first_seen_date", "%_gain_mc"
    ]]
    df = df.join(df7).join(df30).join(df60).fillna(0)

    for col in ["nse_code", "industry"]:
        if col in df.columns:
            df[col] = df[col].astype(str)

    conn.close()
    return df.reset_index()


@st.cache_data
def get_historical_market_cap():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    df = pd.read_sql("SELECT date, name, nse_code, industry, market_cap FROM highs", conn)
    df['date'] = pd.to_datetime(df['date'])
    return df


@st.cache_data
def get_all_dates():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    df = pd.read_sql("SELECT DISTINCT date FROM highs ORDER BY date DESC", conn)
    conn.close()
    return pd.to_datetime(df['date']).dt.date.tolist()


@st.cache_data
def get_data_for_date(selected_date):
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    df = pd.read_sql("SELECT * FROM highs WHERE date = ?", conn, params=(selected_date,))
    for col in ["nse_code", "bse_code", "industry", "name"]:
        if col in df.columns:
            df[col] = df[col].astype(str)
    conn.close()
    return df

@st.cache_data
def get_sparkline_data():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    df = pd.read_sql("SELECT name, date FROM highs", conn)
    conn.close()
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = 1  # presence flag
    return df
