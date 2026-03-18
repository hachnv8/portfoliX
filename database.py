import mysql.connector
from mysql.connector import Error
import json
import streamlit as st
import platform
import os
import base64
from cryptography.fernet import Fernet

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
        # Tạo bảng valuation_criteria
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS valuation_criteria (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                criteria_name VARCHAR(255) NOT NULL,
                notes TEXT,
                image_paths JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        # Tạo bảng user_api_keys (lưu key đã mã hoá)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_api_keys (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL UNIQUE,
                service_name VARCHAR(100) NOT NULL DEFAULT 'gemini',
                encrypted_key TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        # Tạo/migrate bảng stock_analysis (đúng cấu trúc JSON)
        # Kiểm tra nếu bảng cũ (có buy_point_1) thì xóa và tạo lại
        cursor.execute("SHOW TABLES LIKE 'stock_analysis'")
        if cursor.fetchone():
            cursor.execute("SHOW COLUMNS FROM stock_analysis LIKE 'buy_point_1'")
            if cursor.fetchone():
                # Bảng cũ, xóa tạo lại
                cursor.execute("DROP TABLE stock_analysis")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_analysis (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                p_e DOUBLE,
                p_b DOUBLE,
                eps_status VARCHAR(50),
                current_zone VARCHAR(50),
                signal_status VARCHAR(100),
                is_buying_zone BOOLEAN DEFAULT FALSE,
                entry_min DOUBLE,
                entry_max DOUBLE,
                target DOUBLE,
                action VARCHAR(100),
                analysis_note TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE KEY unique_user_symbol (user_id, symbol)
            )
        ''')
        conn.commit()
        cursor.close()
        conn.close()

# Tự động khởi tạo DB khi module được load
init_db()

# === MÃ HOÁ API KEY ===
_ENCRYPTION_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.encryption_key')

def _get_encryption_key():
    """Lấy hoặc tạo mới encryption key (Fernet symmetric key)."""
    if os.path.exists(_ENCRYPTION_KEY_FILE):
        with open(_ENCRYPTION_KEY_FILE, 'rb') as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(_ENCRYPTION_KEY_FILE, 'wb') as f:
            f.write(key)
        return key

def encrypt_api_key(plain_key):
    """Mã hoá API key."""
    fernet = Fernet(_get_encryption_key())
    return fernet.encrypt(plain_key.encode()).decode()

def decrypt_api_key(encrypted_key):
    """Giải mã API key."""
    try:
        fernet = Fernet(_get_encryption_key())
        return fernet.decrypt(encrypted_key.encode()).decode()
    except Exception:
        return None

def save_user_api_key(user_id, plain_key, service_name='gemini'):
    """Lưu API key đã mã hoá vào DB."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        encrypted = encrypt_api_key(plain_key)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_api_keys (user_id, service_name, encrypted_key) 
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE encrypted_key = %s, service_name = %s
        """, (user_id, service_name, encrypted, encrypted, service_name))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving API key: {e}")
        return False

def load_user_api_key(user_id, service_name='gemini'):
    """Load và giải mã API key từ DB. Trả về plain key hoặc None."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT encrypted_key FROM user_api_keys WHERE user_id = %s AND service_name = %s", (user_id, service_name))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row:
            return decrypt_api_key(row[0])
        return None
    except Exception:
        return None
