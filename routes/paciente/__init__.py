from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
import logging
from functools import wraps
from datetime import datetime, timedelta, date

logger = logging.getLogger(__name__)

def init_paciente(mysql, app):
    """Inicializa o blueprint do paciente"""
    
    paciente_bp = Blueprint('paciente', __name__, url_prefix='/paciente')
    
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
        """Obtém o ID do paciente a partir do user_id da sessão"""
        if 'user_id' not in session:
            return None
        if session.get('paciente_id'):
            return session['paciente_id']
        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT id FROM pacientes WHERE usuario_id = %s", (session['user_id'],))
            resultado = cur.fetchone()
            cur.close()
            if resultado:
                paciente_id = resultado[0] if isinstance(resultado, (list, tuple)) else resultado.get('id')
                session['paciente_id'] = paciente_id
                return paciente_id
            return None
        except Exception as e:
            logger.error(f"Erro ao obter paciente_id: {e}")
            return None
    
    def paciente_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Faça login para acessar.', 'warning')
                return redirect(url_for('auth.login'))
            if session.get('user_type') != 'paciente':
                flash('Acesso restrito a pacientes.', 'danger')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated_function
    
    # ========== ROTA DO DASHBOARD ==========
    @paciente_bp.route('/dashboard')
    @paciente_required
    def dashboard():
        try:
            paciente_id = obter_paciente_id()
            if not paciente_id:
                flash('Perfil de paciente não encontrado.', 'danger')
                return redirect(url_for('auth.logout'))
            
            cur = mysql.connection.cursor()
            
            # Buscar dados do paciente
            cur.execute("""
                SELECT u.nome, COALESCE(p.telefone, '') as telefone, 
                       COALESCE(p.endereco, '') as endereco, COALESCE(u.email, '') as email,
                       p.data_nascimento, COALESCE(p.genero, '') as genero
                FROM pacientes p
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE p.id = %s
            """, (paciente_id,))
            row = cur.fetchone()
            
            if row:
                paciente_nome = garantir_string(row[0])
                paciente_telefone = garantir_string(row[1])
                paciente_endereco = garantir_string(row[2])
                paciente_email = garantir_string(row[3])
                paciente_data_nasc = formatar_data(row[4], '%d/%m/%Y') if row[4] else None
                paciente_genero = garantir_string(row[5])
            else:
                paciente_nome = session.get('user_name', 'Paciente')
                paciente_telefone = ''
                paciente_endereco = ''
                paciente_email = ''
                paciente_data_nasc = None
                paciente_genero = ''
            
            # Buscar consultas
            cur.execute("""
                SELECT c.id, COALESCE(mu.nome, 'Médico') as medico_nome, 
                       COALESCE(m.especialidade, 'Clínico Geral') as especialidade, 
                       c.data_hora, COALESCE(c.status, 'agendada') as status
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
                status = c[4] if len(c) > 4 else 'agendada'
                consultas.append({
                    'id': c[0],
                    'medico_nome': garantir_string(c[1]),
                    'especialidade': garantir_string(c[2]),
                    'data_hora': formatar_data(c[3]),
                    'status': status,
                    'status_class': {
                        'agendada': 'warning',
                        'realizada': 'success',
                        'cancelada': 'danger',
                        'confirmada': 'info'
                    }.get(status, 'secondary')
                })
            
            # Estatísticas
            cur.execute("SELECT COUNT(*) FROM consultas WHERE paciente_id = %s", (paciente_id,))
            total_consultas = cur.fetchone()[0] if cur.fetchone() else 0
            
            cur.execute("SELECT COUNT(*) FROM consultas WHERE paciente_id = %s AND DATE(data_hora) = CURDATE()", (paciente_id,))
            consultas_hoje = cur.fetchone()[0] if cur.fetchone() else 0
            
            cur.execute("SELECT COUNT(*) FROM consultas WHERE paciente_id = %s AND status = 'agendada'", (paciente_id,))
            consultas_agendadas = cur.fetchone()[0] if cur.fetchone() else 0
            
            cur.execute("SELECT COUNT(*) FROM consultas WHERE paciente_id = %s AND status = 'realizada'", (paciente_id,))
            consultas_realizadas = cur.fetchone()[0] if cur.fetchone() else 0
            
            cur.execute("SELECT COUNT(*) FROM consultas WHERE paciente_id = %s AND status = 'cancelada'", (paciente_id,))
            consultas_canceladas = cur.fetchone()[0] if cur.fetchone() else 0
            
            cur.close()
            
            stats = {
                'total_consultas': total_consultas,
                'consultas_hoje': consultas_hoje
            }
            
            return render_template('paciente/dashboard.html', 
                                 consultas=consultas,
                                 stats=stats,
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
                                 user=session)
        except Exception as e:
            logger.error(f"Erro no dashboard: {e}")
            flash('Erro ao carregar dashboard. Tente novamente.', 'danger')
            return redirect(url_for('paciente.minhas_consultas'))
    
    # ========== MINHAS CONSULTAS ==========
    @paciente_bp.route('/consultas')
    @paciente_required
    def minhas_consultas():
        try:
            paciente_id = obter_paciente_id()
            if not paciente_id:
                flash('Perfil de paciente não encontrado.', 'danger')
                return redirect(url_for('auth.logout'))
            
            cur = mysql.connection.cursor()
            cur.execute("""
                SELECT c.id, COALESCE(mu.nome, 'Médico') as medico_nome, 
                       COALESCE(m.especialidade, 'Clínico Geral') as especialidade, 
                       c.data_hora, COALESCE(c.status, 'agendada') as status
                FROM consultas c
                JOIN medicos m ON c.medico_id = m.id
                JOIN usuarios mu ON m.usuario_id = mu.id
                WHERE c.paciente_id = %s
                ORDER BY c.data_hora DESC
            """, (paciente_id,))
            consultas_raw = cur.fetchall()
            cur.close()
            
            consultas = []
            for c in consultas_raw:
                status = c[4] if len(c) > 4 else 'agendada'
                consultas.append({
                    'id': c[0],
                    'medico_nome': garantir_string(c[1]),
                    'especialidade': garantir_string(c[2]),
                    'data_hora': formatar_data(c[3]),
                    'data_short': formatar_data(c[3], '%d/%m/%Y'),
                    'hora': formatar_data(c[3], '%H:%M'),
                    'status': status,
                    'status_class': {
                        'agendada': 'warning',
                        'realizada': 'success',
                        'cancelada': 'danger'
                    }.get(status, 'secondary')
                })
            
            return render_template('paciente/consultas.html', consultas=consultas, user=session, user_type='paciente')
        except Exception as e:
            logger.error(f"Erro em minhas_consultas: {e}")
            flash('Erro ao carregar consultas.', 'danger')
            return redirect(url_for('paciente.dashboard'))
    
    # ========== AGENDAR CONSULTA ==========
    @paciente_bp.route('/agendar', methods=['GET', 'POST'])
    @paciente_required
    def agendar_consulta():
        paciente_id = obter_paciente_id()
        if not paciente_id:
            flash('Perfil de paciente não encontrado.', 'danger')
            return redirect(url_for('auth.logout'))
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT m.id, COALESCE(u.nome, 'Médico') as nome, 
                   COALESCE(m.especialidade, 'Clínico Geral') as especialidade
            FROM medicos m
            JOIN usuarios u ON m.usuario_id = u.id
            WHERE u.ativo = 1
            ORDER BY u.nome
        """)
        medicos_raw = cur.fetchall()
        cur.close()
        
        medicos = []
        for m in medicos_raw:
            medicos.append({
                'id': m[0],
                'nome': garantir_string(m[1]),
                'especialidade': garantir_string(m[2])
            })
        
        horarios = ['08:00', '09:00', '10:00', '11:00', '14:00', '15:00', '16:00', '17:00']
        data_minima = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        data_maxima = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        
        if request.method == 'POST':
            medico_id = request.form.get('medico_id')
            data_consulta = request.form.get('data_consulta')
            hora_consulta = request.form.get('hora_consulta')
            sintomas = request.form.get('sintomas', '')
            observacoes = request.form.get('observacoes', '')
            
            if not medico_id or not data_consulta or not hora_consulta:
                flash('Preencha todos os campos.', 'danger')
                return redirect(request.url)
            
            try:
                data_hora = datetime.strptime(f"{data_consulta} {hora_consulta}", "%Y-%m-%d %H:%M")
            except:
                flash('Data/hora inválida.', 'danger')
                return redirect(request.url)
            
            if data_hora <= datetime.now():
                flash('Não é possível agendar em datas passadas.', 'danger')
                return redirect(request.url)
            
            hora = data_hora.hour
            if hora < 8 or hora > 17:
                flash('Horário fora do expediente (8h às 17h).', 'danger')
                return redirect(request.url)
            
            cur = mysql.connection.cursor()
            cur.execute("SELECT COUNT(*) FROM consultas WHERE medico_id = %s AND data_hora = %s AND status != 'cancelada'",
                       (medico_id, data_hora))
            count = cur.fetchone()[0]
            if count > 0:
                cur.close()
                flash('Horário indisponível. Escolha outro horário.', 'danger')
                return redirect(request.url)
            
            try:
                cur.execute("""
                    INSERT INTO consultas (paciente_id, medico_id, data_hora, status, sintomas, observacoes)
                    VALUES (%s, %s, %s, 'agendada', %s, %s)
                """, (paciente_id, medico_id, data_hora, sintomas, observacoes))
                mysql.connection.commit()
                cur.close()
                
                flash('Consulta agendada com sucesso!', 'success')
                return redirect(url_for('paciente.minhas_consultas'))
            except Exception as e:
                mysql.connection.rollback()
                cur.close()
                logger.error(f"Erro ao agendar: {e}")
                flash('Erro ao agendar consulta.', 'danger')
                return redirect(request.url)
        
        return render_template('paciente/agendar_consulta.html', 
                               medicos=medicos, horarios=horarios,
                               data_minima=data_minima, data_maxima=data_maxima,
                               user=session, user_type='paciente')
    
    return paciente_bp
