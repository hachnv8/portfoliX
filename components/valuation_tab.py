import streamlit as st
import pandas as pd
import json
from database import get_db_connection


def save_analysis_json(user_id, json_data):
    """Lưu toàn bộ dữ liệu từ JSON vào DB đúng cấu trúc."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        for t in json_data.get('tickers', []):
            symbol = t['symbol']
            fund = t.get('fundamental', {})
            tech = t.get('technical_status', {})
            plan = t.get('trading_plan', {})
            note = t.get('analysis_note', '')
            
            cursor.execute("""
                INSERT INTO stock_analysis 
                    (user_id, symbol, p_e, p_b, eps_status, current_zone, signal_status, is_buying_zone, entry_min, entry_max, target, action, analysis_note)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    p_e=%s, p_b=%s, eps_status=%s, current_zone=%s, signal_status=%s, is_buying_zone=%s,
                    entry_min=%s, entry_max=%s, target=%s, action=%s, analysis_note=%s
            """, (
                user_id, symbol,
                fund.get('p_e'), fund.get('p_b'), fund.get('eps_status'),
                tech.get('current_zone'), tech.get('signal'), tech.get('is_buying_zone', False),
                plan.get('entry_min'), plan.get('entry_max'), plan.get('target'), plan.get('action'),
                note,
                # ON DUPLICATE UPDATE values:
                fund.get('p_e'), fund.get('p_b'), fund.get('eps_status'),
                tech.get('current_zone'), tech.get('signal'), tech.get('is_buying_zone', False),
                plan.get('entry_min'), plan.get('entry_max'), plan.get('target'), plan.get('action'),
                note
            ))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Lỗi lưu dữ liệu: {e}")
        return False


def load_all_analysis(user_id):
    """Lấy toàn bộ phân tích."""
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    try:
        df = pd.read_sql("""
            SELECT symbol, p_e, p_b, eps_status, current_zone, signal_status, 
                   is_buying_zone, entry_min, entry_max, target, action, analysis_note, updated_at
            FROM stock_analysis WHERE user_id = %s ORDER BY symbol
        """, conn, params=(user_id,))
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def delete_stock_analysis(user_id, symbol):
    """Xóa phân tích 1 mã."""
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    cursor.execute("DELETE FROM stock_analysis WHERE user_id = %s AND symbol = %s", (user_id, symbol.upper()))
    conn.commit()
    cursor.close()
    conn.close()
    return True


def check_buy_alerts(portfolio_df, user_id):
    """So sánh giá hiện tại với vùng mua (entry_min - entry_max)."""
    alerts = []
    if portfolio_df.empty or 'Giá hiện tại' not in portfolio_df.columns:
        return alerts
    
    analysis_df = load_all_analysis(user_id)
    if analysis_df.empty:
        return alerts
    
    for _, row in portfolio_df.iterrows():
        symbol = row['Mã']
        current_price = row.get('Giá hiện tại', 0)
        if not current_price or current_price == 0:
            continue
        
        match = analysis_df[analysis_df['symbol'] == symbol]
        if match.empty:
            continue
        
        a = match.iloc[0]
        entry_min = a.get('entry_min')
        entry_max = a.get('entry_max')
        
        if pd.notna(entry_min) and pd.notna(entry_max):
            low = float(entry_min) * 1000
            high = float(entry_max) * 1000
            if low <= current_price <= high:
                alerts.append(f"🔔 **{symbol}** đang ở VÙNG MUA: {entry_min} - {entry_max} (Giá: {current_price:,.0f})")
            elif current_price < low:
                alerts.append(f"🚨 **{symbol}** THẤP HƠN vùng mua {entry_min} (Giá: {current_price:,.0f}) — Cơ hội tích sản!")
    
    return alerts


def render_valuation_tab():
    """Tab Phân tích Cổ phiếu — Import JSON hoặc xem chi tiết."""
    user_id = st.session_state.get('user_id')
    if not user_id:
        st.warning("Vui lòng đăng nhập.")
        return

    st.subheader("📊 Phân tích & Chiến lược Cổ phiếu")
    
    # === BẢNG TỔNG HỢP (dạng bảng tĩnh giống hình) ===
    analysis_df = load_all_analysis(user_id)
    
    if not analysis_df.empty:
        st.markdown(f"#### Tóm tắt chiến lược \"Gom hàng\" cho {st.session_state.get('username', '')}:")
        
        # Tạo bảng hiển thị đúng format hình
        summary_rows = []
        for _, row in analysis_df.iterrows():
            entry_str = f"{row['entry_min']:.1f} - {row['entry_max']:.1f}" if pd.notna(row['entry_min']) and pd.notna(row['entry_max']) else ''
            if row['current_zone'] == 'Green':
                zone_html = '<span style="background-color: #e6f4ea; color: #1e8e3e; padding: 4px 12px; border-radius: 20px; font-weight: bold;">🟢 Xanh</span>'
            elif row['current_zone'] == 'Pink':
                zone_html = '<span style="background-color: #fce8e6; color: #d93025; padding: 4px 12px; border-radius: 20px; font-weight: bold;">🔴 Hồng</span>'
            elif row['current_zone'] == 'Neutral':
                zone_html = '<span style="background-color: #fef7e0; color: #b08d00; padding: 4px 12px; border-radius: 20px; font-weight: bold;">🟡 Trung tính</span>'
            else:
                zone_html = row['current_zone'] if row['current_zone'] else ''
                
            signal = row['signal_status'].replace('_', ' ') if row['signal_status'] else ''
            action = row['action'].replace('_', ' ') if row['action'] else ''
            
            summary_rows.append({
                'Mã': row['symbol'],
                'P/E': f"{row['p_e']:.1f}" if pd.notna(row['p_e']) else '',
                'P/B': f"{row['p_b']:.1f}" if pd.notna(row['p_b']) else '',
                'Vùng': zone_html,
                'Trạng thái': signal,
                'Vùng mua (Tích sản)': entry_str,
                'Mục tiêu': row['target'],
                'Hành động': action,
            })
        
        summary_df = pd.DataFrame(summary_rows)
        # Sử dụng HTML Table để render được badge màu
        table_html = summary_df.to_html(escape=False, index=False)
        st.markdown(f"""<style>
.custom-stock-table {{ width: 100%; border-collapse: collapse; font-family: ui-sans-serif, system-ui, -apple-system; font-size: 14px; margin-bottom: 20px; }}
.custom-stock-table th {{ border-bottom: 2px solid #f0f2f6; color: #31333F; font-weight: 600; padding: 10px 16px; text-align: left; }}
.custom-stock-table td {{ border-bottom: 1px solid #f0f2f6; padding: 10px 16px; color: #31333F; vertical-align: middle; }}
</style>
<div style="overflow-x:auto;">
    {table_html.replace('<table border="1" class="dataframe">', '<table class="custom-stock-table">')}
</div>""", unsafe_allow_html=True)
        
        # Chi tiết từng mã
        st.markdown("### 📝 Chi tiết phân tích từng mã")
        for _, row in analysis_df.iterrows():
            sym = row['symbol']
            zone_emoji = "🟢" if row['current_zone'] == 'Green' else "🔴" if row['current_zone'] == 'Pink' else "⚪"
            entry_str = f"{row['entry_min']} - {row['entry_max']}" if pd.notna(row['entry_min']) else "Chưa có"
            
            with st.expander(f"{zone_emoji} **{sym}** — {row['signal_status']} | Mua: {entry_str} | Target: {row['target']}"):
                c1, c2, c3 = st.columns(3)
                c1.metric("P/E", f"{row['p_e']:.1f}" if pd.notna(row['p_e']) else "N/A")
                c2.metric("P/B", f"{row['p_b']:.1f}" if pd.notna(row['p_b']) else "N/A")
                c3.metric("EPS", row['eps_status'])
                
                st.markdown("---")
                st.markdown(f"**📌 Nhận định:**\n\n{row['analysis_note']}")
                
                if st.button(f"🗑️ Xóa {sym}", key=f"del_{sym}"):
                    delete_stock_analysis(user_id, sym)
                    st.rerun()
    else:
        st.info("Chưa có phân tích nào. Dán JSON bên dưới để bắt đầu.")
    
    st.divider()
    
    # === NHẬP JSON ===
    st.markdown("### 📥 Nhập dữ liệu JSON")
    
    with st.expander("📄 Xem & Copy JSON Template (Mẫu chuẩn cho AI)"):
        st.code('''{
  "tickers": [
    {
      "symbol": "TICKER",
      "fundamental": { 
        "p_e": 0.0, 
        "p_b": 0.0, 
        "eps_status": "Dương/Âm" 
      },
      "technical_status": {
        "current_zone": "Xanh/Hồng/Trung tính",
        "signal": "Mô tả tín hiệu",
        "is_buying_zone": false
      },
      "trading_plan": {
        "entry_min": 0.0,
        "entry_max": 0.0,
        "target": 0.0,
        "action": "Hành động khuyến nghị"
      },
      "analysis_note": "Nhận định chi tiết..."
    }
  ]
}''', language="json")
    
    # Dùng session_state key binding cho text_area
    if 'json_input_key' not in st.session_state:
        st.session_state['json_input_key'] = 0
        
    json_input = st.text_area(
        "Dán nội dung JSON vào đây:",
        height=300,
        key=f"json_input_area_{st.session_state['json_input_key']}",
        placeholder='{\n  "tickers": [\n    { "symbol": "HPG", "fundamental": {...}, "trading_plan": {...}, ... }\n  ]\n}'
    )
    
    if json_input.strip():
        try:
            data = json.loads(json_input)
            tickers = data.get('tickers', [])
            
            if tickers:
                # Preview bảng trước khi import
                preview = []
                for t in tickers:
                    plan = t.get('trading_plan', {})
                    tech = t.get('technical_status', {})
                    fund = t.get('fundamental', {})
                    preview.append({
                        'Mã': t['symbol'],
                        'P/E': fund.get('p_e'),
                        'P/B': fund.get('p_b'),
                        'Vùng': tech.get('current_zone'),
                        'Tín hiệu': tech.get('signal', '').replace('_', ' '),
                        'Vùng mua': f"{plan.get('entry_min', '')} - {plan.get('entry_max', '')}",
                        'Mục tiêu': plan.get('target'),
                        'Hành động': plan.get('action', '').replace('_', ' '),
                    })
                
                st.markdown(f"**Preview — {len(tickers)} mã:**")
                st.dataframe(pd.DataFrame(preview), use_container_width=True, hide_index=True)
                
                if st.button("✅ Xác nhận Import", type="primary", use_container_width=True):
                    if save_analysis_json(user_id, data):
                        st.success(f"✅ Import/Cập nhật thành công {len(tickers)} mã!")
                        # Clear text area bằng cách thay đổi key
                        st.session_state['json_input_key'] += 1
                        st.rerun()
            else:
                st.warning("JSON không chứa dữ liệu tickers.")
        except json.JSONDecodeError:
            st.error("❌ Nội dung JSON không hợp lệ! Kiểm tra lại cú pháp.")
