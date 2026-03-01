# routes/admin/estatisticas.py
from flask import render_template, session, redirect, url_for, flash
from datetime import datetime
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def init_estatisticas_routes(admin_bp, mysql):
    """Rotas para estatísticas e relatórios"""
    
    # ---------- FUNÇÃO AUXILIAR DE QUERY ----------
    def execute_query(query, params=None, fetch=False, one=False):
        try:
            cur = mysql.connection.cursor()
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            
            if fetch:
                result = cur.fetchall()
                if one and result:
                    result = result[0]
            else:
                mysql.connection.commit()
                result = None
            
            cur.close()
            return result
        except Exception as e:
            mysql.connection.rollback()
            logger.error(f"Database error: {e}")
            return None
    
    # ---------- DECORATOR DE AUTENTICAÇÃO ----------
    def admin_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Por favor, faça login para acessar o painel administrativo.', 'warning')
                return redirect(url_for('admin.login'))
            
            if session.get('user_type') != 'admin':
                flash('Acesso restrito a administradores.', 'danger')
                return redirect(url_for('admin.login'))
            
            return f(*args, **kwargs)
        return decorated_function
    
    # ---------- PÁGINA DE ESTATÍSTICAS ----------
    @admin_bp.route('/estatisticas')
    @admin_required
    def estatisticas():
        """Página de estatísticas detalhadas"""
        try:
            # Estatísticas por mês (últimos 6 meses)
            consultas_por_mes = execute_query("""
                SELECT 
                    DATE_FORMAT(data_hora, '%%Y-%%m') as mes,
                    COUNT(*) as total
                FROM consultas
                WHERE data_hora >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
                GROUP BY DATE_FORMAT(data_hora, '%%Y-%%m')
                ORDER BY mes DESC
            """, fetch=True) or []
            
            # Top 5 médicos
            top_medicos = execute_query("""
                SELECT 
                    m_u.nome,
                    COUNT(*) as total_consultas
                FROM consultas c
                JOIN medicos m ON c.medico_id = m.id
                JOIN usuarios m_u ON m.usuario_id = m_u.id
                GROUP BY c.medico_id
                ORDER BY total_consultas DESC
                LIMIT 5
            """, fetch=True) or []
            
            # Distribuição por status
            status_distribuicao = execute_query("""
                SELECT status, COUNT(*) as total
                FROM consultas
                GROUP BY status
            """, fetch=True) or []
            
            # Total de diagnósticos
            total_diagnosticos = execute_query(
                "SELECT COUNT(*) FROM diagnostico", 
                fetch=True, one=True
            )
            total_diagnosticos = total_diagnosticos[0] if total_diagnosticos else 0
            
            # Média de consultas por dia
            media_consultas = execute_query("""
                SELECT AVG(consultas_por_dia) FROM (
                    SELECT DATE(data_hora) as dia, COUNT(*) as consultas_por_dia
                    FROM consultas
                    GROUP BY DATE(data_hora)
                ) as stats
            """, fetch=True, one=True)
            media_consultas = round(media_consultas[0], 1) if media_consultas and media_consultas[0] else 0
            
            return render_template('admin/estatisticas.html',
                                 consultas_por_mes=consultas_por_mes,
                                 top_medicos=top_medicos,
                                 status_distribuicao=status_distribuicao,
                                 total_diagnosticos=total_diagnosticos,
                                 media_consultas=media_consultas,
                                 now=datetime.now(),
                                 user=session)
        except Exception as e:
            logger.error(f"Erro ao carregar estatísticas: {e}")
            flash('Erro ao carregar estatísticas.', 'danger')
            return render_template('admin/estatisticas.html', user=session)