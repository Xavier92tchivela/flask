# routes/admin/auth.py
from flask import render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
import logging
import re
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger(__name__)

def init_auth_routes(admin_bp, mysql):
    """Rotas de autenticação do admin"""
    
    # ---------- FUNÇÃO AUXILIAR DE QUERY ----------
    def execute_query(query, params=None, fetch=False, one=False, commit=True):
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
                if commit:
                    mysql.connection.commit()
                result = None
            
            cur.close()
            return result
        except Exception as e:
            if commit:
                mysql.connection.rollback()
            logger.error(f"Database error: {e}")
            return None
    
    # ---------- ROTA DE LOGIN ----------
    @admin_bp.route('/login', methods=['GET', 'POST'])
    def login():
        """Página de login do administrador"""
        # Se já estiver logado como admin, redirecionar para dashboard
        if session.get('user_type') == 'admin' and session.get('user_id'):
            return redirect(url_for('admin.dashboard'))
        
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            senha = request.form.get('senha', '').strip()
            
            # Validação básica
            if not email or not senha:
                flash('Por favor, preencha email e senha.', 'danger')
                return redirect(url_for('admin.login'))
            
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                flash('Email inválido.', 'danger')
                return redirect(url_for('admin.login'))
            
            try:
                # Buscar usuário pelo email
                user = execute_query("""
                    SELECT id, nome, email, senha, tipo, ativo 
                    FROM usuarios 
                    WHERE email = %s AND tipo = 'admin'
                """, (email,), fetch=True, one=True)
                
                if not user:
                    logger.warning(f"Tentativa de login admin com email não encontrado: {email}")
                    flash('Email ou senha incorretos.', 'danger')
                    return redirect(url_for('admin.login'))
                
                # Verificar se está ativo
                if not user[5]:  # ativo
                    flash('Esta conta de administrador está inativa. Contate o suporte.', 'danger')
                    return redirect(url_for('admin.login'))
                
                # Verificar senha com hash
                if check_password_hash(user[3], senha):  # user[3] é a senha
                    # Login bem-sucedido
                    session.clear()
                    session['user_id'] = user[0]
                    session['user_name'] = user[1]
                    session['user_email'] = user[2]
                    session['user_type'] = user[4]
                    session['logged_in'] = True
                    session['admin_logged_in'] = True
                    
                    logger.info(f"Admin login bem-sucedido: {email}")
                    flash(f'Bem-vindo, {user[1]}!', 'success')
                    return redirect(url_for('admin.dashboard'))
                else:
                    logger.warning(f"Tentativa de login admin com senha incorreta: {email}")
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
        if session.get('user_type') == 'admin':
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
            
            if not email:
                flash('Por favor, informe seu email.', 'danger')
                return redirect(url_for('admin.recuperar_senha'))
            
            # Buscar admin
            admin = execute_query("""
                SELECT id, nome, email FROM usuarios 
                WHERE email = %s AND tipo = 'admin'
            """, (email,), fetch=True, one=True)
            
            if admin:
                # Gerar token único para reset de senha
                reset_token = str(uuid.uuid4())
                expiracao = datetime.now() + timedelta(hours=1)
                
                # Salvar token no banco
                execute_query("""
                    UPDATE usuarios 
                    SET reset_token = %s, 
                        reset_token_expira = %s
                    WHERE id = %s
                """, (reset_token, expiracao, admin[0]), commit=True)
                
                # TODO: Implementar envio de email
                # send_reset_email(admin[1], admin[2], reset_token)
                
                logger.info(f"Token de recuperação gerado para: {email}")
                flash('Instruções de recuperação enviadas para seu email.', 'success')
            else:
                # Por segurança, não revelar se email existe
                logger.info(f"Tentativa de recuperação para email não admin: {email}")
                flash('Se o email existir no sistema, instruções serão enviadas.', 'info')
            
            return redirect(url_for('admin.login'))
        
        return render_template('admin/recuperar_senha.html')

    # ---------- ROTA DE RESET DE SENHA ----------
    @admin_bp.route('/reset-senha/<token>', methods=['GET', 'POST'])
    def reset_senha(token):
        """Página para resetar senha com token"""
        # Verificar se token é válido
        user = execute_query("""
            SELECT id, nome, email 
            FROM usuarios 
            WHERE reset_token = %s 
            AND reset_token_expira > NOW()
        """, (token,), fetch=True, one=True)
        
        if not user:
            flash('Link inválido ou expirado. Solicite nova recuperação.', 'danger')
            return redirect(url_for('admin.recuperar_senha'))
        
        if request.method == 'POST':
            nova_senha = request.form.get('nova_senha', '')
            confirmar_senha = request.form.get('confirmar_senha', '')
            
            if not nova_senha or len(nova_senha) < 6:
                flash('A senha deve ter pelo menos 6 caracteres.', 'danger')
                return render_template('admin/reset_senha.html', token=token)
            
            if nova_senha != confirmar_senha:
                flash('As senhas não coincidem.', 'danger')
                return render_template('admin/reset_senha.html', token=token)
            
            # Gerar hash da nova senha
            senha_hash = generate_password_hash(nova_senha)
            
            # Atualizar senha e limpar token
            execute_query("""
                UPDATE usuarios 
                SET senha = %s, 
                    reset_token = NULL, 
                    reset_token_expira = NULL 
                WHERE id = %s
            """, (senha_hash, user[0]), commit=True)
            
            logger.info(f"Senha resetada para admin: {user[2]}")
            flash('Senha alterada com sucesso! Faça login.', 'success')
            return redirect(url_for('admin.login'))
        
        return render_template('admin/reset_senha.html', token=token)

    # ---------- ROTA PARA CRIAR PRIMEIRO ADMIN (SE NECESSÁRIO) ----------
    @admin_bp.route('/setup', methods=['GET', 'POST'])
    def setup():
        """Criar primeiro administrador (apenas se não existir nenhum)"""
        # Verificar se já existe admin
        existe_admin = execute_query("""
            SELECT COUNT(*) as total FROM usuarios WHERE tipo = 'admin'
        """, fetch=True, one=True)
        
        if existe_admin and existe_admin[0] > 0:
            flash('Já existem administradores no sistema.', 'warning')
            return redirect(url_for('admin.login'))
        
        if request.method == 'POST':
            nome = request.form.get('nome', '').strip()
            email = request.form.get('email', '').strip().lower()
            senha = request.form.get('senha', '')
            confirmar = request.form.get('confirmar_senha', '')
            
            # Validações
            if not nome or not email or not senha:
                flash('Todos os campos são obrigatórios.', 'danger')
                return render_template('admin/setup.html')
            
            if senha != confirmar:
                flash('As senhas não coincidem.', 'danger')
                return render_template('admin/setup.html')
            
            if len(senha) < 6:
                flash('A senha deve ter pelo menos 6 caracteres.', 'danger')
                return render_template('admin/setup.html')
            
            # Gerar hash da senha
            senha_hash = generate_password_hash(senha)
            
            # Criar admin
            user_uuid = str(uuid.uuid4())
            execute_query("""
                INSERT INTO usuarios (uuid, nome, email, senha, tipo, ativo)
                VALUES (%s, %s, %s, %s, 'admin', 1)
            """, (user_uuid, nome, email, senha_hash), commit=True)
            
            logger.info(f"Primeiro administrador criado: {email}")
            flash('Administrador criado com sucesso! Faça login.', 'success')
            return redirect(url_for('admin.login'))
        
        return render_template('admin/setup.html')
