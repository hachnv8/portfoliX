import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
try:
    from vnstock import Trading
except ImportError:
    st.error("Thư viện vnstock chưa được cài đặt. Hãy chạy: pip install vnstock")

# Xóa hai dòng st.set_page_config và st.title ở đây để gọi sau khi tính toán xong P&L

# Tạm thời refresh ứng dụng mỗi 15 giây để lấy giá realtime tự động
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=15000, limit=None, key="data_refresh")
except ImportError:
    pass

import sqlite3
import os

DB_FILENAME = 'portfolio.db'

def init_db():
    conn = sqlite3.connect(DB_FILENAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            buy_price REAL NOT NULL,
            quantity INTEGER NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def load_portfolio():
    conn = sqlite3.connect(DB_FILENAME)
    df = pd.read_sql_query("SELECT id, symbol as Mã, buy_price as 'Giá mua', quantity as 'Số lượng' FROM portfolio", conn)
    conn.close()
    return df

with st.sidebar:
    st.header("Thêm Cổ phiếu")
    with st.form("add_stock_form", clear_on_submit=True):
        symbol = st.text_input("Mã Cổ phiếu (VD: VCB, FPT, HPG)").upper()
        
        # Cho phép nhập cả giá VND thực tế hoặc giá rút gọn (hiển thị trên các app ck như SSI: VCB giá 90.5 là 90,500đ)
        # Tự động convert giá nhập vào thành giá VND thực tế cho 1 cổ phiếu
        buy_price_input = st.number_input("Giá mua (có thể nhập 31.65 hoặc 31650 tùy thói quen)", min_value=0.0, step=0.1)
        quantity = st.number_input("Số lượng cổ phiếu", min_value=1, step=100)
        
        submitted = st.form_submit_button("Thêm vào danh mục")
        
        if submitted:
            # Logic convert: nếu nhập giá < 1000 thì ngầm hiểu là hệ rút gọn (x 1000) giống trên app chứng khoán
            buy_price = buy_price_input * 1000 if 0 < buy_price_input < 1000 else buy_price_input
            
            if symbol:
                conn = sqlite3.connect(DB_FILENAME)
                c = conn.cursor()
                
                # Check if symbol already exists
                c.execute("SELECT id, buy_price, quantity FROM portfolio WHERE symbol = ?", (symbol,))
                existing_row = c.fetchone()
                
                if existing_row:
                    row_id, old_price, old_quantity = existing_row
                    # Calculate new average price and total quantity
                    new_quantity = old_quantity + quantity
                    new_avg_price = ((old_price * old_quantity) + (buy_price * quantity)) / new_quantity
                    
                    c.execute("UPDATE portfolio SET buy_price = ?, quantity = ? WHERE id = ?",
                              (new_avg_price, new_quantity, row_id))
                    st.success(f"Đã cập nhật khối lượng và trung bình giá cho {symbol}!")
                else:
                    c.execute("INSERT INTO portfolio (symbol, buy_price, quantity) VALUES (?, ?, ?)", 
                              (symbol, buy_price, quantity))
                    st.success(f"Đã thêm {symbol} vào danh mục!")
                    
                conn.commit()
                conn.close()
            else:
                st.warning("Vui lòng nhập mã cổ phiếu.")
            
    if st.button("Xóa toàn bộ danh mục"):
        conn = sqlite3.connect(DB_FILENAME)
        c = conn.cursor()
        c.execute("DELETE FROM portfolio")
        conn.commit()
        conn.close()
        st.rerun()

st.header("📊 Danh mục hiện tại")

with st.expander("✏️ Chỉnh sửa danh mục (Sửa giá mua, số lượng hoặc xóa)"):
    st.info("Chỉnh sửa trực tiếp vào bảng bên dưới, sau đó bấm 'Lưu thay đổi'. Bạn có thể thêm hoặc xóa hàng.")
    portfolio = load_portfolio()
    
    # Do st.data_editor trả về DataFrame mới, ta cần đối chiếu sự thay đổi với DB
    edited_df = st.data_editor(
        portfolio.drop(columns=['id']), # Ẩn cột ID khi hiển thị cho người dùng sửa
        num_rows="dynamic", 
        use_container_width=True,
        hide_index=True
    )
    
    if st.button("Lưu thay đổi"):
        # Cách đơn giản nhất để cập nhật bảng là xóa toàn bộ và chèn lại dựa trên edited_df
        # Nếu danh mục không quá lớn, cách này hoạt động tốt và dễ cài đặt
        conn = sqlite3.connect(DB_FILENAME)
        c = conn.cursor()
        c.execute("DELETE FROM portfolio")
        
        for _, row in edited_df.iterrows():
            c.execute("INSERT INTO portfolio (symbol, buy_price, quantity) VALUES (?, ?, ?)",
                      (row['Mã'], row['Giá mua'], row['Số lượng']))
        conn.commit()
        conn.close()
        st.success("Đã lưu thay đổi vào cơ sở dữ liệu!")
        st.rerun()

if not portfolio.empty:
    symbols = portfolio['Mã'].unique().tolist()
    symbols_str = ",".join(symbols)
    
    # Lấy giá realtime
    try:
        # Chuyển data_editor & header xuống đây vì cần phải đọc data để set page title trước
        realtime_data = Trading().price_board(symbols)
        
        # Tìm cột mã cổ phiếu ('Mã CP', 'Mã', 'Symbol'...)
        sym_col = next((col for col in realtime_data.columns if 'mã' in col.lower() or 'symbol' in col.lower()), None)
        # Tìm cột giá hiện tại ('Khớp lệnh', 'Giá', 'Current Price'...)
        # Ưu tiên chữ 'khớp lệnh' vì bảng giá thường ghi là "GIÁ KHỚP LỆNH" hoặc "Khớp lệnh"
        price_col = next((col for col in realtime_data.columns if 'khớp lệnh' in col.lower() or 'close' in col.lower() or 'giá' in col.lower()), None)
        
        if sym_col and price_col:
            price_dict = dict(zip(realtime_data[sym_col], realtime_data[price_col]))
        else:
            price_dict = {sym: 0.0 for sym in symbols}
            st.warning("Không tìm thấy cột cột giá trong dữ liệu trả về từ vnstock.")
        
        # Map giá hiện tại cho các mã
        portfolio['Giá hiện tại'] = portfolio['Mã'].map(price_dict).astype(float)
        
        # vnstock v3 trả về giá trị thực (không bị chia cho 1000 như bản cũ)
        portfolio['Tổng vốn'] = portfolio['Giá mua'] * portfolio['Số lượng']
        portfolio['Giá trị hiện tại'] = portfolio['Giá hiện tại'] * portfolio['Số lượng']
        portfolio['Lãi/Lỗ'] = portfolio['Giá trị hiện tại'] - portfolio['Tổng vốn']
        portfolio['% Lãi/Lỗ'] = (portfolio['Lãi/Lỗ'] / portfolio['Tổng vốn']) * 100
        
        # Hàm tô màu
        def color_profit_loss(val):
            if pd.isna(val):
                return ''
            color = 'green' if val > 0 else 'red' if val < 0 else 'black'
            return f'color: {color}; font-weight: bold;'

        # Áp dụng styling pandas mới (2.1.0+ dùng map, phiên bản cũ dùng applymap)
        try:
            styled_df = portfolio.style.map(color_profit_loss, subset=['Lãi/Lỗ', '% Lãi/Lỗ'])
        except AttributeError:
            styled_df = portfolio.style.applymap(color_profit_loss, subset=['Lãi/Lỗ', '% Lãi/Lỗ'])
            
        styled_df = styled_df.format({
            'Giá mua': '{:,.0f}',
            'Giá hiện tại': '{:,.0f}',
            'Tổng vốn': '{:,.0f}',
            'Giá trị hiện tại': '{:,.0f}',
            'Lãi/Lỗ': '{:,.0f}',
            '% Lãi/Lỗ': '{:.2f}%'
        })
        
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        # Tính toán tổng quan để gán vào page title
        total_pnl = portfolio['Lãi/Lỗ'].sum()
        total_invested = portfolio['Tổng vốn'].sum()
        total_value = portfolio['Giá trị hiện tại'].sum()
        
        pct_pnl_str = f"{(total_pnl/total_invested)*100 if total_invested else 0:+.2f}%"
        pnl_str = f"{total_pnl:+,.0f}đ"
        page_title = f"{pnl_str} ({pct_pnl_str}) - Danh mục"
        
        st.set_page_config(page_title=page_title, layout="wide")
        
        st.subheader("💰 Tổng quan tài khoản")
        col1, col2, col3 = st.columns(3)
        col1.metric("Tổng vốn đầu tư", f"{total_invested:,.0f} VNĐ")
        col2.metric("Giá trị hiện tại", f"{total_value:,.0f} VNĐ")
        col3.metric(
            "Tổng Lãi/Lỗ", 
            f"{total_pnl:,.0f} VNĐ", 
            pct_pnl_str
        )
        
        if st.button("🔄 Cập nhật giá"):
            st.rerun()
            
    except Exception as e:
        st.set_page_config(page_title="Lỗi - Danh mục", layout="wide")
        st.error(f"Lỗi khi lấy dữ liệu realtime từ vnstock. Lỗi cụ thể: {e}")
        st.info("Hãy kiểm tra kết nối mạng hoặc thử lại sau. Đảm bảo mã cổ phiếu là mã có thực trên sàn CK VN.")
else:
    st.info("Danh mục hiện tại đang trống. Vui lòng thêm cổ phiếu ở sidebar bên trái.")
