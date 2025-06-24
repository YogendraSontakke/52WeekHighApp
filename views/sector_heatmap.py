import streamlit as st
import pandas as pd
from db_utils import get_momentum_summary, get_historical_market_cap, get_all_dates
from plot_utils import sector_heatmap, animated_sector_heatmap

def main():
    st.title("🔥 Sector Heatmap")

    momentum_data = get_momentum_summary()
    hist_data = get_historical_market_cap()
    all_dates = get_all_dates()

    industries = ["All"] + sorted(momentum_data['industry'].dropna().unique())
    selected_industry = st.selectbox("Industry", industries)

    start_date, end_date = st.select_slider(
        "Select date range",
        options=all_dates,
        value=(min(all_dates), max(all_dates)),
        format_func=lambda d: d.strftime('%Y-%m-%d')
    )
    start_date, end_date = sorted([start_date, end_date])

    hist_filtered = hist_data[
        (hist_data["date"].dt.date >= start_date) &
        (hist_data["date"].dt.date <= end_date)
    ]
    if selected_industry != "All":
        hist_filtered = hist_filtered[hist_filtered["industry"] == selected_industry]
        momentum_data = momentum_data[momentum_data["industry"] == selected_industry]

    combined = pd.merge(hist_filtered, momentum_data[["name", "%_gain_mc"]], on="name", how="left")

    heat_df = combined.groupby("industry").agg(
        Count=("name", "count"),
        Avg_Gain_Percent=("%_gain_mc", "mean")
    ).reset_index()

    if not heat_df.empty:
        fig = sector_heatmap(heat_df, f"Sector Heatmap: {start_date} to {end_date}")
        st.plotly_chart(fig, use_container_width=True)

        st.download_button(
            "📥 Download Heatmap Data (CSV)",
            data=heat_df.to_csv(index=False),
            file_name=f"heatmap_data_{start_date}_to_{end_date}.csv"
        )
    else:
        st.warning("No data for selected filters.")

    # Animated heatmap
    st.subheader("⏳ Animated Weekly Heatmap")
    hist_data["week"] = hist_data["date"].dt.to_period("W").apply(lambda r: r.start_time.date())
    combined_week = pd.merge(hist_data, momentum_data[["name", "%_gain_mc"]], on="name", how="left")
    if selected_industry != "All":
        combined_week = combined_week[combined_week["industry"] == selected_industry]

    weekly_agg = combined_week.groupby(["week", "industry"]).agg(
        Count=("name", "count"),
        Avg_Gain_Percent=("%_gain_mc", "mean")
    ).reset_index()

    if not weekly_agg.empty:
        anim_fig = animated_sector_heatmap(weekly_agg, "Weekly Sector Heatmap")
        st.plotly_chart(anim_fig, use_container_width=True)
    else:
        st.warning("Not enough data for animation.")
