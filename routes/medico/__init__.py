# routes/medico/__init__.py
from flask import Blueprint
import logging
import traceback
from .base import init_medico_base
from .medico_dashboard import init_medico_dashboard
from .medico_pedidos import init_medico_pedidos
from .medico_perfil import init_medico_perfil
from .medico_consultas import init_medico_consultas
from .medico_pacientes import init_medico_pacientes
from .medico_api import init_medico_api
from .medico_debug import init_medico_debug
from .medico_receitas import init_medico_receitas
from .consulta import create_consulta_blueprint  # 👈 IMPORTANTE

# Configurar logger
logger = logging.getLogger(__name__)

def init_medico(mysql, client, gemini_available, MODEL_NAME, app, receita_service=None):
    """
    Inicializa e retorna o blueprint completo do médico
    """
    try:
        print("\n" + "="*50)
        print("INICIALIZANDO BLUEPRINT MÉDICO")
        print("="*50)
        
        medico_bp = Blueprint('medico', __name__, url_prefix='/medico')
        
        # Inicializar funções base
        base = init_medico_base(mysql)
        
        # Lista de módulos a serem registrados
        modules = [
            init_medico_dashboard(base),
            init_medico_pedidos(base, gemini_available),
            init_medico_perfil(base),
            init_medico_consultas(base),
            init_medico_pacientes(mysql, base),
            init_medico_api(mysql, base),
            init_medico_debug(base),
        ]
        
        # Inicializar módulo de receitas se o serviço foi fornecido
        if receita_service:
            logger.info("=" * 50)
            logger.info("INICIALIZANDO MÓDULO DE RECEITAS")
            logger.info("=" * 50)
            logger.info(f"Gemini disponível: {gemini_available}")
            
            try:
                receitas_module = init_medico_receitas(mysql, base, receita_service, gemini_available)
                modules.append(receitas_module)
                logger.info(f"Módulo de receitas inicializado com sucesso! Rotas: {len(receitas_module['routes'])}")
            except Exception as e:
                logger.error(f"Erro ao inicializar módulo de receitas: {e}")
                logger.error(traceback.format_exc())
        else:
            logger.warning("Serviço de receitas não fornecido. Módulo de receitas não será inicializado.")
        
        # Registrar todas as rotas dos módulos principais
        total_rotas = 0
        for idx, module in enumerate(modules):
            logger.info(f"Registrando rotas do módulo {idx+1}/{len(modules)} - {len(module['routes'])} rotas")
            
            for route in module['routes']:
                medico_bp.add_url_rule(**route)
                total_rotas += 1
                logger.debug(f"  Rota registrada: {route.get('rule')}")
        
        logger.info(f"Total de {total_rotas} rotas registradas no blueprint médico (módulos principais)")
        
        # 👈 REGISTRAR O BLUEPRINT DE CONSULTAS DETALHADAS
        try:
            consulta_detalhes_bp = create_consulta_blueprint(mysql)
            medico_bp.register_blueprint(consulta_detalhes_bp)
            logger.info("✅ Blueprint de consultas detalhadas registrado em /medico/consulta")
        except Exception as e:
            logger.error(f"❌ Erro ao registrar blueprint de consultas detalhadas: {e}")
            logger.error(traceback.format_exc())
        
        # Exportar funções para outros blueprints
        medico_bp.obter_info_medico = base['obter_info_medico']
        medico_bp.execute_query = base['execute_query']
        medico_bp.formatar_data = base['formatar_data']
        medico_bp.calcular_idade = base['calcular_idade']
        
        logger.info("✅ Blueprint médico inicializado com sucesso!")
        print("="*50)
        
        return medico_bp
        
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar blueprint médico: {e}")
        logger.error(traceback.format_exc())
        raise

# Exportar a função principal
__all__ = ['init_medico']