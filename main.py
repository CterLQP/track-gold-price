import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

# --- Kết nối và tải dữ liệu từ Database ---
DB_FILE = 'gold_prices.db'

# Sử dụng cache của Streamlit để tránh đọc DB liên tục mỗi khi có tương tác
# ttl (time-to-live): Dữ liệu sẽ được cache trong 60 giây trước khi đọc lại từ DB
# Điều này giúp app phản hồi nhanh hơn và giảm tải cho DB.
@st.cache_data(ttl=60)
def load_data_from_db(limit=None):
    """Tải dữ liệu giá vàng từ SQLite database."""
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False) # check_same_thread=False cần thiết cho Streamlit
        query = "SELECT timestamp, world_gold_price FROM gold_prices ORDER BY timestamp ASC"
        if limit and isinstance(limit, int) and limit > 0:
             query = f"SELECT timestamp, world_gold_price FROM (SELECT * FROM gold_prices ORDER BY timestamp DESC LIMIT {limit}) ORDER BY timestamp ASC"
            # Lấy N bản ghi mới nhất, sau đó sắp xếp lại theo thời gian tăng dần cho biểu đồ

        df = pd.read_sql_query(query, conn)
        conn.close()

        # Chuyển đổi cột timestamp sang kiểu datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Đặt timestamp làm index (cần cho st.line_chart)
        df.set_index('timestamp', inplace=True)

        # Đổi tên cột để dễ hiểu hơn trên biểu đồ
        df.rename(columns={'world_gold_price': 'Giá Vàng TG (VND/cây)'}, inplace=True)

        return df
    except sqlite3.Error as e:
        st.error(f"Lỗi kết nối hoặc truy vấn database: {e}")
        # Trả về DataFrame rỗng nếu có lỗi
        return pd.DataFrame(columns=['Giá Vàng TG (VND/cây)'])
    except Exception as e:
        st.error(f"Lỗi không xác định khi tải dữ liệu: {e}")
        # Trả về DataFrame rỗng nếu có lỗi
        return pd.DataFrame(columns=['Giá Vàng TG (VND/cây)'])

# --- Giao diện Streamlit ---
st.set_page_config(page_title="Biểu đồ Giá Vàng Thế Giới", layout="wide")

st.title("📈 Biểu đồ Xu hướng Giá Vàng Thế Giới (VND/cây)")
st.caption(f"Dữ liệu được cập nhật tự động. Lần làm mới cuối: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# --- Lựa chọn số lượng điểm dữ liệu ---
st.sidebar.header("Tùy chọn hiển thị")
num_points = st.sidebar.select_slider(
    "Số lượng điểm dữ liệu mới nhất cần hiển thị:",
    options=[50, 100, 200, 500, 1000, 'Tất cả'],
    value=200 # Giá trị mặc định
)

# --- Tải dữ liệu dựa trên lựa chọn ---
limit_query = None
if isinstance(num_points, int):
    limit_query = num_points

df_gold = load_data_from_db(limit=limit_query)

# --- Hiển thị biểu đồ và thông tin ---
if not df_gold.empty:
    st.subheader("Biểu đồ đường:")
    # Vẽ biểu đồ đường
    st.line_chart(df_gold)

    # Hiển thị giá mới nhất
    latest_timestamp = df_gold.index[-1]
    latest_price = df_gold['Giá Vàng TG (VND/cây)'].iloc[-1]

    st.subheader("Giá trị mới nhất:")
    st.metric(label="Giá Vàng TG (VND/cây)",
              value=f"{latest_price:,.2f} VND",
              # Có thể thêm delta nếu muốn so sánh với điểm trước đó
              # delta=f"{latest_price - df_gold['Giá Vàng TG (VND/cây)'].iloc[-2]:,.2f} VND" # Bỏ comment nếu muốn hiển thị thay đổi
              )
    st.caption(f"Thời điểm ghi nhận: {latest_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

    # Tùy chọn: Hiển thị bảng dữ liệu
    if st.checkbox("Hiển thị dữ liệu dạng bảng"):
        st.subheader("Dữ liệu chi tiết:")
        # Định dạng lại cột giá trị để dễ đọc hơn trong bảng
        df_display = df_gold.copy()
        df_display['Giá Vàng TG (VND/cây)'] = df_display['Giá Vàng TG (VND/cây)'].map('{:,.2f}'.format)
        st.dataframe(df_display.sort_index(ascending=False)) # Sắp xếp mới nhất lên đầu
else:
    st.warning(f"Không tìm thấy dữ liệu trong file '{DB_FILE}' hoặc file không tồn tại. Hãy đảm bảo script thu thập dữ liệu đang chạy và lưu vào đúng file.")

st.sidebar.info("Lưu ý: Script thu thập dữ liệu gốc cần chạy để cập nhật file `gold_prices.db`.")
st.sidebar.button("Làm mới dữ liệu") # Nút này sẽ trigger chạy lại script Streamlit và @st.cache_data sẽ kiểm tra ttl
