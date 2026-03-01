# routes/medico/dashboard.py
from flask import render_template, session, flash, redirect, url_for
from datetime import datetime
import logging, traceback

logger = logging.getLogger(__name__)

def init_medico_dashboard(base):
    """Inicializa rotas de dashboard do médico"""
    
    medico_required = base['medico_required']
    obter_info_medico = base['obter_info_medico']
    execute_query = base['execute_query']
    formatar_data = base['formatar_data']
    
    # ========== ROTA: DASHBOARD ==========
    def dashboard():
        try:
            medico_info = obter_info_medico()
            if not medico_info:
                flash('Informações do médico não encontradas.', 'danger')
                return redirect(url_for('auth.login'))
            
            medico_id = medico_info.get('id')
            
            # Estatísticas básicas
            contadores = {
                'total_pedidos': 0, 'pedidos_pendentes': 0, 'pedidos_em_analise': 0,
                'pedidos_concluidos': 0, 'resultados_pendentes': 0, 'consultas_hoje': 0,
                'total_receitas': 0
            }
            
            if medico_id and medico_id > 0:
                # Total de pedidos
                result = execute_query("""
                    SELECT COUNT(*) FROM pedidos_analise WHERE medico_id = %s
                """, (medico_id,), fetch=True, one=True)
                if result:
                    contadores['total_pedidos'] = result[0]
                
                # Pedidos por status
                status_counts = execute_query("""
                    SELECT status, COUNT(*) FROM pedidos_analise 
                    WHERE medico_id = %s GROUP BY status
                """, (medico_id,), fetch=True)
                
                if status_counts:
                    for s, c in status_counts:
                        if s == 'pendente':
                            contadores['pedidos_pendentes'] = c
                        elif s == 'em_analise':
                            contadores['pedidos_em_analise'] = c
                        elif s == 'concluido':
                            contadores['pedidos_concluidos'] = c
                
                # Resultados pendentes
                resultados = execute_query("""
                    SELECT COUNT(*) FROM pedidos_analise 
                    WHERE medico_id = %s AND status = 'concluido' 
                    AND status_aprovacao = 'pendente'
                """, (medico_id,), fetch=True, one=True)
                if resultados:
                    contadores['resultados_pendentes'] = resultados[0]
                
                # Consultas hoje
                hoje = datetime.now().strftime('%Y-%m-%d')
                consultas = execute_query("""
                    SELECT COUNT(*) FROM consultas 
                    WHERE medico_id = %s AND DATE(data_hora) = %s
                """, (medico_id, hoje), fetch=True, one=True)
                if consultas:
                    contadores['consultas_hoje'] = consultas[0]
                
                # Receitas
                receitas = execute_query("""
                    SELECT COUNT(*) FROM receita r
                    JOIN consultas c ON r.consulta_id = c.id
                    WHERE c.medico_id = %s
                """, (medico_id,), fetch=True, one=True)
                if receitas:
                    contadores['total_receitas'] = receitas[0]
            
            # Consultas recentes
            consultas_recentes = []
            meses_contagem = {1:0, 2:0, 3:0, 4:0, 5:0, 6:0, 7:0, 8:0, 9:0, 10:0, 11:0, 12:0}
            
            if medico_id and medico_id > 0:
                consultas = execute_query("""
                    SELECT c.id, c.data_hora, c.status, u.nome,
                           MONTH(c.data_hora) as mes
                    FROM consultas c
                    JOIN pacientes p ON c.paciente_id = p.id
                    JOIN usuarios u ON p.usuario_id = u.id
                    WHERE c.medico_id = %s
                    ORDER BY c.data_hora DESC LIMIT 10
                """, (medico_id,), fetch=True)
                
                if consultas:
                    for c in consultas:
                        # Contar por mês
                        if len(c) > 4 and c[4]:  # mes
                            try:
                                mes = int(c[4])
                                if mes in meses_contagem:
                                    meses_contagem[mes] += 1
                            except:
                                pass
                        
                        consultas_recentes.append({
                            'id': c[0],
                            'data_hora': formatar_data(c[1]),
                            'status': c[2],
                            'paciente_nome': c[3],
                            'tem_analise_pendente': False,  # Você pode implementar lógica real
                            'tem_resultado': False  # Você pode implementar lógica real
                        })
            
            return render_template('medico/dashboard.html',
                                 consultas_recentes=consultas_recentes,
                                 consultas=consultas_recentes,  # 👈 Adicionado para compatibilidade
                                 contadores=contadores,
                                 meses_contagem=meses_contagem,  # 👈 ADICIONADO!
                                 user=session,
                                 medico=medico_info)
            
        except Exception as e:
            logger.error(f"Erro no dashboard: {e}")
            logger.error(traceback.format_exc())
            flash('Erro ao carregar dashboard.', 'danger')
            return render_template('medico/dashboard.html',
                                 consultas_recentes=[],
                                 consultas=[],  # 👈 Adicionado
                                 contadores={},
                                 meses_contagem={1:0, 2:0, 3:0, 4:0, 5:0, 6:0, 7:0, 8:0, 9:0, 10:0, 11:0, 12:0},  # 👈 ADICIONADO
                                 user=session,
                                 medico={'nome': 'Erro'})
    
    return {
        'routes': [
            {'rule': '/dashboard', 'view_func': dashboard, 'methods': ['GET']}
        ]
    }