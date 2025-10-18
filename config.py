import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'sistema-medico-secret-key')
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'root')
    MYSQL_DB = os.getenv('MYSQL_DB', 'sistema_medico')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
