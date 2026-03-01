from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import uuid
import logging
import random
import string
from datetime import date

logger = logging.getLogger(__name__)

_mysql = None

def set_mysql(mysql_instance):
    global _mysql
    _mysql = mysql_instance


def execute_query_auth(query, params=None, fetch=False):
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


def create_auth_blueprint():
    auth_bp = Blueprint('auth', __name__)

    # ================= INDEX =================
    @auth_bp.route('/')
    def index():
        return render_template('index.html')

    # ================= LOGIN =================
    @auth_bp.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            email = request.form['email']
            password = request.form['password']

            user = execute_query_auth("""
                SELECT id, nome, email, senha, tipo 
                FROM usuarios 
                WHERE email = %s AND ativo = TRUE
            """, (email,), True)

            if not user or user[0][3] != password:
                flash('Email ou senha incorretos.', 'danger')
                return redirect(url_for('auth.login'))

            user_id, nome, _, _, tipo = user[0]

            session['user_id'] = user_id
            session['user_name'] = nome
            session['user_type'] = tipo

            flash('Login realizado com sucesso!', 'success')

            if tipo == 'medico':
                return redirect(url_for('medico.dashboard'))

            if tipo == 'paciente':
                return redirect(url_for('paciente.dashboard'))

            if tipo == 'analista':
                analista = execute_query_auth(
                    "SELECT id FROM analistas WHERE usuario_id = %s",
                    (user_id,), True
                )

                if not analista:
                    flash('Perfil de analista não encontrado. Contacte o administrador.', 'danger')
                    return redirect(url_for('auth.logout'))

                session['analista_id'] = analista[0][0]
                return redirect(url_for('analista.dashboard'))

        return render_template('login.html')

    # ================= REGISTER =================
    @auth_bp.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            nome = request.form['nome']
            email = request.form['email']
            telefone = request.form['telefone']
            senha = request.form['password']
            tipo = request.form['tipo']

            if execute_query_auth("SELECT id FROM usuarios WHERE email = %s", (email,), True):
                flash('Este email já está cadastrado.', 'danger')
                return redirect(url_for('auth.register'))

            user_uuid = str(uuid.uuid4())

            execute_query_auth("""
                INSERT INTO usuarios (uuid, nome, email, senha, telefone, tipo, ativo)
                VALUES (%s, %s, %s, %s, %s, %s, TRUE)
            """, (user_uuid, nome, email, senha, telefone, tipo))

            user_id = execute_query_auth(
                "SELECT id FROM usuarios WHERE email = %s",
                (email,), True
            )[0][0]

            # ===== PACIENTE =====
            if tipo == 'paciente':
                execute_query_auth("""
                    INSERT INTO pacientes (usuario_id, data_nascimento, genero, endereco)
                    VALUES (%s, %s, %s, %s)
                """, (
                    user_id,
                    request.form.get('data_nascimento'),
                    request.form.get('genero'),
                    request.form.get('endereco')
                ))

            # ===== MÉDICO =====
            elif tipo == 'medico':
                execute_query_auth("""
                    INSERT INTO medicos (usuario_id, especialidade, crm)
                    VALUES (%s, %s, %s)
                """, (
                    user_id,
                    request.form.get('especialidade'),
                    request.form.get('crm')
                ))

            # ===== ANALISTA (CORRETO) =====
            elif tipo == 'analista':
                execute_query_auth("""
                    INSERT INTO analistas (
                        usuario_id,
                        especialidade,
                        registro_profissional,
                        telefone,
                        is_supervisor,
                        status,
                        experiencia,
                        carga_horaria_semanal,
                        data_contratacao
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user_id,
                    request.form.get('area_atuacao'),
                    request.form.get('registro_profissional'),
                    telefone,
                    0,
                    'ativo',
                    request.form.get('formacao'),
                    None,
                    date.today()
                ))

            flash('Conta criada com sucesso! Faça login.', 'success')
            return redirect(url_for('auth.login'))

        return render_template('register.html')

    # ================= LOGOUT =================
    @auth_bp.route('/logout')
    def logout():
        session.clear()
        flash('Você saiu da sua conta.', 'info')
        return redirect(url_for('auth.index'))

    # ================= PERFIL =================
    @auth_bp.route('/perfil')
    def perfil():
        if 'user_id' not in session:
            flash('Faça login.', 'warning')
            return redirect(url_for('auth.login'))

        user_id = session['user_id']
        tipo = session['user_type']

        if tipo == 'analista':
            analista = execute_query_auth("""
                SELECT a.*, u.nome, u.email 
                FROM analistas a
                JOIN usuarios u ON u.id = a.usuario_id
                WHERE a.usuario_id = %s
            """, (user_id,), True)

            if analista:
                return render_template('perfil_analista.html', analista=analista[0])

        flash('Perfil não encontrado.', 'danger')
        return redirect(url_for('auth.index'))

    return auth_bp


def init_auth(mysql_instance):
    set_mysql(mysql_instance)
    return create_auth_blueprint()
