# config.py - APENAS definições de configuração
import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

class Config:
    # Chave secreta para sessões
    SECRET_KEY = os.getenv('SECRET_KEY', 'sistema-medico-secret-key')
    
    # Configurações do MySQL
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'root')
    MYSQL_DB = os.getenv('MYSQL_DB', 'sistema_medico')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
    
    # Configurações da API Gemini
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    
    # Configurações de upload
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
    
    # Configurações Flask
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() in ['true', '1', 'yes']

# NÃO adicione código para executar aqui
# Este arquivo deve apenas definir a classe Config