# routes/admin.py
from flask import Blueprint
from .admin.auth import init_auth_routes
from .admin.dashboard import init_dashboard_routes
from .admin.medicos import init_medicos_routes
from .admin.analistas import init_analistas_routes
from .admin.pacientes import init_pacientes_routes
from .admin.consultas import init_consultas_routes
from .admin.estatisticas import init_estatisticas_routes
from .admin.configuracoes import init_configuracoes_routes

def init_admin(mysql):
    """Inicializa todas as rotas do admin"""
    admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
    
    # Inicializar cada grupo de rotas
    init_auth_routes(admin_bp, mysql)
    init_dashboard_routes(admin_bp, mysql)
    init_medicos_routes(admin_bp, mysql)
    init_analistas_routes(admin_bp, mysql)
    init_pacientes_routes(admin_bp, mysql)
    init_consultas_routes(admin_bp, mysql)
    init_estatisticas_routes(admin_bp, mysql)
    init_configuracoes_routes(admin_bp, mysql)
    
    return admin_bp