import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time

# --- Các hàm lấy dữ liệu từ code gốc (loại bỏ phần không cần thiết) ---

# @st.cache_data(ttl=60) # Cân nhắc cache để tránh request liên tục nếu web có giới hạn
def fetch_web_data():
    """Tải nội dung HTML từ trang web Trading Economics."""
    url = "https://tradingeconomics.com/commodities"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10) # Thêm timeout
        response.raise_for_status() # Kiểm tra lỗi HTTP (4xx, 5xx)
        return response.content
    except requests.exceptions.RequestException as e:
        st.error(f"Lỗi mạng hoặc HTTP khi tải dữ liệu: {e}")
        return None
    except Exception as e:
        st.error(f"Lỗi không xác định khi tải dữ liệu web: {e}")
        return None

def clean_major_name(major):
    """Làm sạch tên hàng hóa để so sánh chính xác."""
    return major.split("\n\n")[0].strip() if "\n\n" in major else major.strip()

def format_value(value):
    """Định dạng giá trị để luôn có 2 chữ số sau dấu thập phân."""
    try:
        # Thử chuyển đổi trực tiếp sang float trước
        f_value = float(value)
        return f"{f_value:.2f}"
    except ValueError:
         # Nếu không được, xử lý như chuỗi (code gốc)
        if "." in value:
            integer_part, decimal_part = value.split(".", 1)
            # Đảm bảo decimal_part chỉ chứa số và giới hạn độ dài nếu cần
            decimal_part = ''.join(filter(str.isdigit, decimal_part))[:2]
            return f"{integer_part}.{decimal_part.ljust(2, '0')}" # Dùng ljust để đảm bảo 2 chữ số
        elif value.isdigit():
             return f"{value}.00"
        else:
            # Trường hợp không thể định dạng, trả về giá trị gốc hoặc None/Error
            st.warning(f"Không thể định dạng giá trị: {value}")
            return value # Hoặc return None

# @st.cache_data(ttl=60) # Cache hàm này nếu muốn giảm tần suất request
def get_world_gold_price():
    """Trích xuất giá vàng thế giới từ Trading Economics (USD/ounce)."""
    html_content = fetch_web_data()
    if not html_content:
        # st.error("Lỗi: Không thể tải dữ liệu từ Trading Economics.") # Đã báo lỗi trong fetch_web_data
        return None

    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        # Tìm bảng dựa vào id hoặc class cụ thể hơn nếu có thể
        # Ví dụ: table = soup.find('table', {'id': 'some-specific-id'})
        # Hoặc dựa vào cấu trúc gần đó
        tables = soup.find_all('table', {'class': 'table table-hover table-striped table-heatmap'})

        if not tables:
             # Thử tìm tất cả các bảng nếu class không khớp
             tables = soup.find_all('table')
             if len(tables) < 2: # Vẫn giữ logic cũ nếu tìm theo class thất bại
                 st.error("Lỗi: Không tìm thấy bảng dữ liệu phù hợp trên Trading Economics.")
                 return None
             # Giả sử bảng thứ 2 là bảng cần thiết nếu tìm theo class thất bại
             target_table = tables[1]
        else:
             target_table = tables[0] # Thường bảng đầu tiên nếu tìm theo class thành công


        rows = target_table.find_all('tr')
        if not rows or len(rows) < 2:
             st.error("Lỗi: Bảng dữ liệu tìm thấy không có hàng dữ liệu (chỉ có header?).")
             return None

        # Bỏ qua hàng tiêu đề (thường là hàng đầu tiên)
        data_rows = rows[1:]

        for row in data_rows:
            # Lấy tất cả cột td và th trong hàng
            cols = row.find_all(['td', 'th'], recursive=False) # recursive=False để tránh lấy thẻ lồng nhau không mong muốn
            if len(cols) > 1: # Cần ít nhất 2 cột (tên và giá)
                commodity_name_element = cols[0].find('b') # Thường tên nằm trong thẻ <b>
                if commodity_name_element:
                    commodity_name = clean_major_name(commodity_name_element.text)
                    if commodity_name == "Gold":
                        price_str = cols[1].text.strip()
                        formatted_price_str = format_value(price_str)
                        try:
                            price_float = float(formatted_price_str)
                            return price_float
                        except (ValueError, TypeError) as e:
                            st.error(f"Lỗi: Không thể chuyển đổi giá vàng '{formatted_price_str}' sang số. Lỗi: {e}")
                            return None
                # else: # Log nếu không tìm thấy thẻ <b> nếu cần debug
                #     st.warning(f"Không tìm thấy thẻ 'b' trong cột đầu tiên của hàng: {row}")


        st.error("Lỗi: Không tìm thấy 'Gold' trong bảng dữ liệu đã xác định.")
        return None
    except Exception as e:
        st.error(f"Lỗi khi xử lý HTML (BeautifulSoup): {e}")
        return None

# --- Khởi tạo Session State ---
if 'gold_data_session' not in st.session_state:
    st.session_state.gold_data_session = pd.DataFrame(columns=['timestamp', 'Giá (USD/ounce)'])
    st.session_state.gold_data_session.set_index('timestamp', inplace=True)


# --- Giao diện Streamlit ---
st.set_page_config(page_title="Biểu đồ Giá Vàng Thế Giới (Live)", layout="wide")
st.title("📉 Biểu đồ Xu hướng Giá Vàng Thế Giới (USD/ounce)")
st.caption("Biểu đồ hiển thị dữ liệu được cập nhật trong phiên làm việc hiện tại.")
st.info("Giá được lấy trực tiếp từ Trading Economics. Biểu đồ sẽ tự xây dựng khi bạn nhấn nút 'Cập nhật'.")

# --- Nút cập nhật và Logic ---
col1, col2 = st.columns([1, 5]) # Chia cột để nút nhỏ hơn

with col1:
    if st.button("🔄 Cập nhật giá"):
        with st.spinner("Đang lấy giá vàng mới nhất..."):
            current_price = get_world_gold_price()
            current_time = pd.to_datetime(datetime.now())

            if current_price is not None:
                # Tạo DataFrame mới cho điểm dữ liệu hiện tại
                new_data = pd.DataFrame({'Giá (USD/ounce)': [current_price]}, index=[current_time])
                new_data.index.name = 'timestamp'

                # Nối DataFrame mới vào DataFrame trong session_state
                st.session_state.gold_data_session = pd.concat([st.session_state.gold_data_session, new_data])

                # Giữ lại N điểm dữ liệu cuối cùng (ví dụ: 1000 điểm) để tránh quá tải bộ nhớ
                max_points = 1000
                if len(st.session_state.gold_data_session) > max_points:
                    st.session_state.gold_data_session = st.session_state.gold_data_session.tail(max_points)

                st.success(f"Đã cập nhật giá: ${current_price:.2f}")
            else:
                st.error("Không thể lấy được giá vàng lần này.")

# --- Hiển thị biểu đồ và thông tin ---
if not st.session_state.gold_data_session.empty:
    st.subheader("Biểu đồ đường:")
    # Vẽ biểu đồ
    st.line_chart(st.session_state.gold_data_session[['Giá (USD/ounce)']])

    # Hiển thị giá mới nhất
    latest_timestamp = st.session_state.gold_data_session.index[-1]
    latest_price = st.session_state.gold_data_session['Giá (USD/ounce)'].iloc[-1]

    # Tính toán thay đổi so với điểm trước đó (nếu có)
    delta = None
    delta_color = "normal"
    if len(st.session_state.gold_data_session) > 1:
        previous_price = st.session_state.gold_data_session['Giá (USD/ounce)'].iloc[-2]
        delta_value = latest_price - previous_price
        delta = f"{delta_value:+.2f} USD" # Thêm dấu + cho giá trị dương
        if delta_value > 0:
            delta_color = "normal"
        elif delta_value < 0:
            delta_color = "inverse"

    st.metric(label="Giá USD/ounce mới nhất",
              value=f"${latest_price:,.2f}",
              delta=delta,
              delta_color=delta_color)
    st.caption(f"Thời điểm cập nhật cuối: {latest_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

    # Tùy chọn: Hiển thị bảng dữ liệu
    if st.checkbox("Hiển thị dữ liệu phiên hiện tại"):
        st.dataframe(st.session_state.gold_data_session.sort_index(ascending=False), use_container_width=True)
else:
    st.info("Nhấn nút 'Cập nhật giá' để bắt đầu thu thập dữ liệu và vẽ biểu đồ.")

# Thêm khoảng trống cuối trang
st.write("")
st.write("")

# --- Cân nhắc Auto-refresh (Nâng cao) ---
# Để tự động cập nhật, bạn cần cài đặt: pip install streamlit-autorefresh
# Rồi thêm vào cuối code:
# from streamlit_autorefresh import st_autorefresh
# # Cập nhật mỗi 60 giây
# count = st_autorefresh(interval=60 * 1000, key="goldautorefresh")
# st.caption(f"Tự động làm mới sau mỗi 60 giây. Lượt làm mới: {count}")
# Lưu ý: Tự động cập nhật sẽ liên tục request đến web, hãy cân nhắc tần suất phù hợp.
