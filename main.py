import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# --- Hàm tải dữ liệu từ Yahoo Finance ---

# Cache dữ liệu để tránh tải lại liên tục khi thay đổi widget không liên quan đến ngày tháng
# ttl=timedelta(hours=1): Cache dữ liệu trong 1 giờ
@st.cache_data(ttl=timedelta(hours=1))
def load_gold_data(ticker, start_date, end_date):
    """
    Tải dữ liệu lịch sử cho một mã ticker từ Yahoo Finance.
    ticker: Mã chứng khoán (ví dụ: 'GC=F' cho Gold Futures)
    start_date: Ngày bắt đầu (kiểu date hoặc datetime)
    end_date: Ngày kết thúc (kiểu date hoặc datetime)
    """
    try:
        # yfinance thường không bao gồm end_date, nên cần +1 ngày
        # Chuyển đổi date thành datetime nếu cần để cộng timedelta
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.min.time()) + timedelta(days=1)

        # Tải dữ liệu
        data = yf.download(ticker, start=start_dt, end=end_dt, progress=False) # Tắt progress bar

        if data.empty:
            st.warning(f"Không tìm thấy dữ liệu cho mã {ticker} trong khoảng thời gian đã chọn.")
            return None
        # Đổi tên cột cho thân thiện hơn
        data.rename(columns={
            'Open': 'Mở cửa',
            'High': 'Cao nhất',
            'Low': 'Thấp nhất',
            'Close': 'Đóng cửa',
            'Adj Close': 'Đóng cửa điều chỉnh',
            'Volume': 'Khối lượng'
            }, inplace=True)
        return data
    except Exception as e:
        st.error(f"Lỗi khi tải dữ liệu từ yfinance: {e}")
        return None

# --- Thiết lập giao diện Streamlit ---
st.set_page_config(page_title="Biểu đồ Lịch sử Giá Vàng", layout="wide")
st.title("📈 Biểu đồ Lịch sử Giá Vàng (USD/ounce)")
st.caption("Dữ liệu được lấy từ Yahoo Finance.")

# --- Chọn Ticker ---
# Có thể thêm các lựa chọn khác như 'GLD' (ETF) nếu muốn
ticker_choice = st.selectbox(
    "Chọn loại dữ liệu vàng:",
    options=['GC=F', 'GLD'],
    format_func=lambda x: f"{x} (Gold Futures)" if x == 'GC=F' else f"{x} (SPDR Gold Shares ETF)"
)
st.write(f"Đang sử dụng mã: **{ticker_choice}**")


# --- Sidebar cho lựa chọn thời gian ---
st.sidebar.header("📅 Chọn khoảng thời gian")

# Các khoảng thời gian định sẵn
predefined_ranges = {
    "1 Tháng": timedelta(days=30),
    "3 Tháng": timedelta(days=90),
    "6 Tháng": timedelta(days=180),
    "1 Năm": timedelta(days=365),
    "5 Năm": timedelta(days=365*5),
    "Từ đầu năm (YTD)": "YTD",
    "Tất cả": "ALL"
}

# Sử dụng st.radio để chọn nhanh
selected_range_key = st.sidebar.radio(
    "Chọn nhanh:",
    options=list(predefined_ranges.keys()),
    index=3 # Mặc định chọn "1 Năm"
)

# Xác định ngày bắt đầu và kết thúc dựa trên lựa chọn nhanh
today = datetime.now().date()
start_date_auto = today - timedelta(days=365) # Mặc định
end_date_auto = today

if predefined_ranges[selected_range_key] == "YTD":
    start_date_auto = datetime(today.year, 1, 1).date()
    end_date_auto = today
elif predefined_ranges[selected_range_key] == "ALL":
    # yfinance sẽ tự lấy tất cả nếu start date đủ xa
    # Đặt ngày bắt đầu rất sớm (ví dụ: 1970) để lấy hết lịch sử có thể
    start_date_auto = datetime(1970, 1, 1).date()
    end_date_auto = today
else:
    time_delta = predefined_ranges[selected_range_key]
    start_date_auto = today - time_delta
    end_date_auto = today

# Cho phép tùy chỉnh ngày bắt đầu và kết thúc
st.sidebar.markdown("---") # Dòng kẻ ngang phân cách
start_date = st.sidebar.date_input("Ngày bắt đầu tùy chỉnh", start_date_auto)
end_date = st.sidebar.date_input("Ngày kết thúc tùy chỉnh", end_date_auto)

# --- Validate ngày tháng ---
if start_date > end_date:
    st.error("Lỗi: Ngày kết thúc phải sau ngày bắt đầu.")
    st.stop() # Dừng thực thi nếu ngày không hợp lệ

# --- Tải và hiển thị dữ liệu ---
st.subheader(f"Dữ liệu từ {start_date.strftime('%d/%m/%Y')} đến {end_date.strftime('%d/%m/%Y')}")

# Tải dữ liệu dựa trên lựa chọn của người dùng
gold_data = load_gold_data(ticker_choice, start_date, end_date)

if gold_data is not None and not gold_data.empty:
    # Chọn cột để vẽ biểu đồ (Thường là 'Đóng cửa')
    chart_column = 'Đóng cửa'
    if chart_column not in gold_data.columns:
        st.error(f"Không tìm thấy cột '{chart_column}' trong dữ liệu trả về.")
        st.stop()

    # --- Vẽ biểu đồ ---
    st.line_chart(gold_data[[chart_column]])

    # --- Hiển thị thêm thông tin (tùy chọn) ---
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    try:
        latest_price = gold_data[chart_column].iloc[-1]
        price_change = gold_data[chart_column].iloc[-1] - gold_data[chart_column].iloc[-2] if len(gold_data) > 1 else 0
        percent_change = (price_change / gold_data[chart_column].iloc[-2] * 100) if len(gold_data) > 1 and gold_data[chart_column].iloc[-2] != 0 else 0

        col1.metric(f"Giá {chart_column} cuối cùng", f"${latest_price:,.2f}", f"{price_change:+.2f} ({percent_change:+.2f}%)")
        col2.metric("Cao nhất (trong khoảng)", f"${gold_data['Cao nhất'].max():,.2f}")
        col3.metric("Thấp nhất (trong khoảng)", f"${gold_data['Thấp nhất'].min():,.2f}")
    except IndexError:
        st.warning("Không đủ dữ liệu để tính toán thông tin tóm tắt.")
    except Exception as e:
        st.error(f"Lỗi khi tính toán thông tin tóm tắt: {e}")


    # --- Hiển thị bảng dữ liệu (tùy chọn) ---
    if st.checkbox("Hiển thị dữ liệu chi tiết dạng bảng"):
        st.dataframe(gold_data.sort_index(ascending=False)) # Sắp xếp mới nhất lên đầu
else:
    st.info("Không có dữ liệu để hiển thị. Vui lòng thử lại hoặc chọn khoảng thời gian khác.")

st.sidebar.markdown("---")
st.sidebar.caption("Lưu ý: Dữ liệu tài chính có thể có độ trễ.")
