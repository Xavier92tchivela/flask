# routes/enfermeiro/__init__.py
from flask import Blueprint
from . import dashboard, triagem, sinais_vitais, historico, perfil, api, agendamento, internados, medicamentos

def set_mysql(mysql_instance):
    """Configura a conexão MySQL em todos os submódulos"""
    if hasattr(dashboard, 'set_mysql'):
        dashboard.set_mysql(mysql_instance)
    if hasattr(triagem, 'set_mysql'):
        triagem.set_mysql(mysql_instance)
    if hasattr(sinais_vitais, 'set_mysql'):
        sinais_vitais.set_mysql(mysql_instance)
    if hasattr(historico, 'set_mysql'):
        historico.set_mysql(mysql_instance)
    if hasattr(perfil, 'set_mysql'):
        perfil.set_mysql(mysql_instance)
    if hasattr(api, 'set_mysql'):
        api.set_mysql(mysql_instance)
    if hasattr(agendamento, 'set_mysql'):
        agendamento.set_mysql(mysql_instance)
    if hasattr(internados, 'set_mysql'):
        internados.set_mysql(mysql_instance)
    if hasattr(medicamentos, 'set_mysql'):
        medicamentos.set_mysql(mysql_instance)

def init_enfermeiro(mysql_instance):
    """Inicializa o blueprint do enfermeiro com todos os submódulos"""
    set_mysql(mysql_instance)
    
    # Cria o blueprint principal
    bp = Blueprint('enfermeiro', __name__, url_prefix='/enfermeiro')
    
    # Registra os blueprints de cada submódulo
    bp.register_blueprint(dashboard.dashboard_bp)
    bp.register_blueprint(triagem.triagem_bp)
    bp.register_blueprint(sinais_vitais.sinais_vitais_bp)
    bp.register_blueprint(historico.historico_bp)
    bp.register_blueprint(perfil.perfil_bp)
    bp.register_blueprint(api.api_bp)
    bp.register_blueprint(agendamento.agendamento_bp)
    bp.register_blueprint(internados.internados_bp)
    bp.register_blueprint(medicamentos.medicamentos_bp)
    
    return bp