# routes/analista/routes/dashboard.py
from flask import render_template, session, flash, redirect, url_for, jsonify
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def register_dashboard_routes(bp, analista_required, execute_query, formatar_data):
    
    @bp.route('/dashboard')
    @analista_required
    def dashboard():
        """Dashboard do analista"""
        try:
            user_id = session.get('user_id')
            
            # Buscar informações do analista
            analista_info = execute_query("""
                SELECT a.id, u.nome, a.especialidade 
                FROM analistas a
                JOIN usuarios u ON a.usuario_id = u.id
                WHERE u.id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                flash('Perfil de analista não encontrado.', 'danger')
                return redirect(url_for('auth.login'))
            
            analista_id = analista_info[0]
            session['analista_id'] = analista_id
            session['user_name'] = analista_info[1]
            session['analista_especialidade'] = analista_info[2]
            
            # 👈 CRIAR DICIONÁRIO DE ESTATÍSTICAS
            estatisticas = {
                'pendentes': 0,
                'em_analise': 0,
                'concluidos': 0,
                'urgentes': 0
            }
            
            # Buscar estatísticas do banco
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE analista_id = %s AND status = 'pendente'
            """, (analista_id,), fetch=True, one=True)
            estatisticas['pendentes'] = result[0] if result else 0
            
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE analista_id = %s AND status = 'em_analise'
            """, (analista_id,), fetch=True, one=True)
            estatisticas['em_analise'] = result[0] if result else 0
            
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE analista_id = %s AND status = 'concluido'
            """, (analista_id,), fetch=True, one=True)
            estatisticas['concluidos'] = result[0] if result else 0
            
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE analista_id = %s AND urgencia = 'urgente' 
                AND status IN ('pendente', 'em_analise')
            """, (analista_id,), fetch=True, one=True)
            estatisticas['urgentes'] = result[0] if result else 0
            
            # Buscar pedidos recentes
            pedidos_recentes = execute_query("""
                SELECT 
                    pa.id,
                    pa.tipo_exame,
                    pa.urgencia,
                    pa.status,
                    pa.data_solicitacao,
                    u.nome as paciente_nome
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                WHERE pa.analista_id = %s
                ORDER BY 
                    CASE pa.status 
                        WHEN 'pendente' THEN 1
                        WHEN 'em_analise' THEN 2
                        ELSE 3
                    END,
                    pa.data_solicitacao DESC
                LIMIT 5
            """, (analista_id,), fetch=True)
            
            pedidos_list = []
            if pedidos_recentes:
                for p in pedidos_recentes:
                    pedidos_list.append({
                        'id': p[0],
                        'tipo_exame': p[1],
                        'urgencia': p[2],
                        'status': p[3],
                        'data_solicitacao': formatar_data(p[4]),
                        'paciente_nome': p[5] or 'Não informado'
                    })
            
            # 👈 PASSAR TODAS AS VARIÁVEIS PARA O TEMPLATE
            return render_template('analista/dashboard.html',
                                 user=session,
                                 estatisticas=estatisticas,        # 👈 IMPORTANTE!
                                 pedidos_atribuidos=pedidos_list,
                                 now=datetime.now())
            
        except Exception as e:
            logger.error(f"Erro no dashboard: {e}")
            flash('Erro ao carregar dashboard.', 'danger')
            # 👈 MESMO EM CASO DE ERRO, PASSAR VALORES PADRÃO
            return render_template('analista/dashboard.html',
                                 user=session,
                                 estatisticas={'pendentes':0, 'em_analise':0, 'concluidos':0, 'urgentes':0},
                                 pedidos_atribuidos=[],
                                 now=datetime.now())

    @bp.route('/api/dashboard-stats')
    @analista_required
    def api_dashboard_stats():
        """API para obter estatísticas do dashboard"""
        try:
            user_id = session.get('user_id')
            
            analista_info = execute_query("""
                SELECT a.id FROM analistas a
                WHERE a.usuario_id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                return jsonify({'error': 'Analista não encontrado'}), 404
            
            analista_id = analista_info[0]
            
            estatisticas = {
                'pendentes': 0,
                'em_analise': 0,
                'concluidos': 0,
                'urgentes': 0,
                'total': 0
            }
            
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE analista_id = %s AND status = 'pendente'
            """, (analista_id,), fetch=True, one=True)
            estatisticas['pendentes'] = result[0] if result else 0
            
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE analista_id = %s AND status = 'em_analise'
            """, (analista_id,), fetch=True, one=True)
            estatisticas['em_analise'] = result[0] if result else 0
            
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE analista_id = %s AND status = 'concluido'
            """, (analista_id,), fetch=True, one=True)
            estatisticas['concluidos'] = result[0] if result else 0
            
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE analista_id = %s AND urgencia = 'urgente' 
                AND status IN ('pendente', 'em_analise')
            """, (analista_id,), fetch=True, one=True)
            estatisticas['urgentes'] = result[0] if result else 0
            
            estatisticas['total'] = estatisticas['pendentes'] + estatisticas['em_analise'] + estatisticas['concluidos']
            
            return jsonify({'success': True, 'estatisticas': estatisticas})
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500