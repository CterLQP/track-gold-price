# Lưu file này với tên .py, ví dụ: gold_chart_app.py
import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import os # Thêm thư viện os để kiểm tra file

# --- Kết nối và tải dữ liệu từ Database ---
# Lấy đường dẫn tuyệt đối đến thư mục chứa script Streamlit
APP_DIR = os.path.dirname(os.path.abspath(__file__))
# Tạo đường dẫn tuyệt đối đến file database
DB_FILE = os.path.join(APP_DIR, 'gold_prices.db')

# Sử dụng cache của Streamlit để tránh đọc DB liên tục mỗi khi có tương tác
# ttl (time-to-live): Dữ liệu sẽ được cache trong 60 giây trước khi đọc lại từ DB
# allow_output_mutation=True: Cần thiết khi trả về đối tượng có thể thay đổi như DataFrame
@st.cache_data(ttl=60)
def load_data_from_db(limit=None):
    """Tải dữ liệu giá vàng từ SQLite database."""
    # Kiểm tra xem file DB có tồn tại không
    if not os.path.exists(DB_FILE):
        st.error(f"Lỗi: Không tìm thấy file database '{DB_FILE}'. Hãy đảm bảo script thu thập dữ liệu đang chạy và tạo file này.")
        return pd.DataFrame(columns=['Giá Vàng TG (VND/cây)']) # Trả về DataFrame rỗng

    try:
        # Sử dụng check_same_thread=False vì Streamlit chạy trong môi trường đa luồng
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        # Chọn cột timestamp và world_gold_price (đã là VND/cây)
        query = "SELECT timestamp, world_gold_price FROM gold_prices ORDER BY timestamp ASC"

        # Nếu người dùng chọn giới hạn số điểm dữ liệu
        if limit and isinstance(limit, int) and limit > 0:
             # Lấy N bản ghi mới nhất theo timestamp, sau đó sắp xếp lại tăng dần cho biểu đồ
             query = f"SELECT timestamp, world_gold_price FROM (SELECT * FROM gold_prices ORDER BY timestamp DESC LIMIT {limit}) ORDER BY timestamp ASC"

        df = pd.read_sql_query(query, conn)
        conn.close()

        # Kiểm tra nếu df rỗng sau khi query
        if df.empty:
            st.warning(f"Không có dữ liệu nào trong bảng 'gold_prices' của file '{DB_FILE}'.")
            return pd.DataFrame(columns=['Giá Vàng TG (VND/cây)'])

        # Chuyển đổi cột timestamp sang kiểu datetime
        # errors='coerce' sẽ chuyển các giá trị không hợp lệ thành NaT (Not a Time)
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')

        # Loại bỏ các hàng có timestamp không hợp lệ (NaT)
        df.dropna(subset=['timestamp'], inplace=True)

        # Kiểm tra lại nếu df rỗng sau khi loại bỏ NaT
        if df.empty:
            st.warning("Dữ liệu timestamp không hợp lệ, không thể vẽ biểu đồ.")
            return pd.DataFrame(columns=['Giá Vàng TG (VND/cây)'])

        # Đặt timestamp làm index (cần cho st.line_chart)
        df.set_index('timestamp', inplace=True)

        # Đổi tên cột để dễ hiểu hơn trên biểu đồ
        # Lưu ý: Cột 'world_gold_price' trong DB thực chất là giá VND/cây theo code gốc
        df.rename(columns={'world_gold_price': 'Giá Vàng TG (VND/cây)'}, inplace=True)

        return df

    except sqlite3.Error as e:
        st.error(f"Lỗi kết nối hoặc truy vấn database SQLite: {e}")
        return pd.DataFrame(columns=['Giá Vàng TG (VND/cây)']) # Trả về DataFrame rỗng
    except Exception as e:
        st.error(f"Lỗi không xác định khi tải dữ liệu: {e}")
        return pd.DataFrame(columns=['Giá Vàng TG (VND/cây)']) # Trả về DataFrame rỗng

# --- Giao diện Streamlit ---
st.set_page_config(page_title="Biểu đồ Giá Vàng Thế Giới", layout="wide")

st.title("📈 Biểu đồ Xu hướng Giá Vàng Thế Giới (VND/cây)")
st.caption(f"Dữ liệu được làm mới tự động mỗi phút. Lần tải trang: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# --- Lựa chọn số lượng điểm dữ liệu ---
st.sidebar.header("Tùy chọn hiển thị")
num_points_options = [50, 100, 200, 500, 1000, 'Tất cả']
num_points = st.sidebar.select_slider(
    "Số lượng điểm dữ liệu mới nhất:",
    options=num_points_options,
    value=200 # Giá trị mặc định
)

# --- Tải dữ liệu dựa trên lựa chọn ---
limit_query = None
if isinstance(num_points, int):
    limit_query = num_points

df_gold = load_data_from_db(limit=limit_query)

# --- Hiển thị biểu đồ và thông tin ---
if not df_gold.empty:
    st.subheader(f"Biểu đồ đường ({'Tất cả' if limit_query is None else str(limit_query) + ' điểm mới nhất'})")

    # Vẽ biểu đồ đường
    # Cung cấp tên cột cụ thể để vẽ
    st.line_chart(df_gold[['Giá Vàng TG (VND/cây)']])

    # Hiển thị giá mới nhất
    try:
        latest_timestamp = df_gold.index[-1]
        latest_price = df_gold['Giá Vàng TG (VND/cây)'].iloc[-1]

        # Tính toán thay đổi so với điểm trước đó (nếu có đủ dữ liệu)
        delta = None
        delta_color = "normal"
        if len(df_gold) > 1:
            previous_price = df_gold['Giá Vàng TG (VND/cây)'].iloc[-2]
            delta_value = latest_price - previous_price
            delta = f"{delta_value:,.2f} VND"
            if delta_value > 0:
                delta_color = "normal" # Mặc định Streamlit là xanh lá
            elif delta_value < 0:
                delta_color = "inverse" # Mặc định Streamlit là đỏ

        st.subheader("Giá trị mới nhất:")
        st.metric(label="Giá Vàng TG (VND/cây)",
                  value=f"{latest_price:,.2f} VND",
                  delta=delta,
                  delta_color=delta_color)
        st.caption(f"Thời điểm ghi nhận: {latest_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

    except IndexError:
        st.info("Chưa đủ dữ liệu để hiển thị giá trị mới nhất.")
    except Exception as e:
         st.error(f"Lỗi khi hiển thị giá trị mới nhất: {e}")


    # Tùy chọn: Hiển thị bảng dữ liệu
    if st.checkbox("Hiển thị dữ liệu dạng bảng"):
        st.subheader("Dữ liệu chi tiết:")
        # Tạo bản sao để định dạng hiển thị, giữ nguyên kiểu số trong df_gold
        df_display = df_gold.copy()
        # Định dạng lại cột giá trị để dễ đọc hơn trong bảng
        df_display['Giá Vàng TG (VND/cây)'] = df_display['Giá Vàng TG (VND/cây)'].map('{:,.2f}'.format)
        st.dataframe(df_display.sort_index(ascending=False)) # Sắp xếp mới nhất lên đầu
else:
    # Thông báo lỗi/cảnh báo đã được hiển thị trong hàm load_data_from_db
    st.info("Chưa có dữ liệu để vẽ biểu đồ. Hãy đảm bảo script gốc đang chạy và lưu dữ liệu.")

# Thêm nút làm mới thủ công vào sidebar
if st.sidebar.button("Làm mới dữ liệu ngay"):
    # Xóa cache và chạy lại để lấy dữ liệu mới nhất
    st.cache_data.clear()
    st.rerun()

st.sidebar.info("Lưu ý: Script thu thập dữ liệu gốc (code bạn cung cấp) cần chạy để cập nhật file `gold_prices.db`.")
