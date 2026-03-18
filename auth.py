import hashlib
import streamlit as st
from database import get_db_connection

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

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
    except Exception:
        return False

def render_auth_ui(localS):
    """
    Hiển thị giao diện Đăng nhập / Đăng ký.
    Trả về (True, user_id, username) nếu đăng nhập thành công, ngược lại (False, None, "").
    """
    st.title("🔐 Đăng nhập Hệ thống")
    tab1, tab2 = st.tabs(["Đăng nhập", "Đăng ký"])
    
    with tab1:
        with st.form("login_form"):
            l_user = st.text_input("Tên đăng nhập")
            l_pass = st.text_input("Mật khẩu", type="password")
            if st.form_submit_button("Đăng nhập"):
                uid = login_user(l_user, l_pass)
                if uid:
                    # Lưu vào local storage để lần sau không cần đăng nhập lại
                    localS.setItem("portfolix_user_id", str(uid), key="set_uid")
                    localS.setItem("portfolix_username", l_user, key="set_uname")
                    
                    st.success("Đăng nhập thành công!")
                    return True, uid, l_user
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
    
    return False, None, ""
