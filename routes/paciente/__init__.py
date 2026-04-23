from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
import logging
from functools import wraps
from datetime import datetime, timedelta, date

logger = logging.getLogger(__name__)

def init_paciente(mysql, app):
    paciente_bp = Blueprint('paciente', __name__, url_prefix='/paciente')

    # =========================
    # HELPERS
    # =========================
    def garantir_string(valor):
        if valor is None:
            return ''
        if isinstance(valor, bytes):
            try:
                return valor.decode('utf-8')
            except:
                return str(valor)
        return str(valor)

    def formatar_data(data, formato='%d/%m/%Y %H:%M'):
        if not data:
            return ''
        if isinstance(data, (datetime, date)):
            return data.strftime(formato)
        return str(data)

    def obter_paciente_id():
        return session.get('paciente_id')

    # =========================
    # MIDDLEWARE PROFISSIONAL
    # =========================
    def paciente_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Faça login.', 'warning')
                return redirect(url_for('auth.login'))

            if session.get('user_type') != 'paciente':
                flash('Acesso restrito.', 'danger')
                return redirect(url_for('auth.login'))

            # 🔥 garante paciente automaticamente
            if 'paciente_id' not in session:
                try:
                    cur = mysql.connection.cursor()
                    cur.execute("SELECT id FROM pacientes WHERE usuario_id = %s", (session['user_id'],))
                    paciente = cur.fetchone()

                    if paciente:
                        session['paciente_id'] = paciente[0]
                    else:
                        cur.execute("INSERT INTO pacientes (usuario_id) VALUES (%s)", (session['user_id'],))
                        mysql.connection.commit()

                        cur.execute("SELECT id FROM pacientes WHERE usuario_id = %s", (session['user_id'],))
                        paciente = cur.fetchone()
                        session['paciente_id'] = paciente[0]

                    cur.close()
                except Exception as e:
                    logger.error(f"Erro ao garantir paciente: {e}")
                    flash('Erro interno.', 'danger')
                    return redirect(url_for('auth.logout'))

            return f(*args, **kwargs)
        return decorated_function

    # =========================
    # DASHBOARD
    # =========================
    @paciente_bp.route('/dashboard')
    @paciente_required
    def dashboard():
        try:
            paciente_id = obter_paciente_id()

            cur = mysql.connection.cursor()

            # PERFIL
            cur.execute("""
                SELECT u.nome, COALESCE(p.telefone,''), COALESCE(p.endereco,''), COALESCE(u.email,''),
                       p.data_nascimento, COALESCE(p.genero,'')
                FROM pacientes p
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE p.id = %s
            """, (paciente_id,))
            row = cur.fetchone()

            paciente_nome = garantir_string(row[0]) if row else session.get('user_name', 'Paciente')
            paciente_telefone = garantir_string(row[1]) if row else ''
            paciente_endereco = garantir_string(row[2]) if row else ''
            paciente_email = garantir_string(row[3]) if row else ''
            paciente_data_nasc = formatar_data(row[4], '%d/%m/%Y') if row else ''
            paciente_genero = garantir_string(row[5]) if row else ''

            # CONSULTAS
            cur.execute("""
                SELECT c.id, COALESCE(mu.nome,'Médico'), COALESCE(m.especialidade,'Clínico Geral'),
                       c.data_hora, COALESCE(c.status,'agendada')
                FROM consultas c
                JOIN medicos m ON c.medico_id = m.id
                JOIN usuarios mu ON m.usuario_id = mu.id
                WHERE c.paciente_id = %s
                ORDER BY c.data_hora DESC
                LIMIT 10
            """, (paciente_id,))
            consultas_raw = cur.fetchall()

            consultas = []
            for c in consultas_raw:
                consultas.append({
                    'id': c[0],
                    'medico_nome': garantir_string(c[1]),
                    'especialidade': garantir_string(c[2]),
                    'data_hora': formatar_data(c[3]),
                    'status': c[4],
                    'status_class': {
                        'agendada': 'warning',
                        'realizada': 'success',
                        'cancelada': 'danger',
                        'confirmada': 'info'
                    }.get(c[4], 'secondary')
                })

            # STATS
            def count(query):
                cur.execute(query, (paciente_id,))
                row = cur.fetchone()
                return row[0] if row else 0

            total_consultas = count("SELECT COUNT(*) FROM consultas WHERE paciente_id = %s")
            consultas_hoje = count("SELECT COUNT(*) FROM consultas WHERE paciente_id = %s AND DATE(data_hora)=CURDATE()")
            consultas_agendadas = count("SELECT COUNT(*) FROM consultas WHERE paciente_id = %s AND status='agendada'")
            consultas_realizadas = count("SELECT COUNT(*) FROM consultas WHERE paciente_id = %s AND status='realizada'")
            consultas_canceladas = count("SELECT COUNT(*) FROM consultas WHERE paciente_id = %s AND status='cancelada'")

            cur.close()

            return render_template(
                'paciente/dashboard.html',
                consultas=consultas,
                stats={
                    'total_consultas': total_consultas,
                    'consultas_hoje': consultas_hoje
                },
                consultas_agendadas=consultas_agendadas,
                consultas_realizadas=consultas_realizadas,
                consultas_canceladas=consultas_canceladas,
                consultas_hoje=consultas_hoje,
                paciente_id=paciente_id,
                paciente_nome=paciente_nome,
                paciente_data_nasc=paciente_data_nasc,
                paciente_genero=paciente_genero,
                paciente_telefone=paciente_telefone,
                paciente_endereco=paciente_endereco,
                paciente_email=paciente_email,
                user=session
            )

        except Exception as e:
            logger.error(f"Erro no dashboard: {e}")
            flash('Erro ao carregar dashboard.', 'danger')
            return redirect(url_for('paciente.minhas_consultas'))

    # =========================
    # CONSULTAS
    # =========================
    @paciente_bp.route('/consultas')
    @paciente_required
    def minhas_consultas():
        try:
            paciente_id = obter_paciente_id()

            cur = mysql.connection.cursor()
            cur.execute("""
                SELECT c.id, mu.nome, m.especialidade, c.data_hora, c.status
                FROM consultas c
                JOIN medicos m ON c.medico_id = m.id
                JOIN usuarios mu ON m.usuario_id = mu.id
                WHERE c.paciente_id = %s
                ORDER BY c.data_hora DESC
            """, (paciente_id,))
            data = cur.fetchall()
            cur.close()

            consultas = []
            for c in data:
                consultas.append({
                    'id': c[0],
                    'medico_nome': garantir_string(c[1]),
                    'especialidade': garantir_string(c[2]),
                    'data_hora': formatar_data(c[3]),
                    'status': c[4]
                })

            return render_template('paciente/consultas.html', consultas=consultas, user=session)

        except Exception as e:
            logger.error(e)
            flash('Erro ao carregar consultas.', 'danger')
            return redirect(url_for('paciente.dashboard'))

    return paciente_bp
