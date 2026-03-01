# routes/medico/medico_api.py
from flask import jsonify
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def init_medico_api(mysql, base):  # 👈 RENOMEADO DE init_api PARA init_medico_api
    """Inicializa rotas de API do médico"""
    
    execute_query = base['execute_query']
    formatar_data = base['formatar_data']
    obter_info_medico = base['obter_info_medico']
    medico_required = base['medico_required']
    
    # ========== API: PEDIDOS RECENTES ==========
    @medico_required
    def api_pedidos_recentes():
        try:
            medico_info = obter_info_medico()
            if not medico_info:
                return jsonify({'error': 'Médico não encontrado'}), 401
            
            medico_id = medico_info.get('id')
            if not medico_id or medico_id < 0:
                return jsonify({'pedidos': []})
            
            pedidos = execute_query("""
                SELECT pa.id, pa.tipo_exame, pa.status, pa.data_solicitacao,
                       pa.status_aprovacao, COALESCE(p_u.nome, 'Não informado') as paciente_nome
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios p_u ON p.usuario_id = p_u.id
                WHERE pa.medico_id = %s
                ORDER BY pa.data_solicitacao DESC LIMIT 5
            """, (medico_id,), fetch=True)
            
            pedidos_lista = []
            if pedidos:
                for p in pedidos:
                    pedidos_lista.append({
                        'id': p[0], 
                        'tipo_exame': p[1], 
                        'status': p[2],
                        'data_solicitacao': formatar_data(p[3], '%d/%m/%Y'),
                        'status_aprovacao': p[4], 
                        'paciente_nome': p[5]
                    })
            
            return jsonify({'pedidos': pedidos_lista})
            
        except Exception as e:
            logger.error(f"Erro em api_pedidos_recentes: {e}")
            return jsonify({'error': str(e)}), 500
    
    # ========== API: CONTADORES ==========
    @medico_required
    def api_contadores():
        try:
            medico_info = obter_info_medico()
            if not medico_info:
                return jsonify({'error': 'Médico não encontrado'}), 401
            
            medico_id = medico_info.get('id')
            if not medico_id or medico_id < 0:
                return jsonify({
                    'resultados_pendentes': 0, 
                    'analises_solicitadas': 0,
                    'notificacoes': 0, 
                    'consultas_hoje': 0
                })
            
            resultados = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status = 'concluido' 
                AND status_aprovacao = 'pendente'
            """, (medico_id,), fetch=True, one=True)
            
            analises = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status IN ('pendente', 'em_analise')
            """, (medico_id,), fetch=True, one=True)
            
            hoje = datetime.now().strftime('%Y-%m-%d')
            consultas = execute_query("""
                SELECT COUNT(*) FROM consultas 
                WHERE medico_id = %s AND DATE(data_hora) = %s
            """, (medico_id, hoje), fetch=True, one=True)
            
            resultados_pendentes = resultados[0] if resultados else 0
            
            return jsonify({
                'resultados_pendentes': resultados_pendentes,
                'analises_solicitadas': analises[0] if analises else 0,
                'notificacoes': resultados_pendentes,
                'consultas_hoje': consultas[0] if consultas else 0
            })
            
        except Exception as e:
            logger.error(f"Erro em api_contadores: {e}")
            return jsonify({'error': str(e)}), 500
    
    # ========== API: NOTIFICAÇÕES ==========
    @medico_required
    def api_notificacoes():
        try:
            medico_info = obter_info_medico()
            if not medico_info:
                return jsonify({'error': 'Médico não encontrado'}), 401
            
            medico_id = medico_info.get('id')
            if not medico_id or medico_id < 0:
                return jsonify({'notificacoes': []})
            
            pedidos = execute_query("""
                SELECT pa.id, pa.tipo_exame, pa.data_solicitacao,
                       COALESCE(p_u.nome, 'Paciente') as paciente_nome
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios p_u ON p.usuario_id = p_u.id
                WHERE pa.medico_id = %s 
                AND pa.status = 'concluido' AND pa.status_aprovacao = 'pendente'
                ORDER BY pa.data_conclusao DESC LIMIT 5
            """, (medico_id,), fetch=True)
            
            notificacoes = []
            if pedidos:
                for p in pedidos:
                    data = p[2] if isinstance(p[2], datetime) else datetime.now()
                    dias = (datetime.now() - data).days
                    
                    if dias == 0:
                        tempo = "Hoje"
                    elif dias == 1:
                        tempo = "Ontem"
                    else:
                        tempo = f"{dias} dias atrás"
                    
                    notificacoes.append({
                        'id': p[0], 
                        'titulo': f"Resultado: {p[1]}",
                        'mensagem': f"Resultado de {p[3]} aguardando revisão",
                        'link': f"/medico/revisar-analise/{p[0]}",
                        'tempo': tempo
                    })
            
            return jsonify({'notificacoes': notificacoes})
            
        except Exception as e:
            logger.error(f"Erro em api_notificacoes: {e}")
            return jsonify({'error': str(e)}), 500
    
    # ========== API: DIAGNÓSTICO SISTEMA ==========
    @medico_required
    def api_diagnostico_sistema():
        try:
            medico_info = obter_info_medico()
            if not medico_info:
                return jsonify({'error': 'Médico não encontrado'}), 401
            
            total_pedidos = execute_query("SELECT COUNT(*) FROM pedidos_analise", fetch=True, one=True)
            
            total_medico = 0
            if medico_info.get('id') and medico_info['id'] > 0:
                total_medico = execute_query(
                    "SELECT COUNT(*) FROM pedidos_analise WHERE medico_id = %s",
                    (medico_info['id'],), fetch=True, one=True
                )
            
            nao_atribuidos = execute_query(
                "SELECT COUNT(*) FROM pedidos_analise WHERE analista_id IS NULL",
                fetch=True, one=True
            )
            
            return jsonify({
                'medico': {
                    'id': medico_info.get('id'),
                    'nome': medico_info.get('nome'),
                    'especialidade': medico_info.get('especialidade')
                },
                'pedidos': {
                    'total_sistema': total_pedidos[0] if total_pedidos else 0,
                    'total_medico': total_medico[0] if total_medico else 0,
                    'nao_atribuidos': nao_atribuidos[0] if nao_atribuidos else 0
                }
            })
            
        except Exception as e:
            logger.error(f"Erro em api_diagnostico_sistema: {e}")
            return jsonify({'error': str(e)}), 500
    
    return {
        'routes': [
            {'rule': '/api/pedidos-recentes', 'view_func': api_pedidos_recentes, 'methods': ['GET']},
            {'rule': '/api/contadores', 'view_func': api_contadores, 'methods': ['GET']},
            {'rule': '/api/notificacoes', 'view_func': api_notificacoes, 'methods': ['GET']},
            {'rule': '/api/diagnostico-sistema', 'view_func': api_diagnostico_sistema, 'methods': ['GET']}
        ]
    }

# 👈 EXPORTAR A FUNÇÃO COM O NOME CORRETO
__all__ = ['init_medico_api']