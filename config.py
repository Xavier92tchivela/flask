# config.py - Configuração para Aiven MySQL Cloud
import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

class Config:
    # Chave secreta para sessões
    SECRET_KEY = os.getenv('SECRET_KEY', 'sistema-medico-secret-key')
    
    # Configurações do MySQL (Aiven Cloud)
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'mysql-23322c83-xaviertchivela53-0149.j.aivencloud.com')
    MYSQL_USER = os.getenv('MYSQL_USER', 'avnadmin')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
    MYSQL_DB = os.getenv('MYSQL_DB', 'defaultdb')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', 13574))
    
    # SSL para Aiven
    MYSQL_SSL_MODE = os.getenv('MYSQL_SSL_MODE', 'REQUIRED')
    
    # Configurações da API Gemini
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    
    # Configurações de upload
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
    
    # Configurações Flask
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ['true', '1', 'yes']
