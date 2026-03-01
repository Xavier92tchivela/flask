# routes/analista/blueprint.py
from flask import Blueprint
import logging

logger = logging.getLogger(__name__)

def init_analista(mysql, client, gemini_available, MODEL_NAME, app):
    """Inicializa e configura o blueprint do analista"""
    
    print("\n" + "=" * 50)
    print("INICIALIZANDO BLUEPRINT DO ANALISTA")
    print("=" * 50)
    
    from .decorators import analista_required
    from .database import set_mysql, execute_query
    from .helpers import formatar_data, calcular_idade
    from .gemini_service import set_gemini_config, analisar_imagem_com_gemini, salvar_imagem_temporaria, preparar_contexto_clinico
    from .notifications import set_notification_deps, criar_notificacao_medico, salvar_diagnostico_ia
    from .file_utils import set_app_config
    
    # Configurar dependências
    set_mysql(mysql)
    set_gemini_config(gemini_available, MODEL_NAME, app)
    set_notification_deps(execute_query, logger)
    set_app_config(app)
    
    print("Dependências configuradas")
    
    # Importar rotas
    from .routes.dashboard import register_dashboard_routes
    from .routes.pedidos import register_pedidos_routes
    from .routes.analise import register_analise_routes
    from .routes.historico import register_historico_routes
    from .routes.perfil import register_perfil_routes
    
    # Criar blueprint
    analista_bp = Blueprint('analista', __name__, url_prefix='/analista')
    print("Blueprint criado")
    
    # Registrar rotas
    print("\nRegistrando rotas:")
    
    register_dashboard_routes(analista_bp, analista_required, execute_query, formatar_data)
    print("  - Dashboard routes registradas")
    
    register_pedidos_routes(analista_bp, analista_required, execute_query, formatar_data, calcular_idade)
    print("  - Pedidos routes registradas")
    
    register_analise_routes(analista_bp, analista_required, execute_query, formatar_data, calcular_idade,
                           analisar_imagem_com_gemini, salvar_imagem_temporaria, preparar_contexto_clinico,
                           criar_notificacao_medico, salvar_diagnostico_ia, gemini_available, MODEL_NAME)
    print("  - Analise routes registradas")
    
    register_historico_routes(analista_bp, analista_required, execute_query, formatar_data)
    print("  - Historico routes registradas")
    
    register_perfil_routes(analista_bp, analista_required, execute_query, formatar_data)
    print("  - Perfil routes registradas")
    
    print("\n" + "=" * 50)
    print("BLUEPRINT DO ANALISTA INICIALIZADO COM SUCESSO!")
    print("=" * 50 + "\n")
    
    return analista_bp