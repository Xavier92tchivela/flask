# routes/admin/consultas.py
from flask import render_template, request, redirect, url_for, flash, session, jsonify
import logging

logger = logging.getLogger(__name__)

def init_consultas_routes(admin_bp, mysql):
    """Rotas para gerenciamento de consultas"""
    
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
        from functools import wraps
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
    
    # ---------- LISTAR CONSULTAS ----------
    @admin_bp.route('/consultas')
    @admin_required
    def consultas():
        """Lista todas as consultas do sistema"""
        try:
            consultas = execute_query("""
                SELECT 
                    c.id,
                    CONCAT(p_u.nome) as paciente,
                    CONCAT('Dr. ', m_u.nome) as medico,
                    c.data_hora,
                    c.status,
                    c.criado_em,
                    m.especialidade
                FROM consultas c
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios p_u ON p.usuario_id = p_u.id
                JOIN medicos m ON c.medico_id = m.id
                JOIN usuarios m_u ON m.usuario_id = m_u.id
                ORDER BY c.data_hora DESC
                LIMIT 100
            """, fetch=True) or []
            
            return render_template('admin/consultas.html', consultas=consultas, user=session)
        except Exception as e:
            logger.error(f"Erro ao listar consultas: {e}")
            flash('Erro ao carregar consultas.', 'danger')
            return render_template('admin/consultas.html', consultas=[], user=session)