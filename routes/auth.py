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


def execute_query_auth(query, params=None, fetch=False):
    """Executa query sem conversão de bytes (texto plano)"""
    try:
        cur = _mysql.connection.cursor()
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)

        if fetch:
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
    """Valida qualquer email válido"""
    if not email or not isinstance(email, str):
        return False
    
    email = email.lower().strip()
    padrao = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    return re.match(padrao, email) is not None


def formatar_email(email):
    """Formata email removendo espaços e convertendo para minúsculas"""
    if not email:
        return email
    
    return email.lower().strip()


def verificar_senha(senha_banco, senha_digitada):
    """Verifica senha suportando múltiplos formatos"""
    
    # 1. Tentar verificar como hash do werkzeug
    try:
        if check_password_hash(senha_banco, senha_digitada):
            return True
    except:
        pass
    
    # 2. Comparação direta (texto plano)
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
            email = request.form['email'].lower().strip()
            password = request.form['password']
            
            print(f"Email digitado: {email}")
            
            if not validar_email(email):
                flash('Email inválido. Digite um email válido.', 'danger')
                return redirect(url_for('auth.login'))
            
            email_formatado = formatar_email(email)
            print(f"Email formatado: {email_formatado}")

            # Buscar usuário
            user = execute_query_auth("""
                SELECT id, nome, email, senha, tipo 
                FROM usuarios 
                WHERE email = %s AND ativo = 1
            """, (email_formatado,), True)

            print(f"Resultado query: {user}")

            if not user or len(user) == 0:
                print("Usuário não encontrado!")
                flash('Email ou senha incorretos.', 'danger')
                return redirect(url_for('auth.login'))

            user_id, nome, email_bd, senha_banco, tipo = user[0]
            print(f"Usuário encontrado: ID={user_id}, Nome={nome}, Tipo={tipo}")

            # Verificar senha
            if not verificar_senha(senha_banco, password):
                print("Senha incorreta!")
                flash('Email ou senha incorretos.', 'danger')
                return redirect(url_for('auth.login'))
            
            # Configurar sessão
            session.clear()
            session['user_id'] = user_id
            session['user_name'] = nome
            session['user_type'] = tipo
            session['logged_in'] = True
            session.modified = True
            
            print(f"Sessão configurada: user_type={tipo}")

            flash('Login realizado com sucesso!', 'success')

            # Redirecionamentos
            if tipo == 'medico':
                medico = execute_query_auth(
                    "SELECT id FROM medicos WHERE usuario_id = %s",
                    (user_id,), True
                )
                if medico:
                    session['medico_id'] = medico[0][0]
                return redirect(url_for('medico.dashboard'))
            
            elif tipo == 'paciente':
                paciente = execute_query_auth(
                    "SELECT id FROM pacientes WHERE usuario_id = %s",
                    (user_id,), True
                )
                if paciente:
                    session['paciente_id'] = paciente[0][0]
                return redirect(url_for('paciente.dashboard'))
            
            elif tipo == 'analista':
                analista = execute_query_auth(
                    "SELECT id FROM analistas WHERE usuario_id = %s",
                    (user_id,), True
                )
                if analista:
                    session['analista_id'] = analista[0][0]
                return redirect(url_for('analista.dashboard'))
            
            elif tipo == 'enfermeiro':
                enfermeiro = execute_query_auth(
                    "SELECT id FROM enfermeiros WHERE usuario_id = %s",
                    (user_id,), True
                )
                if enfermeiro:
                    session['enfermeiro_id'] = enfermeiro[0][0]
                return redirect(url_for('enfermeiro.dashboard.index'))
            
            elif tipo == 'farmaceutico':
                farmaceutico = execute_query_auth("""
                    SELECT id, crf, especialidade 
                    FROM farmaceuticos 
                    WHERE usuario_id = %s AND ativo = 1
                """, (user_id,), True)
                
                if farmaceutico:
                    session['farmaceutico_id'] = farmaceutico[0][0]
                    session['farmaceutico_crf'] = farmaceutico[0][1] if farmaceutico[0][1] else ''
                    session['farmaceutico_especialidade'] = farmaceutico[0][2] if farmaceutico[0][2] else ''
                    print(f"Farmacêutico logado: ID={session['farmaceutico_id']}")
                    return redirect(url_for('farmaceutico.dashboard'))
                else:
                    print("FARMACÊUTICO NÃO ENCONTRADO!")
                    flash('Dados do farmacêutico não encontrados. Contate o suporte.', 'danger')
                    return redirect(url_for('auth.logout'))
            
            # Admin
            elif tipo == 'admin':
                return redirect(url_for('admin.dashboard'))
            
            # Outros tipos
            else:
                return redirect(url_for('dashboard'))

        return render_template('login.html')

    @auth_bp.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            nome = request.form['nome']
            email = request.form['email'].lower().strip()
            telefone = request.form['telefone']
            senha = request.form['password']
            tipo = request.form['tipo']
            
            if not validar_email(email):
                flash('Digite um email válido.', 'danger')
                return redirect(url_for('auth.register'))
            
            email_formatado = formatar_email(email)

            # Verificar se email já existe
            existing = execute_query_auth(
                "SELECT id FROM usuarios WHERE email = %s",
                (email_formatado,), True
            )
            if existing and len(existing) > 0:
                flash('Este email já está cadastrado.', 'danger')
                return redirect(url_for('auth.register'))

            senha_hash = generate_password_hash(senha)

            # Inserir usuário
            execute_query_auth("""
                INSERT INTO usuarios (uuid, nome, email, senha, telefone, tipo, ativo)
                VALUES (%s, %s, %s, %s, %s, %s, 1)
            """, (
                str(uuid.uuid4()),
                nome,
                email_formatado,
                senha_hash,
                telefone,
                tipo
            ))

            # Buscar ID do usuário criado
            user_result = execute_query_auth(
                "SELECT id FROM usuarios WHERE email = %s",
                (email_formatado,), True
            )
            
            if user_result and len(user_result) > 0:
                user_id = user_result[0][0]

                # Inserir na tabela específica conforme tipo
                if tipo == 'paciente':
                    execute_query_auth(
                        "INSERT INTO pacientes (usuario_id) VALUES (%s)",
                        (user_id,)
                    )
                elif tipo == 'medico':
                    execute_query_auth(
                        "INSERT INTO medicos (usuario_id) VALUES (%s)",
                        (user_id,)
                    )
                elif tipo == 'analista':
                    execute_query_auth(
                        "INSERT INTO analistas (usuario_id, status) VALUES (%s, 'ativo')",
                        (user_id,)
                    )
                elif tipo == 'enfermeiro':
                    execute_query_auth(
                        "INSERT INTO enfermeiros (usuario_id) VALUES (%s)",
                        (user_id,)
                    )
                elif tipo == 'farmaceutico':
                    execute_query_auth("""
                        INSERT INTO farmaceuticos (usuario_id, crf, especialidade, ativo) 
                        VALUES (%s, %s, %s, 1)
                    """, (user_id, 'AGUARDANDO_CRF', 'Aguardando cadastro'))
                    
                    flash('Conta de farmacêutico criada! Complete seu cadastro com CRF.', 'info')
                    return redirect(url_for('auth.completar_cadastro_farmaceutico'))

            flash('Conta criada com sucesso! Faça login.', 'success')
            return redirect(url_for('auth.login'))

        return render_template('register.html')

    @auth_bp.route('/completar-cadastro-farmaceutico', methods=['GET', 'POST'])
    def completar_cadastro_farmaceutico():
        user_id = session.get('user_id')
        if not user_id:
            flash('Sessão expirada. Faça login novamente.', 'danger')
            return redirect(url_for('auth.login'))
        
        if request.method == 'POST':
            crf = request.form.get('crf', '').strip().upper()
            especialidade = request.form.get('especialidade', '').strip()
            
            if not crf or len(crf) < 5:
                flash('CRF inválido. Digite um CRF válido (mínimo 5 caracteres).', 'danger')
                return redirect(url_for('auth.completar_cadastro_farmaceutico'))
            
            # Verificar se CRF já existe
            existe = execute_query_auth(
                "SELECT id FROM farmaceuticos WHERE crf = %s AND usuario_id != %s",
                (crf, user_id), True
            )
            if existe and len(existe) > 0:
                flash('Este CRF já está cadastrado para outro farmacêutico.', 'danger')
                return redirect(url_for('auth.completar_cadastro_farmaceutico'))
            
            # Atualizar dados do farmacêutico
            execute_query_auth("""
                UPDATE farmaceuticos 
                SET crf = %s, especialidade = %s, ativo = 1
                WHERE usuario_id = %s
            """, (crf, especialidade, user_id))
            
            # Atualizar sessão
            session['farmaceutico_crf'] = crf
            session['farmaceutico_especialidade'] = especialidade
            
            flash('Cadastro completo! Agora você pode acessar o sistema.', 'success')
            return redirect(url_for('auth.login'))
        
        return render_template('completar_cadastro_farmaceutico.html')

    @auth_bp.route('/recuperar-senha', methods=['GET', 'POST'])
    def recuperar_senha():
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            
            if not email:
                flash('Por favor, informe seu email.', 'danger')
                return redirect(url_for('auth.recuperar_senha'))
            
            if not validar_email(email):
                flash('Digite um email válido.', 'danger')
                return redirect(url_for('auth.recuperar_senha'))
            
            email_formatado = formatar_email(email)
            
            user = execute_query_auth("""
                SELECT id, nome, email, tipo FROM usuarios 
                WHERE email = %s AND ativo = 1
            """, (email_formatado,), True)
            
            if user and len(user) > 0:
                reset_token = str(uuid.uuid4())
                expiracao = datetime.now() + timedelta(hours=1)
                
                execute_query_auth("""
                    UPDATE usuarios 
                    SET reset_token = %s, reset_token_expira = %s
                    WHERE id = %s
                """, (reset_token, expiracao, user[0][0]))
                
                logger.info(f"Token de recuperação gerado para: {email_formatado}")
                flash('Instruções de recuperação enviadas para seu email.', 'success')
            else:
                logger.info(f"Email não encontrado: {email_formatado}")
                flash('Se o email existir no sistema, instruções serão enviadas.', 'info')
            
            return redirect(url_for('auth.login'))
        
        return render_template('recuperar_senha.html')

    @auth_bp.route('/reset-senha/<token>', methods=['GET', 'POST'])
    def reset_senha(token):
        user = execute_query_auth("""
            SELECT id, nome, email FROM usuarios 
            WHERE reset_token = %s AND reset_token_expira > NOW()
        """, (token,), True)
        
        if not user or len(user) == 0:
            flash('Link inválido ou expirado. Solicite nova recuperação.', 'danger')
            return redirect(url_for('auth.recuperar_senha'))
        
        user_id, nome, email = user[0]
        
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
            
            logger.info(f"Senha resetada para: {email}")
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
