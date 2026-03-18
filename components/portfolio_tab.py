import streamlit as st
import pandas as pd
import json
import streamlit.components.v1 as components
from database import get_db_connection

def load_portfolio(user_id):
    conn = get_db_connection()
    if not conn: return pd.DataFrame()
    query = "SELECT id, symbol as Mã, buy_price as 'Giá mua', quantity as 'Số lượng' FROM portfolio WHERE user_id = %s"
    df = pd.read_sql(query, conn, params=(user_id,))
    conn.close()
    return df

def render_portfolio_tab(portfolio, user_id):
    """
    Xử lý logic và giao diện cho Tab Danh Mục Đầu Tư.
    Bao gồm tính toán lãi/lỗ theo giá hiện tại từ vnstock, hiển thị bảng, chỉ số, và biểu đồ PnL hằng ngày.
    """
    if portfolio.empty:
        st.info("Danh mục đang trống. Hãy thêm cổ phiếu ở sidebar.")
        return 0, 0, "+0đ (+0.0%)"
        
    page_title_info = "Danh mục đầu tư"
    total_pnl = 0
    total_invested = 0
    
    try:
        from vnstock import Trading
        import time as _time
        
        symbols = portfolio['Mã'].unique().tolist()
        realtime_data = None
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                with st.status(f"🔄 Đang kết nối vnstock... (lần {attempt + 1}/{max_retries})", expanded=True) as status:
                    st.write(f"Đang lấy giá realtime cho: {', '.join(symbols)}")
                    realtime_data = Trading().price_board(symbols)
                    status.update(label="✅ Kết nối vnstock thành công!", state="complete")
                break  # Thành công, thoát loop
            except Exception as retry_err:
                if attempt < max_retries - 1:
                    st.warning(f"⚠️ Lần {attempt + 1}: Không kết nối được vnstock ({retry_err}). Thử lại sau 5 giây...")
                    _time.sleep(5)
                else:
                    st.error(f"❌ Không thể kết nối vnstock sau {max_retries} lần thử. Lỗi: {retry_err}")
                    st.info("💡 Hiển thị danh mục với dữ liệu cơ bản (không có giá realtime).")
        
        if realtime_data is not None and not realtime_data.empty:
            sym_col = next((col for col in realtime_data.columns if 'mã' in col.lower() or 'symbol' in col.lower()), None)
            price_col = next((col for col in realtime_data.columns if 'khớp lệnh' in col.lower() or 'close' in col.lower() or 'giá' in col.lower()), None)
            ref_col = next((col for col in realtime_data.columns if 'tham chiếu' in col.lower() or 'reference' in col.lower()), None)
        
            if sym_col and price_col and ref_col:
                price_dict = dict(zip(realtime_data[sym_col], realtime_data[price_col]))
                ref_dict = dict(zip(realtime_data[sym_col], realtime_data[ref_col]))
                
                portfolio['Giá hiện tại'] = portfolio['Mã'].map(price_dict).astype(float)
                portfolio['Giá hiện tại'] = portfolio['Giá hiện tại'].apply(lambda x: x * 1000 if pd.notna(x) and x < 1000 else x)
                portfolio['Giá hiện tại'] = portfolio['Giá hiện tại'].fillna(portfolio['Giá mua'])
                
                portfolio['Giá tham chiếu'] = portfolio['Mã'].map(ref_dict).astype(float)
                portfolio['Giá tham chiếu'] = portfolio['Giá tham chiếu'].apply(lambda x: x * 1000 if pd.notna(x) and x < 1000 else x)
                portfolio['Giá tham chiếu'] = portfolio['Giá tham chiếu'].fillna(portfolio['Giá hiện tại'])
                
                portfolio['Tổng vốn'] = portfolio['Giá mua'] * portfolio['Số lượng']
                portfolio['Giá trị hiện tại'] = portfolio['Giá hiện tại'] * portfolio['Số lượng']
                portfolio['Lãi/Lỗ'] = portfolio['Giá trị hiện tại'] - portfolio['Tổng vốn']
                
                portfolio['Lãi/Lỗ trong ngày'] = (portfolio['Giá hiện tại'] - portfolio['Giá tham chiếu']) * portfolio['Số lượng']
                
                total_pnl = portfolio['Lãi/Lỗ'].sum()
                total_invested = portfolio['Tổng vốn'].sum()
                pct_pnl_val = (total_pnl / total_invested * 100) if total_invested else 0
                
                sign = "+" if total_pnl >= 0 else ""
                page_title_info = f"{sign}{total_pnl:,.0f}đ ({sign}{pct_pnl_val:.1f}%)"
            
    except ImportError:
        st.error("Thư viện vnstock chưa được cài đặt. Hãy chạy: pip install vnstock")
    except Exception as e:
        print(f"Error in vnstock calculation: {e}")
        
    # Lưu DB cuối ngày
    import datetime
    now_vn = datetime.datetime.utcnow() + datetime.timedelta(hours=7)
    if now_vn.hour > 14 or (now_vn.hour == 14 and now_vn.minute >= 45):
        try:
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
            print(f"Error in PnL database saving: {e}")

    # Render giao diện bảng
    def color_profit_loss(val):
        if pd.isna(val): return ''
        color = 'green' if val > 0 else 'red' if val < 0 else 'white'
        return f'color: {color}; font-weight: bold;'

    if 'Lãi/Lỗ' in portfolio.columns:
        portfolio['% Lãi/Lỗ'] = (portfolio['Lãi/Lỗ'] / portfolio['Tổng vốn']) * 100
        
        # Sắp xếp danh mục
        portfolio = portfolio.sort_values(by='Giá trị hiện tại', ascending=False)
        
        # Ẩn cột
        display_df = portfolio.drop(columns=['id', 'Giá tham chiếu']) if 'id' in portfolio.columns else portfolio
        
        subset_cols = ['Lãi/Lỗ', '% Lãi/Lỗ']
        if 'Lãi/Lỗ trong ngày' in display_df.columns:
            subset_cols.append('Lãi/Lỗ trong ngày')
            
        styled_df = display_df.style.applymap(color_profit_loss, subset=subset_cols)
        styled_df = styled_df.format({
            'Giá mua': '{:,.0f}', 'Giá hiện tại': '{:,.0f}',
            'Tổng vốn': '{:,.0f}', 'Giá trị hiện tại': '{:,.0f}',
            'Lãi/Lỗ': '{:,.0f}', '% Lãi/Lỗ': '{:.2f}%',
            'Lãi/Lỗ trong ngày': '{:,.0f}'
        })
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        total_value = portfolio['Giá trị hiện tại'].sum()
        pct_pnl_str = f"{(total_pnl/total_invested)*100 if total_invested else 0:+.2f}%"
        
        st.subheader("💰 Tổng quan tài khoản")
        col1, col2, col3 = st.columns(3)
        col1.metric("Tổng vốn đầu tư", f"{total_invested:,.0f} VNĐ")
        col2.metric("Giá trị hiện tại", f"{total_value:,.0f} VNĐ")
        col3.metric("Tổng Lãi/Lỗ", f"{total_pnl:,.0f} VNĐ", pct_pnl_str)
        
        # Hiển thị biểu đồ
        conn = get_db_connection()
        if conn:
            daily_query = "SELECT record_date, total_pnl, total_invested FROM daily_pnl WHERE user_id = %s ORDER BY record_date"
            daily_df = pd.read_sql(daily_query, conn, params=(user_id,))
            conn.close()
            
            if not daily_df.empty:
                st.divider()
                st.subheader("📈 Lịch sử Lãi/Lỗ hằng ngày (%)")
                
                daily_df['record_date_str'] = pd.to_datetime(daily_df['record_date']).dt.strftime('%d/%m/%Y')
                daily_df['pct_pnl'] = ((daily_df['total_pnl'] / daily_df['total_invested']) * 100).round(2)
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
        
    return total_pnl, total_invested, page_title_info
