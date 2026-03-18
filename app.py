import streamlit as st
from streamlit_local_storage import LocalStorage

# Import các components sau khi đã refactor
from auth import render_auth_ui
from components.sidebar import render_sidebar
from components.portfolio_tab import load_portfolio, render_portfolio_tab
from components.valuation_tab import render_valuation_tab
from components.criteria_tab import render_criteria_tab

# Khởi tạo LocalStorage
localS = LocalStorage()

# --- KHỞI TẠO SESSION STATE VÀ TỰ ĐỘNG ĐĂNG NHẬP ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['user_id'] = None
    st.session_state['username'] = ""
    st.session_state['page_title_info'] = "Danh mục đầu tư" # Session state giữ title tạm

# Đọc Cookie/LocalStorage để tự động đăng nhập (nếu chưa login)
if not st.session_state['logged_in']:
    saved_user_id = localS.getItem("portfolix_user_id")
    saved_username = localS.getItem("portfolix_username")
    
    if saved_user_id and saved_username:
        st.session_state['logged_in'] = True
        st.session_state['user_id'] = int(saved_user_id)
        st.session_state['username'] = saved_username
        st.rerun()

# Cấu hình trang (Tên tab trên trình duyệt sẽ lấy từ session_state)
st.set_page_config(page_title=st.session_state.get('page_title_info', 'Danh mục đầu tư'), layout="wide")


# --- GIAO DIỆN CHÍNH (ROUTER) ---
if not st.session_state['logged_in']:
    # Hiển thị giao diện đăng nhập nếu chưa log in
    success, uid, uname = render_auth_ui(localS)
    if success:
        st.session_state['logged_in'] = True
        st.session_state['user_id'] = uid
        st.session_state['username'] = uname
        st.rerun()
else:
    # 1. Tải danh mục hiện tại của User
    user_id = st.session_state['user_id']
    portfolio = load_portfolio(user_id)
    
    # 2. Hiển thị Sidebar
    needs_rerun = render_sidebar(localS, portfolio)
    if needs_rerun:
        st.rerun()
        
    # 3. Main Layout
    st.header(f"📊 Danh mục của {st.session_state['username']}")
    tab_port, tab_crit, tab_val = st.tabs(["Danh mục đầu tư", "Tiêu chí Định giá", "Định giá Cổ phiếu"])
    
    with tab_port:
        try:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=30000, limit=None, key="data_refresh")
        except ImportError:
            pass
        _, _, new_title = render_portfolio_tab(portfolio, user_id)
        # Cập nhật title trình duyệt nếu có thay đổi
        if new_title != st.session_state.get('page_title_info'):
            st.session_state['page_title_info'] = new_title
            
    with tab_crit:
        render_criteria_tab()
            
    with tab_val:
        render_valuation_tab()
