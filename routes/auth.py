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
            result = cur.fetchall()
            if one and result:
                result = result[0]
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
    """Verifica senha de forma robusta - suporta hash e texto plano"""
    if not senha_banco or not senha_digitada:
        return False
    
    # 1. Tentar verificar como hash do werkzeug
    try:
        if check_password_hash(senha_banco, senha_digitada):
            print("✅ Senha verificada com hash (werkzeug)")
            return True
    except Exception as e:
        print(f"Erro no check_password_hash: {e}")
    
    # 2. Comparação direta (texto plano - fallback)
    if senha_banco == senha_digitada:
        print("✅ Senha verificada como texto plano")
        return True
    
    print("❌ Senha incorreta")
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
            
            print(f"\n===== LOGIN DEBUG =====")
            print(f"Email digitado: {email}")
            
            if not validar_email(email):
                flash('Email inválido.', 'danger')
                return redirect(url_for('auth.login'))
            
            email_formatado = formatar_email(email)
            print(f"Email formatado: {email_formatado}")

            # Buscar usuário
            user = execute_query_auth("""
                SELECT id, nome, email, senha, tipo 
                FROM usuarios 
                WHERE email = %s AND ativo = 1
            """, (email_formatado,), fetch=True, one=True)

            print(f"Resultado query: {user}")

            if not user:
                print("Usuário não encontrado!")
                flash('Email ou senha incorretos.', 'danger')
                return redirect(url_for('auth.login'))

            # Extrair dados
            if isinstance(user, dict):
                user_id = user['id']
                nome = user['nome']
                senha_banco = user['senha']
                tipo = user['tipo']
            else:
                user_id, nome, _, senha_banco, tipo = user

            # Decodificar bytes se necessário
            if isinstance(nome, bytes):
                nome = nome.decode('utf-8')
            if isinstance(email, bytes):
                email = email.decode('utf-8')

            print(f"Usuário encontrado: ID={user_id}, Nome={nome}, Tipo={tipo}")
            print(f"Hash da senha no banco: {senha_banco[:50]}...")

            # Verificar senha
            if not verificar_senha(senha_banco, password):
                flash('Email ou senha incorretos.', 'danger')
                return redirect(url_for('auth.login'))
            
            print("✅ Senha correta!")
            
            # Buscar IDs específicos conforme tipo
            medico_id = None
            paciente_id = None
            analista_id = None
            enfermeiro_id = None
            farmaceutico_id = None
            
            if tipo == 'medico':
                medico = execute_query_auth(
                    "SELECT id FROM medicos WHERE usuario_id = %s",
                    (user_id,), fetch=True, one=True
                )
                if medico:
                    medico_id = medico[0] if isinstance(medico, (list, tuple)) else medico.get('id')
                    print(f"Médico ID encontrado: {medico_id}")
            
            elif tipo == 'paciente':
                paciente = execute_query_auth(
                    "SELECT id FROM pacientes WHERE usuario_id = %s",
                    (user_id,), fetch=True, one=True
                )
                if paciente:
                    paciente_id = paciente[0] if isinstance(paciente, (list, tuple)) else paciente.get('id')
                    print(f"Paciente ID encontrado: {paciente_id}")
            
            elif tipo == 'analista':
                analista = execute_query_auth(
                    "SELECT id FROM analistas WHERE usuario_id = %s",
                    (user_id,), fetch=True, one=True
                )
                if analista:
                    analista_id = analista[0] if isinstance(analista, (list, tuple)) else analista.get('id')
                    print(f"Analista ID encontrado: {analista_id}")
            
            elif tipo == 'enfermeiro':
                enfermeiro = execute_query_auth(
                    "SELECT id FROM enfermeiros WHERE usuario_id = %s",
                    (user_id,), fetch=True, one=True
                )
                if enfermeiro:
                    enfermeiro_id = enfermeiro[0] if isinstance(enfermeiro, (list, tuple)) else enfermeiro.get('id')
                    print(f"Enfermeiro ID encontrado: {enfermeiro_id}")
            
            elif tipo == 'farmaceutico':
                farmaceutico = execute_query_auth(
                    "SELECT id FROM farmaceuticos WHERE usuario_id = %s",
                    (user_id,), fetch=True, one=True
                )
                if farmaceutico:
                    farmaceutico_id = farmaceutico[0] if isinstance(farmaceutico, (list, tuple)) else farmaceutico.get('id')
                    print(f"Farmacêutico ID encontrado: {farmaceutico_id}")
            
            # Configurar sessão
            session.clear()
            session['user_id'] = user_id
            session['user_name'] = nome
            session['user_type'] = tipo
            session['logged_in'] = True
            session.permanent = True
            
            if medico_id:
                session['medico_id'] = medico_id
            if paciente_id:
                session['paciente_id'] = paciente_id
            if analista_id:
                session['analista_id'] = analista_id
            if enfermeiro_id:
                session['enfermeiro_id'] = enfermeiro_id
            if farmaceutico_id:
                session['farmaceutico_id'] = farmaceutico_id
            
            print(f"Sessão configurada: {dict(session)}")

            flash('Login realizado com sucesso!', 'success')

            # Redirecionamentos
            if tipo == 'medico':
                return redirect(url_for('medico.dashboard'))
            elif tipo == 'paciente':
                return redirect(url_for('paciente.dashboard'))
            elif tipo == 'analista':
                return redirect(url_for('analista.dashboard'))
            elif tipo == 'enfermeiro':
                return redirect(url_for('enfermeiro.dashboard.index'))
            elif tipo == 'farmaceutico':
                return redirect(url_for('farmaceutico.dashboard'))
            elif tipo == 'admin':
                return redirect(url_for('admin.dashboard'))
            else:
                return redirect(url_for('dashboard'))

        return render_template('login.html')

    @auth_bp.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            nome = request.form.get('nome', '')
            email = request.form.get('email', '').lower().strip()
            telefone = request.form.get('telefone', '')
            senha = request.form.get('password', '')
            tipo = request.form.get('tipo', 'paciente')

            if not validar_email(email):
                flash('Digite um email válido.', 'danger')
                return redirect(url_for('auth.register'))

            email_formatado = formatar_email(email)

            existing = execute_query_auth(
                "SELECT id FROM usuarios WHERE email = %s",
                (email_formatado,), fetch=True, one=True
            )
            if existing:
                flash('Este email já está cadastrado.', 'danger')
                return redirect(url_for('auth.register'))

            senha_hash = generate_password_hash(senha)
            execute_query_auth("""
                INSERT INTO usuarios (uuid, nome, email, senha, telefone, tipo, ativo)
                VALUES (%s, %s, %s, %s, %s, %s, 1)
            """, (str(uuid.uuid4()), nome, email_formatado, senha_hash, telefone, tipo))

            user_result = execute_query_auth(
                "SELECT id FROM usuarios WHERE email = %s",
                (email_formatado,), fetch=True, one=True
            )

            if user_result:
                if isinstance(user_result, dict):
                    user_id = user_result['id']
                elif isinstance(user_result, (list, tuple)):
                    user_id = user_result[0]
                else:
                    user_id = user_result

                if tipo == 'paciente':
                    execute_query_auth("INSERT INTO pacientes (usuario_id) VALUES (%s)", (user_id,))
                elif tipo == 'medico':
                    execute_query_auth("INSERT INTO medicos (usuario_id) VALUES (%s)", (user_id,))
                elif tipo == 'analista':
                    execute_query_auth("INSERT INTO analistas (usuario_id, status) VALUES (%s, 'ativo')", (user_id,))
                elif tipo == 'enfermeiro':
                    execute_query_auth("INSERT INTO enfermeiros (usuario_id) VALUES (%s)", (user_id,))
                elif tipo == 'farmaceutico':
                    execute_query_auth("""
                        INSERT INTO farmaceuticos (usuario_id, crf, especialidade, ativo) 
                        VALUES (%s, %s, %s, 1)
                    """, (user_id, 'AGUARDANDO_CRF', 'Aguardando cadastro'))
                    flash('Conta de farmacêutico criada! Complete seu cadastro.', 'info')
                    return redirect(url_for('auth.completar_cadastro_farmaceutico'))

            flash('Conta criada com sucesso! Faça login.', 'success')
            return redirect(url_for('auth.login'))

        return render_template('register.html')

    @auth_bp.route('/completar-cadastro-farmaceutico', methods=['GET', 'POST'])
    def completar_cadastro_farmaceutico():
        user_id = session.get('user_id')
        if not user_id:
            flash('Sessão expirada.', 'danger')
            return redirect(url_for('auth.login'))
        
        if request.method == 'POST':
            crf = request.form.get('crf', '').strip().upper()
            especialidade = request.form.get('especialidade', '').strip()
            
            if not crf or len(crf) < 5:
                flash('CRF inválido.', 'danger')
                return redirect(url_for('auth.completar_cadastro_farmaceutico'))
            
            existe = execute_query_auth(
                "SELECT id FROM farmaceuticos WHERE crf = %s AND usuario_id != %s",
                (crf, user_id), fetch=True, one=True
            )
            if existe:
                flash('CRF já cadastrado.', 'danger')
                return redirect(url_for('auth.completar_cadastro_farmaceutico'))
            
            execute_query_auth("""
                UPDATE farmaceuticos SET crf = %s, especialidade = %s, ativo = 1
                WHERE usuario_id = %s
            """, (crf, especialidade, user_id))
            
            session['farmaceutico_crf'] = crf
            session['farmaceutico_especialidade'] = especialidade
            
            flash('Cadastro completo!', 'success')
            return redirect(url_for('auth.login'))
        
        return render_template('completar_cadastro_farmaceutico.html')

    @auth_bp.route('/recuperar-senha', methods=['GET', 'POST'])
    def recuperar_senha():
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            
            if not email or not validar_email(email):
                flash('Digite um email válido.', 'danger')
                return redirect(url_for('auth.recuperar_senha'))
            
            email_formatado = formatar_email(email)
            
            user = execute_query_auth("""
                SELECT id, nome, email, tipo FROM usuarios 
                WHERE email = %s AND ativo = 1
            """, (email_formatado,), fetch=True, one=True)
            
            if user:
                reset_token = str(uuid.uuid4())
                expiracao = datetime.now() + timedelta(hours=1)
                
                if isinstance(user, dict):
                    user_id = user['id']
                else:
                    user_id = user[0]
                
                execute_query_auth("""
                    UPDATE usuarios 
                    SET reset_token = %s, reset_token_expira = %s
                    WHERE id = %s
                """, (reset_token, expiracao, user_id))
                
                flash('Instruções enviadas para o email.', 'success')
            else:
                flash('Se o email existir, enviaremos instruções.', 'info')
            
            return redirect(url_for('auth.login'))
        
        return render_template('recuperar_senha.html')

    @auth_bp.route('/reset-senha/<token>', methods=['GET', 'POST'])
    def reset_senha(token):
        user = execute_query_auth("""
            SELECT id, nome, email FROM usuarios 
            WHERE reset_token = %s AND reset_token_expira > NOW()
        """, (token,), fetch=True, one=True)
        
        if not user:
            flash('Link inválido ou expirado.', 'danger')
            return redirect(url_for('auth.recuperar_senha'))
        
        if isinstance(user, dict):
            user_id = user['id']
            nome = user['nome']
            email = user['email']
        else:
            user_id, nome, email = user
        
        if request.method == 'POST':
            nova_senha = request.form.get('nova_senha', '')
            confirmar_senha = request.form.get('confirmar_senha', '')
            
            if not nova_senha or len(nova_senha) < 6:
                flash('Senha deve ter pelo menos 6 caracteres.', 'danger')
                return render_template('reset_senha.html', token=token)
            
            if nova_senha != confirmar_senha:
                flash('As senhas não coincidem.', 'danger')
                return render_template('reset_senha.html', token=token)
            
            senha_hash = generate_password_hash(nova_senha)
            
            execute_query_auth("""
                UPDATE usuarios SET senha = %s, reset_token = NULL, reset_token_expira = NULL WHERE id = %s
            """, (senha_hash, user_id))
            
            flash('Senha alterada com sucesso!', 'success')
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
