# routes/medico/medico_dashboard.py
from datetime import datetime, timedelta
from flask import render_template, session, jsonify
import logging
import traceback

logger = logging.getLogger(__name__)

def init_medico_dashboard(base):
    """
    Inicializa rotas do dashboard do médico
    
    Args:
        base: Dicionário com funções base
    
    Returns:
        Dicionário com as rotas do módulo
    """
    
    medico_required = base['medico_required']
    obter_info_medico = base['obter_info_medico']
    execute_query = base['execute_query']
    formatar_data = base['formatar_data']
    
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
        return str(valor) if valor else ''
    
    @medico_required
    def dashboard():
        """Dashboard principal do médico"""
        try:
            print("\n" + "="*60)
            print("CARREGANDO DASHBOARD DO MEDICO")
            print("="*60)
            
            # Obter informações do médico
            medico_info = obter_info_medico()
            if not medico_info:
                print("ERRO: Medico nao encontrado")
                return render_template('medico/dashboard.html', 
                                     error="Médico não encontrado",
                                     consultas=[],
                                     consultasHoje=0,
                                     contadorResultados=0,
                                     contadorAnalises=0,
                                     contadorPedidos=0,
                                     user=session)
            
            medico_id = medico_info.get('id')
            print(f"Medico ID: {medico_id}")
            print(f"Medico Nome: {medico_info.get('nome')}")
            
            # ===== 1. BUSCAR CONSULTAS PARA O DASHBOARD =====
            print("\n[1] Buscando consultas do medico...")
            
            # Verificar total de consultas
            total_consultas_db = execute_query("""
                SELECT COUNT(*) FROM consultas WHERE medico_id = %s
            """, (medico_id,), fetch=True, one=True)
            
            print(f"Total de consultas no banco: {total_consultas_db[0] if total_consultas_db else 0}")
            
            # Buscar as 10 consultas mais recentes
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
            
            print(f"Consultas encontradas: {len(consultas_raw)}")
            
            if consultas_raw:
                # Mostrar primeira consulta como exemplo
                nome_paciente = converter_bytes_para_string(consultas_raw[0][1])
                print(f"Primeira consulta: {nome_paciente} - {consultas_raw[0][2]} - {consultas_raw[0][3]}")
            else:
                print("Nenhuma consulta encontrada!")
                
                # Debug: verificar se o médico existe
                medico_check = execute_query("SELECT id FROM medicos WHERE id = %s", (medico_id,), fetch=True, one=True)
                print(f"Medico existe? {medico_check}")
                
                # Verificar consultas de outros médicos
                outras = execute_query("SELECT COUNT(*) FROM consultas", fetch=True, one=True)
                print(f"Total no sistema: {outras[0] if outras else 0}")
            
            # Processar consultas
            consultas = []
            for c in consultas_raw:
                paciente_nome = converter_bytes_para_string(c[1])
                
                # Formatar data
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
                    'agendada': 'primary',
                    'confirmada': 'info',
                    'realizada': 'success',
                    'cancelada': 'danger',
                    'pendente': 'warning'
                }.get(c[3], 'secondary')
                
                consultas.append({
                    'id': c[0],
                    'paciente_nome': paciente_nome,
                    'data_consulta': data_consulta,
                    'hora_consulta': hora_consulta,
                    'status': c[3] or 'desconhecido',
                    'status_class': status_class,
                    'tem_analise_pendente': False,
                    'tem_resultado': False
                })
            
            print(f"Consultas processadas: {len(consultas)}")
            
            # ===== 2. BUSCAR CONTAGENS =====
            print("\n[2] Buscando contagens...")
            
            hoje = datetime.now().strftime('%Y-%m-%d')
            consultas_hoje = execute_query("""
                SELECT COUNT(*) FROM consultas 
                WHERE medico_id = %s AND DATE(data_hora) = %s
            """, (medico_id, hoje), fetch=True, one=True)
            
            resultados_pendentes = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status = 'concluido' 
                AND status_aprovacao = 'pendente'
            """, (medico_id,), fetch=True, one=True)
            
            analises_solicitadas = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status IN ('pendente', 'em_analise')
            """, (medico_id,), fetch=True, one=True)
            
            total_pedidos = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s
            """, (medico_id,), fetch=True, one=True)
            
            consultas_hoje_val = consultas_hoje[0] if consultas_hoje else 0
            resultados_pendentes_val = resultados_pendentes[0] if resultados_pendentes else 0
            analises_solicitadas_val = analises_solicitadas[0] if analises_solicitadas else 0
            total_pedidos_val = total_pedidos[0] if total_pedidos else 0
            
            print(f"Consultas hoje: {consultas_hoje_val}")
            print(f"Resultados pendentes: {resultados_pendentes_val}")
            print(f"Analises solicitadas: {analises_solicitadas_val}")
            print(f"Total pedidos: {total_pedidos_val}")
            
            # ===== 3. RENDERIZAR =====
            print("\n[3] Renderizando template...")
            print(f"Consultas para exibir: {len(consultas)}")
            print("="*60 + "\n")
            
            return render_template('medico/dashboard.html',
                                 consultas=consultas,
                                 consultasHoje=consultas_hoje_val,
                                 contadorResultados=resultados_pendentes_val,
                                 contadorAnalises=analises_solicitadas_val,
                                 contadorPedidos=total_pedidos_val,
                                 user=session)
            
        except Exception as e:
            print("\nERRO NO DASHBOARD:")
            print(f"Tipo: {type(e).__name__}")
            print(f"Erro: {e}")
            traceback.print_exc()
            
            return render_template('medico/dashboard.html',
                                 error=str(e),
                                 consultas=[],
                                 consultasHoje=0,
                                 contadorResultados=0,
                                 contadorAnalises=0,
                                 contadorPedidos=0,
                                 user=session)
    
    return {
        'routes': [
            {'rule': '/dashboard', 'view_func': dashboard, 'methods': ['GET']}
        ]
    }

# Exportar a função
__all__ = ['init_medico_dashboard']
