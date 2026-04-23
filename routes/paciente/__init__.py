from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
import logging
from functools import wraps
from datetime import datetime, timedelta, date

logger = logging.getLogger(__name__)

def init_paciente(mysql, app):
    """Inicializa e retorna o blueprint do paciente"""
    
    paciente_bp = Blueprint('paciente', __name__, url_prefix='/paciente')
    
    def garantir_string(valor):
        """Converte para string de forma segura"""
        if valor is None:
            return ''
        if isinstance(valor, bytes):
            try:
                return valor.decode('utf-8')
            except:
                return str(valor)
        if isinstance(valor, (int, float)):
            return str(valor)
        if isinstance(valor, (datetime, date)):
            return formatar_data(valor)
        return str(valor) if valor is not None else ''
    
    def formatar_data(data, formato='%d/%m/%Y %H:%M'):
        """Formata data de forma segura"""
        if not data:
            return ''
        if isinstance(data, datetime):
            return data.strftime(formato)
        if isinstance(data, date):
            return data.strftime(formato)
        return str(data)
    
    def obter_paciente_id():
        """Obtém o ID do paciente logado com segurança"""
        if 'user_id' not in session:
            logger.warning("obter_paciente_id: user_id não está na sessão")
            return None
        if session.get('user_type') != 'paciente':
            logger.warning(f"obter_paciente_id: user_type é {session.get('user_type')}, não 'paciente'")
            return None
        
        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT id FROM pacientes WHERE usuario_id = %s", (session['user_id'],))
            resultado = cur.fetchone()
            cur.close()
            if resultado:
                return resultado[0]
            logger.warning(f"obter_paciente_id: Nenhum paciente encontrado para usuario_id={session['user_id']}")
            return None
        except Exception as e:
            logger.error(f"Erro ao obter paciente_id: {e}")
            return None
    
    def paciente_required(f):
        """Decorator para garantir acesso apenas de pacientes"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Faça login para acessar esta página.', 'warning')
                return redirect(url_for('auth.login'))
            if session.get('user_type') != 'paciente':
                flash('Acesso restrito a pacientes.', 'warning')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated_function
    
    # ========== DASHBOARD CORRIGIDO ==========
    @paciente_bp.route('/dashboard')
    @paciente_required
    def dashboard():
        try:
            # Verificar sessão
            if 'user_id' not in session:
                flash('Sessão expirada. Faça login novamente.', 'warning')
                return redirect(url_for('auth.login'))
            
            paciente_id = obter_paciente_id()
            if not paciente_id:
                flash('Perfil de paciente não encontrado. Contate o administrador.', 'danger')
                return redirect(url_for('auth.logout'))
            
            cur = mysql.connection.cursor()
            
            # Buscar dados do paciente com COALESCE para evitar NULL
            cur.execute("""
                SELECT 
                    COALESCE(p_u.nome, 'Paciente') as nome,
                    p.data_nascimento,
                    COALESCE(p.genero, '') as genero,
                    COALESCE(p.telefone, '') as telefone,
                    COALESCE(p.endereco, '') as endereco,
                    COALESCE(p_u.email, '') as email
                FROM pacientes p 
                JOIN usuarios p_u ON p.usuario_id = p_u.id 
                WHERE p.id = %s
            """, (paciente_id,))
            
            paciente_info = cur.fetchone()
            
            # Garantir valores padrão
            if paciente_info:
                if isinstance(paciente_info, dict):
                    paciente_nome = garantir_string(paciente_info.get('nome', 'Paciente'))
                    paciente_data_nasc = paciente_info.get('data_nascimento')
                    paciente_genero = garantir_string(paciente_info.get('genero', ''))
                    paciente_telefone = garantir_string(paciente_info.get('telefone', ''))
                    paciente_endereco = garantir_string(paciente_info.get('endereco', ''))
                    paciente_email = garantir_string(paciente_info.get('email', ''))
                else:
                    paciente_nome = garantir_string(paciente_info[0]) if len(paciente_info) > 0 else session.get('user_name', 'Paciente')
                    paciente_data_nasc = paciente_info[1] if len(paciente_info) > 1 else None
                    paciente_genero = garantir_string(paciente_info[2]) if len(paciente_info) > 2 else ''
                    paciente_telefone = garantir_string(paciente_info[3]) if len(paciente_info) > 3 else ''
                    paciente_endereco = garantir_string(paciente_info[4]) if len(paciente_info) > 4 else ''
                    paciente_email = garantir_string(paciente_info[5]) if len(paciente_info) > 5 else ''
            else:
                paciente_nome = session.get('user_name', 'Paciente')
                paciente_data_nasc = None
                paciente_genero = ''
                paciente_telefone = ''
                paciente_endereco = ''
                paciente_email = session.get('user_email', '')
            
            paciente_data_nasc = formatar_data(paciente_data_nasc, '%d/%m/%Y') if paciente_data_nasc else None
            
            # Buscar consultas
            cur.execute("""
                SELECT 
                    c.id, 
                    COALESCE(m_u.nome, 'Médico') as medico_nome, 
                    COALESCE(m.especialidade, 'Clínico Geral') as especialidade, 
                    c.data_hora, 
                    COALESCE(c.status, 'agendada') as status
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
                if isinstance(c, dict):
                    status = c.get('status', 'agendada')
                    consultas.append({
                        'id': c.get('id'),
                        'medico_nome': garantir_string(c.get('medico_nome', 'Médico')),
                        'especialidade': garantir_string(c.get('especialidade', 'Clínico Geral')),
                        'data_hora': formatar_data(c.get('data_hora')),
                        'status': garantir_string(status),
                        'status_class': {
                            'agendada': 'warning', 'realizada': 'success',
                            'cancelada': 'danger', 'confirmada': 'info'
                        }.get(status, 'secondary')
                    })
                else:
                    status = c[4] if len(c) > 4 else 'agendada'
                    consultas.append({
                        'id': c[0],
                        'medico_nome': garantir_string(c[1]) if len(c) > 1 else 'Médico',
                        'especialidade': garantir_string(c[2]) if len(c) > 2 else 'Clínico Geral',
                        'data_hora': formatar_data(c[3]) if len(c) > 3 else '',
                        'status': garantir_string(status),
                        'status_class': {
                            'agendada': 'warning', 'realizada': 'success',
                            'cancelada': 'danger', 'confirmada': 'info'
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
            import traceback
            logger.error(traceback.format_exc())
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
                SELECT 
                    c.id, 
                    COALESCE(m_u.nome, 'Médico') as nome, 
                    COALESCE(m.especialidade, 'Clínico Geral') as especialidade, 
                    c.data_hora, 
                    COALESCE(c.status, 'agendada') as status
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
                if isinstance(c, dict):
                    status = c.get('status', 'agendada')
                    consultas_formatadas.append({
                        'id': c.get('id'),
                        'medico_nome': garantir_string(c.get('nome', 'Médico')),
                        'especialidade': garantir_string(c.get('especialidade', 'Clínico Geral')),
                        'data_hora': formatar_data(c.get('data_hora')),
                        'data_short': formatar_data(c.get('data_hora'), '%d/%m/%Y'),
                        'hora': formatar_data(c.get('data_hora'), '%H:%M'),
                        'status': garantir_string(status),
                        'status_class': {
                            'agendada': 'warning', 'realizada': 'success',
                            'cancelada': 'danger', 'confirmada': 'info'
                        }.get(status, 'secondary')
                    })
                else:
                    status = c[4] if len(c) > 4 else 'agendada'
                    consultas_formatadas.append({
                        'id': c[0],
                        'medico_nome': garantir_string(c[1]) if len(c) > 1 else 'Médico',
                        'especialidade': garantir_string(c[2]) if len(c) > 2 else 'Clínico Geral',
                        'data_hora': formatar_data(c[3]) if len(c) > 3 else '',
                        'data_short': formatar_data(c[3] if len(c) > 3 else None, '%d/%m/%Y'),
                        'hora': formatar_data(c[3] if len(c) > 3 else None, '%H:%M'),
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
            if isinstance(m, dict):
                medicos.append({
                    'id': m.get('id'),
                    'nome': garantir_string(m.get('nome', 'Médico')),
                    'especialidade': garantir_string(m.get('especialidade', 'Clínico Geral'))
                })
            else:
                medicos.append({
                    'id': m[0],
                    'nome': garantir_string(m[1]) if len(m) > 1 else 'Médico',
                    'especialidade': garantir_string(m[2]) if len(m) > 2 else 'Clínico Geral'
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
                flash('Preencha todos os campos obrigatórios.', 'danger')
                return redirect(request.url)
            
            try:
                data_hora = datetime.strptime(f"{data_consulta} {hora_consulta}", "%Y-%m-%d %H:%M")
            except:
                flash('Formato de data/hora inválido.', 'danger')
                return redirect(request.url)
            
            if data_hora <= datetime.now():
                flash('Não é possível agendar consultas em datas/horários passados.', 'danger')
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
                flash(f'Erro ao agendar: {str(e)}', 'danger')
                return redirect(request.url)
        
        return render_template('paciente/agendar_consulta.html', 
                               medicos=medicos, horarios=horarios,
                               data_minima=data_minima, data_maxima=data_maxima,
                               user=session, user_type='paciente')
    
    # ========== DETALHES CONSULTA ==========
    @paciente_bp.route('/consultas/<int:consulta_id>')
    @paciente_required
    def detalhes_consulta(consulta_id):
        paciente_id = obter_paciente_id()
        if not paciente_id:
            flash('Perfil de paciente não encontrado.', 'danger')
            return redirect(url_for('auth.logout'))
        
        cur = mysql.connection.cursor()
        
        cur.execute("""
            SELECT 
                c.id, 
                COALESCE(m_u.nome, 'Médico') as medico_nome, 
                COALESCE(m.especialidade, 'Clínico Geral') as especialidade, 
                c.data_hora, 
                COALESCE(c.status, 'agendada') as status,
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
        
        if isinstance(row, dict):
            consulta = {
                'id': row.get('id'),
                'medico_nome': garantir_string(row.get('medico_nome', 'Médico')),
                'especialidade': garantir_string(row.get('especialidade', 'Clínico Geral')),
                'data_hora': formatar_data(row.get('data_hora')),
                'status': garantir_string(row.get('status', 'agendada')),
                'observacoes': garantir_string(row.get('observacoes', '')),
                'paciente_nome': garantir_string(row.get('paciente_nome', 'Paciente')),
                'sintomas_raw': garantir_string(row.get('sintomas', ''))
            }
        else:
            consulta = {
                'id': row[0],
                'medico_nome': garantir_string(row[1]) if len(row) > 1 else 'Médico',
                'especialidade': garantir_string(row[2]) if len(row) > 2 else 'Clínico Geral',
                'data_hora': formatar_data(row[3] if len(row) > 3 else None),
                'status': garantir_string(row[4] if len(row) > 4 else 'agendada'),
                'observacoes': garantir_string(row[5] if len(row) > 5 else ''),
                'paciente_nome': garantir_string(row[6] if len(row) > 6 else 'Paciente'),
                'sintomas_raw': garantir_string(row[7] if len(row) > 7 else '')
            }
        
        # Buscar receitas
        cur.execute("""
            SELECT id, COALESCE(diagnostico, '') as diagnostico, 
                   COALESCE(prescricao, '') as prescricao, 
                   created_at
            FROM receita 
            WHERE consulta_id = %s 
            ORDER BY created_at DESC
        """, (consulta_id,))
        receitas_raw = cur.fetchall()
        cur.close()
        
        receitas = []
        for r in receitas_raw:
            if isinstance(r, dict):
                receitas.append({
                    'id': r.get('id'),
                    'diagnostico': garantir_string(r.get('diagnostico', '')),
                    'prescricao': garantir_string(r.get('prescricao', '')),
                    'created_at': formatar_data(r.get('created_at'), '%d/%m/%Y %H:%M')
                })
            else:
                receitas.append({
                    'id': r[0],
                    'diagnostico': garantir_string(r[1]) if len(r) > 1 else '',
                    'prescricao': garantir_string(r[2]) if len(r) > 2 else '',
                    'created_at': formatar_data(r[3] if len(r) > 3 else None, '%d/%m/%Y %H:%M')
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
    
    # ========== CANCELAR CONSULTA ==========
    @paciente_bp.route('/consultas/<int:consulta_id>/cancelar', methods=['POST'])
    @paciente_required
    def cancelar_consulta(consulta_id):
        paciente_id = obter_paciente_id()
        if not paciente_id:
            flash('Perfil de paciente não encontrado.', 'danger')
            return redirect(url_for('auth.logout'))
        
        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT status FROM consultas WHERE id = %s AND paciente_id = %s", (consulta_id, paciente_id))
            consulta = cur.fetchone()
            if not consulta:
                flash('Consulta não encontrada.', 'danger')
                return redirect(url_for('paciente.minhas_consultas'))
            
            status = consulta[0] if consulta else 'agendada'
            if status != 'agendada':
                flash('Apenas consultas agendadas podem ser canceladas.', 'warning')
                return redirect(url_for('paciente.detalhes_consulta', consulta_id=consulta_id))
            
            cur.execute("UPDATE consultas SET status = 'cancelada' WHERE id = %s AND paciente_id = %s", (consulta_id, paciente_id))
            mysql.connection.commit()
            cur.close()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': 'Consulta cancelada com sucesso!'})
            
            flash('Consulta cancelada com sucesso!', 'success')
        except Exception as e:
            mysql.connection.rollback()
            logger.error(f"Erro ao cancelar consulta: {e}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': str(e)}), 500
            flash('Erro ao cancelar consulta.', 'danger')
        
        return redirect(url_for('paciente.minhas_consultas'))
    
    # ========== PERFIL ==========
    @paciente_bp.route('/perfil', methods=['GET', 'POST'])
    @paciente_required
    def perfil():
        paciente_id = obter_paciente_id()
        if not paciente_id:
            flash('Perfil de paciente não encontrado.', 'danger')
            return redirect(url_for('auth.logout'))
        
        if request.method == 'POST':
            telefone = request.form.get('telefone', '')
            endereco = request.form.get('endereco', '')
            data_nascimento = request.form.get('data_nascimento')
            genero = request.form.get('genero', '')
            
            cur = mysql.connection.cursor()
            cur.execute("""
                UPDATE pacientes 
                SET telefone=%s, endereco=%s, data_nascimento=%s, genero=%s
                WHERE id=%s
            """, (telefone, endereco, data_nascimento, genero, paciente_id))
            mysql.connection.commit()
            cur.close()
            
            flash('Perfil atualizado com sucesso!', 'success')
            return redirect(url_for('paciente.perfil'))
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT 
                COALESCE(p_u.nome, 'Paciente') as nome,
                COALESCE(p.telefone, '') as telefone,
                COALESCE(p.endereco, '') as endereco,
                COALESCE(p_u.email, '') as email,
                p.data_nascimento,
                COALESCE(p.genero, '') as genero
            FROM pacientes p
            JOIN usuarios p_u ON p.usuario_id = p_u.id
            WHERE p.id = %s
        """, (paciente_id,))
        info = cur.fetchone()
        cur.close()
        
        if info:
            if isinstance(info, dict):
                return render_template('paciente/perfil.html',
                    paciente_nome=garantir_string(info.get('nome', 'Paciente')),
                    telefone=garantir_string(info.get('telefone', '')),
                    endereco=garantir_string(info.get('endereco', '')),
                    email=garantir_string(info.get('email', '')),
                    data_nascimento=info.get('data_nascimento'),
                    genero=garantir_string(info.get('genero', '')),
                    user=session)
            else:
                return render_template('paciente/perfil.html',
                    paciente_nome=garantir_string(info[0]) if len(info) > 0 else 'Paciente',
                    telefone=garantir_string(info[1]) if len(info) > 1 else '',
                    endereco=garantir_string(info[2]) if len(info) > 2 else '',
                    email=garantir_string(info[3]) if len(info) > 3 else '',
                    data_nascimento=info[4] if len(info) > 4 else None,
                    genero=garantir_string(info[5]) if len(info) > 5 else '',
                    user=session)
        
        return render_template('paciente/perfil.html', user=session)
    
    # ========== VISUALIZAR RECEITA ==========
    @paciente_bp.route('/receita/<int:receita_id>')
    @paciente_required
    def visualizar_receita(receita_id):
        paciente_id = obter_paciente_id()
        if not paciente_id:
            flash('Perfil de paciente não encontrado.', 'danger')
            return redirect(url_for('auth.logout'))
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT 
                r.id, 
                COALESCE(r.diagnostico, '') as diagnostico, 
                COALESCE(r.prescricao, '') as prescricao, 
                r.created_at,
                c.id as consulta_id, 
                c.data_hora,
                COALESCE(m_u.nome, 'Médico') as medico_nome,
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
        
        if isinstance(row, dict):
            receita = {
                'id': row.get('id'),
                'diagnostico': garantir_string(row.get('diagnostico', '')),
                'prescricao': garantir_string(row.get('prescricao', '')),
                'created_at': row.get('created_at'),
                'consulta_id': row.get('consulta_id'),
                'data_consulta': formatar_data(row.get('data_hora')),
                'medico_nome': garantir_string(row.get('medico_nome', 'Médico')),
                'especialidade': garantir_string(row.get('especialidade', 'Clínico Geral')),
                'paciente_nome': garantir_string(row.get('paciente_nome', 'Paciente'))
            }
        else:
            receita = {
                'id': row[0],
                'diagnostico': garantir_string(row[1]) if len(row) > 1 else '',
                'prescricao': garantir_string(row[2]) if len(row) > 2 else '',
                'created_at': row[3] if len(row) > 3 else None,
                'consulta_id': row[4] if len(row) > 4 else None,
                'data_consulta': formatar_data(row[5] if len(row) > 5 else None),
                'medico_nome': garantir_string(row[6]) if len(row) > 6 else 'Médico',
                'especialidade': garantir_string(row[7]) if len(row) > 7 else 'Clínico Geral',
                'paciente_nome': garantir_string(row[8]) if len(row) > 8 else 'Paciente'
            }
        
        return render_template('paciente/visualizar_receita.html', receita=receita, user=session)
    
    return paciente_bp
