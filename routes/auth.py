from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_mysql = None

def set_mysql(mysql_instance):
    global _mysql
    _mysql = mysql_instance


def execute_query_auth(query, params=None, fetch=False, one=False):
    try:
        cur = _mysql.connection.cursor()
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)

        if fetch:
            if one:
                result = cur.fetchone()
            else:
                result = cur.fetchall()
        else:
            _mysql.connection.commit()
            result = None

        cur.close()
        return result
    except Exception as e:
        _mysql.connection.rollback()
        logger.error(f"Database error in auth: {e}")
        return None


def validar_email(email):
    if not email or not isinstance(email, str):
        return False
    email = email.lower().strip()
    padrao = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(padrao, email) is not None


def formatar_email(email):
    if not email:
        return email
    return email.lower().strip()


def verificar_senha(senha_banco, senha_digitada):
    if not senha_banco or not senha_digitada:
        return False
    try:
        if check_password_hash(senha_banco, senha_digitada):
            return True
    except Exception as e:
        logger.error(f"Erro no check_password_hash: {e}")
    if senha_banco == senha_digitada:
        return True
    return False


def create_auth_blueprint():
    auth_bp = Blueprint('auth', __name__)

    @auth_bp.route('/')
    def index():
        return render_template('index.html')

    @auth_bp.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            email = request.form.get('email', '').lower().strip()
            password = request.form.get('password', '')
            
            print(f"Login attempt: {email}")
            
            if not validar_email(email):
                flash('Email inválido.', 'danger')
                return redirect(url_for('auth.login'))
            
            email_formatado = formatar_email(email)

            user = execute_query_auth("""
                SELECT id, nome, email, senha, tipo 
                FROM usuarios 
                WHERE email = %s AND ativo = 1
            """, (email_formatado,), fetch=True, one=True)

            if not user:
                flash('Email ou senha incorretos.', 'danger')
                return redirect(url_for('auth.login'))

            user_id = user['id']
            nome = user['nome']
            senha_banco = user['senha']
            tipo = user['tipo']

            if not verificar_senha(senha_banco, password):
                flash('Email ou senha incorretos.', 'danger')
                return redirect(url_for('auth.login'))
            
            # Configurar sessão
            session.clear()
            session['user_id'] = user_id
            session['user_name'] = nome
            session['user_type'] = tipo
            session['logged_in'] = True

            # Buscar ou criar IDs específicos
            if tipo == 'paciente':
                paciente = execute_query_auth(
                    "SELECT id FROM pacientes WHERE usuario_id = %s",
                    (user_id,), fetch=True, one=True
                )
                if paciente:
                    session['paciente_id'] = paciente['id']
                else:
                    execute_query_auth(
                        "INSERT INTO pacientes (usuario_id) VALUES (%s)",
                        (user_id,)
                    )
                    paciente = execute_query_auth(
                        "SELECT id FROM pacientes WHERE usuario_id = %s",
                        (user_id,), fetch=True, one=True
                    )
                    if paciente:
                        session['paciente_id'] = paciente['id']
            
            elif tipo == 'medico':
                medico = execute_query_auth(
                    "SELECT id FROM medicos WHERE usuario_id = %s",
                    (user_id,), fetch=True, one=True
                )
                if medico:
                    session['medico_id'] = medico['id']
            
            elif tipo == 'farmaceutico':
                farmaceutico = execute_query_auth(
                    "SELECT id FROM farmaceuticos WHERE usuario_id = %s AND ativo = 1",
                    (user_id,), fetch=True, one=True
                )
                if farmaceutico:
                    session['farmaceutico_id'] = farmaceutico['id']

            flash(f'Bem-vindo, {nome}!', 'success')
            
            # REDIRECIONAMENTO DIRETO - SEM try/except
            if tipo == 'paciente':
                return redirect('/paciente/dashboard')
            elif tipo == 'medico':
                return redirect('/medico/dashboard')
            elif tipo == 'farmaceutico':
                return redirect('/farmaceutico/dashboard')
            elif tipo == 'analista':
                return redirect('/analista/dashboard')
            elif tipo == 'enfermeiro':
                return redirect('/enfermeiro/dashboard/')
            elif tipo == 'admin':
                return redirect('/admin/dashboard')
            else:
                return redirect('/')

        return render_template('login.html')

    @auth_bp.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            nome = request.form.get('nome', '')
            email = request.form.get('email', '').lower().strip()
            telefone = request.form.get('telefone', '')
            senha = request.form.get('password', '')
            tipo = request.form.get('tipo', '')
            
            if not nome or not email or not senha or not tipo:
                flash('Todos os campos são obrigatórios.', 'danger')
                return redirect(url_for('auth.register'))
            
            if not validar_email(email):
                flash('Digite um email válido.', 'danger')
                return redirect(url_for('auth.register'))
            
            if len(senha) < 6:
                flash('A senha deve ter pelo menos 6 caracteres.', 'danger')
                return redirect(url_for('auth.register'))
            
            email_formatado = formatar_email(email)

            existing_user = execute_query_auth(
                "SELECT id FROM usuarios WHERE email = %s",
                (email_formatado,), fetch=True, one=True
            )
            
            if existing_user:
                flash('Este email já está cadastrado.', 'danger')
                return redirect(url_for('auth.register'))

            senha_hash = generate_password_hash(senha)
            user_uuid = str(uuid.uuid4())

            execute_query_auth("""
                INSERT INTO usuarios (uuid, nome, email, senha, telefone, tipo, ativo)
                VALUES (%s, %s, %s, %s, %s, %s, 1)
            """, (user_uuid, nome, email_formatado, senha_hash, telefone, tipo))

            user = execute_query_auth(
                "SELECT id FROM usuarios WHERE email = %s",
                (email_formatado,), fetch=True, one=True
            )
            
            if not user:
                flash('Erro ao criar usuário.', 'danger')
                return redirect(url_for('auth.register'))
            
            user_id = user['id']

            if tipo == 'paciente':
                execute_query_auth("INSERT INTO pacientes (usuario_id) VALUES (%s)", (user_id,))
                flash('Conta criada com sucesso! Faça login.', 'success')
            elif tipo == 'medico':
                execute_query_auth("INSERT INTO medicos (usuario_id) VALUES (%s)", (user_id,))
                flash('Conta criada com sucesso! Faça login.', 'success')
            elif tipo == 'farmaceutico':
                execute_query_auth("""
                    INSERT INTO farmaceuticos (usuario_id, crf, especialidade, ativo) 
                    VALUES (%s, %s, %s, 1)
                """, (user_id, 'AGUARDANDO_CRF', 'Aguardando cadastro'))
                flash('Conta de farmacêutico criada! Complete seu cadastro.', 'info')
                return redirect(url_for('auth.completar_cadastro_farmaceutico'))
            else:
                flash('Conta criada com sucesso! Faça login.', 'success')

            return redirect(url_for('auth.login'))

        return render_template('register.html')

    @auth_bp.route('/completar-cadastro-farmaceutico', methods=['GET', 'POST'])
    def completar_cadastro_farmaceutico():
        if request.method == 'POST':
            user_id = session.get('user_id')
            if not user_id:
                flash('Sessão expirada.', 'danger')
                return redirect(url_for('auth.login'))
            
            crf = request.form.get('crf', '').strip().upper()
            especialidade = request.form.get('especialidade', '').strip()
            
            if not crf:
                flash('O CRF é obrigatório.', 'danger')
                return redirect(url_for('auth.completar_cadastro_farmaceutico'))
            
            if len(crf) < 5:
                flash('CRF inválido.', 'danger')
                return redirect(url_for('auth.completar_cadastro_farmaceutico'))
            
            existe_crf = execute_query_auth(
                "SELECT id FROM farmaceuticos WHERE crf = %s AND usuario_id != %s",
                (crf, user_id), fetch=True, one=True
            )
            if existe_crf:
                flash('Este CRF já está cadastrado.', 'danger')
                return redirect(url_for('auth.completar_cadastro_farmaceutico'))
            
            execute_query_auth("""
                UPDATE farmaceuticos 
                SET crf = %s, especialidade = %s, ativo = 1
                WHERE usuario_id = %s
            """, (crf, especialidade, user_id))
            
            flash('Cadastro completo! Faça login.', 'success')
            return redirect(url_for('auth.login'))
        
        return render_template('completar_cadastro_farmaceutico.html')

    @auth_bp.route('/recuperar-senha', methods=['GET', 'POST'])
    def recuperar_senha():
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            
            if not email:
                flash('Informe seu email.', 'danger')
                return redirect(url_for('auth.recuperar_senha'))
            
            if not validar_email(email):
                flash('Email inválido.', 'danger')
                return redirect(url_for('auth.recuperar_senha'))
            
            email_formatado = formatar_email(email)
            
            user = execute_query_auth("""
                SELECT id, nome, email FROM usuarios 
                WHERE email = %s AND ativo = 1
            """, (email_formatado,), fetch=True, one=True)
            
            if user:
                reset_token = str(uuid.uuid4())
                expiracao = datetime.now() + timedelta(hours=1)
                
                execute_query_auth("""
                    UPDATE usuarios 
                    SET reset_token = %s, reset_token_expira = %s
                    WHERE id = %s
                """, (reset_token, expiracao, user['id']))
                
                flash('Instruções enviadas para seu email.', 'success')
            else:
                flash('Se o email existir, instruções serão enviadas.', 'info')
            
            return redirect(url_for('auth.login'))
        
        return render_template('recuperar_senha.html')

    @auth_bp.route('/reset-senha/<token>', methods=['GET', 'POST'])
    def reset_senha(token):
        user = execute_query_auth("""
            SELECT id, nome, email 
            FROM usuarios 
            WHERE reset_token = %s AND reset_token_expira > NOW()
        """, (token,), fetch=True, one=True)
        
        if not user:
            flash('Link inválido ou expirado.', 'danger')
            return redirect(url_for('auth.recuperar_senha'))
        
        user_id = user['id']
        
        if request.method == 'POST':
            nova_senha = request.form.get('nova_senha', '')
            confirmar_senha = request.form.get('confirmar_senha', '')
            
            if not nova_senha or len(nova_senha) < 6:
                flash('A senha deve ter pelo menos 6 caracteres.', 'danger')
                return render_template('reset_senha.html', token=token)
            
            if nova_senha != confirmar_senha:
                flash('As senhas não coincidem.', 'danger')
                return render_template('reset_senha.html', token=token)
            
            senha_hash = generate_password_hash(nova_senha)
            
            execute_query_auth("""
                UPDATE usuarios 
                SET senha = %s, reset_token = NULL, reset_token_expira = NULL 
                WHERE id = %s
            """, (senha_hash, user_id))
            
            flash('Senha alterada com sucesso! Faça login.', 'success')
            return redirect(url_for('auth.login'))
        
        return render_template('reset_senha.html', token=token)

    @auth_bp.route('/logout')
    def logout():
        session.clear()
        flash('Você saiu da sua conta.', 'info')
        return redirect(url_for('auth.index'))

    return auth_bp


def init_auth(mysql_instance):
    set_mysql(mysql_instance)
    return create_auth_blueprint()
