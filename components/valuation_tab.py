import streamlit as st
import pandas as pd
from PIL import Image
import os

try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

def fetch_stock_data(symbol):
    """
    Sử dụng vnstock để lấy dữ liệu cơ bản của mã cổ phiếu.
    """
    try:
        from vnstock import stock_historical_data, financial_ratio
        import datetime
        
        try:
            ratio_df = financial_ratio(symbol, 'yearly', True)
            if not ratio_df.empty:
                return ratio_df.iloc[:, :5].to_string()
            return "Không tìm thấy dữ liệu tài chính cho mã này."
        except Exception as e:
            return f"Lỗi khi lấy dữ liệu tài chính: {e}"
    except ImportError:
        return "Thư viện vnstock chưa được cài đặt."
    except Exception as e:
        return f"Lỗi không xác định: {e}"


def evaluate_stock_with_ai(api_key, symbol, stock_data, user_notes, image_paths):
    """
    Gọi Google Gemini API để đánh giá dựa trên dữ liệu & Tiêu chí của user.
    """
    if not HAS_GENAI:
        return "Thư viện google-generativeai chưa được cài đặt xong. Vui lòng chờ trong giây lát hoặc thử lại."
        
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        prompt = f"""
        Bạn là một chuyên gia phân tích tài chính chứng khoán độc lập và sắc sảo.
        Nhiệm vụ của bạn là định giá và phân tích mã cổ phiếu: {symbol.upper()}.
        
        Dưới đây là dữ liệu tài chính các năm gần nhất của công ty:
        {stock_data}
        
        -- QUAN TRỌNG: TIÊU CHÍ ĐÁNH GIÁ CỦA TÔI --
        Vui lòng phân tích và kết luận DỰA TRÊN NGHIÊM NGẶT các tiêu chí và ghi chú sau đây của tôi:
        {user_notes if user_notes else "Không có ghi chú text nào."}
        
        Bên cạnh đó, tôi có đính kèm các hình ảnh mẫu (công thức, đồ thị, bảng biểu). Hãy đọc và áp dụng các thông tin trong ảnh vào việc định giá.
        
        YÊU CẦU ĐẦU RA:
        1. Đánh giá Tích cực / Tiêu cực dựa trên các tiêu chí của tôi.
        2. Dựa theo dữ liệu cung cấp, định giá xem mã cổ phiếu này hiện tại Đang Rẻ, Đang Đắt, hay Hợp lý so với các tiêu chí tôi đưa ra.
        3. Kết luận ngắn gọn có nên đưa vào danh mục theo chiến lược của tôi hay không.
        (Định dạng kết quả bằng Markdown đẹp mắt).
        """
        
        contents = [prompt]
        
        if image_paths:
            for img_path in image_paths:
                if os.path.exists(img_path):
                    img = Image.open(img_path)
                    contents.append(img)
        
        # Tự động retry nếu bị rate limit (429)
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = model.generate_content(contents)
                return response.text
            except Exception as retry_err:
                if '429' in str(retry_err) and attempt < max_retries - 1:
                    wait_time = 35 * (attempt + 1)
                    st.toast(f"⏳ Đang chờ hết giới hạn free tier ({wait_time}s)... Lần thử {attempt + 2}/{max_retries}")
                    time.sleep(wait_time)
                else:
                    raise retry_err
        
    except Exception as e:
        return f"Lỗi trong quá trình gọi AI: {str(e)}"
        

def render_valuation_tab():
    """
    Giao diện và Logic cho Tab Định Giá Cổ phiếu.
    """
    from components.criteria_tab import load_criteria_list, load_criteria_detail
    from database import save_user_api_key, load_user_api_key
    
    user_id = st.session_state.get('user_id')
    if not user_id:
        st.warning("Vui lòng đăng nhập.")
        return

    # Auto-load API key từ DB nếu chưa có trong session
    if 'gemini_api_key' not in st.session_state or not st.session_state['gemini_api_key']:
        saved_key = load_user_api_key(user_id)
        if saved_key:
            st.session_state['gemini_api_key'] = saved_key

    st.subheader("🤖 Phân tích & Định giá bằng AI (Gemini)")
    
    # Khu vực cấu hình API Key
    has_key = bool(st.session_state.get('gemini_api_key'))
    with st.expander("🔑 Cấu hình Google Gemini API Key", expanded=not has_key):
        if has_key:
            st.success("✅ API Key đã được lưu và mã hoá trong hệ thống.")
            st.caption("Bạn có thể nhập key mới bên dưới để thay thế.")
        else:
            st.write("Để sử dụng tính năng này miễn phí, hãy lấy API Key tại [Google AI Studio](https://aistudio.google.com/app/apikey).")
        
        api_key_input = st.text_input("Nhập Gemini API Key mới:", type="password", key="gemini_key_input")
        
        if st.button("💾 Lưu API Key"):
            if api_key_input:
                if save_user_api_key(user_id, api_key_input):
                    st.session_state['gemini_api_key'] = api_key_input
                    st.success("✅ API Key đã được mã hoá và lưu vào cơ sở dữ liệu thành công!")
                    st.rerun()
                else:
                    st.error("Lỗi khi lưu API Key!")
            else:
                st.warning("Vui lòng nhập API Key.")
                
    st.divider()
    
    st.markdown("### 🎯 Định giá Cổ phiếu")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        symbol_evaluate = st.text_input("Mã Cổ phiếu cần Phân tích (VD: HPG)", "").upper().strip()
        
        # === DROPDOWN CHỌN TIÊU CHÍ ===
        st.markdown("---")
        st.markdown("**📌 Chọn Bộ Tiêu chí Định giá:**")
        criteria_list = load_criteria_list(user_id)
        
        selected_criteria_id = None
        if not criteria_list:
            st.warning("⚠️ Chưa có tiêu chí nào. Vui lòng tạo ở Tab 'Tiêu chí Định giá' trước.")
        else:
            criteria_options = {f"{cname}": cid for cid, cname, _ in criteria_list}
            selected_name = st.selectbox(
                "Chọn tiêu chí đã lưu:", 
                options=list(criteria_options.keys()),
                key="criteria_dropdown"
            )
            selected_criteria_id = criteria_options.get(selected_name)
            
            # Hiển thị preview tiêu chí đã chọn
            if selected_criteria_id:
                detail = load_criteria_detail(selected_criteria_id)
                if detail:
                    with st.expander("👁️ Xem nội dung tiêu chí đã chọn"):
                        if detail['notes']:
                            st.text(detail['notes'][:300] + ("..." if len(detail['notes']) > 300 else ""))
                        if detail['image_paths']:
                            st.caption(f"📎 {len(detail['image_paths'])} hình ảnh đính kèm")
        
        st.markdown("---")
        start_eval = st.button("🚀 Bắt đầu Đánh giá AI", type="primary", use_container_width=True)
            
    with col2:
        if start_eval:
            api_key = st.session_state.get('gemini_api_key', '')
            if not api_key:
                st.error("❌ Vui lòng Cấu hình Google Gemini API Key ở mục phía trên trước!")
            elif not symbol_evaluate:
                st.warning("❌ Vui lòng nhập Mã Cổ phiếu!")
            elif not selected_criteria_id:
                st.warning("❌ Vui lòng chọn một Bộ Tiêu chí!")
            else:
                with st.spinner(f"Đang kéo dữ liệu tài chính cho {symbol_evaluate} và phân tích bằng AI... (có thể mất 15-30s)"):
                    # 1. Fetch data
                    stock_data_txt = fetch_stock_data(symbol_evaluate)
                    
                    # 2. Lấy tiêu chí từ DB
                    detail = load_criteria_detail(selected_criteria_id)
                    user_notes = detail['notes'] if detail else ""
                    user_images = detail['image_paths'] if detail else []
                    
                    # 3. Gửi AI
                    result = evaluate_stock_with_ai(api_key, symbol_evaluate, stock_data_txt, user_notes, user_images)
                    
                    st.markdown("### 📈 Kết quả Phân tích từ AI:")
                    st.markdown(result)
