import mysql.connector
from mysql.connector import Error
import json
import streamlit as st
import platform

# Đọc file config.json
config_file = "config.json"
try:
    with open(config_file, "r") as f:
        config_data = json.load(f)
except FileNotFoundError:
    st.error(f"Không tìm thấy file cấu hình {config_file}!")
    st.stop()

# Tự động chọn môi trường: 'local' (nếu chạy trên Windows) hoặc 'production' (nếu chạy trên Linux/VPS)
ENVIRONMENT = "local" if platform.system() == "Windows" else "production"
db_config = config_data.get(ENVIRONMENT, {})

DB_HOST = db_config.get("host", "localhost")
DB_USER = db_config.get("user", "root")
DB_PASSWORD = db_config.get("password", "")
DB_NAME = db_config.get("database", "portfolio_db")

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        return conn
    except Error as e:
        st.error(f"Lỗi kết nối MySQL: {e}")
        return None

def init_db():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        # Tạo bảng users
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL
            )
        ''')
        # Tạo bảng portfolio
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                buy_price DOUBLE NOT NULL,
                quantity INT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        # Tạo bảng daily_pnl
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_pnl (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                record_date DATE NOT NULL,
                total_pnl DOUBLE NOT NULL,
                total_invested DOUBLE NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE KEY unique_user_date (user_id, record_date)
            )
        ''')
        conn.commit()
        cursor.close()
        conn.close()

# Tự động khởi tạo DB khi module được load
init_db()
