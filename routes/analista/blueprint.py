# routes/analista/blueprint.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import logging
from datetime import datetime
import traceback

logger = logging.getLogger(__name__)

# FUNÇÃO AUXILIAR REMOVIDA - NÃO CRIAR NOVAS CONEXÕES!

def init_analista(mysql, client, gemini_available, MODEL_NAME, app):
    """Inicializa e configura o blueprint do analista"""
    
    print("\n" + "=" * 50)
    print("INICIALIZANDO BLUEPRINT DO ANALISTA")
    print("=" * 50)
    
    # Importações dentro da função para evitar importação circular
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
    
    # Importar rotas (dentro da função também)
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
    
    # As rotas de análise já incluem todas as funções necessárias
    register_analise_routes(analista_bp, analista_required, execute_query, formatar_data, calcular_idade,
                           analisar_imagem_com_gemini, salvar_imagem_temporaria, preparar_contexto_clinico,
                           criar_notificacao_medico, salvar_diagnostico_ia, gemini_available, MODEL_NAME)
    print("  - Analise routes registradas (inclui análise IA e manual)")
    
    register_historico_routes(analista_bp, analista_required, execute_query, formatar_data)
    print("  - Historico routes registradas")
    
    register_perfil_routes(analista_bp, analista_required, execute_query, formatar_data)
    print("  - Perfil routes registradas")
    
    # ============ REMOVIDO: Rotas duplicadas de análise manual ============
    # As funções analise_manual e salvar_analise_manual agora estão no arquivo analise.py
    # Para não duplicar, removemos esta seção
    
    print("\n" + "=" * 50)
    print("BLUEPRINT DO ANALISTA INICIALIZADO COM SUCESSO!")
    print("=" * 50 + "\n")
    
    return analista_bp
