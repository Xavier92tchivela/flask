import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuração principal da aplicação"""
    
    # Segurança
    SECRET_KEY = os.getenv('SECRET_KEY', 'sistema-medico-secret-key-change-in-production')
    
    # Configurações de URL (para geração de links em emails, etc)
    SERVER_NAME = os.getenv('SERVER_NAME', None)  # Deixe None em desenvolvimento
    PREFERRED_URL_SCHEME = os.getenv('PREFERRED_URL_SCHEME', 'http')
    APPLICATION_ROOT = os.getenv('APPLICATION_ROOT', '/')
    
    # Banco de dados MySQL (Aiven)
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'mysql-23322c83-xaviertchivela53-0149.j.aivencloud.com')
    MYSQL_USER = os.getenv('MYSQL_USER', 'avnadmin')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'AVNS_N67xkQR_g7zx0KQbi8q')
    MYSQL_DB = os.getenv('MYSQL_DB', 'defaultdb')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', 13574))
    MYSQL_SSL_MODE = os.getenv('MYSQL_SSL_MODE', 'REQUIRED')
    
    # Google Gemini AI
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    
    # Upload de arquivos
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'static/uploads')
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'pdf'}
    
    # Configurações de sessão
    PERMANENT_SESSION_LIFETIME = int(os.getenv('PERMANENT_SESSION_LIFETIME', 86400))  # 24 horas
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() in ['true', '1', 'yes']
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Modo debug
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ['true', '1', 'yes']
    TESTING = os.getenv('FLASK_TESTING', 'False').lower() in ['true', '1', 'yes']
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def get_database_config(cls):
        """Retorna configuração do banco de dados como dicionário"""
        return {
            'host': cls.MYSQL_HOST,
            'user': cls.MYSQL_USER,
            'password': cls.MYSQL_PASSWORD,
            'database': cls.MYSQL_DB,
            'port': cls.MYSQL_PORT,
            'ssl_mode': cls.MYSQL_SSL_MODE
        }
    
    @classmethod
    def is_production(cls):
        """Verifica se está em ambiente de produção"""
        return not cls.DEBUG and cls.SERVER_NAME is not None

# Ambiente específico para desenvolvimento
class DevelopmentConfig(Config):
    DEBUG = True
    SERVER_NAME = None  # Sem SERVER_NAME em desenvolvimento
    PREFERRED_URL_SCHEME = 'http'
    SESSION_COOKIE_SECURE = False

# Ambiente específico para produção
class ProductionConfig(Config):
    DEBUG = False
    SERVER_NAME = os.getenv('SERVER_NAME', 'hospitalcacula.com')
    PREFERRED_URL_SCHEME = 'https'
    SESSION_COOKIE_SECURE = True

# Dicionário de configurações por ambiente
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
