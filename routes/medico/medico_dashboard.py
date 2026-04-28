# routes/medico/medico_dashboard.py (VERSÃO COMPLETAMENTE CORRIGIDA)
from datetime import datetime, timedelta
from flask import render_template, session, jsonify
import logging
import traceback

logger = logging.getLogger(__name__)

# Flag global para evitar registro duplicado
_DASHBOARD_REGISTERED = False

def init_medico_dashboard(base):
    """
    Inicializa rotas do dashboard do médico (com proteção contra duplicação)
    """
    global _DASHBOARD_REGISTERED
    
    medico_required = base.get('medico_required')
    obter_info_medico = base.get('obter_info_medico')
    execute_query = base.get('execute_query')
    formatar_data = base.get('formatar_data')
    
    if not medico_required or not obter_info_medico:
        logger.error("Funções base não encontradas para medico_dashboard")
        return {'routes': []}
    
    def converter_bytes_para_string(valor):
        if valor is None:
            return ''
        if isinstance(valor, bytes):
            try:
                return valor.decode('utf-8', errors='ignore')
            except:
                return str(valor)
        return str(valor) if valor else ''
    
    def extrair_valor_consulta(consulta, indice, padrao=''):
        """
        Extrai valor de forma segura de um resultado de consulta
        Suporta tanto dicionário quanto tupla/lista
        """
        if consulta is None:
            return padrao
        
        # Se for dicionário
        if isinstance(consulta, dict):
            # Mapear índices para chaves
            chaves_map = {
                0: 'id',
                1: 'paciente_nome',
                2: 'data_hora',
                3: 'status'
            }
            chave = chaves_map.get(indice)
            if chave:
                return consulta.get(chave, padrao)
            return padrao
        
        # Se for tupla/lista
        if isinstance(consulta, (tuple, list)):
            if len(consulta) > indice:
                return consulta[indice]
            return padrao
        
        return padrao
    
    def converter_consulta_para_dict(consulta):
        """
        Converte resultado de consulta (dict ou tuple) para dicionário padronizado
        """
        if not consulta:
            return None
        
        # Se já for dicionário
        if isinstance(consulta, dict):
            return {
                'id': consulta.get('id'),
                'paciente_nome': converter_bytes_para_string(consulta.get('paciente_nome', '')),
                'data_hora': consulta.get('data_hora'),
                'status': consulta.get('status', 'desconhecido')
            }
        
        # Se for tupla/lista
        if isinstance(consulta, (tuple, list)):
            num_fields = len(consulta)
            return {
                'id': consulta[0] if num_fields > 0 else None,
                'paciente_nome': converter_bytes_para_string(consulta[1]) if num_fields > 1 else '',
                'data_hora': consulta[2] if num_fields > 2 else None,
                'status': consulta[3] if num_fields > 3 else 'desconhecido'
            }
        
        return None
    
    def extrair_contador(resultado):
        """
        Extrai valor de contador de forma segura
        """
        if resultado is None:
            return 0
        
        # Se for dicionário
        if isinstance(resultado, dict):
            # Tenta várias chaves comuns
            for chave in ['total', 'COUNT(*)', 'count', 'quantidade']:
                if chave in resultado:
                    valor = resultado[chave]
                    if isinstance(valor, bytes):
                        return int(valor.decode('utf-8', errors='ignore'))
                    return int(valor) if valor else 0
            # Se não encontrou chave, pega o primeiro valor
            valores = list(resultado.values())
            if valores:
                valor = valores[0]
                if isinstance(valor, bytes):
                    return int(valor.decode('utf-8', errors='ignore'))
                return int(valor) if valor else 0
            return 0
        
        # Se for tupla/lista
        if isinstance(resultado, (tuple, list)):
            if len(resultado) > 0:
                valor = resultado[0]
                if isinstance(valor, bytes):
                    return int(valor.decode('utf-8', errors='ignore'))
                return int(valor) if valor else 0
            return 0
        
        # Se for número
        if isinstance(resultado, (int, float)):
            return int(resultado)
        
        return 0
    
    @medico_required
    def dashboard():
        """Dashboard principal do médico"""
        try:
            print("\n" + "="*60)
            print("CARREGANDO DASHBOARD DO MEDICO")
            print("="*60)
            
            medico_info = obter_info_medico()
            if not medico_info:
                return render_template('medico/dashboard.html', 
                                     error="Médico não encontrado",
                                     consultas=[],
                                     consultasHoje=0,
                                     contadorResultados=0,
                                     contadorAnalises=0,
                                     contadorPedidos=0,
                                     user=session)
            
            medico_id = medico_info.get('id')
            print(f"Médico ID: {medico_id}")
            
            # Buscar consultas
            consultas_raw = execute_query("""
                SELECT 
                    c.id,
                    u.nome as paciente_nome,
                    c.data_hora,
                    c.status
                FROM consultas c
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE c.medico_id = %s
                ORDER BY c.data_hora DESC
                LIMIT 10
            """, (medico_id,), fetch=True) or []
            
            print(f"Total de consultas encontradas: {len(consultas_raw)}")
            if consultas_raw:
                print(f"Tipo do primeiro resultado: {type(consultas_raw[0])}")
            
            consultas = []
            for c_raw in consultas_raw:
                # Converter para dicionário padronizado
                c_dict = converter_consulta_para_dict(c_raw)
                if not c_dict:
                    continue
                
                paciente_nome = c_dict.get('paciente_nome', '')
                data_hora = c_dict.get('data_hora')
                status = c_dict.get('status', 'desconhecido')
                
                # Processar data e hora
                if data_hora:
                    if isinstance(data_hora, datetime):
                        data_consulta = data_hora.strftime('%d/%m/%Y')
                        hora_consulta = data_hora.strftime('%H:%M')
                    else:
                        data_consulta = str(data_hora)[:10] if len(str(data_hora)) > 10 else str(data_hora)
                        hora_consulta = str(data_hora)[11:16] if len(str(data_hora)) > 16 else ''
                else:
                    data_consulta = ''
                    hora_consulta = ''
                
                status_class = {
                    'agendada': 'primary', 
                    'confirmada': 'info',
                    'realizada': 'success', 
                    'cancelada': 'danger',
                    'pendente': 'warning'
                }.get(status, 'secondary')
                
                consultas.append({
                    'id': c_dict.get('id'),
                    'paciente_nome': paciente_nome,
                    'data_consulta': data_consulta,
                    'hora_consulta': hora_consulta,
                    'status': status,
                    'status_class': status_class,
                    'tem_analise_pendente': False,
                    'tem_resultado': False
                })
            
            print(f"Consultas processadas: {len(consultas)}")
            
            # Buscar contagens
            hoje = datetime.now().strftime('%Y-%m-%d')
            consultas_hoje_result = execute_query("""
                SELECT COUNT(*) FROM consultas 
                WHERE medico_id = %s AND DATE(data_hora) = %s
            """, (medico_id, hoje), fetch=True, one=True)
            
            consultas_hoje = extrair_contador(consultas_hoje_result)
            
            resultados_pendentes_result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status = 'concluido' AND status_aprovacao = 'pendente'
            """, (medico_id,), fetch=True, one=True)
            
            resultados_pendentes = extrair_contador(resultados_pendentes_result)
            
            analises_solicitadas_result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status IN ('pendente', 'em_analise')
            """, (medico_id,), fetch=True, one=True)
            
            analises_solicitadas = extrair_contador(analises_solicitadas_result)
            
            total_pedidos_result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s
            """, (medico_id,), fetch=True, one=True)
            
            total_pedidos = extrair_contador(total_pedidos_result)
            
            print(f"Contadores: ConsultasHoje={consultas_hoje}, Resultados={resultados_pendentes}, Análises={analises_solicitadas}, TotalPedidos={total_pedidos}")
            
            return render_template('medico/dashboard.html',
                                 consultas=consultas,
                                 consultasHoje=consultas_hoje,
                                 contadorResultados=resultados_pendentes,
                                 contadorAnalises=analises_solicitadas,
                                 contadorPedidos=total_pedidos,
                                 user=session)
            
        except Exception as e:
            print(f"ERRO NO DASHBOARD: {e}")
            traceback.print_exc()
            return render_template('medico/dashboard.html',
                                 error=str(e), 
                                 consultas=[], 
                                 consultasHoje=0,
                                 contadorResultados=0, 
                                 contadorAnalises=0, 
                                 contadorPedidos=0,
                                 user=session)
    
    # EVITAR REGISTRO DUPLICADO
    if not _DASHBOARD_REGISTERED:
        _DASHBOARD_REGISTERED = True
        logger.info("Registrando rota /dashboard do médico")
        return {
            'routes': [
                {'rule': '/dashboard', 'view_func': dashboard, 'methods': ['GET']}
            ]
        }
    else:
        logger.warning("Tentativa de registro duplicado da rota /dashboard - IGNORADA")
        return {'routes': []}

__all__ = ['init_medico_dashboard']
