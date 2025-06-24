import plotly.express as px

def sector_heatmap(heat_df, title):
    heat_df = heat_df.copy()
    heat_df["Avg_Gain_Percent"] = heat_df["Avg_Gain_Percent"].round(2)

    fig = px.density_heatmap(
        heat_df,
        x="industry",
        y="Count",
        z="Avg_Gain_Percent",
        color_continuous_scale="RdYlGn",
        title=title,
        hover_data=["industry", "Count", "Avg_Gain_Percent"]
    )
    # Removed unsupported text updates
    fig.update_traces(
        hovertemplate="<b>%{x}</b><br>Count: %{y}<br>Avg Gain: %{z:.2f}%<extra></extra>"
    )
    fig.update_layout(
        xaxis_title="Industry",
        yaxis_title="Company Count",
        height=600,
        margin=dict(l=40, r=40, t=80, b=40)
    )
    return fig

def animated_sector_heatmap(weekly_agg, title):
    weekly_agg = weekly_agg.copy()
    weekly_agg["Avg_Gain_Percent"] = weekly_agg["Avg_Gain_Percent"].round(2)

    fig = px.density_heatmap(
        weekly_agg,
        x="industry",
        y="Count",
        z="Avg_Gain_Percent",
        animation_frame="week",
        color_continuous_scale="RdYlGn",
        title=title,
        hover_data=["industry", "Count", "Avg_Gain_Percent"]
    )
    # Removed unsupported text updates
    fig.update_traces(
        hovertemplate="<b>%{x}</b><br>Count: %{y}<br>Avg Gain: %{z:.2f}%<extra></extra>"
    )
    fig.update_layout(
        xaxis_title="Industry",
        yaxis_title="Company Count",
        height=600
    )
    return fig

def market_cap_line_chart(stock_data, company_name):
    fig = px.line(
        stock_data,
        x="date",
        y="market_cap",
        title=f"Market Cap Trend - {company_name}",
        markers=True
    )
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Market Cap",
        height=500
    )
    return fig
