# routes/admin/auth.py
from flask import render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
import logging
import re
from datetime import datetime, timedelta
import uuid
import traceback

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
                # Buscar usuário pelo email
                result = execute_query("""
                    SELECT id, nome, email, senha, tipo, ativo 
                    FROM usuarios 
                    WHERE email = %s AND tipo = 'admin'
                """, (email,), fetch=True, one=True)
                
                print(f"DEBUG - Resultado da query: {result}")
                print(f"DEBUG - Tipo do resultado: {type(result)}")
                
                if not result:
                    logger.warning(f"Admin não encontrado: {email}")
                    flash('Email ou senha incorretos.', 'danger')
                    return redirect(url_for('admin.login'))
                
                # Verificar se é tupla ou lista
                if isinstance(result, (tuple, list)):
                    # Verificar tamanho da tupla
                    if len(result) < 6:
                        logger.error(f"Tupla muito pequena: {len(result)} colunas")
                        flash('Erro nos dados do usuário. Contate o suporte.', 'danger')
                        return redirect(url_for('admin.login'))
                    
                    user_id = result[0]
                    user_nome = result[1]
                    user_email = result[2]
                    user_senha = result[3]
                    user_tipo = result[4]
                    user_ativo = result[5]
                    
                    print(f"DEBUG - ID: {user_id}, Nome: {user_nome}, Tipo: {user_tipo}, Ativo: {user_ativo}")
                else:
                    # Se for dicionário
                    user_id = result.get('id')
                    user_nome = result.get('nome')
                    user_email = result.get('email')
                    user_senha = result.get('senha')
                    user_tipo = result.get('tipo')
                    user_ativo = result.get('ativo')
                
                # Verificar se está ativo
                if not user_ativo:
                    flash('Esta conta está inativa. Contate o suporte.', 'danger')
                    return redirect(url_for('admin.login'))
                
                # Verificar senha
                senha_valida = False
                
                try:
                    # Tentar verificar com pbkdf2
                    if user_senha and user_senha.startswith('pbkdf2:'):
                        senha_valida = check_password_hash(user_senha, senha)
                        print(f"DEBUG - Verificação pbkdf2: {senha_valida}")
                    
                    # Tentar verificação scrypt
                    elif user_senha and user_senha.startswith('scrypt:'):
                        try:
                            senha_valida = check_password_hash(user_senha, senha)
                            print(f"DEBUG - Verificação scrypt: {senha_valida}")
                            if senha_valida:
                                # Migrar para pbkdf2
                                novo_hash = generate_password_hash(senha, method='pbkdf2:sha256')
                                execute_query("""
                                    UPDATE usuarios SET senha = %s WHERE id = %s
                                """, (novo_hash, user_id), commit=True)
                                print("DEBUG - Senha migrada de scrypt para pbkdf2")
                        except Exception as e:
                            print(f"DEBUG - Erro ao verificar scrypt: {e}")
                            senha_valida = False
                    
                    # Tentar comparação direta (texto plano)
                    elif user_senha == senha:
                        senha_valida = True
                        novo_hash = generate_password_hash(senha, method='pbkdf2:sha256')
                        execute_query("""
                            UPDATE usuarios SET senha = %s WHERE id = %s
                        """, (novo_hash, user_id), commit=True)
                        print("DEBUG - Senha migrada de texto plano para pbkdf2")
                    
                except Exception as e:
                    print(f"DEBUG - Erro ao verificar senha: {e}")
                    traceback.print_exc()
                    senha_valida = False
                
                if not senha_valida:
                    logger.warning(f"Senha incorreta para admin: {email}")
                    flash('Email ou senha incorretos.', 'danger')
                    return redirect(url_for('admin.login'))
                
                # Login bem-sucedido
                session.clear()
                session['user_id'] = user_id
                session['user_name'] = user_nome
                session['user_email'] = user_email
                session['user_type'] = user_tipo
                session['logged_in'] = True
                session['admin_logged_in'] = True
                session.permanent = True
                
                logger.info(f"Admin login bem-sucedido: {email}")
                flash(f'Bem-vindo, {user_nome}!', 'success')
                return redirect(url_for('admin.dashboard'))
                    
            except Exception as e:
                logger.error(f"Erro no login admin: {e}")
                traceback.print_exc()
                flash('Erro ao processar login. Tente novamente.', 'danger')
                return redirect(url_for('admin.login'))
        
        return render_template('admin/login.html')

    # ---------- ROTA DE LOGOUT ----------
    @admin_bp.route('/logout')
    def logout():
        if session.get('user_type') == 'admin':
            logger.info(f"Admin logout: {session.get('user_email')}")
        session.clear()
        flash('Você saiu do sistema.', 'success')
        return redirect(url_for('admin.login'))

    # ---------- ROTA DE RECUPERAÇÃO DE SENHA ----------
    @admin_bp.route('/recuperar-senha', methods=['GET', 'POST'])
    def recuperar_senha():
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            
            if not email:
                flash('Por favor, informe seu email.', 'danger')
                return redirect(url_for('admin.recuperar_senha'))
            
            admin = execute_query("""
                SELECT id, nome, email FROM usuarios 
                WHERE email = %s AND tipo = 'admin'
            """, (email,), fetch=True, one=True)
            
            if admin:
                reset_token = str(uuid.uuid4())
                expiracao = datetime.now() + timedelta(hours=1)
                
                admin_id = admin[0] if isinstance(admin, (tuple, list)) else admin.get('id')
                
                execute_query("""
                    UPDATE usuarios 
                    SET reset_token = %s, reset_token_expira = %s
                    WHERE id = %s
                """, (reset_token, expiracao, admin_id), commit=True)
                
                logger.info(f"Token gerado para: {email}")
                flash('Instruções enviadas para seu email.', 'success')
            else:
                flash('Se o email existir, enviaremos instruções.', 'info')
            
            return redirect(url_for('admin.login'))
        
        return render_template('admin/recuperar_senha.html')

    # ---------- ROTA DE RESET DE SENHA ----------
    @admin_bp.route('/reset-senha/<token>', methods=['GET', 'POST'])
    def reset_senha(token):
        user = execute_query("""
            SELECT id, nome, email 
            FROM usuarios 
            WHERE reset_token = %s AND reset_token_expira > NOW()
        """, (token,), fetch=True, one=True)
        
        if not user:
            flash('Link inválido ou expirado.', 'danger')
            return redirect(url_for('admin.recuperar_senha'))
        
        user_id = user[0] if isinstance(user, (tuple, list)) else user.get('id')
        
        if request.method == 'POST':
            nova_senha = request.form.get('nova_senha', '')
            confirmar_senha = request.form.get('confirmar_senha', '')
            
            if not nova_senha or len(nova_senha) < 6:
                flash('A senha deve ter pelo menos 6 caracteres.', 'danger')
                return render_template('admin/reset_senha.html', token=token)
            
            if nova_senha != confirmar_senha:
                flash('As senhas não coincidem.', 'danger')
                return render_template('admin/reset_senha.html', token=token)
            
            senha_hash = generate_password_hash(nova_senha, method='pbkdf2:sha256')
            
            execute_query("""
                UPDATE usuarios 
                SET senha = %s, reset_token = NULL, reset_token_expira = NULL 
                WHERE id = %s
            """, (senha_hash, user_id), commit=True)
            
            logger.info(f"Senha resetada para admin")
            flash('Senha alterada com sucesso!', 'success')
            return redirect(url_for('admin.login'))
        
        return render_template('admin/reset_senha.html', token=token)

    # ---------- ROTA DE SETUP ----------
    @admin_bp.route('/setup', methods=['GET', 'POST'])
    def setup():
        existe_admin = execute_query("""
            SELECT COUNT(*) as total FROM usuarios WHERE tipo = 'admin'
        """, fetch=True, one=True)
        
        total_admins = existe_admin[0] if existe_admin and isinstance(existe_admin, (tuple, list)) else (existe_admin.get('total') if existe_admin else 0)
        
        if total_admins > 0:
            flash('Já existem administradores no sistema.', 'warning')
            return redirect(url_for('admin.login'))
        
        if request.method == 'POST':
            nome = request.form.get('nome', '').strip()
            email = request.form.get('email', '').strip().lower()
            senha = request.form.get('senha', '')
            confirmar = request.form.get('confirmar_senha', '')
            
            if not nome or not email or not senha:
                flash('Todos os campos são obrigatórios.', 'danger')
                return render_template('admin/setup.html')
            
            if senha != confirmar:
                flash('As senhas não coincidem.', 'danger')
                return render_template('admin/setup.html')
            
            if len(senha) < 6:
                flash('A senha deve ter pelo menos 6 caracteres.', 'danger')
                return render_template('admin/setup.html')
            
            senha_hash = generate_password_hash(senha, method='pbkdf2:sha256')
            user_uuid = str(uuid.uuid4())
            
            execute_query("""
                INSERT INTO usuarios (uuid, nome, email, senha, tipo, ativo, criado_em, atualizado_em)
                VALUES (%s, %s, %s, %s, 'admin', 1, NOW(), NOW())
            """, (user_uuid, nome, email, senha_hash), commit=True)
            
            logger.info(f"Primeiro admin criado: {email}")
            flash('Administrador criado com sucesso! Faça login.', 'success')
            return redirect(url_for('admin.login'))
        
        return render_template('admin/setup.html')
