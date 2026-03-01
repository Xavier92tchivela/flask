# routes/medico/consulta/__init__.py
from flask import Blueprint
from .medico_routes import register_medico_routes
from .consultas_detalhes import register_detalhes_routes
from .consultas_acoes import register_acoes_routes
from .consultas_agendamento import register_agendamento_routes
from .consultas_editar import register_editar_routes
from .consultas_api import register_api_routes

def create_consulta_blueprint(mysql):
    """
    Cria e configura o blueprint de consultas para médicos
    
    Este blueprint gerencia todas as rotas relacionadas a consultas:
    - Listagem de consultas do médico
    - Detalhes de uma consulta específica
    - Ações (confirmar, cancelar, realizar)
    - Agendamento de consultas
    - Edição de consultas
    - APIs para calendário e disponibilidade
    
    Args:
        mysql: Conexão com MySQL
        
    Returns:
        Blueprint configurado com todas as rotas de consulta
    """
    
    consulta_bp = Blueprint('consulta', __name__, 
                           url_prefix='/consulta')
    
    # Registrar todas as rotas dos submódulos
    register_medico_routes(consulta_bp, mysql)    # Rotas para listagem de consultas do médico
    register_detalhes_routes(consulta_bp, mysql)  # Rotas para detalhes da consulta
    register_acoes_routes(consulta_bp, mysql)     # Rotas para ações (confirmar, cancelar, realizar)
    register_agendamento_routes(consulta_bp, mysql) # Rotas para agendamento
    register_editar_routes(consulta_bp, mysql)    # Rotas para edição
    register_api_routes(consulta_bp, mysql)       # Rotas de API
    
    print(f"[OK] Blueprint de consultas registrado com {len(consulta_bp.deferred_functions)} rotas")
    
    return consulta_bp


# Exportar a função principal
__all__ = ['create_consulta_blueprint']