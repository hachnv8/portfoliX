import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import os

# Cấu hình trang (phải gọi đầu tiên)
st.set_page_config(page_title="Danh mục đầu tư", layout="wide")

try:
    from vnstock import Trading
except ImportError:
    st.error("Thư viện vnstock chưa được cài đặt. Hãy chạy: pip install vnstock")

# Tạm thời refresh ứng dụng mỗi 15 giây để lấy giá realtime tự động
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=15000, limit=None, key="data_refresh")
except ImportError:
    pass

DB_FILENAME = 'portfolio.db'

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def init_db():
    conn = sqlite3.connect(DB_FILENAME)
    c = conn.cursor()
    # Tạo bảng users
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    # Tạo bảng portfolio với cột user_id
    c.execute('''
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            buy_price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Kiểm tra nếu bảng portfolio cũ chưa có cột user_id thì cần migrate (cho server cũ)
    c.execute("PRAGMA table_info(portfolio)")
    columns = [column[1] for column in c.fetchall()]
    if 'user_id' not in columns:
        # Cách đơn giản nhất là xóa và tạo lại nếu chưa có dữ liệu quan trọng, 
        # hoặc alter table. Ở đây tôi dùng alter table để an toàn.
        try:
            c.execute("ALTER TABLE portfolio ADD COLUMN user_id INTEGER DEFAULT 1")
        except:
            pass
            
    conn.commit()
    conn.close()

init_db()

def load_portfolio(user_id):
    conn = sqlite3.connect(DB_FILENAME)
    query = "SELECT id, symbol as Mã, buy_price as 'Giá mua', quantity as 'Số lượng' FROM portfolio WHERE user_id = ?"
    df = pd.read_sql_query(query, conn, params=(user_id,))
    conn.close()
    return df

# --- QUẢN LÝ ĐĂNG NHẬP ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['user_id'] = None
    st.session_state['username'] = ""

def login_user(username, password):
    conn = sqlite3.connect(DB_FILENAME)
    c = conn.cursor()
    c.execute("SELECT id, password FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    if result and result[1] == hash_password(password):
        return result[0]
    return None

def register_user(username, password):
    try:
        conn = sqlite3.connect(DB_FILENAME)
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hash_password(password)))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

# Giao diện Đăng nhập / Đăng ký
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
                        st.error("Tên đăng nhập đã tồn tại!")
    st.stop() # Dừng không cho xem nội dung bên dưới khi chưa login

# --- NỘI DUNG SAU KHI ĐĂNG NHẬP ---
user_id = st.session_state['user_id']

with st.sidebar:
    st.write(f"👤 Chào, **{st.session_state['username']}**")
    if st.button("Đăng xuất"):
        st.session_state['logged_in'] = False
        st.session_state['user_id'] = None
        st.rerun()
        
    st.divider()
    st.header("Thêm Cổ phiếu")
    with st.form("add_stock_form", clear_on_submit=True):
        symbol = st.text_input("Mã Cổ phiếu (VD: VCB, FPT, HPG)").upper()
        buy_price_input = st.number_input("Giá mua", min_value=0.0, step=0.1)
        quantity = st.number_input("Số lượng cổ phiếu", min_value=1, step=100)
        submitted = st.form_submit_button("Thêm vào danh mục")
        
        if submitted:
            buy_price = buy_price_input * 1000 if 0 < buy_price_input < 1000 else buy_price_input
            if symbol:
                conn = sqlite3.connect(DB_FILENAME)
                c = conn.cursor()
                c.execute("SELECT id, buy_price, quantity FROM portfolio WHERE symbol = ? AND user_id = ?", (symbol, user_id))
                existing_row = c.fetchone()
                
                if existing_row:
                    row_id, old_price, old_quantity = existing_row
                    new_quantity = old_quantity + quantity
                    new_avg_price = ((old_price * old_quantity) + (buy_price * quantity)) / new_quantity
                    c.execute("UPDATE portfolio SET buy_price = ?, quantity = ? WHERE id = ?", (new_avg_price, new_quantity, row_id))
                    st.success(f"Đã cập nhật {symbol}!")
                else:
                    c.execute("INSERT INTO portfolio (user_id, symbol, buy_price, quantity) VALUES (?, ?, ?, ?)", 
                              (user_id, symbol, buy_price, quantity))
                    st.success(f"Đã thêm {symbol}!")
                conn.commit()
                conn.close()
                st.rerun()
            else:
                st.warning("Vui lòng nhập mã cổ phiếu.")
            
    if st.button("Xóa toàn bộ danh mục"):
        conn = sqlite3.connect(DB_FILENAME)
        c = conn.cursor()
        c.execute("DELETE FROM portfolio WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        st.rerun()

st.header(f"📊 Danh mục của {st.session_state['username']}")

portfolio = load_portfolio(user_id)

with st.expander("✏️ Chỉnh sửa danh mục"):
    edited_df = st.data_editor(
        portfolio.drop(columns=['id']), 
        num_rows="dynamic", 
        use_container_width=True,
        hide_index=True
    )
    
    if st.button("Lưu thay đổi"):
        conn = sqlite3.connect(DB_FILENAME)
        c = conn.cursor()
        c.execute("DELETE FROM portfolio WHERE user_id = ?", (user_id,))
        for _, row in edited_df.iterrows():
            if pd.notna(row['Mã']) and row['Số lượng'] > 0:
                c.execute("INSERT INTO portfolio (user_id, symbol, buy_price, quantity) VALUES (?, ?, ?, ?)",
                          (user_id, row['Mã'], row['Giá mua'], row['Số lượng']))
        conn.commit()
        conn.close()
        st.success("Đã lưu thay đổi!")
        st.rerun()

if not portfolio.empty:
    symbols = portfolio['Mã'].unique().tolist()
    try:
        realtime_data = Trading().price_board(symbols)
        sym_col = next((col for col in realtime_data.columns if 'mã' in col.lower() or 'symbol' in col.lower()), None)
        price_col = next((col for col in realtime_data.columns if 'khợp lệnh' in col.lower() or 'close' in col.lower() or 'giá' in col.lower()), None)
        
        if sym_col and price_col:
            price_dict = dict(zip(realtime_data[sym_col], realtime_data[price_col]))
        else:
            price_dict = {sym: 0.0 for sym in symbols}
        
        portfolio['Giá hiện tại'] = portfolio['Mã'].map(price_dict).astype(float)
        portfolio['Tổng vốn'] = portfolio['Giá mua'] * portfolio['Số lượng']
        portfolio['Giá trị hiện tại'] = portfolio['Giá hiện tại'] * portfolio['Số lượng']
        portfolio['Lãi/Lỗ'] = portfolio['Giá trị hiện tại'] - portfolio['Tổng vốn']
        portfolio['% Lãi/Lỗ'] = (portfolio['Lãi/Lỗ'] / portfolio['Tổng vốn']) * 100
        
        def color_profit_loss(val):
            if pd.isna(val): return ''
            color = 'green' if val > 0 else 'red' if val < 0 else 'white'
            return f'color: {color}; font-weight: bold;'

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
        
    except Exception as e:
        st.error(f"Lỗi khi lấy dữ liệu: {e}")
else:
    st.info("Danh mục đang trống. Hãy thêm cổ phiếu ở sidebar.")

