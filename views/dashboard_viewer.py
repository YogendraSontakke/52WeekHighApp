import streamlit as st
import pandas as pd
import plotly.express as px
from db_utils import get_all_dates, get_data_for_date


def load_all_highs(start_date=None, end_date=None):
    all_dates = get_all_dates()
    print(f"All available dates: {all_dates}")
    if not all_dates:
        return pd.DataFrame()

    if start_date and end_date:
        selected_dates = [d for d in all_dates if start_date <= d <= end_date]
    else:
        selected_dates = all_dates
    print(f"Selected dates: {selected_dates}")

    dfs = []
    for d in selected_dates:
        df = get_data_for_date(d)
        print(f"Loaded {len(df) if df is not None else 0} records for {d}")
        if df is not None and not df.empty:
            dfs.append(df)

    if not dfs:
        print("No data found for selected dates")
        return pd.DataFrame()

    all_data = pd.concat(dfs, ignore_index=True)
    all_data["date"] = pd.to_datetime(all_data["date"])
    return all_data


def main():
    st.title("📊 Full-Screen 52-Week Highs Dashboard")

    # --- Date Range Filter
    all_dates = get_all_dates()
    if not all_dates:
        st.warning("No data available.")
        return

    st.sidebar.header("🗓 Date Range")
    start_date, end_date = st.sidebar.select_slider(
        "Select date range",
        options=all_dates,
        value=(min(all_dates), max(all_dates)),
        format_func=lambda d: d.strftime("%Y-%m-%d")
    )

    df = load_all_highs(start_date, end_date)
    if df.empty:
        st.warning("No data available in selected range.")
        return

    total_highs = len(df)
    total_companies = df["name"].nunique()
    top_industry = df["industry"].value_counts().idxmax()
    top_industry_count = df["industry"].value_counts().max()

    # --- KPI Cards
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Total 52-Week High Records", total_highs)
    kpi2.metric("Unique Companies", total_companies)
    kpi3.metric(f"Top Industry", f"{top_industry} ({top_industry_count})")

    # --- Highs Over Time
    st.subheader("📆 Highs Over Time")
    daily_counts = df.groupby("date").size().reset_index(name="count")
    st.plotly_chart(px.line(daily_counts, x="date", y="count", title="Daily 52-Week High Counts"), use_container_width=True)

    # --- Industry Breakdown
    st.subheader("🏭 Industry-wise Activity")
    top_ind = df["industry"].value_counts().reset_index()
    top_ind.columns = ["industry", "count"]
    top_ind = top_ind.sort_values("count", ascending=False)
    st.plotly_chart(px.bar(top_ind, x="industry", y="count", title="Top Industries by 52-Week Highs"), use_container_width=True)

    # --- Top Companies by Appearances
    st.subheader("🏆 Top Companies by Frequency")
    top_companies = df["name"].value_counts().reset_index()
    top_companies.columns = ["Company", "Appearances"]

    st.dataframe(
        top_companies,
        use_container_width=True,
        height=400
    )

    st.download_button("📥 Download Full Dataset", df.to_csv(index=False), "all_52_week_highs.csv")
