# routes/medico/dashboard_otimizado.py
"""
Rotas otimizadas para o dashboard do médico
"""

from flask import render_template, session, jsonify, request,url_for,redirect,flash
import logging
from services.dashboard_service import DashboardService

logger = logging.getLogger(__name__)

def init_dashboard_otimizado(mysql, base, medico_required):
    """Inicializa rotas otimizadas do dashboard"""
    
    obter_info_medico = base['obter_info_medico']
    
    @medico_required
    def dashboard_otimizado():
        """Dashboard do médico com dados em cache"""
        
        medico_info = obter_info_medico()
        if not medico_info:
            flash('Informações do médico não encontradas.', 'danger')
            return redirect(url_for('auth.login'))
        
        medico_id = medico_info.get('id')
        
        # Buscar dados do dashboard (com cache)
        dados = DashboardService.get_dados_dashboard(medico_id, mysql)
        
        return render_template('medico/dashboard_otimizado.html',
                             medico=medico_info,
                             consultas=dados['ultimas_consultas'],
                             consultasHoje=dados['consultas_hoje'],
                             contadorResultados=dados['resultados_pendentes'],
                             contadorAnalises=dados['analises_solicitadas'],
                             contadorPedidos=dados['total_pedidos'],
                             user=session,
                             dados=dados)
    
    @medico_required
    def api_pedidos_recentes():
        """API para carregar pedidos recentes via AJAX"""
        
        medico_info = obter_info_medico()
        if not medico_info:
            return jsonify({'error': 'Não autorizado'}), 401
        
        medico_id = medico_info.get('id')
        
        try:
            cur = mysql.connection.cursor()
            cur.execute("""
                SELECT 
                    pa.id,
                    pa.tipo_exame,
                    pa.status,
                    pa.status_aprovacao,
                    DATE_FORMAT(pa.data_solicitacao, '%d/%m/%Y %H:%i') as data_solicitacao,
                    u.nome as paciente_nome
                FROM pedidos_analise pa
                JOIN pacientes p ON pa.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE pa.medico_id = %s
                ORDER BY pa.data_solicitacao DESC
                LIMIT 5
            """, (medico_id,))
            
            pedidos = cur.fetchall()
            cur.close()
            
            pedidos_lista = []
            for p in pedidos:
                pedidos_lista.append({
                    'id': p[0],
                    'tipo_exame': p[1],
                    'status': p[2],
                    'status_aprovacao': p[3],
                    'data_solicitacao': p[4],
                    'paciente_nome': p[5]
                })
            
            return jsonify({'pedidos': pedidos_lista})
            
        except Exception as e:
            logger.error(f"Erro ao buscar pedidos: {e}")
            return jsonify({'pedidos': []})
    
    @medico_required
    def api_contadores():
        """API para carregar contadores via AJAX"""
        
        medico_info = obter_info_medico()
        if not medico_info:
            return jsonify({'error': 'Não autorizado'}), 401
        
        medico_id = medico_info.get('id')
        
        try:
            # Usar o serviço com cache
            dados = DashboardService.get_dados_dashboard(medico_id, mysql)
            
            return jsonify({
                'consultas_hoje': dados['consultas_hoje'],
                'resultados_pendentes': dados['resultados_pendentes'],
                'analises_solicitadas': dados['analises_solicitadas'],
                'notificacoes': dados['notificacoes']
            })
            
        except Exception as e:
            logger.error(f"Erro ao buscar contadores: {e}")
            return jsonify({
                'consultas_hoje': 0,
                'resultados_pendentes': 0,
                'analises_solicitadas': 0,
                'notificacoes': 0
            })
    
    @medico_required
    def api_notificacoes():
        """API para carregar notificações via AJAX"""
        
        medico_info = obter_info_medico()
        if not medico_info:
            return jsonify({'error': 'Não autorizado'}), 401
        
        medico_id = medico_info.get('id')
        
        try:
            cur = mysql.connection.cursor()
            cur.execute("""
                SELECT 
                    pa.id,
                    pa.tipo_exame,
                    u.nome as paciente_nome,
                    DATE_FORMAT(pa.data_conclusao, '%d/%m/%Y %H:%i') as data_conclusao,
                    TIMESTAMPDIFF(HOUR, pa.data_conclusao, NOW()) as horas_atras
                FROM pedidos_analise pa
                JOIN pacientes p ON pa.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE pa.medico_id = %s 
                  AND pa.status = 'concluido' 
                  AND pa.status_aprovacao = 'pendente'
                  AND pa.data_conclusao >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                ORDER BY pa.data_conclusao DESC
                LIMIT 5
            """, (medico_id,))
            
            notificacoes = cur.fetchall()
            cur.close()
            
            notificacoes_lista = []
            for n in notificacoes:
                tempo = f"há {n[4]} horas" if n[4] < 24 else f"há {n[4]//24} dias"
                notificacoes_lista.append({
                    'id': n[0],
                    'titulo': f"Resultado: {n[1]}",
                    'mensagem': f"{n[2]} - Aguardando revisão",
                    'tempo': tempo,
                    'link': f"/medico/revisar-analise/{n[0]}"
                })
            
            return jsonify({'notificacoes': notificacoes_lista})
            
        except Exception as e:
            logger.error(f"Erro ao buscar notificações: {e}")
            return jsonify({'notificacoes': []})
    
    # Retornar as rotas
    return {
        'routes': [
            {'rule': '/dashboard', 'view_func': dashboard_otimizado, 'methods': ['GET']},
            {'rule': '/api/pedidos-recentes', 'view_func': api_pedidos_recentes, 'methods': ['GET']},
            {'rule': '/api/contadores', 'view_func': api_contadores, 'methods': ['GET']},
            {'rule': '/api/notificacoes', 'view_func': api_notificacoes, 'methods': ['GET']}
        ]
    }