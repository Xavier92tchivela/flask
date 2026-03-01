# routes/admin/auth.py
from flask import render_template, request, redirect, url_for, flash, session
import logging

logger = logging.getLogger(__name__)

def init_auth_routes(admin_bp, mysql):
    """Rotas de autenticação do admin"""
    
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
    
    # ---------- ROTA DE LOGIN ----------
    @admin_bp.route('/login', methods=['GET', 'POST'])
    def login():
        """Página de login do administrador"""
        if 'user_id' in session and session.get('user_type') == 'admin':
            return redirect(url_for('admin.dashboard'))
        
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            senha = request.form.get('senha', '').strip()
            
            if not email or not senha:
                flash('Por favor, preencha email e senha.', 'danger')
                return redirect(url_for('admin.login'))
            
            try:
                user = execute_query("""
                    SELECT id, nome, email, tipo, ativo 
                    FROM usuarios 
                    WHERE email = %s AND senha = %s AND tipo = 'admin' AND ativo = TRUE
                """, (email, senha), fetch=True, one=True)
                
                if user:
                    session.clear()
                    session['user_id'] = user[0]
                    session['user_name'] = user[1]
                    session['user_email'] = user[2]
                    session['user_type'] = user[3]
                    session['logged_in'] = True
                    
                    logger.info(f"Admin login: {email}")
                    flash('Login realizado com sucesso!', 'success')
                    return redirect(url_for('admin.dashboard'))
                else:
                    inactive = execute_query("""
                        SELECT id FROM usuarios 
                        WHERE email = %s AND tipo = 'admin' AND ativo = FALSE
                    """, (email,), fetch=True, one=True)
                    
                    if inactive:
                        flash('Esta conta de administrador está inativa. Contate o suporte.', 'danger')
                    else:
                        flash('Email ou senha incorretos.', 'danger')
                    
                    return redirect(url_for('admin.login'))
                    
            except Exception as e:
                logger.error(f"Erro no login admin: {e}")
                flash('Erro ao processar login. Tente novamente.', 'danger')
                return redirect(url_for('admin.login'))
        
        return render_template('admin/login.html')

    # ---------- ROTA DE LOGOUT ----------
    @admin_bp.route('/logout')
    def logout():
        """Logout do administrador"""
        if 'user_id' in session and session.get('user_type') == 'admin':
            logger.info(f"Admin logout: {session.get('user_email')}")
        session.clear()
        flash('Você saiu do sistema.', 'success')
        return redirect(url_for('admin.login'))

    # ---------- ROTA DE RECUPERAÇÃO DE SENHA ----------
    @admin_bp.route('/recuperar-senha', methods=['GET', 'POST'])
    def recuperar_senha():
        """Recuperação de senha para admin"""
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            
            admin = execute_query("""
                SELECT id, nome FROM usuarios 
                WHERE email = %s AND tipo = 'admin'
            """, (email,), fetch=True, one=True)
            
            if admin:
                flash('Instruções de recuperação enviadas para seu email.', 'success')
                logger.info(f"Recuperação de senha solicitada para: {email}")
            else:
                flash('Email não encontrado na base de administradores.', 'danger')
            
            return redirect(url_for('admin.login'))
        
        return render_template('admin/recuperar_senha.html')