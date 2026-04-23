
# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'sistema-medico-secret-key')
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'mysql-23322c83-xaviertchivela53-0149.j.aivencloud.com')
    MYSQL_USER = os.getenv('MYSQL_USER', 'avnadmin')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'AVNS_N67xkQR_g7zx0KQbi8q')
    MYSQL_DB = os.getenv('MYSQL_DB', 'defaultdb')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', 13574))
    MYSQL_SSL_MODE = os.getenv('MYSQL_SSL_MODE', 'REQUIRED')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ['true', '1', 'yes']
Use Control + Shift + m to toggle the tab key moving focus. Alternatively, use esc then tab to move to the next interactive element on the page.
 
