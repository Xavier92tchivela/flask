# routes/medico/medico_debug.py
"""
Módulo de debug para o médico
"""

from flask import jsonify, session
import logging

logger = logging.getLogger(__name__)

def init_medico_debug(base):  # 👈 NOME CORRETO
    """Inicializa rotas de debug do médico"""
    
    medico_required = base['medico_required']
    obter_info_medico = base['obter_info_medico']
    execute_query = base['execute_query']
    
    # ========== ROTA: DEBUG SESSÃO ==========
    @medico_required
    def debug_sessao():
        """Retorna informações da sessão atual"""
        try:
            medico_info = obter_info_medico()
            
            return jsonify({
                'sessao': {
                    'user_id': session.get('user_id'),
                    'user_type': session.get('user_type'),
                    'user_name': session.get('user_name')
                },
                'medico_info': medico_info,
                'status': 'ok'
            })
        except Exception as e:
            logger.error(f"Erro no debug_sessao: {e}")
            return jsonify({'error': str(e)}), 500
    
    # ========== ROTA: DEBUG BANCO ==========
    @medico_required
    def debug_banco():
        """Testa conexão com o banco de dados"""
        try:
            # Testar conexão
            resultado = execute_query("SELECT 1 as teste", fetch=True, one=True)
            
            # Contar registros
            total_medicos = execute_query("SELECT COUNT(*) FROM medicos", fetch=True, one=True)
            total_pacientes = execute_query("SELECT COUNT(*) FROM pacientes", fetch=True, one=True)
            total_consultas = execute_query("SELECT COUNT(*) FROM consultas", fetch=True, one=True)
            total_pedidos = execute_query("SELECT COUNT(*) FROM pedidos_analise", fetch=True, one=True)
            
            return jsonify({
                'conexao': 'ok' if resultado else 'falha',
                'teste': resultado[0] if resultado else None,
                'contagens': {
                    'medicos': total_medicos[0] if total_medicos else 0,
                    'pacientes': total_pacientes[0] if total_pacientes else 0,
                    'consultas': total_consultas[0] if total_consultas else 0,
                    'pedidos': total_pedidos[0] if total_pedidos else 0
                }
            })
        except Exception as e:
            logger.error(f"Erro no debug_banco: {e}")
            return jsonify({'error': str(e)}), 500
    
    # ========== ROTA: DEBUG INFO ==========
    @medico_required
    def debug_info():
        """Retorna informações do sistema"""
        try:
            medico_info = obter_info_medico()
            
            return jsonify({
                'medico': {
                    'id': medico_info.get('id'),
                    'nome': medico_info.get('nome'),
                    'email': medico_info.get('email'),
                    'especialidade': medico_info.get('especialidade'),
                    'crm': medico_info.get('crm')
                },
                'sistema': {
                    'python': 'ok',
                    'flask': 'ok',
                    'database': 'conectado'
                }
            })
        except Exception as e:
            logger.error(f"Erro no debug_info: {e}")
            return jsonify({'error': str(e)}), 500
    
    return {
        'routes': [
            {'rule': '/debug/sessao', 'view_func': debug_sessao, 'methods': ['GET']},
            {'rule': '/debug/banco', 'view_func': debug_banco, 'methods': ['GET']},
            {'rule': '/debug/info', 'view_func': debug_info, 'methods': ['GET']}
        ]
    }

# 👈 EXPORTAR A FUNÇÃO COM O NOME CORRETO
__all__ = ['init_medico_debug']