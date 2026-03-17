import streamlit as st
import pandas as pd
import mysql.connector
from mysql.connector import Error
import hashlib
import os
import json
import streamlit.components.v1 as components

# --- CẤU HÌNH DATABASE MYSQL ---
# Bạn hãy điền thông tin database của mình vào đây
MYSQL_CONFIG = {
    'host': '36.50.135.128',
    'user': 'portfolio_user',
    'password': 'portfolio_password',
    'database': 'portfolio_db'
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        return conn
    except Error as e:
        st.error(f"Lỗi kết nối MySQL: {e}")
        return None

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def init_db():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        # Tạo bảng users
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL
            )
        ''')
        # Tạo bảng portfolio
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                buy_price DOUBLE NOT NULL,
                quantity INT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        # Tạo bảng daily_pnl
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_pnl (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                record_date DATE NOT NULL,
                total_pnl DOUBLE NOT NULL,
                total_invested DOUBLE NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE KEY unique_user_date (user_id, record_date)
            )
        ''')
        conn.commit()
        cursor.close()

init_db()

# --- CẬP NHẬT TỰ ĐỘNG MÃ CỔ PHIẾU ---
# Chạy script lấy mã cổ phiếu nếu file chưa có hoặc đã cũ hơn 7 ngày
import os
import time
import subprocess

symbols_file = "symbols.txt"
if not os.path.exists(symbols_file) or (time.time() - os.path.getmtime(symbols_file) > 86400 * 7):
    try:
        subprocess.run(["python", "update_symbols.py"], check=True)
    except Exception as e:
        print(f"Lỗi khi chạy file cập nhật mã cổ phiếu: {e}")

# --- KHỞI TẠO SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['user_id'] = None
    st.session_state['username'] = ""

# --- HÀM TRỢ GIÚP ---
def load_portfolio(user_id):
    conn = get_db_connection()
    if not conn: return pd.DataFrame()
    query = "SELECT id, symbol as Mã, buy_price as 'Giá mua', quantity as 'Số lượng' FROM portfolio WHERE user_id = %s"
    df = pd.read_sql(query, conn, params=(user_id,))
    conn.close()
    return df

def login_user(username, password):
    conn = get_db_connection()
    if not conn: return None
    cursor = conn.cursor()
    cursor.execute("SELECT id, password FROM users WHERE username = %s", (username,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    if result and result[1] == hash_password(password):
        return result[0]
    return None

def register_user(username, password):
    try:
        conn = get_db_connection()
        if not conn: return False
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hash_password(password)))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Error:
        return False

# --- LOGIC TÍNH TOÁN P&L (ĐỂ ĐẶT TITLE) ---
page_title = "Danh mục đầu tư"
user_id = st.session_state.get('user_id')

if st.session_state.get('logged_in'):
    portfolio = load_portfolio(user_id)
    if not portfolio.empty:
        try:
            import requests
            symbols = portfolio['Mã'].unique().tolist()
            
            price_dict = {}
            for sym in symbols:
                try:
                    # Using Yahoo Finance to bypass corporate DNS blocks on VN trading sites
                    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}.VN?range=1d&interval=1d"
                    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                    res = requests.get(url, headers=headers, timeout=5)
                    
                    if res.status_code == 200:
                        data = res.json()
                        latest_price = data['chart']['result'][0]['meta']['regularMarketPrice']
                        if latest_price:
                            if latest_price < 1000:
                                latest_price *= 1000 # convert to actual VND value if returned in thousands
                            price_dict[sym] = latest_price
                except Exception as e:
                    print(f"Error fetching {sym} from Yahoo: {e}")
                    pass            
            
            # Map existing prices and fill missing ones with the 'Giá mua' (Buy Price) as fallback or 0
            if price_dict:
                portfolio['Giá hiện tại'] = portfolio['Mã'].map(price_dict).fillna(portfolio['Giá mua']).astype(float)
            else:
                portfolio['Giá hiện tại'] = portfolio['Giá mua'].astype(float) # Fallback to buy price if API entirely fails
                
            portfolio['Tổng vốn'] = portfolio['Giá mua'] * portfolio['Số lượng']
            portfolio['Giá trị hiện tại'] = portfolio['Giá hiện tại'] * portfolio['Số lượng']
            portfolio['Lãi/Lỗ'] = portfolio['Giá trị hiện tại'] - portfolio['Tổng vốn']
            
            total_pnl = portfolio['Lãi/Lỗ'].sum()
            total_invested = portfolio['Tổng vốn'].sum()
            pct_pnl = (total_pnl / total_invested * 100) if total_invested else 0
            
            
            # Cập nhật title động
            sign = "+" if total_pnl >= 0 else ""
            page_title = f"{sign}{total_pnl:,.0f}đ ({sign}{pct_pnl:.1f}%)"
            
            # Lưu P&L hằng ngày vào database
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO daily_pnl (user_id, record_date, total_pnl, total_invested) 
                    VALUES (%s, CURDATE(), %s, %s) 
                    ON DUPLICATE KEY UPDATE total_pnl=%s, total_invested=%s
                """, (user_id, total_pnl, total_invested, total_pnl, total_invested))
                conn.commit()
                cursor.close()
                conn.close()
        except Exception as e:
            print(f"Error in PnL calculation block: {e}")
            pass

# Cấu hình trang (phải gọi đầu tiên hoặc sau logic tính toán không dùng streamlit component)
st.set_page_config(page_title=page_title, layout="wide")

# Tự động refresh
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=15000, limit=None, key="data_refresh")
except ImportError:
    pass

# --- GIAO DIỆN ---
if not st.session_state['logged_in']:
    st.title("🔐 Đăng nhập Hệ thống")
    tab1, tab2 = st.tabs(["Đăng nhập", "Đăng ký"])
    
    with tab1:
        with st.form("login_form"):
            l_user = st.text_input("Tên đăng nhập")
            l_pass = st.text_input("Mật khẩu", type="password")
            if st.form_submit_button("Đăng nhập"):
                uid = login_user(l_user, l_pass)
                if uid:
                    st.session_state['logged_in'] = True
                    st.session_state['user_id'] = uid
                    st.session_state['username'] = l_user
                    st.success("Đăng nhập thành công!")
                    st.rerun()
                else:
                    st.error("Sai tên đăng nhập hoặc mật khẩu!")
    
    with tab2:
        with st.form("register_form"):
            r_user = st.text_input("Tên đăng nhập mới")
            r_pass = st.text_input("Mật khẩu mới", type="password")
            r_pass_conf = st.text_input("Xác nhận mật khẩu", type="password")
            if st.form_submit_button("Đăng ký"):
                if r_pass != r_pass_conf:
                    st.error("Mật khẩu xác nhận không khớp!")
                elif len(r_user) < 3:
                    st.error("Tên đăng nhập quá ngắn!")
                else:
                    if register_user(r_user, r_pass):
                        st.success("Đăng ký thành công! Hãy chuyển sang tab Đăng nhập.")
                    else:
                        st.error("Tên đăng nhập đã tồn tại hoặc lỗi DB!")
    st.stop()

# --- SAU KHI ĐĂNG NHẬP ---
with st.sidebar:
    st.write(f"👤 Chào, **{st.session_state['username']}**")
    if st.button("Đăng xuất"):
        st.session_state['logged_in'] = False
        st.session_state['user_id'] = None
        st.rerun()
        
    st.divider()
    st.header("Thêm Cổ phiếu")
    
    # Load symbols for autocomplete
    try:
        with open("symbols.txt", "r") as f:
            valid_symbols = [line.strip().upper() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        valid_symbols = ["VCB", "FPT", "HPG", "VHM", "VIC", "VNM", "BID", "CTG", "TCB", "MBB"] # Default fallback
    
    with st.form("add_stock_form", clear_on_submit=True):
        symbol = st.selectbox("Mã Cổ phiếu", options=[""] + valid_symbols)
        buy_price_input = st.number_input("Giá mua", min_value=0.0, step=0.1)
        quantity = st.number_input("Số lượng cổ phiếu", min_value=1, step=100)
        submitted = st.form_submit_button("Thêm vào danh mục")
        
        if submitted:
            buy_price = buy_price_input * 1000 if 0 < buy_price_input < 1000 else buy_price_input
            if symbol:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id, buy_price, quantity FROM portfolio WHERE symbol = %s AND user_id = %s", (symbol, user_id))
                    existing_row = cursor.fetchone()
                    
                    if existing_row:
                        row_id, old_price, old_quantity = existing_row
                        new_quantity = old_quantity + quantity
                        new_avg_price = ((old_price * old_quantity) + (buy_price * quantity)) / new_quantity
                        cursor.execute("UPDATE portfolio SET buy_price = %s, quantity = %s WHERE id = %s", (new_avg_price, new_quantity, row_id))
                    else:
                        cursor.execute("INSERT INTO portfolio (user_id, symbol, buy_price, quantity) VALUES (%s, %s, %s, %s)", 
                                     (user_id, symbol, buy_price, quantity))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    st.success(f"Đã cập nhật {symbol}!")
                    st.rerun()
            else:
                st.warning("Vui lòng nhập mã cổ phiếu.")
    
    # --- CHỈNH SỬA / XÓA CỔ PHIẾU CÁ NHÂN ---
    if not portfolio.empty:
        st.divider()
        st.header("Quản lý / Chỉnh sửa Cổ phiếu")
        
        # Lấy danh sách mã đang có trong danh mục
        symbols_in_portfolio = portfolio['Mã'].tolist()
        selected_symbol = st.selectbox("Chọn mã để sửa/xóa", options=symbols_in_portfolio)
        
        if selected_symbol:
            # Lấy thông tin hiện tại của mã đó
            row = portfolio[portfolio['Mã'] == selected_symbol].iloc[0]
            current_price = float(row['Giá mua'])
            current_qty = int(row['Số lượng'])
            
            # Form chỉnh sửa
            with st.form("edit_stock_form"):
                new_price_input = st.number_input("Giá mua mới", min_value=0.0, value=current_price/1000 if current_price < 1000000 else current_price, step=0.1)
                new_qty = st.number_input("Số lượng mới", min_value=1, value=current_qty, step=1)
                
                col_edit, col_del = st.columns(2)
                update_btn = col_edit.form_submit_button("Cập nhật")
                delete_btn = col_del.form_submit_button("Xóa mã này")
                
                if update_btn:
                    new_price = new_price_input * 1000 if 0 < new_price_input < 1000 else new_price_input
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE portfolio SET buy_price = %s, quantity = %s WHERE symbol = %s AND user_id = %s", 
                                     (new_price, new_qty, selected_symbol, user_id))
                        conn.commit()
                        cursor.close()
                        conn.close()
                        st.success(f"Đã cập nhật {selected_symbol}!")
                        st.rerun()
                
                if delete_btn:
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM portfolio WHERE symbol = %s AND user_id = %s", (selected_symbol, user_id))
                        conn.commit()
                        cursor.close()
                        conn.close()
                        st.warning(f"Đã xóa {selected_symbol}!")
                        st.rerun()
            
    if st.button("Xóa toàn bộ danh mục"):
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM portfolio WHERE user_id = %s", (user_id,))
            conn.commit()
            cursor.close()
            conn.close()
            st.rerun()

st.header(f"📊 Danh mục của {st.session_state['username']}")

# Hiển thị bảng dữ liệu (đã có biến portfolio từ đầu file)
if not st.session_state.get('logged_in'):
    st.stop()

if not portfolio.empty:
    def color_profit_loss(val):
        if pd.isna(val): return ''
        color = 'green' if val > 0 else 'red' if val < 0 else 'white'
        return f'color: {color}; font-weight: bold;'

    if 'Lãi/Lỗ' in portfolio.columns:
        portfolio['% Lãi/Lỗ'] = (portfolio['Lãi/Lỗ'] / portfolio['Tổng vốn']) * 100
        styled_df = portfolio.style.applymap(color_profit_loss, subset=['Lãi/Lỗ', '% Lãi/Lỗ'])
        styled_df = styled_df.format({
            'Giá mua': '{:,.0f}', 'Giá hiện tại': '{:,.0f}',
            'Tổng vốn': '{:,.0f}', 'Giá trị hiện tại': '{:,.0f}',
            'Lãi/Lỗ': '{:,.0f}', '% Lãi/Lỗ': '{:.2f}%'
        })
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        total_pnl = portfolio['Lãi/Lỗ'].sum()
        total_invested = portfolio['Tổng vốn'].sum()
        total_value = portfolio['Giá trị hiện tại'].sum()
        pct_pnl_str = f"{(total_pnl/total_invested)*100 if total_invested else 0:+.2f}%"
        
        st.subheader("💰 Tổng quan tài khoản")
        col1, col2, col3 = st.columns(3)
        col1.metric("Tổng vốn đầu tư", f"{total_invested:,.0f} VNĐ")
        col2.metric("Giá trị hiện tại", f"{total_value:,.0f} VNĐ")
        col3.metric("Tổng Lãi/Lỗ", f"{total_pnl:,.0f} VNĐ", pct_pnl_str)
        
        # Hiển thị Biểu đồ PnL hằng ngày
        conn = get_db_connection()
        if conn:
            daily_query = "SELECT record_date, total_pnl, total_invested FROM daily_pnl WHERE user_id = %s ORDER BY record_date"
            daily_df = pd.read_sql(daily_query, conn, params=(user_id,))
            conn.close()
            
            if not daily_df.empty:
                st.divider()
                st.subheader("📈 Lịch sử Lãi/Lỗ hằng ngày (%)")
                
                daily_df['record_date_str'] = pd.to_datetime(daily_df['record_date']).dt.strftime('%d/%m/%Y')
                
                # Tính toán % Lãi/Lỗ và làm tròn 2 chữ số thập phân
                daily_df['pct_pnl'] = ((daily_df['total_pnl'] / daily_df['total_invested']) * 100).round(2)
                # Xử lý trường hợp chia cho 0 nếu total_invested = 0
                daily_df['pct_pnl'] = daily_df['pct_pnl'].fillna(0)
                
                categories = daily_df['record_date_str'].tolist()
                data = daily_df['pct_pnl'].tolist()
                
                highchart_html = f"""
                <script src="https://cdnjs.cloudflare.com/ajax/libs/highcharts/11.4.0/highcharts.js"></script>
                <div id="container" style="width:100%; height:300px;"></div>
                <script>
                    var checkInterval = setInterval(function() {{
                        if (typeof Highcharts !== 'undefined') {{
                            clearInterval(checkInterval);
                            Highcharts.chart('container', {{
                                chart: {{
                                    type: 'areaspline',
                                    backgroundColor: 'transparent'
                                }},
                                title: {{ text: null }},
                                xAxis: {{
                                    categories: {json.dumps(categories)},
                                    labels: {{ style: {{ color: '#aaaaaa' }} }},
                                    gridLineColor: '#333333'
                                }},
                                yAxis: {{
                                    title: {{ text: null }},
                                    labels: {{ format: '{{value}}%', style: {{ color: '#aaaaaa' }} }},
                                    gridLineColor: '#333333'
                                }},
                                legend: {{ enabled: false }},
                                credits: {{ enabled: false }},
                                tooltip: {{
                                    pointFormat: '<b>{{point.y}}%</b>'
                                }},
                                plotOptions: {{
                                    areaspline: {{
                                        fillOpacity: 0.2,
                                        color: '#00ff00',
                                        marker: {{ enabled: true, radius: 4 }}
                                    }}
                                }},
                                series: [{{
                                    name: 'Lãi/Lỗ',
                                    data: {json.dumps(data)}
                                }}]
                            }});
                        }}
                    }}, 50);
                </script>
                """
                components.html(highchart_html, height=330)
    else:
        st.dataframe(portfolio, use_container_width=True, hide_index=True)
else:
    st.info("Danh mục đang trống. Hãy thêm cổ phiếu ở sidebar.")

