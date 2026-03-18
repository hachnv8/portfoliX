import streamlit as st
import os
import json
from PIL import Image
from database import get_db_connection

def save_criteria(user_id, name, notes, image_paths):
    """Lưu tiêu chí vào DB."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO valuation_criteria (user_id, criteria_name, notes, image_paths) VALUES (%s, %s, %s, %s)",
            (user_id, name, notes, json.dumps(image_paths))
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Lỗi lưu tiêu chí: {e}")
        return False

def load_criteria_list(user_id):
    """Lấy danh sách tiêu chí đã lưu của user."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    cursor.execute("SELECT id, criteria_name, created_at FROM valuation_criteria WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def load_criteria_detail(criteria_id):
    """Lấy chi tiết 1 tiêu chí theo ID."""
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()
    cursor.execute("SELECT criteria_name, notes, image_paths FROM valuation_criteria WHERE id = %s", (criteria_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        return {
            "name": row[0],
            "notes": row[1] or "",
            "image_paths": json.loads(row[2]) if row[2] else []
        }
    return None

def delete_criteria(criteria_id):
    """Xóa 1 tiêu chí."""
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    cursor.execute("DELETE FROM valuation_criteria WHERE id = %s", (criteria_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return True

def render_criteria_tab():
    """
    Giao diện cho Tab Tiêu chí Định giá.
    Cho phép người dùng nhập tên tiêu chí, ghi chú Text, Upload Hình ảnh
    và lưu vào DB. Hiển thị danh sách các tiêu chí đã lưu bên dưới.
    """
    user_id = st.session_state.get('user_id')
    if not user_id:
        st.warning("Vui lòng đăng nhập.")
        return
        
    st.subheader("⚙️ Thiết lập Tiêu chí Định giá")
    st.write("Tạo các bộ tiêu chuẩn định giá riêng biệt. Mỗi bộ có thể chứa ghi chú và hình ảnh tham chiếu.")
    
    # === FORM THÊM MỚI TIÊU CHÍ ===
    st.markdown("### ➕ Tạo Tiêu chí mới")
    
    criteria_name = st.text_input("Tên Tiêu chí (VD: 'Chiến lược Value Investing', 'Tiêu chí Tăng trưởng'...)")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("#### 📝 Ghi chú")
        notes = st.text_area(
            "Nhập các tiêu chuẩn tài chính (VD: P/E < 15, ROE > 15%, Biên lãi gộp > 20%...)", 
            height=250,
            key="criteria_notes_input"
        )
        
    with col2:
        st.markdown("#### 🖼️ Hình ảnh Tham chiếu")
        uploaded_files = st.file_uploader(
            "Chọn hình ảnh...", 
            type=['png', 'jpg', 'jpeg'], 
            accept_multiple_files=True,
            key="criteria_img_uploader"
        )
        
        upload_dir = "uploads"
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
        
        # Xử lý ảnh upload
        uploaded_paths = []
        if uploaded_files:
            for uploaded_file in uploaded_files:
                file_path = os.path.join(upload_dir, uploaded_file.name)
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                uploaded_paths.append(file_path)
            st.success(f"Đã tải lên {len(uploaded_paths)} ảnh.")
    
    # Nút Lưu
    if st.button("💾 Lưu Tiêu chí", type="primary", use_container_width=True):
        if not criteria_name or not criteria_name.strip():
            st.error("Vui lòng nhập Tên Tiêu chí!")
        elif not notes and not uploaded_paths:
            st.error("Vui lòng nhập Ghi chú hoặc tải lên Hình ảnh!")
        else:
            if save_criteria(user_id, criteria_name.strip(), notes, uploaded_paths):
                st.success(f"✅ Đã lưu tiêu chí: **{criteria_name.strip()}**")
                st.rerun()
            else:
                st.error("Lưu thất bại!")
    
    # === DANH SÁCH TIÊU CHÍ ĐÃ LƯU ===
    st.divider()
    st.markdown("### 📋 Danh sách Tiêu chí đã lưu")
    
    criteria_list = load_criteria_list(user_id)
    
    if not criteria_list:
        st.info("Chưa có tiêu chí nào được lưu. Hãy tạo tiêu chí mới ở phía trên.")
    else:
        for cid, cname, created_at in criteria_list:
            with st.expander(f"📌 {cname}  _(tạo lúc: {created_at})_"):
                detail = load_criteria_detail(cid)
                if detail:
                    if detail['notes']:
                        st.markdown("**Ghi chú:**")
                        st.text(detail['notes'])
                    if detail['image_paths']:
                        st.markdown("**Hình ảnh:**")
                        img_cols = st.columns(min(len(detail['image_paths']), 3))
                        for idx, img_path in enumerate(detail['image_paths']):
                            if os.path.exists(img_path):
                                try:
                                    img = Image.open(img_path)
                                    img_cols[idx % 3].image(img, caption=os.path.basename(img_path), use_container_width=True)
                                except Exception:
                                    pass
                    
                    if st.button(f"🗑️ Xóa tiêu chí này", key=f"del_criteria_{cid}"):
                        delete_criteria(cid)
                        st.success(f"Đã xóa: {cname}")
                        st.rerun()
