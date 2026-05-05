# routes/medico/medico_api.py - VERSÃO COMPLETAMENTE CORRIGIDA
from flask import jsonify
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def init_medico_api(mysql, base):
    """Inicializa rotas de API do médico"""
    
    execute_query = base['execute_query']
    formatar_data = base['formatar_data']
    obter_info_medico = base['obter_info_medico']
    medico_required = base['medico_required']
    
    # ===== FUNÇÃO AUXILIAR PARA CONVERTER BYTES =====
    def converter_bytes_para_string(valor):
        """Converte bytes para string se necessário"""
        if valor is None:
            return ''
        if isinstance(valor, bytes):
            try:
                return valor.decode('utf-8', errors='ignore')
            except:
                return str(valor)
        if isinstance(valor, str):
            return valor
        if isinstance(valor, datetime):
            return valor.strftime('%d/%m/%Y %H:%M')
        return str(valor) if valor else ''
    
    # Função segura para extrair valor de resultado
    def extrair_valor(resultado, indice=0, padrao=0):
        """Extrai valor de forma segura de resultados de consulta"""
        if resultado is None:
            return padrao
        try:
            if isinstance(resultado, (tuple, list)) and len(resultado) > indice:
                valor = resultado[indice]
                if isinstance(valor, bytes):
                    return int(valor.decode('utf-8', errors='ignore'))
                return int(valor) if valor is not None else padrao
            elif isinstance(resultado, dict):
                # Pegar o primeiro valor do dicionário
                valores = list(resultado.values())
                if len(valores) > indice:
                    valor = valores[indice]
                    if isinstance(valor, bytes):
                        return int(valor.decode('utf-8', errors='ignore'))
                    return int(valor) if valor is not None else padrao
            return padrao
        except Exception as e:
            logger.warning(f"Erro ao extrair valor: {e}")
            return padrao
    
    # ========== API: PEDIDOS RECENTES - CORRIGIDA ==========
    @medico_required
    def api_pedidos_recentes():
        try:
            medico_info = obter_info_medico()
            if not medico_info:
                return jsonify({'error': 'Médico não encontrado'}), 401
            
            medico_id = medico_info.get('id')
            if not medico_id:
                return jsonify({'pedidos': []})
            
            # Buscar pedidos
            pedidos_raw = execute_query("""
                SELECT 
                    pa.id, 
                    COALESCE(p_u.nome, 'Paciente') as paciente_nome,
                    pa.tipo_exame, 
                    pa.status, 
                    pa.data_solicitacao,
                    pa.status_aprovacao
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios p_u ON p.usuario_id = p_u.id
                WHERE pa.medico_id = %s
                ORDER BY pa.data_solicitacao DESC LIMIT 5
            """, (medico_id,), fetch=True)
            
            pedidos_lista = []
            if pedidos_raw:
                for p in pedidos_raw:
                    # Se for dicionário (execute_query com dict)
                    if isinstance(p, dict):
                        pedido_id = p.get('id', 0)
                        paciente_nome = converter_bytes_para_string(p.get('paciente_nome', 'Paciente'))
                        tipo_exame = converter_bytes_para_string(p.get('tipo_exame', 'Exame'))
                        status = converter_bytes_para_string(p.get('status', 'pendente'))
                        data_solicitacao = p.get('data_solicitacao', '')
                        if isinstance(data_solicitacao, datetime):
                            data_str = data_solicitacao.strftime('%d/%m/%Y')
                        else:
                            data_str = converter_bytes_para_string(data_solicitacao)
                        
                        pedidos_lista.append({
                            'id': pedido_id,
                            'paciente_nome': paciente_nome,
                            'tipo_exame': tipo_exame,
                            'status': status,
                            'data_solicitacao': data_str,
                            'status_aprovacao': converter_bytes_para_string(p.get('status_aprovacao', ''))
                        })
                    # Se for tupla/lista
                    elif isinstance(p, (tuple, list)) and len(p) >= 5:
                        pedidos_lista.append({
                            'id': p[0],
                            'paciente_nome': converter_bytes_para_string(p[1]),
                            'tipo_exame': converter_bytes_para_string(p[2]),
                            'status': converter_bytes_para_string(p[3]),
                            'data_solicitacao': converter_bytes_para_string(p[4]),
                            'status_aprovacao': converter_bytes_para_string(p[5]) if len(p) > 5 else ''
                        })
            
            return jsonify({'pedidos': pedidos_lista})
            
        except Exception as e:
            logger.error(f"Erro em api_pedidos_recentes: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'pedidos': []}), 200
    
    # ========== API: CONTADORES ==========
    @medico_required
    def api_contadores():
        try:
            medico_info = obter_info_medico()
            if not medico_info:
                return jsonify({'error': 'Médico não encontrado'}), 401
            
            medico_id = medico_info.get('id')
            if not medico_id:
                return jsonify({
                    'consultas_hoje': 0,
                    'resultados_pendentes': 0,
                    'analises_solicitadas': 0,
                    'pacientes_internados': 0,
                    'leitos_ocupados': 0
                })
            
            # Consultas hoje
            hoje = datetime.now().strftime('%Y-%m-%d')
            consultas_result = execute_query("""
                SELECT COUNT(*) as total FROM consultas 
                WHERE medico_id = %s AND DATE(data_hora) = %s
            """, (medico_id, hoje), fetch=True, one=True)
            
            consultas_hoje = 0
            if consultas_result:
                if isinstance(consultas_result, dict):
                    consultas_hoje = consultas_result.get('total', 0)
                elif isinstance(consultas_result, (tuple, list)):
                    consultas_hoje = consultas_result[0] if consultas_result[0] else 0
                else:
                    consultas_hoje = consultas_result if isinstance(consultas_result, (int, float)) else 0
            
            # Resultados pendentes
            resultados_result = execute_query("""
                SELECT COUNT(*) as total FROM pedidos_analise 
                WHERE medico_id = %s AND status = 'concluido' 
                AND status_aprovacao = 'pendente'
            """, (medico_id,), fetch=True, one=True)
            
            resultados_pendentes = 0
            if resultados_result:
                if isinstance(resultados_result, dict):
                    resultados_pendentes = resultados_result.get('total', 0)
                elif isinstance(resultados_result, (tuple, list)):
                    resultados_pendentes = resultados_result[0] if resultados_result[0] else 0
                else:
                    resultados_pendentes = resultados_result if isinstance(resultados_result, (int, float)) else 0
            
            # Análises solicitadas
            analises_result = execute_query("""
                SELECT COUNT(*) as total FROM pedidos_analise 
                WHERE medico_id = %s AND status IN ('pendente', 'em_analise')
            """, (medico_id,), fetch=True, one=True)
            
            analises_solicitadas = 0
            if analises_result:
                if isinstance(analises_result, dict):
                    analises_solicitadas = analises_result.get('total', 0)
                elif isinstance(analises_result, (tuple, list)):
                    analises_solicitadas = analises_result[0] if analises_result[0] else 0
                else:
                    analises_solicitadas = analises_result if isinstance(analises_result, (int, float)) else 0
            
            # Pacientes internados
            internados_result = execute_query("""
                SELECT COUNT(*) as total FROM internacoes_pacientes 
                WHERE status = 'ativa'
            """, fetch=True, one=True)
            
            pacientes_internados = 0
            if internados_result:
                if isinstance(internados_result, dict):
                    pacientes_internados = internados_result.get('total', 0)
                elif isinstance(internados_result, (tuple, list)):
                    pacientes_internados = internados_result[0] if internados_result[0] else 0
                else:
                    pacientes_internados = internados_result if isinstance(internados_result, (int, float)) else 0
            
            return jsonify({
                'consultas_hoje': consultas_hoje,
                'resultados_pendentes': resultados_pendentes,
                'analises_solicitadas': analises_solicitadas,
                'pacientes_internados': pacientes_internados,
                'leitos_ocupados': pacientes_internados,
                'notificacoes': resultados_pendentes
            })
            
        except Exception as e:
            logger.error(f"Erro em api_contadores: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({
                'consultas_hoje': 0,
                'resultados_pendentes': 0,
                'analises_solicitadas': 0,
                'pacientes_internados': 0,
                'leitos_ocupados': 0,
                'notificacoes': 0
            }), 200
    
    # ========== API: NOTIFICAÇÕES - CORRIGIDA ==========
    @medico_required
    def api_notificacoes():
        try:
            medico_info = obter_info_medico()
            if not medico_info:
                return jsonify({'error': 'Médico não encontrado'}), 401
            
            medico_id = medico_info.get('id')
            if not medico_id:
                return jsonify({'notificacoes': []})
            
            pedidos_raw = execute_query("""
                SELECT 
                    pa.id, 
                    pa.tipo_exame, 
                    pa.data_conclusao,
                    COALESCE(p_u.nome, 'Paciente') as paciente_nome
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios p_u ON p.usuario_id = p_u.id
                WHERE pa.medico_id = %s 
                AND pa.status = 'concluido' 
                AND pa.status_aprovacao = 'pendente'
                ORDER BY pa.data_conclusao DESC LIMIT 5
            """, (medico_id,), fetch=True)
            
            notificacoes = []
            if pedidos_raw:
                for p in pedidos_raw:
                    # Extrair dados com segurança
                    if isinstance(p, dict):
                        pedido_id = p.get('id', 0)
                        tipo_exame = converter_bytes_para_string(p.get('tipo_exame', 'Exame'))
                        paciente_nome = converter_bytes_para_string(p.get('paciente_nome', 'Paciente'))
                        data_conclusao = p.get('data_conclusao')
                    else:
                        pedido_id = p[0] if len(p) > 0 else 0
                        tipo_exame = converter_bytes_para_string(p[1]) if len(p) > 1 else 'Exame'
                        paciente_nome = converter_bytes_para_string(p[3]) if len(p) > 3 else 'Paciente'
                        data_conclusao = p[2] if len(p) > 2 else None
                    
                    # Calcular tempo
                    if data_conclusao and isinstance(data_conclusao, datetime):
                        dias = (datetime.now() - data_conclusao).days
                    else:
                        dias = 0
                    
                    if dias == 0:
                        tempo = "Hoje"
                    elif dias == 1:
                        tempo = "Ontem"
                    else:
                        tempo = f"{dias} dias atrás"
                    
                    notificacoes.append({
                        'id': pedido_id,
                        'titulo': f"Resultado: {tipo_exame}",
                        'mensagem': f"Resultado de {paciente_nome} aguardando revisão",
                        'link': f"/medico/revisar-analise/{pedido_id}",
                        'tempo': tempo
                    })
            
            return jsonify({'notificacoes': notificacoes})
            
        except Exception as e:
            logger.error(f"Erro em api_notificacoes: {e}")
            return jsonify({'notificacoes': []}), 200
    
    return {
        'routes': [
            {'rule': '/api/pedidos-recentes', 'view_func': api_pedidos_recentes, 'methods': ['GET']},
            {'rule': '/api/contadores', 'view_func': api_contadores, 'methods': ['GET']},
            {'rule': '/api/notificacoes', 'view_func': api_notificacoes, 'methods': ['GET']}
        ]
    }

# Exportar a função
__all__ = ['init_medico_api']
