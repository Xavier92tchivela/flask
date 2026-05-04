"""Rotas de dashboard para analista"""
from flask import render_template, session, flash, redirect, url_for, jsonify
from datetime import datetime
import logging
import traceback

logger = logging.getLogger(__name__)

def register_dashboard_routes(bp, analista_required, execute_query, formatar_data):
    
    @bp.route('/dashboard')
    @analista_required
    def dashboard():
        """Dashboard do analista"""
        try:
            user_id = session.get('user_id')
            
            analista_info = execute_query("""
                SELECT a.id, u.nome, a.especialidade 
                FROM analistas a
                JOIN usuarios u ON a.usuario_id = u.id
                WHERE u.id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                flash('Perfil de analista não encontrado.', 'danger')
                return redirect(url_for('auth.login'))
            
            # Verificar se é dict ou tuple
            if isinstance(analista_info, dict):
                analista_id = analista_info.get('id')
                analista_nome = analista_info.get('nome')
                analista_especialidade = analista_info.get('especialidade')
            else:
                analista_id = analista_info[0]
                analista_nome = analista_info[1]
                analista_especialidade = analista_info[2]
            
            session['analista_id'] = analista_id
            session['user_name'] = analista_nome
            session['analista_especialidade'] = analista_especialidade
            
            # Estatísticas básicas
            estatisticas = {
                'pendentes': 0, 
                'em_analise': 0, 
                'concluidos': 0, 
                'urgentes': 0,
                'hoje': 0,
                'amanha': 0,
                'esta_semana': 0
            }
            
            hoje = datetime.now().date()
            
            # Contagem de pendentes
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE (analista_id = %s OR analista_id IS NULL) AND status = 'pendente'
            """, (analista_id,), fetch=True, one=True)
            estatisticas['pendentes'] = result[0] if result else 0
            
            # Contagem de em análise
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE (analista_id = %s OR analista_id IS NULL) AND status = 'em_analise'
            """, (analista_id,), fetch=True, one=True)
            estatisticas['em_analise'] = result[0] if result else 0
            
            # Contagem de concluídos
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE (analista_id = %s OR analista_id IS NULL) AND status = 'concluido'
            """, (analista_id,), fetch=True, one=True)
            estatisticas['concluidos'] = result[0] if result else 0
            
            # Contagem de urgentes
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE (analista_id = %s OR analista_id IS NULL) 
                AND urgencia = 'urgente' 
                AND status IN ('pendente', 'em_analise')
            """, (analista_id,), fetch=True, one=True)
            estatisticas['urgentes'] = result[0] if result else 0
            
            # Pedidos de hoje
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE (analista_id = %s OR analista_id IS NULL) 
                AND DATE(data_solicitacao) = %s
            """, (analista_id, hoje), fetch=True, one=True)
            estatisticas['hoje'] = result[0] if result else 0
            
            # Pedidos desta semana
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE (analista_id = %s OR analista_id IS NULL) 
                AND YEARWEEK(data_solicitacao) = YEARWEEK(CURDATE())
            """, (analista_id,), fetch=True, one=True)
            estatisticas['esta_semana'] = result[0] if result else 0
            
            # Pedidos recentes
            pedidos_recentes = execute_query("""
                SELECT 
                    pa.id, 
                    pa.tipo_exame, 
                    pa.urgencia, 
                    pa.status, 
                    pa.data_solicitacao,
                    COALESCE(u.nome, 'Confidencial') as paciente_nome
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                WHERE pa.analista_id = %s OR pa.analista_id IS NULL
                ORDER BY 
                    CASE pa.status 
                        WHEN 'pendente' THEN 1
                        WHEN 'em_analise' THEN 2
                        ELSE 3
                    END,
                    pa.data_solicitacao DESC
                LIMIT 10
            """, (analista_id,), fetch=True)
            
            pedidos_list = []
            if pedidos_recentes:
                for p in pedidos_recentes:
                    if isinstance(p, dict):
                        pedidos_list.append({
                            'id': p.get('id'),
                            'tipo_exame': p.get('tipo_exame') or 'N/A',
                            'urgencia': p.get('urgencia') or 'normal',
                            'status': p.get('status') or 'pendente',
                            'data_solicitacao': formatar_data(p.get('data_solicitacao')),
                            'paciente_nome': p.get('paciente_nome') or 'Confidencial'
                        })
                    else:
                        pedidos_list.append({
                            'id': p[0],
                            'tipo_exame': p[1] or 'N/A',
                            'urgencia': p[2] or 'normal',
                            'status': p[3] or 'pendente',
                            'data_solicitacao': formatar_data(p[4]),
                            'paciente_nome': p[5] or 'Confidencial'
                        })
            
            return render_template('analista/dashboard.html',
                                 user=session,
                                 estatisticas=estatisticas,
                                 pedidos_atribuidos=pedidos_list,
                                 analista_info=analista_info,
                                 now=datetime.now())
            
        except Exception as e:
            logger.error(f"❌ Erro no dashboard: {e}")
            logger.error(traceback.format_exc())
            flash('Erro ao carregar dashboard.', 'danger')
            return render_template('analista/dashboard.html',
                                 user=session,
                                 estatisticas={'pendentes':0,'em_analise':0,'concluidos':0,'urgentes':0,'hoje':0,'amanha':0,'esta_semana':0},
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
            
            # Verificar se é dict ou tuple
            if isinstance(analista_info, dict):
                analista_id = analista_info.get('id')
            else:
                analista_id = analista_info[0]
            
            hoje = datetime.now().date()
            
            # Estatísticas
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE (analista_id = %s OR analista_id IS NULL) AND status = 'pendente'
            """, (analista_id,), fetch=True, one=True)
            pendentes = result[0] if result else 0
            
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE (analista_id = %s OR analista_id IS NULL) AND status = 'em_analise'
            """, (analista_id,), fetch=True, one=True)
            em_analise = result[0] if result else 0
            
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE (analista_id = %s OR analista_id IS NULL) AND status = 'concluido'
            """, (analista_id,), fetch=True, one=True)
            concluidos = result[0] if result else 0
            
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE (analista_id = %s OR analista_id IS NULL) 
                AND urgencia = 'urgente' 
                AND status IN ('pendente', 'em_analise')
            """, (analista_id,), fetch=True, one=True)
            urgentes = result[0] if result else 0
            
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE (analista_id = %s OR analista_id IS NULL) 
                AND DATE(data_solicitacao) = %s
            """, (analista_id, hoje), fetch=True, one=True)
            hoje_count = result[0] if result else 0
            
            result = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE (analista_id = %s OR analista_id IS NULL) 
                AND YEARWEEK(data_solicitacao) = YEARWEEK(CURDATE())
            """, (analista_id,), fetch=True, one=True)
            semana_count = result[0] if result else 0
            
            estatisticas = {
                'pendentes': pendentes,
                'em_analise': em_analise,
                'concluidos': concluidos,
                'urgentes': urgentes,
                'total': pendentes + em_analise + concluidos,
                'hoje': hoje_count,
                'esta_semana': semana_count
            }
            
            return jsonify({
                'success': True, 
                'estatisticas': estatisticas,
                'pendentes': pendentes,
                'em_analise': em_analise,
                'concluidos': concluidos,
                'urgentes': urgentes,
                'hoje': hoje_count,
                'esta_semana': semana_count
            })
            
        except Exception as e:
            logger.error(f"❌ Erro na API de estatísticas: {e}")
            logger.error(traceback.format_exc())
            return jsonify({'success': False, 'error': str(e)}), 500
