import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import json
import os

# Caching data loading
@st.cache_data
def load_data():
    df_orders = pd.read_csv("orders_dataset.csv", parse_dates=["order_purchase_timestamp"])
    df_payments = pd.read_csv("order_payments_dataset.csv")
    df_customers = pd.read_csv("customers_dataset.csv")
    
    # Gabungkan hanya kolom yang diperlukan untuk analisis
    df_payments = df_orders[["order_id", "customer_id", "order_purchase_timestamp", "order_status"]].merge(df_payments, on="order_id", how="left")
    df_payments = df_payments.merge(df_customers[["customer_id", "customer_state", "customer_unique_id"]], on="customer_id", how="left")
    
    return df_orders, df_payments, df_customers

df_orders, df_payments, df_customers = load_data()

# Sidebar Filters
st.sidebar.header("Filter Data")
start_date, end_date = st.sidebar.date_input("Rentang Waktu", 
    [df_orders["order_purchase_timestamp"].min(), df_orders["order_purchase_timestamp"].max()])
selected_state = st.sidebar.multiselect("Pilih Negara Bagian", df_customers["customer_state"].unique())

# Filter data lebih efisien
df_filtered = df_payments.query("(@start_date <= order_purchase_timestamp) & (order_purchase_timestamp <= @end_date)")
if selected_state:
    df_filtered = df_filtered[df_filtered["customer_state"].isin(selected_state)]

# Precompute metrics
total_orders = df_filtered["order_id"].nunique()
total_customers = df_filtered["customer_unique_id"].nunique()
total_revenue = df_filtered["payment_value"].sum()

# Dashboard
st.title("E-Commerce Sales Dashboard")
col1, col2, col3 = st.columns(3)
col1.metric("Total Orders", total_orders)
col2.metric("Total Customers", total_customers)
col3.metric("Total Revenue", f"${total_revenue:,.2f}")

# Trend Sales per Bulan
df_filtered["month_year"] = df_filtered["order_purchase_timestamp"].dt.to_period("M").astype(str)
trend_sales = df_filtered.groupby("month_year", as_index=False)["payment_value"].sum()
fig_trend = px.line(trend_sales, x="month_year", y="payment_value", title="Tren Penjualan per Bulan")
st.plotly_chart(fig_trend)

# Caching GeoJSON Loading
@st.cache_data
def load_geojson():
    geojson_path = "brazil_states.geojson"
    if not os.path.exists(geojson_path):
        url = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"
        response = requests.get(url)
        if response.status_code == 200:
            with open(geojson_path, "w", encoding="utf-8") as f:
                f.write(response.text)
    with open(geojson_path, "r", encoding="utf-8") as f:
        return json.load(f)

brazil_geojson = load_geojson()

# Geospatial Analysis
df_state = df_filtered.groupby("customer_state", as_index=False).agg(
    num_customers=("customer_id", "nunique"),
    num_orders=("order_id", "nunique"),
    total_revenue=("payment_value", "sum")
)
fig_map = px.choropleth(df_state, geojson=brazil_geojson, locations="customer_state",
    featureidkey="properties.sigla", color="total_revenue",
    hover_data=["num_customers", "num_orders", "total_revenue"], title="Distribusi Customer, Order, dan Revenue per State",
    color_continuous_scale="Viridis")
fig_map.update_geos(fitbounds="locations", visible=False)
st.plotly_chart(fig_map)

# Payment Analysis
with st.container():
    st.subheader("Analisis Pembayaran")
    col1, col2 = st.columns(2)
    
    # Bar Chart: Rata-rata Nilai Pembayaran per Status Pesanan
    with col1:
        payment_status = df_filtered.groupby("order_status", as_index=False)["payment_value"].mean().sort_values("payment_value", ascending=False)
        fig_payment_status = px.bar(payment_status, x="order_status", y="payment_value",
            title="Rata-rata Nilai Pembayaran per Status Pesanan", labels={"order_status": "Status Pesanan", "payment_value": "Rata-rata Pembayaran (BRL)"},
            color_discrete_sequence=["#636EFA"])
        fig_payment_status.update_layout(xaxis_tickangle=-45, showlegend=False)
        st.plotly_chart(fig_payment_status, use_container_width=True)
    
    # Pie Chart: Orders by Payment Type
    with col2:
        payment_counts = df_filtered["payment_type"].value_counts().reset_index()
        payment_counts.columns = ["payment_type", "count"]
        fig_pie = px.pie(payment_counts, names="payment_type", values="count", title="Proporsi Order Berdasarkan Metode Pembayaran")
        st.plotly_chart(fig_pie, use_container_width=True)

# RFM Analysis
rfm = df_filtered.groupby("customer_id", as_index=False).agg(
    Recency=("order_purchase_timestamp", lambda x: (df_orders["order_purchase_timestamp"].max() - x.max()).days),
    Frequency=("order_id", "count"),
    Monetary=("payment_value", "sum")
)
st.subheader("RFM Analysis Table")
st.dataframe(rfm)
##
