# routes/medico/medico_api.py
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
                    paciente_nome = converter_bytes_para_string(p[1])
                    tipo_exame = converter_bytes_para_string(p[2])
                    status = converter_bytes_para_string(p[3])
                    data = p[4]
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
            
            # Consultas hoje
            hoje = datetime.now().strftime('%Y-%m-%d')
            consultas = execute_query("""
                SELECT COUNT(*) FROM consultas 
                WHERE medico_id = %s AND DATE(data_hora) = %s
            """, (medico_id, hoje), fetch=True, one=True)
            
            # Resultados pendentes
            resultados = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status = 'concluido' 
                AND status_aprovacao = 'pendente'
            """, (medico_id,), fetch=True, one=True)
            
            # Análises solicitadas (pendentes + em análise)
            analises = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status IN ('pendente', 'em_analise')
            """, (medico_id,), fetch=True, one=True)
            
            # Total de pedidos criados
            pedidos_criados = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s
            """, (medico_id,), fetch=True, one=True)
            
            consultas_hoje = consultas[0] if consultas else 0
            resultados_pendentes = resultados[0] if resultados else 0
            
            return jsonify({
                'consultas_hoje': consultas_hoje,
                'resultados_pendentes': resultados_pendentes,
                'analises_solicitadas': analises[0] if analises else 0,
                'pedidos_criados': pedidos_criados[0] if pedidos_criados else 0,
                'notificacoes': resultados_pendentes
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
                    paciente_nome = converter_bytes_para_string(p[3])
                    tipo_exame = converter_bytes_para_string(p[1])
                    
                    data = p[2]
                    if isinstance(data, datetime):
                        dias = (datetime.now() - data).days
                        data_ref = data
                    else:
                        dias = 0
                        data_ref = datetime.now()
                    
                    if dias == 0:
                        tempo = "Hoje"
                    elif dias == 1:
                        tempo = "Ontem"
                    else:
                        tempo = f"{dias} dias atrás"
                    
                    notificacoes.append({
                        'id': p[0],
                        'titulo': f"Resultado: {tipo_exame}",
                        'mensagem': f"Resultado de {paciente_nome} aguardando revisão",
                        'link': f"/medico/revisar-analise/{p[0]}",
                        'tempo': tempo
                    })
            
            return jsonify({'notificacoes': notificacoes})
            
        except Exception as e:
            logger.error(f"Erro em api_notificacoes: {e}")
            return jsonify({'error': str(e)}), 500
    
    return {
        'routes': [
            {'rule': '/api/pedidos-recentes', 'view_func': api_pedidos_recentes, 'methods': ['GET']},
            {'rule': '/api/contadores', 'view_func': api_contadores, 'methods': ['GET']},
            {'rule': '/api/notificacoes', 'view_func': api_notificacoes, 'methods': ['GET']}
        ]
    }

# Exportar a função
__all__ = ['init_medico_api']