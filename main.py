import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta
import time # Required for time.sleep
# Import the specific function if possible, otherwise rely on vnstock being installed
try:
    from vnstock.explorer.misc import sjc_gold_price
except ImportError:
    st.error("Thư viện 'vnstock' chưa được cài đặt hoặc không tìm thấy hàm 'sjc_gold_price'. Vui lòng cài đặt: pip install vnstock")
    st.stop()


# --- Constants ---
GOLD_TICKER = 'GC=F'
FOREX_TICKER = 'VND=X'
OUNCE_TO_CAY_FACTOR = 1.20565303
LOGO_URL_SIDEBAR = "https://res.cloudinary.com/dd7gti2kn/image/upload/v1745678186/samples/people/LOGO_LQP_msfted.png"
SJC_FETCH_INTERVAL_DAYS = 7 # Fetch SJC data every 7 days
SJC_FETCH_DELAY_SECONDS = 2 # Delay between SJC API calls
SJC_TARGET_BRANCH = 'Hồ Chí Minh' # Branch to filter SJC prices for consistency
CACHE_TTL_SECONDS = 10800 # Cache data for 3 hours (3 * 60 * 60)

# --- Set Page Config FIRST ---
st.set_page_config(
    page_title="Biểu đồ Giá Vàng",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🪙"
)

# --- Custom CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Inter', sans-serif; }
    /* Main content area styling */
    .main .block-container {
        padding: 1.5rem 2rem;
        /* background-color: #fcfcfc; */
    }
    /* Sidebar styling - Reverted */
    [data-testid="stSidebar"] {
        padding-top: 1rem;
        /* background-color: #FFFFFF; */
        /* border-right: 1px solid #e6e6e6; */
    }
    .stAlert, [data-testid="stExpander"] {
        border-radius: 0.5rem;
        border: 1px solid #eee;
    }
    [data-testid="stExpander"] summary {
        font-weight: 600;
    }
    .footer-caption { color: grey; font-size: 0.85em; }
    .footer-copyright { text-align: right; color: grey; font-size: 0.85em; }
    /* Metric styling */
    [data-testid="stMetric"] {
        background-color: #FFFFFF; border: 1px solid #e6e6e6; border-radius: 0.5rem;
        padding: 1rem 1.25rem; transition: box-shadow 0.2s ease-in-out;
    }
    [data-testid="stMetric"]:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    [data-testid="stMetricLabel"] { font-weight: 500; color: #555555; font-size: 0.9em; padding-bottom: 0.25rem; }
    [data-testid="stMetricValue"] { font-weight: 700; font-size: 2em; color: #1E1E1E; line-height: 1.2; }
    [data-testid="stMetricDelta"] { font-weight: 500; font-size: 0.95em; padding-top: 0.25rem; }
    /* Subheader styling - Reverted border */
    h2 {
        margin-bottom: 0.8rem;
        margin-top: 1.5rem;
        /* border-bottom: 1px solid #eee; */
        /* padding-bottom: 0.3rem; */
    }
    /* Chart styling */
    .stPlotlyChart {
        margin-bottom: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)


# --- Data Fetching Function (World Gold & Forex) ---
@st.cache_data(ttl=CACHE_TTL_SECONDS) # Increased TTL
def fetch_world_historical_data(start_date, end_date):
    """Fetches world gold and forex data."""
    try:
        # Add a small delay before fetching yfinance data
        time.sleep(0.5)
        gold_data = yf.download(GOLD_TICKER, start=start_date, end=end_date + timedelta(days=1), progress=False)
        time.sleep(0.5) # Another small delay
        forex_data = yf.download(FOREX_TICKER, start=start_date, end=end_date + timedelta(days=1), progress=False)
        if gold_data.empty or forex_data.empty: return None, None
        return gold_data, forex_data
    except Exception as e:
        # Check specifically for rate limit error if possible (yfinance might wrap it)
        if 'YFRateLimitError' in str(e) or 'Too Many Requests' in str(e):
             print(f"Yahoo Finance Rate Limit Error (World Data): {e}")
             # Return None to indicate failure, caller will show error message
             return None, None
        else:
             print(f"Error fetching world data: {e}")
             return None, None

# --- Data Fetching Function (SJC Historical via vnstock) ---
@st.cache_data(ttl=CACHE_TTL_SECONDS) # Increased TTL
def fetch_sjc_historical_data(start_date, end_date):
    """
    Fetches historical SJC gold prices using vnstock by iterating through dates.
    Filters for a specific branch and sell price.
    """
    all_sjc_prices = []
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        try:
            # Add a small delay even for vnstock calls, just in case its source is also sensitive
            time.sleep(0.2)
            prices = sjc_gold_price(date=date_str)
            if not prices.empty:
                target_price = prices[prices['branch'] == SJC_TARGET_BRANCH]['sell_price']
                if not target_price.empty:
                    price_value = pd.to_numeric(str(target_price.iloc[0]).replace(',', ''), errors='coerce')
                    if pd.notna(price_value):
                         all_sjc_prices.append({'Timestamp': pd.to_datetime(current_date), 'Giá SJC (VND/cây)': price_value})
        except Exception as e:
            # Check specifically for rate limit error if possible (less likely for vnstock source?)
            if 'Too Many Requests' in str(e):
                 print(f"Rate Limit Error (SJC Data) on {date_str}: {e}")
                 # Optionally break or just continue, hoping later calls succeed
            else:
                 print(f"Error fetching SJC on {date_str}: {e}")
        current_date += timedelta(days=SJC_FETCH_INTERVAL_DAYS)
        if current_date <= end_date: time.sleep(SJC_FETCH_DELAY_SECONDS)
    if not all_sjc_prices: return pd.DataFrame()
    else: return pd.DataFrame(all_sjc_prices)


# --- Calculation Function (World Gold VND) ---
def calculate_world_gold_vnd(df_gold, df_forex):
    if df_gold is None or df_forex is None or 'Close' not in df_gold.columns or 'Close' not in df_forex.columns:
        return pd.DataFrame()
    combined_data = pd.DataFrame(index=df_gold.index)
    combined_data['Gold_USD_Oz'] = df_gold['Close']
    combined_data['Forex_VND_USD'] = df_forex['Close']
    combined_data.ffill(inplace=True); combined_data.dropna(inplace=True)
    if combined_data.empty: return pd.DataFrame()
    combined_data['Giá TG Quy Đổi (VND/cây)'] = combined_data['Gold_USD_Oz'] * combined_data['Forex_VND_USD'] * OUNCE_TO_CAY_FACTOR
    combined_data.reset_index(inplace=True); combined_data.rename(columns={'Date': 'Timestamp'}, inplace=True)
    combined_data['Timestamp'] = pd.to_datetime(combined_data['Timestamp'])
    return combined_data[['Timestamp', 'Giá TG Quy Đổi (VND/cây)']]


# --- Streamlit App Layout ---

# --- Sidebar for Controls ---
with st.sidebar:
    st.image(LOGO_URL_SIDEBAR, width=100) # Logo width set to 100
    st.header("📅 Thời gian")
    st.write("")

    predefined_ranges = {
        "1 Tháng": 30, "3 Tháng": 90, "6 Tháng": 180,
        "1 Năm": 365, "Từ đầu năm (YTD)": "YTD", "Tất cả (Tối đa 10 năm)": "Max"
    }
    selected_range_label = st.selectbox("Chọn nhanh:", options=list(predefined_ranges.keys()), index=2)

    st.divider()
    st.markdown("**Hoặc chọn ngày:**")

    today = datetime.now().date()
    if selected_range_label == "Tất cả (Tối đa 10 năm)":
        default_start_date_calc = max(today - timedelta(days=10*365), datetime(2015, 1, 1).date())
    elif selected_range_label == "Từ đầu năm (YTD)":
        default_start_date_calc = datetime(today.year, 1, 1).date()
    else:
        default_start_date_calc = today - timedelta(days=predefined_ranges[selected_range_label])
    default_end_date_calc = today

    start_date_input = st.date_input("Từ ngày", default_start_date_calc, label_visibility="collapsed")
    end_date_input = st.date_input("Đến ngày", default_end_date_calc, label_visibility="collapsed")

    start_date = start_date_input
    end_date = end_date_input
    final_label = f"{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}"

    if start_date > end_date:
        st.error("Lỗi: Ngày bắt đầu không được sau ngày kết thúc.")
        st.stop()

    st.divider()
    st.caption(f"SJC lấy mỗi {SJC_FETCH_INTERVAL_DAYS} ngày ({SJC_TARGET_BRANCH}).")


# --- Main Page Layout ---
st.title("📊 Biểu đồ Lịch sử Giá Vàng")
st.caption(f"Giá TG quy đổi & Giá SJC | Khoảng thời gian: {final_label}")
st.write("")

# --- Initialize variables ---
world_data_error = False
sjc_data_error = False
world_gold_vnd_hist = pd.DataFrame()
sjc_hist = pd.DataFrame()
gold_hist = None
forex_hist = None
spread_chart_data = pd.DataFrame()

# --- Fetch World Data ---
# Display error message outside the spinner if fetching fails
fetch_world_success = False
with st.spinner(f"Đang tải dữ liệu giá TG..."):
    gold_hist, forex_hist = fetch_world_historical_data(start_date, end_date)
    if gold_hist is None or forex_hist is None:
        world_data_error = True
    else:
        world_gold_vnd_hist = calculate_world_gold_vnd(gold_hist, forex_hist)
        if world_gold_vnd_hist.empty:
            world_data_error = True
        else:
            fetch_world_success = True # Mark as success only if calculation also works

if world_data_error:
     st.warning("⚠️ Lỗi khi tải dữ liệu giá thế giới (có thể do giới hạn truy cập từ Yahoo Finance). Vui lòng thử lại sau.", icon="📉")
elif fetch_world_success:
     st.toast("Tải dữ liệu giá thế giới thành công!", icon="✅")


# --- Fetch SJC Data ---
fetch_sjc_success = False
with st.spinner(f"Đang tải dữ liệu giá SJC (có thể mất vài phút)..."):
     sjc_hist = fetch_sjc_historical_data(start_date, end_date)
     if sjc_hist.empty:
         sjc_data_error = True
     else:
         sjc_hist['Timestamp'] = pd.to_datetime(sjc_hist['Timestamp'])
         fetch_sjc_success = True

if not sjc_data_error and fetch_sjc_success:
     st.toast("Tải dữ liệu SJC thành công!", icon="✅")
# No explicit error message here, handled by chart display logic


# --- Display Metrics ---
col1, col2, col3 = st.columns(3)

# Function to format delta string
def format_delta(delta_value):
    if delta_value is None or pd.isna(delta_value): return None
    sign = "+" if delta_value > 0 else ""
    return f"{sign}{delta_value:,.0f} VND"

# Metric 1: World Gold
latest_world_price = None
latest_world_date_str = "N/A"
delta_world = None
if not world_data_error:
    latest_world_price = world_gold_vnd_hist.iloc[-1]['Giá TG Quy Đổi (VND/cây)']
    latest_world_date = world_gold_vnd_hist.iloc[-1]['Timestamp']
    latest_world_date_str = latest_world_date.strftime('%d/%m')
    if len(world_gold_vnd_hist) > 1:
         prev_world_price = world_gold_vnd_hist.iloc[-2]['Giá TG Quy Đổi (VND/cây)']
         if pd.notna(latest_world_price) and pd.notna(prev_world_price):
             delta_world = latest_world_price - prev_world_price
with col1:
    st.metric(label=f"Giá TG Quy Đổi ({latest_world_date_str})",
              value=f"{latest_world_price:,.0f} VND" if pd.notna(latest_world_price) else "N/A",
              delta=format_delta(delta_world), help="Giá vàng thế giới quy đổi sang VND/cây (ngày gần nhất có dữ liệu)")

# Metric 2: SJC Gold
latest_sjc_price = None
latest_sjc_date_str = "N/A"
delta_sjc = None
if not sjc_data_error:
    latest_sjc_price = sjc_hist.iloc[-1]['Giá SJC (VND/cây)']
    latest_sjc_date = sjc_hist.iloc[-1]['Timestamp']
    latest_sjc_date_str = latest_sjc_date.strftime('%d/%m')
    if len(sjc_hist) > 1:
         prev_sjc_price = sjc_hist.iloc[-2]['Giá SJC (VND/cây)']
         if pd.notna(latest_sjc_price) and pd.notna(prev_sjc_price):
             delta_sjc = latest_sjc_price - prev_sjc_price
with col2:
    st.metric(label=f"Giá SJC ({latest_sjc_date_str})",
              value=f"{latest_sjc_price:,.0f} VND" if pd.notna(latest_sjc_price) else "N/A",
              delta=format_delta(delta_sjc), help=f"Giá vàng SJC tại {SJC_TARGET_BRANCH} (ngày gần nhất có dữ liệu)")

# Metric 3: Spread
latest_spread = None
latest_spread_date_str = "N/A"
delta_spread = None
spread_calculated_for_metric = False
if pd.notna(latest_world_price) and pd.notna(latest_sjc_price):
    latest_spread = latest_sjc_price - latest_world_price
    latest_spread_date_str = f"~ {datetime.now().strftime('%d/%m')}"
    spread_calculated_for_metric = True
with col3:
    st.metric(label=f"Chênh lệch ({latest_spread_date_str})",
              value=f"{latest_spread:,.0f} VND" if spread_calculated_for_metric else "N/A",
              delta=None, # Omit delta for spread metric
              help="Chênh lệch giữa giá SJC và giá TG quy đổi mới nhất")

st.divider()

# --- Display World Gold Chart ---
st.subheader("🌍 Giá Vàng Thế Giới (Quy đổi VND/cây)")
if world_data_error: st.warning("Lỗi tải hoặc không có dữ liệu giá vàng thế giới.")
else:
    fig_world = px.line(world_gold_vnd_hist, x='Timestamp', y='Giá TG Quy Đổi (VND/cây)',
                        labels={'Timestamp': 'Thời gian', 'Giá TG Quy Đổi (VND/cây)': 'Giá (VND/cây)'})
    fig_world.update_traces(line_color='#1f77b4', hovertemplate="Ngày: %{x|%d/%m/%Y}<br>Giá TG: %{y:,.0f}<extra></extra>")
    fig_world.update_layout(hovermode="x unified", margin=dict(t=10, b=0, l=0, r=0))
    st.plotly_chart(fig_world, use_container_width=True)

# --- Display SJC Chart ---
st.subheader("🇻🇳 Giá Vàng SJC (VND/cây)")
if sjc_data_error: st.warning(f"Không có dữ liệu SJC (Lấy mỗi {SJC_FETCH_INTERVAL_DAYS} ngày).")
else:
    fig_sjc = px.line(sjc_hist, x='Timestamp', y='Giá SJC (VND/cây)',
                      labels={'Timestamp': 'Thời gian', 'Giá SJC (VND/cây)': 'Giá (VND/cây)'}, markers=True)
    fig_sjc.update_traces(line_color='#ff7f0e', hovertemplate="Ngày: %{x|%d/%m/%Y}<br>Giá SJC: %{y:,.0f}<extra></extra>")
    fig_sjc.update_layout(hovermode="x unified", margin=dict(t=10, b=0, l=0, r=0))
    st.plotly_chart(fig_sjc, use_container_width=True)

# --- Calculate and Display Spread Chart using Forward Fill ---
st.subheader("⚖️ Chênh lệch Giá (SJC - Thế Giới Quy Đổi)")
spread_chart_data = pd.DataFrame()
if not world_data_error and not sjc_data_error:
    if not world_gold_vnd_hist.empty and not sjc_hist.empty: # Ensure both DFs have data
        date_range = pd.date_range(start=min(world_gold_vnd_hist['Timestamp'].min(), sjc_hist['Timestamp'].min()),
                                   end=max(world_gold_vnd_hist['Timestamp'].max(), sjc_hist['Timestamp'].max()), freq='D')
        spread_chart_data = pd.DataFrame(index=date_range)
        spread_chart_data.index.name = 'Timestamp'

        spread_chart_data = pd.merge(spread_chart_data, world_gold_vnd_hist.set_index('Timestamp'), left_index=True, right_index=True, how='left')
        sjc_indexed = sjc_hist.set_index('Timestamp')
        spread_chart_data = pd.merge(spread_chart_data, sjc_indexed, left_index=True, right_index=True, how='left')
        spread_chart_data['Giá SJC (VND/cây)'].ffill(inplace=True)
        spread_chart_data.dropna(subset=['Giá TG Quy Đổi (VND/cây)', 'Giá SJC (VND/cây)'], inplace=True)

        if not spread_chart_data.empty:
            spread_chart_data['Chênh lệch (SJC - TG)'] = spread_chart_data['Giá SJC (VND/cây)'] - spread_chart_data['Giá TG Quy Đổi (VND/cây)']
            spread_chart_data.reset_index(inplace=True)

if spread_chart_data.empty or 'Chênh lệch (SJC - TG)' not in spread_chart_data.columns:
    st.warning("Không thể tính hoặc vẽ biểu đồ chênh lệch (thiếu dữ liệu TG hoặc SJC).")
else:
    fig_spread = px.line(spread_chart_data, x='Timestamp', y='Chênh lệch (SJC - TG)',
                         labels={'Timestamp': 'Thời gian', 'Chênh lệch (SJC - TG)': 'Chênh lệch (VND/cây)'})
    fig_spread.update_traces(line_color='#2ca02c', hovertemplate="Ngày: %{x|%d/%m/%Y}<br>Chênh lệch: %{y:,.0f}<extra></extra>")
    fig_spread.update_layout(hovermode="x unified", margin=dict(t=10, b=0, l=0, r=0))
    st.plotly_chart(fig_spread, use_container_width=True)

# --- Display Raw Data (Optional Expander) ---
expander_title_parts = []
if not world_data_error: expander_title_parts.append("TG Gốc")
if not sjc_data_error: expander_title_parts.append("SJC Fetched")

if expander_title_parts:
    with st.expander(f"🔍 Xem dữ liệu gốc ({' & '.join(expander_title_parts)})"):
        num_cols = len(expander_title_parts)
        cols = st.columns(num_cols)
        col_index = 0
        if not world_data_error and gold_hist is not None and forex_hist is not None:
            with cols[col_index]:
                st.caption("Vàng TG (USD/oz)"); st.dataframe(gold_hist.style.format("{:,.2f}"), use_container_width=True, height=250)
                st.caption("Tỷ giá USD/VND"); st.dataframe(forex_hist.style.format("{:,.2f}"), use_container_width=True, height=250)
            col_index += 1
        if not sjc_data_error and not sjc_hist.empty:
             with cols[col_index]:
                st.caption(f"Vàng SJC (mỗi {SJC_FETCH_INTERVAL_DAYS} ngày)"); st.dataframe(sjc_hist.set_index('Timestamp').style.format({'Giá SJC (VND/cây)': '{:,.0f}'}), use_container_width=True, height=250)

# --- Footer ---
st.divider()
col_left, col_right = st.columns([0.7, 0.3])
with col_left:
     st.markdown(f"<p class='footer-caption'>Nguồn: Yahoo Finance (TG), vnstock (SJC). Tải lúc: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}</p>", unsafe_allow_html=True)
with col_right:
     st.markdown("<p class='footer-copyright'>Copyright ©LeQuyPhat</p>", unsafe_allow_html=True)
