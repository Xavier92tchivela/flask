# routes/medico/medico_dashboard.py (VERSÃO COM VERIFICAÇÃO)
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
            
            consultas = []
            for c in consultas_raw:
                paciente_nome = converter_bytes_para_string(c[1])
                
                if c[2]:
                    if isinstance(c[2], datetime):
                        data_consulta = c[2].strftime('%d/%m/%Y')
                        hora_consulta = c[2].strftime('%H:%M')
                    else:
                        data_consulta = str(c[2])[:10]
                        hora_consulta = str(c[2])[11:16] if len(str(c[2])) > 16 else ''
                else:
                    data_consulta = ''
                    hora_consulta = ''
                
                status_class = {
                    'agendada': 'primary', 'confirmada': 'info',
                    'realizada': 'success', 'cancelada': 'danger',
                    'pendente': 'warning'
                }.get(c[3], 'secondary')
                
                consultas.append({
                    'id': c[0], 'paciente_nome': paciente_nome,
                    'data_consulta': data_consulta, 'hora_consulta': hora_consulta,
                    'status': c[3] or 'desconhecido', 'status_class': status_class,
                    'tem_analise_pendente': False, 'tem_resultado': False
                })
            
            # Buscar contagens
            hoje = datetime.now().strftime('%Y-%m-%d')
            consultas_hoje = execute_query("""
                SELECT COUNT(*) FROM consultas 
                WHERE medico_id = %s AND DATE(data_hora) = %s
            """, (medico_id, hoje), fetch=True, one=True)
            
            resultados_pendentes = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status = 'concluido' AND status_aprovacao = 'pendente'
            """, (medico_id,), fetch=True, one=True)
            
            analises_solicitadas = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status IN ('pendente', 'em_analise')
            """, (medico_id,), fetch=True, one=True)
            
            total_pedidos = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s
            """, (medico_id,), fetch=True, one=True)
            
            return render_template('medico/dashboard.html',
                                 consultas=consultas,
                                 consultasHoje=consultas_hoje[0] if consultas_hoje else 0,
                                 contadorResultados=resultados_pendentes[0] if resultados_pendentes else 0,
                                 contadorAnalises=analises_solicitadas[0] if analises_solicitadas else 0,
                                 contadorPedidos=total_pedidos[0] if total_pedidos else 0,
                                 user=session)
            
        except Exception as e:
            print(f"ERRO NO DASHBOARD: {e}")
            traceback.print_exc()
            return render_template('medico/dashboard.html',
                                 error=str(e), consultas=[], consultasHoje=0,
                                 contadorResultados=0, contadorAnalises=0, contadorPedidos=0,
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
