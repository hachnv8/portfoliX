import streamlit as st
from database import get_db_connection

def render_sidebar(localS, portfolio):
    """
    Hiển thị giao diện Sidebar bao gồm: Logout, Thêm mới Cổ phiếu, Chỉnh sửa, Xóa.
    Trả về True nếu có action nào đó cần app phải reload lại (st.rerun).
    """
    user_id = st.session_state['user_id']
    username = st.session_state['username']
    
    with st.sidebar:
        st.write(f"👤 Chào, **{username}**")
        if st.button("Đăng xuất"):
            st.session_state['logged_in'] = False
            st.session_state['user_id'] = None
            st.session_state['username'] = ""
            # Xóa phiên local storage
            localS.deleteItem("portfolix_user_id", key="del_uid")
            localS.deleteItem("portfolix_username", key="del_uname")
            return True # Yêu cầu rerun
            
        st.divider()
        st.header("Thêm Cổ phiếu")
        with st.form("add_stock_form", clear_on_submit=True):
            symbol_input = st.text_input("Mã Cổ phiếu (VD: VCB)")
            symbol = symbol_input.upper().strip() if symbol_input else ""
            
            stock_type = st.radio("Loại", options=["Cổ phiếu đã mua", "Cổ phiếu theo dõi"], horizontal=True)
            is_wl = True if stock_type == "Cổ phiếu theo dõi" else False
            
            if not is_wl:
                buy_price_input = st.number_input("Giá mua", min_value=0.0, step=0.1)
                quantity = st.number_input("Số lượng cổ phiếu", min_value=1, step=100)
            else:
                buy_price_input = 0.0
                quantity = 0
                
            submitted = st.form_submit_button("Thêm")
            
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
                            if is_wl:
                                cursor.execute("UPDATE portfolio SET is_watchlist = 1 WHERE id = %s", (row_id,))
                            else:
                                new_quantity = old_quantity + quantity
                                new_avg_price = ((old_price * old_quantity) + (buy_price * quantity)) / new_quantity if new_quantity > 0 else old_price
                                cursor.execute("UPDATE portfolio SET buy_price = %s, quantity = %s, is_watchlist = 0 WHERE id = %s", (new_avg_price, new_quantity, row_id))
                        else:
                            cursor.execute("INSERT INTO portfolio (user_id, symbol, buy_price, quantity, is_watchlist) VALUES (%s, %s, %s, %s, %s)", 
                                         (user_id, symbol, buy_price, quantity, is_wl))
                        conn.commit()
                        cursor.close()
                        conn.close()
                        st.success(f"Đã cập nhật {symbol}!")
                        return True
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
                is_row_wl = row.get('is_watchlist', False)
                
                # Form chỉnh sửa
                with st.form("edit_stock_form"):
                    if not is_row_wl:
                        current_price = float(row['Giá mua'])
                        current_qty = int(row['Số lượng'])
                        new_price_input = st.number_input("Giá mua mới", min_value=0.0, value=current_price/1000 if current_price < 1000000 else current_price, step=0.1)
                        new_qty = st.number_input("Số lượng mới", min_value=1, value=current_qty, step=1)
                    else:
                        st.info("Cổ phiếu theo dõi không có tuỳ chỉnh giá hay số lượng.")
                        new_price_input = 0.0
                        new_qty = 0
                        
                    col_edit, col_del = st.columns(2)
                    update_btn = col_edit.form_submit_button("Cập nhật")
                    delete_btn = col_del.form_submit_button("Xóa mã này")
                    
                    if update_btn:
                        if not is_row_wl:
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
                                return True
                        else:
                            st.info("Không có dữ liệu gì để cập nhật cho cổ phiếu theo dõi.")
                    
                    if delete_btn:
                        conn = get_db_connection()
                        if conn:
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM portfolio WHERE symbol = %s AND user_id = %s", (selected_symbol, user_id))
                            conn.commit()
                            cursor.close()
                            conn.close()
                            st.warning(f"Đã xóa {selected_symbol}!")
                            return True
                
        if st.button("Xóa toàn bộ danh mục"):
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM portfolio WHERE user_id = %s", (user_id,))
                conn.commit()
                cursor.close()
                conn.close()
                return True
                
    return False
