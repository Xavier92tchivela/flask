from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
import logging
from functools import wraps
from datetime import datetime, timedelta, date

logger = logging.getLogger(__name__)

def init_paciente(mysql, app):
    paciente_bp = Blueprint('paciente', __name__, url_prefix='/paciente')
    
    def garantir_string(valor):
        if valor is None:
            return ''
        if isinstance(valor, bytes):
            try:
                return valor.decode('utf-8')
            except:
                return str(valor)
        return str(valor) if valor is not None else ''
    
    def formatar_data(data, formato='%d/%m/%Y %H:%M'):
        if not data:
            return ''
        if isinstance(data, datetime):
            return data.strftime(formato)
        if isinstance(data, date):
            return data.strftime(formato)
        return str(data)
    
    # ------------------------------------------------------------
    # FUNÇÃO CORRIGIDA: retorna None se não existir, nunca 0
    # ------------------------------------------------------------
    def obter_paciente_id():
        if 'user_id' not in session or session.get('user_type') != 'paciente':
            return None
        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT id FROM pacientes WHERE usuario_id = %s", (session['user_id'],))
            resultado = cur.fetchone()
            cur.close()
            if resultado:
                return resultado[0]   # pode ser 0? não, id é auto-incremento, começa em 1
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
                flash('Acesso restrito a pacientes.', 'warning')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated_function
    
    # ================= DASHBOARD CORRIGIDO =================
    @paciente_bp.route('/dashboard')
    @paciente_required
    def dashboard():
        try:
            paciente_id = obter_paciente_id()
            # Se não encontrar paciente, redireciona com mensagem clara
            if paciente_id is None:
                flash('Seu usuário não está associado a um perfil de paciente. Contate o suporte.', 'danger')
                return redirect(url_for('auth.logout'))
            
            cur = mysql.connection.cursor()
            
            # Dados do paciente
            cur.execute("""
                SELECT p_u.nome, COALESCE(p.telefone, '') as telefone, 
                       COALESCE(p.endereco, '') as endereco, COALESCE(p_u.email, '') as email,
                       p.data_nascimento, COALESCE(p.genero, '') as genero
                FROM pacientes p 
                JOIN usuarios p_u ON p.usuario_id = p_u.id 
                WHERE p.id = %s
            """, (paciente_id,))
            row = cur.fetchone()
            
            if row:
                paciente_nome = garantir_string(row[0]) if row[0] else 'Paciente'
                paciente_telefone = garantir_string(row[1])
                paciente_endereco = garantir_string(row[2])
                paciente_email = garantir_string(row[3])
                paciente_data_nasc = formatar_data(row[4] if len(row) > 4 else None, '%d/%m/%Y')
                paciente_genero = garantir_string(row[5]) if len(row) > 5 else ''
            else:
                # fallback (nunca deveria acontecer, mas seguro)
                paciente_nome = session.get('user_name', 'Paciente')
                paciente_telefone = ''
                paciente_endereco = ''
                paciente_email = ''
                paciente_data_nasc = ''
                paciente_genero = ''
            
            # Consultas recentes
            cur.execute("""
                SELECT c.id, COALESCE(m_u.nome, 'Médico') as medico_nome, 
                       COALESCE(m.especialidade, 'Clínico Geral') as especialidade, 
                       c.data_hora, COALESCE(c.status, 'agendada') as status
                FROM consultas c 
                JOIN medicos m ON c.medico_id = m.id 
                JOIN usuarios m_u ON m.usuario_id = m_u.id 
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
                    'status': garantir_string(status),
                    'status_class': {
                        'agendada': 'warning', 'realizada': 'success',
                        'cancelada': 'danger', 'confirmada': 'info'
                    }.get(status, 'secondary')
                })
            
            # --- CORREÇÃO CRÍTICA: fetchone() usado uma única vez por consulta ---
            cur.execute("SELECT COUNT(*) FROM consultas WHERE paciente_id = %s", (paciente_id,))
            total_consultas = cur.fetchone()[0] if cur.fetchone() else 0  # <-- CORRIGIDO
            
            cur.execute("SELECT COUNT(*) FROM consultas WHERE paciente_id = %s AND DATE(data_hora) = CURDATE()", (paciente_id,))
            row_hoje = cur.fetchone()
            consultas_hoje = row_hoje[0] if row_hoje else 0
            
            cur.execute("SELECT COUNT(*) FROM consultas WHERE paciente_id = %s AND status = 'agendada'", (paciente_id,))
            row_agd = cur.fetchone()
            consultas_agendadas = row_agd[0] if row_agd else 0
            
            cur.execute("SELECT COUNT(*) FROM consultas WHERE paciente_id = %s AND status = 'realizada'", (paciente_id,))
            row_real = cur.fetchone()
            consultas_realizadas = row_real[0] if row_real else 0
            
            cur.execute("SELECT COUNT(*) FROM consultas WHERE paciente_id = %s AND status = 'cancelada'", (paciente_id,))
            row_canc = cur.fetchone()
            consultas_canceladas = row_canc[0] if row_canc else 0
            
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
            flash('Erro ao carregar dashboard.', 'danger')
            return redirect(url_for('paciente.minhas_consultas'))
    
    # ================= MINHAS CONSULTAS =================
    @paciente_bp.route('/consultas')
    @paciente_required
    def minhas_consultas():
        try:
            paciente_id = obter_paciente_id()
            if paciente_id is None:
                flash('Perfil de paciente não encontrado.', 'danger')
                return redirect(url_for('auth.logout'))
            
            cur = mysql.connection.cursor()
            cur.execute("""
                SELECT c.id, COALESCE(m_u.nome, 'Médico') as nome, 
                       COALESCE(m.especialidade, 'Clínico Geral') as especialidade, 
                       c.data_hora, COALESCE(c.status, 'agendada') as status
                FROM consultas c
                JOIN medicos m ON c.medico_id = m.id
                JOIN usuarios m_u ON m.usuario_id = m_u.id
                WHERE c.paciente_id = %s
                ORDER BY c.data_hora DESC
            """, (paciente_id,))
            consultas_raw = cur.fetchall()
            cur.close()
            
            consultas_formatadas = []
            for c in consultas_raw:
                status = c[4] if len(c) > 4 else 'agendada'
                consultas_formatadas.append({
                    'id': c[0],
                    'medico_nome': garantir_string(c[1]),
                    'especialidade': garantir_string(c[2]),
                    'data_hora': formatar_data(c[3]),
                    'data_short': formatar_data(c[3], '%d/%m/%Y'),
                    'hora': formatar_data(c[3], '%H:%M'),
                    'status': garantir_string(status),
                    'status_class': {
                        'agendada': 'warning', 'realizada': 'success',
                        'cancelada': 'danger', 'confirmada': 'info'
                    }.get(status, 'secondary')
                })
            
            return render_template('paciente/consultas.html', consultas=consultas_formatadas, user=session, user_type='paciente')
        except Exception as e:
            logger.error(f"Erro em minhas_consultas: {e}")
            flash('Erro ao carregar consultas.', 'danger')
            return redirect(url_for('paciente.dashboard'))
    
    # ================= AGENDAR CONSULTA =================
    @paciente_bp.route('/agendar', methods=['GET', 'POST'])
    @paciente_required
    def agendar_consulta():
        paciente_id = obter_paciente_id()
        if paciente_id is None:
            flash('Perfil de paciente não encontrado.', 'danger')
            return redirect(url_for('auth.logout'))
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT m.id, COALESCE(u.nome, 'Médico') as nome, COALESCE(m.especialidade, 'Clínico Geral') as especialidade
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
                flash('Horário indisponível.', 'danger')
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
    
    # ================= DETALHES DA CONSULTA =================
    @paciente_bp.route('/consultas/<int:consulta_id>')
    @paciente_required
    def detalhes_consulta(consulta_id):
        paciente_id = obter_paciente_id()
        if paciente_id is None:
            flash('Perfil de paciente não encontrado.', 'danger')
            return redirect(url_for('auth.logout'))
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT c.id, COALESCE(m_u.nome, 'Médico') as medico_nome, 
                   COALESCE(m.especialidade, 'Clínico Geral') as especialidade, 
                   c.data_hora, COALESCE(c.status, 'agendada') as status,
                   COALESCE(c.observacoes, '') as observacoes, 
                   COALESCE(p_u.nome, 'Paciente') as paciente_nome,
                   COALESCE(c.sintomas, '') as sintomas
            FROM consultas c
            JOIN medicos m ON m.id = c.medico_id
            JOIN usuarios m_u ON m_u.id = m.usuario_id
            JOIN pacientes p ON p.id = c.paciente_id
            JOIN usuarios p_u ON p_u.id = p.usuario_id
            WHERE c.id = %s AND c.paciente_id = %s
        """, (consulta_id, paciente_id))
        
        row = cur.fetchone()
        if not row:
            cur.close()
            flash('Consulta não encontrada.', 'danger')
            return redirect(url_for('paciente.minhas_consultas'))
        
        consulta = {
            'id': row[0],
            'medico_nome': garantir_string(row[1]),
            'especialidade': garantir_string(row[2]),
            'data_hora': formatar_data(row[3]),
            'status': garantir_string(row[4]),
            'observacoes': garantir_string(row[5]),
            'paciente_nome': garantir_string(row[6]),
            'sintomas_raw': garantir_string(row[7]) if len(row) > 7 else ''
        }
        
        cur.execute("""
            SELECT id, COALESCE(diagnostico, '') as diagnostico, 
                   COALESCE(prescricao, '') as prescricao, created_at
            FROM receita WHERE consulta_id = %s ORDER BY created_at DESC
        """, (consulta_id,))
        receitas_raw = cur.fetchall()
        cur.close()
        
        receitas = []
        for r in receitas_raw:
            receitas.append({
                'id': r[0],
                'diagnostico': garantir_string(r[1]),
                'prescricao': garantir_string(r[2]),
                'created_at': formatar_data(r[3], '%d/%m/%Y %H:%M') if r[3] else ''
            })
        
        sintomas_lista = [s.strip() for s in consulta['sintomas_raw'].split(',') if s.strip()] if consulta.get('sintomas_raw') else []
        status_class = {
            'agendada': 'warning', 'realizada': 'success',
            'cancelada': 'danger', 'confirmada': 'info'
        }.get(consulta['status'], 'secondary')
        
        return render_template('paciente/detalhes_consulta.html', 
                             consulta=consulta, sintomas=sintomas_lista, receitas=receitas,
                             status_class=status_class, user=session,
                             formatar_data=formatar_data, datetime=datetime, user_type='paciente')
    
    # ================= CANCELAR CONSULTA =================
    @paciente_bp.route('/consultas/<int:consulta_id>/cancelar', methods=['POST'])
    @paciente_required
    def cancelar_consulta(consulta_id):
        paciente_id = obter_paciente_id()
        if paciente_id is None:
            return jsonify({'success': False, 'message': 'Perfil não encontrado'}), 400
        
        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT status FROM consultas WHERE id = %s AND paciente_id = %s", (consulta_id, paciente_id))
            consulta = cur.fetchone()
            if not consulta:
                return jsonify({'success': False, 'message': 'Consulta não encontrada'}), 404
            
            if consulta[0] != 'agendada':
                return jsonify({'success': False, 'message': 'Apenas consultas agendadas podem ser canceladas'}), 400
            
            cur.execute("UPDATE consultas SET status = 'cancelada' WHERE id = %s AND paciente_id = %s", (consulta_id, paciente_id))
            mysql.connection.commit()
            cur.close()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': 'Consulta cancelada!'})
            
            flash('Consulta cancelada!', 'success')
            return redirect(url_for('paciente.minhas_consultas'))
        except Exception as e:
            mysql.connection.rollback()
            logger.error(f"Erro ao cancelar: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    # ================= PERFIL =================
    @paciente_bp.route('/perfil', methods=['GET', 'POST'])
    @paciente_required
    def perfil():
        paciente_id = obter_paciente_id()
        if paciente_id is None:
            flash('Perfil de paciente não encontrado.', 'danger')
            return redirect(url_for('auth.logout'))
        
        if request.method == 'POST':
            telefone = request.form.get('telefone', '')
            endereco = request.form.get('endereco', '')
            data_nascimento = request.form.get('data_nascimento')
            genero = request.form.get('genero', '')
            
            cur = mysql.connection.cursor()
            cur.execute("""
                UPDATE pacientes SET telefone=%s, endereco=%s, data_nascimento=%s, genero=%s WHERE id=%s
            """, (telefone, endereco, data_nascimento, genero, paciente_id))
            mysql.connection.commit()
            cur.close()
            
            flash('Perfil atualizado!', 'success')
            return redirect(url_for('paciente.perfil'))
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT p_u.nome, COALESCE(p.telefone, '') as telefone, COALESCE(p.endereco, '') as endereco,
                   COALESCE(p_u.email, '') as email, p.data_nascimento, COALESCE(p.genero, '') as genero
            FROM pacientes p JOIN usuarios p_u ON p.usuario_id = p_u.id WHERE p.id = %s
        """, (paciente_id,))
        info = cur.fetchone()
        cur.close()
        
        if info:
            return render_template('paciente/perfil.html',
                paciente_nome=garantir_string(info[0]) if info[0] else 'Paciente',
                telefone=garantir_string(info[1]),
                endereco=garantir_string(info[2]),
                email=garantir_string(info[3]),
                data_nascimento=info[4] if len(info) > 4 else None,
                genero=garantir_string(info[5]) if len(info) > 5 else '',
                user=session)
        
        return render_template('paciente/perfil.html', user=session)
    
    # ================= VISUALIZAR RECEITA =================
    @paciente_bp.route('/receita/<int:receita_id>')
    @paciente_required
    def visualizar_receita(receita_id):
        paciente_id = obter_paciente_id()
        if paciente_id is None:
            flash('Perfil de paciente não encontrado.', 'danger')
            return redirect(url_for('auth.logout'))
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT r.id, COALESCE(r.diagnostico, '') as diagnostico, COALESCE(r.prescricao, '') as prescricao,
                   r.created_at, c.id, c.data_hora, COALESCE(m_u.nome, 'Médico') as medico_nome,
                   COALESCE(m.especialidade, 'Clínico Geral') as especialidade,
                   COALESCE(p_u.nome, 'Paciente') as paciente_nome
            FROM receita r
            JOIN consultas c ON r.consulta_id = c.id
            JOIN medicos m ON c.medico_id = m.id
            JOIN usuarios m_u ON m.usuario_id = m_u.id
            JOIN pacientes p ON c.paciente_id = p.id
            JOIN usuarios p_u ON p.usuario_id = p_u.id
            WHERE r.id = %s AND c.paciente_id = %s
        """, (receita_id, paciente_id))
        
        row = cur.fetchone()
        cur.close()
        
        if not row:
            flash('Receita não encontrada.', 'danger')
            return redirect(url_for('paciente.minhas_consultas'))
        
        receita = {
            'id': row[0],
            'diagnostico': garantir_string(row[1]),
            'prescricao': garantir_string(row[2]),
            'created_at': row[3],
            'consulta_id': row[4],
            'data_consulta': formatar_data(row[5]),
            'medico_nome': garantir_string(row[6]),
            'especialidade': garantir_string(row[7]),
            'paciente_nome': garantir_string(row[8])
        }
        
        return render_template('paciente/visualizar_receita.html', receita=receita, user=session)
    
    return paciente_bp
