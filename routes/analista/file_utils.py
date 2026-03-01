"""Utilitários para manipulação de arquivos"""
import os
from flask import current_app
import logging

logger = logging.getLogger(__name__)
_app = None

def set_app_config(app):
    """Configura a referência da aplicação"""
    global _app
    _app = app

def get_app():
    """Retorna a aplicação configurada ou current_app como fallback"""
    if _app:
        return _app
    from flask import current_app
    return current_app

def get_upload_folder(subfolder=''):
    """Retorna o caminho completo da pasta de upload"""
    app = get_app()
    base_folder = app.config.get('UPLOAD_FOLDER', 'static/uploads')
    if subfolder:
        return os.path.join(base_folder, subfolder)
    return base_folder

def get_pedido_anexo_path(filename):
    """Retorna o caminho completo de um anexo de pedido"""
    return os.path.join(get_upload_folder('pedidos'), filename)

def get_temp_folder():
    """Retorna o caminho da pasta temporária"""
    return get_upload_folder('temp')

def ensure_temp_folder():
    """Garante que a pasta temporária existe"""
    temp_dir = get_temp_folder()
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir