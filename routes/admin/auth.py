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
            
            if not email or not senha:
                flash('Por favor, preencha email e senha.', 'danger')
                return redirect(url_for('admin.login'))
            
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                flash('Email inválido.', 'danger')
                return redirect(url_for('admin.login'))
            
            try:
                # Buscar usuário pelo email (agora aceita qualquer tipo que tenha permissão de admin)
                user = execute_query("""
                    SELECT id, nome, email, senha, tipo, ativo 
                    FROM usuarios 
                    WHERE email = %s AND tipo = 'admin' AND ativo = 1
                """, (email,), fetch=True, one=True)
                
                if not user:
                    logger.warning(f"Tentativa de login admin com email não encontrado: {email}")
                    flash('Email ou senha incorretos.', 'danger')
                    return redirect(url_for('admin.login'))
                
                # Verificar senha (suporta pbkdf2 e texto plano)
                senha_valida = False
                
                # Tentar verificar com hash pbkdf2
                if user[3].startswith('pbkdf2:'):
                    senha_valida = check_password_hash(user[3], senha)
                # Tentar comparação direta (texto plano)
                elif user[3] == senha:
                    senha_valida = True
                    # Migrar para hash seguro
                    novo_hash = generate_password_hash(senha, method='pbkdf2:sha256')
                    execute_query("""
                        UPDATE usuarios SET senha = %s WHERE id = %s
                    """, (novo_hash, user[0]), commit=True)
                    logger.info(f"Senha migrada para pbkdf2 para admin: {email}")
                else:
                    senha_valida = False
                
                if not senha_valida:
                    logger.warning(f"Tentativa de login admin com senha incorreta: {email}")
                    flash('Email ou senha incorretos.', 'danger')
                    return redirect(url_for('admin.login'))
                
                # Login bem-sucedido
                session.clear()
                session['user_id'] = user[0]
                session['user_name'] = user[1]
                session['user_email'] = user[2]
                session['user_type'] = user[4]
                session['logged_in'] = True
                session['admin_logged_in'] = True
                session.permanent = True
                
                logger.info(f"Admin login bem-sucedido: {email}")
                flash(f'Bem-vindo, {user[1]}!', 'success')
                return redirect(url_for('admin.dashboard'))
                    
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
            senha_hash = generate_password_hash(nova_senha, method='pbkdf2:sha256')
            
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

    # ---------- ROTA PARA CRIAR ADMIN (SEM RESTRIÇÕES) ----------
    @admin_bp.route('/criar-admin', methods=['GET', 'POST'])
    def criar_admin():
        """Criar administrador (rota protegida por chave secreta)"""
        # Verificar chave secreta para segurança
        chave = request.args.get('chave', '')
        if chave != 'CRIAR_ADMIN_2024':
            flash('Acesso restrito. Use a chave correta na URL.', 'danger')
            return redirect(url_for('admin.login'))
        
        if request.method == 'POST':
            nome = request.form.get('nome', '').strip()
            email = request.form.get('email', '').strip().lower()
            senha = request.form.get('senha', '')
            confirmar = request.form.get('confirmar_senha', '')
            
            # Validações
            if not nome or not email or not senha:
                flash('Todos os campos são obrigatórios.', 'danger')
                return render_template('admin/criar_admin.html')
            
            if senha != confirmar:
                flash('As senhas não coincidem.', 'danger')
                return render_template('admin/criar_admin.html')
            
            if len(senha) < 6:
                flash('A senha deve ter pelo menos 6 caracteres.', 'danger')
                return render_template('admin/criar_admin.html')
            
            # Verificar se email já existe
            existe = execute_query("""
                SELECT id FROM usuarios WHERE email = %s
            """, (email,), fetch=True, one=True)
            
            if existe:
                flash('Este email já está cadastrado no sistema.', 'danger')
                return render_template('admin/criar_admin.html')
            
            # Gerar hash da senha
            senha_hash = generate_password_hash(senha, method='pbkdf2:sha256')
            
            # Criar admin
            user_uuid = str(uuid.uuid4())
            execute_query("""
                INSERT INTO usuarios (uuid, nome, email, senha, tipo, ativo, criado_em, atualizado_em)
                VALUES (%s, %s, %s, %s, 'admin', 1, NOW(), NOW())
            """, (user_uuid, nome, email, senha_hash), commit=True)
            
            logger.info(f"Novo administrador criado: {email}")
            flash('Administrador criado com sucesso! Faça login.', 'success')
            return redirect(url_for('admin.login'))
        
        return render_template('admin/criar_admin.html')

    # ---------- ROTA PARA PROMOVER USUÁRIO A ADMIN ----------
    @admin_bp.route('/promover/<email>')
    def promover_admin(email):
        """Promover um usuário existente a administrador (protegido por chave)"""
        chave = request.args.get('chave', '')
        if chave != 'PROMOVER_ADMIN_2024':
            return 'Acesso negado. Use a chave correta.', 403
        
        # Verificar se usuário existe
        usuario = execute_query("""
            SELECT id, nome, email, tipo FROM usuarios WHERE email = %s
        """, (email,), fetch=True, one=True)
        
        if not usuario:
            return f"Usuário {email} não encontrado.", 404
        
        if usuario[3] == 'admin':
            return f"Usuário {email} já é administrador.", 400
        
        # Promover a admin
        execute_query("""
            UPDATE usuarios SET tipo = 'admin' WHERE email = %s
        """, (email,), commit=True)
        
        logger.info(f"Usuário promovido a admin: {email}")
        return f"✅ Usuário {email} promovido a administrador com sucesso!"
    
    # ---------- ROTA DE SETUP (primeiro admin) ----------
    @admin_bp.route('/setup', methods=['GET', 'POST'])
    def setup():
        """Criar primeiro administrador (apenas se não existir nenhum)"""
        # Verificar se já existe admin
        existe_admin = execute_query("""
            SELECT COUNT(*) as total FROM usuarios WHERE tipo = 'admin'
        """, fetch=True, one=True)
        
        # Se já existe admin, redirecionar para login
        if existe_admin and existe_admin[0] > 0:
            flash('Já existem administradores no sistema. Use /admin/criar-admin?chave=CRIAR_ADMIN_2024 para criar mais.', 'warning')
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
            
            # Verificar se email já existe
            existe = execute_query("""
                SELECT id FROM usuarios WHERE email = %s
            """, (email,), fetch=True, one=True)
            
            if existe:
                flash('Este email já está cadastrado no sistema.', 'danger')
                return render_template('admin/setup.html')
            
            # Gerar hash da senha
            senha_hash = generate_password_hash(senha, method='pbkdf2:sha256')
            
            # Criar admin
            user_uuid = str(uuid.uuid4())
            execute_query("""
                INSERT INTO usuarios (uuid, nome, email, senha, tipo, ativo, criado_em, atualizado_em)
                VALUES (%s, %s, %s, %s, 'admin', 1, NOW(), NOW())
            """, (user_uuid, nome, email, senha_hash), commit=True)
            
            logger.info(f"Primeiro administrador criado: {email}")
            flash('Administrador criado com sucesso! Faça login.', 'success')
            return redirect(url_for('admin.login'))
        
        return render_template('admin/setup.html')
