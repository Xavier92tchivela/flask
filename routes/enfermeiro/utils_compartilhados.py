# routes/enfermeiro/__init__.py
from flask import Blueprint
from routes.enfermeiro.dashboard import dashboard_bp
from routes.enfermeiro.triagem import triagem_bp
from routes.enfermeiro.sinais_vitais import sinais_vitais_bp
from routes.enfermeiro.historico import historico_bp
from routes.enfermeiro.perfil import perfil_bp
from routes.enfermeiro.api import api_bp
from routes.enfermeiro.utils_compartilhados import set_mysql as set_utils_mysql

def init_enfermeiro(mysql_instance):
    """Inicializa o módulo do enfermeiro"""
    # Configurar utils compartilhados
    set_utils_mysql(mysql_instance)
    
    # Configurar cada blueprint com o mysql
    from routes.enfermeiro.dashboard import set_mysql as set_dashboard_mysql
    from routes.enfermeiro.triagem import set_mysql as set_triagem_mysql
    from routes.enfermeiro.sinais_vitais import set_mysql as set_sinais_mysql
    from routes.enfermeiro.historico import set_mysql as set_historico_mysql
    from routes.enfermeiro.perfil import set_mysql as set_perfil_mysql
    from routes.enfermeiro.api import set_mysql as set_api_mysql
    
    set_dashboard_mysql(mysql_instance)
    set_triagem_mysql(mysql_instance)
    set_sinais_mysql(mysql_instance)
    set_historico_mysql(mysql_instance)
    set_perfil_mysql(mysql_instance)
    set_api_mysql(mysql_instance)
    
    # Criar e retornar o blueprint principal
    enfermeiro_bp = Blueprint('enfermeiro', __name__, url_prefix='/enfermeiro')
    enfermeiro_bp.register_blueprint(dashboard_bp)
    enfermeiro_bp.register_blueprint(triagem_bp)
    enfermeiro_bp.register_blueprint(sinais_vitais_bp)
    enfermeiro_bp.register_blueprint(historico_bp)
    enfermeiro_bp.register_blueprint(perfil_bp)
    enfermeiro_bp.register_blueprint(api_bp)
    
    return enfermeiro_bp