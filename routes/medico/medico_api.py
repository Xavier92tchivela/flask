# routes/medico/medico_api.py - VERSÃO COMPLETA CORRIGIDA
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
        # Se já for string, retorna normal
        if isinstance(valor, str):
            return valor
        # Se for outro tipo, converte para string
        return str(valor) if valor else ''
    
    def converter_lista_para_json(dados):
        """Converte todos os campos bytes para string em uma lista de tuplas"""
        if not dados:
            return []
        
        resultados = []
        for item in dados:
            novo_item = []
            for valor in item:
                if isinstance(valor, bytes):
                    novo_item.append(converter_bytes_para_string(valor))
                elif isinstance(valor, datetime):
                    novo_item.append(valor.strftime('%Y-%m-%d %H:%M:%S'))
                else:
                    novo_item.append(valor)
            resultados.append(tuple(novo_item))
        
        return resultados
    
    # Função segura para extrair valor de resultado
    def extrair_valor(resultado, indice=0, padrao=0):
        """Extrai valor de forma segura de resultados de consulta"""
        if resultado is None:
            return padrao
        try:
            # Se for tupla ou lista
            if isinstance(resultado, (tuple, list)) and len(resultado) > indice:
                valor = resultado[indice]
                if isinstance(valor, bytes):
                    return int(valor.decode('utf-8', errors='ignore'))
                return int(valor) if valor is not None else padrao
            # Se for dicionário
            elif isinstance(resultado, dict):
                keys = list(resultado.keys())
                if len(keys) > indice:
                    valor = resultado[keys[indice]]
                else:
                    valor = resultado.get('COUNT(*)', resultado.get('total', padrao))
                if isinstance(valor, bytes):
                    return int(valor.decode('utf-8', errors='ignore'))
                return int(valor) if valor is not None else padrao
            return padrao
        except Exception as e:
            logger.warning(f"Erro ao extrair valor: {e}")
            return padrao
    
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
            
            # Converter bytes para string
            pedidos = converter_lista_para_json(pedidos_raw) if pedidos_raw else []
            
            pedidos_lista = []
            if pedidos:
                for p in pedidos:
                    # Garantir que todos os campos são strings
                    paciente_nome = converter_bytes_para_string(p[1]) if len(p) > 1 else 'Paciente'
                    tipo_exame = converter_bytes_para_string(p[2]) if len(p) > 2 else 'Exame'
                    status = converter_bytes_para_string(p[3]) if len(p) > 3 else 'pendente'
                    data = p[4] if len(p) > 4 else None
                    if isinstance(data, datetime):
                        data_str = data.strftime('%d/%m/%Y')
                    else:
                        data_str = str(data) if data else ''
                    
                    pedidos_lista.append({
                        'id': p[0],
                        'paciente_nome': paciente_nome,
                        'tipo_exame': tipo_exame,
                        'status': status,
                        'data_solicitacao': data_str,
                        'status_aprovacao': converter_bytes_para_string(p[5]) if len(p) > 5 else ''
                    })
            
            return jsonify({'pedidos': pedidos_lista})
            
        except Exception as e:
            logger.error(f"Erro em api_pedidos_recentes: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
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
                    'pedidos_criados': 0,
                    'notificacoes': 0
                })
            
            # Consultas hoje - COM TRATAMENTO DE ERRO
            hoje = datetime.now().strftime('%Y-%m-%d')
            consultas_result = execute_query("""
                SELECT COUNT(*) FROM consultas 
                WHERE medico_id = %s AND DATE(data_hora) = %s
            """, (medico_id, hoje), fetch=True, one=True)
            
            # Extrair valor com segurança
            consultas_hoje = extrair_valor(consultas_result, 0, 0)
            
            # Resultados pendentes
            resultados_result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status = 'concluido' 
                AND status_aprovacao = 'pendente'
            """, (medico_id,), fetch=True, one=True)
            
            resultados_pendentes = extrair_valor(resultados_result, 0, 0)
            
            # Análises solicitadas (pendentes + em análise)
            analises_result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status IN ('pendente', 'em_analise')
            """, (medico_id,), fetch=True, one=True)
            
            analises_solicitadas = extrair_valor(analises_result, 0, 0)
            
            # Total de pedidos criados
            pedidos_result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s
            """, (medico_id,), fetch=True, one=True)
            
            pedidos_criados = extrair_valor(pedidos_result, 0, 0)
            
            # Log para debug
            logger.info(f"API Contadores - Médico {medico_id}: Consultas={consultas_hoje}, Resultados={resultados_pendentes}, Análises={analises_solicitadas}, Total={pedidos_criados}")
            
            return jsonify({
                'consultas_hoje': consultas_hoje,
                'resultados_pendentes': resultados_pendentes,
                'analises_solicitadas': analises_solicitadas,
                'pedidos_criados': pedidos_criados,
                'notificacoes': resultados_pendentes
            })
            
        except Exception as e:
            logger.error(f"Erro em api_contadores: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Retornar valores padrão mesmo em caso de erro
            return jsonify({
                'consultas_hoje': 0,
                'resultados_pendentes': 0,
                'analises_solicitadas': 0,
                'pedidos_criados': 0,
                'notificacoes': 0,
                'error': str(e)
            }), 200  # Retorna 200 mesmo com erro para não quebrar o frontend
    
    # ========== API: NOTIFICAÇÕES - VERSÃO CORRIGIDA ==========
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
            
            # Converter bytes para string
            pedidos = converter_lista_para_json(pedidos_raw) if pedidos_raw else []
            
            notificacoes = []
            if pedidos:
                for p in pedidos:
                    # Garantir que todos os campos são strings
                    paciente_nome = converter_bytes_para_string(p[3]) if len(p) > 3 else 'Paciente'
                    tipo_exame = converter_bytes_para_string(p[1]) if len(p) > 1 else 'Exame'
                    
                    pedido_id = p[0]
                    
                    data = p[2] if len(p) > 2 else None
                    if data and isinstance(data, datetime):
                        dias = (datetime.now() - data).days
                    else:
                        dias = 0
                    
                    if dias == 0:
                        tempo = "Hoje"
                    elif dias == 1:
                        tempo = "Ontem"
                    else:
                        tempo = f"{dias} dias atrás"
                    
                    # CORREÇÃO: Link usando a rota correta
                    notificacoes.append({
                        'id': pedido_id,
                        'titulo': f"Resultado: {tipo_exame}",
                        'mensagem': f"Resultado de {paciente_nome} aguardando revisão",
                        'link': f"/medico/revisar-analise/{pedido_id}",  # <- CORRIGIDO!
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
