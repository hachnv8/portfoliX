import streamlit as st
from streamlit_local_storage import LocalStorage

# Import các components sau khi đã refactor
from auth import render_auth_ui
from components.sidebar import render_sidebar
from components.portfolio_tab import load_portfolio, render_portfolio_tab
from components.valuation_tab import render_valuation_tab, check_buy_alerts
from components.criteria_tab import render_criteria_tab

# Khởi tạo LocalStorage
localS = LocalStorage()

# --- KHỞI TẠO SESSION STATE VÀ TỰ ĐỘNG ĐĂNG NHẬP ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['user_id'] = None
    st.session_state['username'] = ""
    st.session_state['page_title_info'] = "Danh mục đầu tư"

if 'active_tab' not in st.session_state:
    st.session_state['active_tab'] = 0  # 0 = Danh mục, 1 = Tiêu chí, 2 = Định giá

# Đọc Cookie/LocalStorage để tự động đăng nhập (nếu chưa login)
if not st.session_state['logged_in']:
    saved_user_id = localS.getItem("portfolix_user_id")
    saved_username = localS.getItem("portfolix_username")
    
    if saved_user_id and saved_username:
        st.session_state['logged_in'] = True
        st.session_state['user_id'] = int(saved_user_id)
        st.session_state['username'] = saved_username
        st.rerun()

# Cấu hình trang
st.set_page_config(page_title=st.session_state.get('page_title_info', 'Danh mục đầu tư'), layout="wide")

# Tự động refresh CHỈ khi đang ở tab Danh mục (tab 0)
if st.session_state['logged_in'] and st.session_state.get('active_tab', 0) == 0:
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=30000, limit=None, key="data_refresh")
    except ImportError:
        pass

# --- GIAO DIỆN CHÍNH (ROUTER) ---
if not st.session_state['logged_in']:
    success, uid, uname = render_auth_ui(localS)
    if success:
        st.session_state['logged_in'] = True
        st.session_state['user_id'] = uid
        st.session_state['username'] = uname
        st.rerun()
else:
    user_id = st.session_state['user_id']
    portfolio = load_portfolio(user_id)
    
    needs_rerun = render_sidebar(localS, portfolio)
    if needs_rerun:
        st.rerun()
        
    st.header(f"📊 Danh mục của {st.session_state['username']}")
    
    # Dùng radio button ẩn để track active tab
    tab_names = ["Danh mục đầu tư", "Tiêu chí Định giá", "Định giá Cổ phiếu"]
    
    # Tạo 3 cột cho các nút chuyển tab (styling giống tab)
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📈 Danh mục đầu tư", use_container_width=True, 
                     type="primary" if st.session_state['active_tab'] == 0 else "secondary"):
            st.session_state['active_tab'] = 0
            st.rerun()
    with col2:
        if st.button("⚙️ Tiêu chí Định giá", use_container_width=True,
                     type="primary" if st.session_state['active_tab'] == 1 else "secondary"):
            st.session_state['active_tab'] = 1
            st.rerun()
    with col3:
        if st.button("📊 Phân tích CP", use_container_width=True,
                     type="primary" if st.session_state['active_tab'] == 2 else "secondary"):
            st.session_state['active_tab'] = 2
            st.rerun()
    
    st.divider()
    
    # Hiển thị nội dung tab tương ứng
    active = st.session_state['active_tab']
    
    if active == 0:
        _, _, new_title = render_portfolio_tab(portfolio, user_id)
        if new_title != st.session_state.get('page_title_info'):
            st.session_state['page_title_info'] = new_title
        
        # Hiển thị cảnh báo điểm mua
        alerts = check_buy_alerts(portfolio, user_id)
        if alerts:
            st.divider()
            st.markdown("### 🔔 Cảnh báo Điểm mua")
            for alert in alerts:
                st.warning(alert)
    elif active == 1:
        render_criteria_tab()
    elif active == 2:
        render_valuation_tab()
