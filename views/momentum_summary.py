import streamlit as st
from db_utils import get_momentum_summary
from plot_utils import market_cap_line_chart
from db_utils import get_historical_market_cap

def main():
    st.title("📈 Momentum Summary")

    df = get_momentum_summary()

    industries = ["All"] + sorted(df['industry'].dropna().unique().tolist())
    selected_industry = st.selectbox("Industry", industries)
    min_hits = st.slider("Minimum hits in last 30 days", 0, 30, 1)
    min_gain = st.slider("Min % Market Cap Gain Since First Seen", 0, 500, 0)

    filtered_df = df.copy()
    if selected_industry != "All":
        filtered_df = filtered_df[filtered_df['industry'] == selected_industry]

    filtered_df = filtered_df[(filtered_df['hits_30'] >= min_hits) & (filtered_df['%_gain_mc'] >= min_gain)]

    st.markdown(f"Showing **{len(filtered_df)}** companies meeting criteria")
    st.dataframe(filtered_df.sort_values(by=["hits_30", "hits_7"], ascending=False), use_container_width=True)

    st.download_button("📥 Download CSV", filtered_df.to_csv(index=False), "momentum_summary.csv")

    # Market Cap Trend Chart
    if len(filtered_df) > 0:
        selected_stock = st.selectbox("Select Company to View Market Cap Trend", options=filtered_df["name"].unique())
        show_market_cap_trend(selected_stock)
    else:
        st.info("No companies to display market cap trend.")

def show_market_cap_trend(selected_stock):
    hist_data = get_historical_market_cap()
    stock_data = hist_data[hist_data["name"] == selected_stock]
    if not stock_data.empty:
        fig = market_cap_line_chart(stock_data, selected_stock)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning(f"No market cap data available for {selected_stock}")
