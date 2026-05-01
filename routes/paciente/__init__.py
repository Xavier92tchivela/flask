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
        return str(valor)
    
    def formatar_data(data, formato='%d/%m/%Y %H:%M'):
        if not data:
            return ''
        if isinstance(data, (datetime, date)):
            return data.strftime(formato)
        return str(data)
    
    def obter_paciente_id():
        if session.get('paciente_id'):
            return session['paciente_id']
        if 'user_id' not in session:
            return None
        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT id FROM pacientes WHERE usuario_id = %s", (session['user_id'],))
            resultado = cur.fetchone()
            cur.close()
            if resultado:
                if isinstance(resultado, dict):
                    paciente_id = resultado.get('id')
                else:
                    paciente_id = resultado[0]
                session['paciente_id'] = paciente_id
                return paciente_id
            
            # Criar paciente automaticamente
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO pacientes (usuario_id) VALUES (%s)", (session['user_id'],))
            mysql.connection.commit()
            cur.execute("SELECT id FROM pacientes WHERE usuario_id = %s", (session['user_id'],))
            novo = cur.fetchone()
            cur.close()
            if novo:
                paciente_id = novo[0] if isinstance(novo, (list, tuple)) else novo.get('id')
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
    
    # ========== DASHBOARD CORRIGIDO ==========
    @paciente_bp.route('/dashboard')
    @paciente_required
    def dashboard():
        try:
            paciente_id = obter_paciente_id()
            if not paciente_id:
                flash('Perfil de paciente não encontrado.', 'danger')
                return redirect(url_for('paciente.minhas_consultas'))
            
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
            
            if row is None:
                paciente_nome = session.get('user_name', 'Paciente')
                paciente_telefone = ''
                paciente_endereco = ''
                paciente_email = ''
                paciente_data_nasc = None
                paciente_genero = ''
            else:
                if isinstance(row, dict):
                    paciente_nome = garantir_string(row.get('nome', 'Paciente'))
                    paciente_telefone = garantir_string(row.get('telefone', ''))
                    paciente_endereco = garantir_string(row.get('endereco', ''))
                    paciente_email = garantir_string(row.get('email', ''))
                    paciente_data_nasc = row.get('data_nascimento')
                    paciente_genero = garantir_string(row.get('genero', ''))
                else:
                    paciente_nome = garantir_string(row[0]) if row[0] else 'Paciente'
                    paciente_telefone = garantir_string(row[1]) if len(row) > 1 else ''
                    paciente_endereco = garantir_string(row[2]) if len(row) > 2 else ''
                    paciente_email = garantir_string(row[3]) if len(row) > 3 else ''
                    paciente_data_nasc = row[4] if len(row) > 4 else None
                    paciente_genero = garantir_string(row[5]) if len(row) > 5 else ''
            
            paciente_data_nasc = formatar_data(paciente_data_nasc, '%d/%m/%Y') if paciente_data_nasc else None
            
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
            if consultas_raw:
                for c in consultas_raw:
                    if isinstance(c, dict):
                        status = c.get('status', 'agendada')
                        consultas.append({
                            'id': c.get('id'),
                            'medico_nome': garantir_string(c.get('medico_nome', 'Médico')),
                            'especialidade': garantir_string(c.get('especialidade', 'Clínico Geral')),
                            'data_hora': formatar_data(c.get('data_hora')),
                            'status': status,
                            'status_class': {
                                'agendada': 'warning',
                                'realizada': 'success',
                                'cancelada': 'danger'
                            }.get(status, 'secondary')
                        })
                    else:
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
                                'cancelada': 'danger'
                            }.get(status, 'secondary')
                        })
            
            # ========== ESTATÍSTICAS CORRIGIDAS (DictCursor) ==========
            cur.execute("SELECT COUNT(*) as total FROM consultas WHERE paciente_id = %s", (paciente_id,))
            total_row = cur.fetchone()
            total_consultas = total_row['total'] if total_row and isinstance(total_row, dict) else (total_row[0] if total_row else 0)
            
            cur.execute("SELECT COUNT(*) as total FROM consultas WHERE paciente_id = %s AND DATE(data_hora) = CURDATE()", (paciente_id,))
            hoje_row = cur.fetchone()
            consultas_hoje = hoje_row['total'] if hoje_row and isinstance(hoje_row, dict) else (hoje_row[0] if hoje_row else 0)
            
            cur.execute("SELECT COUNT(*) as total FROM consultas WHERE paciente_id = %s AND status = 'agendada'", (paciente_id,))
            agd_row = cur.fetchone()
            consultas_agendadas = agd_row['total'] if agd_row and isinstance(agd_row, dict) else (agd_row[0] if agd_row else 0)
            
            cur.execute("SELECT COUNT(*) as total FROM consultas WHERE paciente_id = %s AND status = 'realizada'", (paciente_id,))
            real_row = cur.fetchone()
            consultas_realizadas = real_row['total'] if real_row and isinstance(real_row, dict) else (real_row[0] if real_row else 0)
            
            cur.execute("SELECT COUNT(*) as total FROM consultas WHERE paciente_id = %s AND status = 'cancelada'", (paciente_id,))
            canc_row = cur.fetchone()
            consultas_canceladas = canc_row['total'] if canc_row and isinstance(canc_row, dict) else (canc_row[0] if canc_row else 0)
            
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
            flash('Erro ao carregar dashboard.', 'danger')
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
            if consultas_raw:
                for c in consultas_raw:
                    if isinstance(c, dict):
                        status = c.get('status', 'agendada')
                        consultas.append({
                            'id': c.get('id'),
                            'medico_nome': garantir_string(c.get('medico_nome', 'Médico')),
                            'especialidade': garantir_string(c.get('especialidade', 'Clínico Geral')),
                            'data_hora': formatar_data(c.get('data_hora')),
                            'data_short': formatar_data(c.get('data_hora'), '%d/%m/%Y'),
                            'hora': formatar_data(c.get('data_hora'), '%H:%M'),
                            'status': status,
                            'status_class': {
                                'agendada': 'warning',
                                'realizada': 'success',
                                'cancelada': 'danger'
                            }.get(status, 'secondary')
                        })
                    else:
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
            if isinstance(m, dict):
                medicos.append({
                    'id': m.get('id'),
                    'nome': garantir_string(m.get('nome', 'Médico')),
                    'especialidade': garantir_string(m.get('especialidade', 'Clínico Geral'))
                })
            else:
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
            cur.execute("SELECT COUNT(*) as total FROM consultas WHERE medico_id = %s AND data_hora = %s AND status != 'cancelada'",
                       (medico_id, data_hora))
            row_count = cur.fetchone()
            count = row_count['total'] if row_count and isinstance(row_count, dict) else (row_count[0] if row_count else 0)
            
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
    
    # ========== DETALHES DA CONSULTA ==========
    @paciente_bp.route('/consultas/<int:consulta_id>')
    @paciente_required
    def detalhes_consulta(consulta_id):
        paciente_id = obter_paciente_id()
        if not paciente_id:
            flash('Perfil de paciente não encontrado.', 'danger')
            return redirect(url_for('auth.logout'))
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT c.id, COALESCE(mu.nome, 'Médico') as medico_nome, 
                   COALESCE(m.especialidade, 'Clínico Geral') as especialidade, 
                   c.data_hora, COALESCE(c.status, 'agendada') as status,
                   COALESCE(c.observacoes, '') as observacoes, 
                   COALESCE(p_u.nome, 'Paciente') as paciente_nome,
                   COALESCE(c.sintomas, '') as sintomas
            FROM consultas c
            JOIN medicos m ON m.id = c.medico_id
            JOIN usuarios mu ON mu.id = m.usuario_id
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
            'cancelada': 'danger'
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
            return jsonify({'success': False, 'message': 'Perfil não encontrado'}), 400
        
        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT status FROM consultas WHERE id = %s AND paciente_id = %s", (consulta_id, paciente_id))
            consulta = cur.fetchone()
            if not consulta:
                return jsonify({'success': False, 'message': 'Consulta não encontrada'}), 404
            
            if isinstance(consulta, dict):
                status = consulta.get('status')
            else:
                status = consulta[0]
            
            if status != 'agendada':
                return jsonify({'success': False, 'message': 'Apenas consultas agendadas podem ser canceladas'}), 400
            
            cur.execute("UPDATE consultas SET status = 'cancelada' WHERE id = %s AND paciente_id = %s", (consulta_id, paciente_id))
            mysql.connection.commit()
            cur.close()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': 'Consulta cancelada!'})
            
            flash('Consulta cancelada com sucesso!', 'success')
            return redirect(url_for('paciente.minhas_consultas'))
        except Exception as e:
            mysql.connection.rollback()
            logger.error(f"Erro ao cancelar: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
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
                UPDATE pacientes SET telefone=%s, endereco=%s, data_nascimento=%s, genero=%s WHERE id=%s
            """, (telefone, endereco, data_nascimento, genero, paciente_id))
            mysql.connection.commit()
            cur.close()
            
            flash('Perfil atualizado!', 'success')
            return redirect(url_for('paciente.perfil'))
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT u.nome, COALESCE(p.telefone, '') as telefone, COALESCE(p.endereco, '') as endereco,
                   COALESCE(u.email, '') as email, p.data_nascimento, COALESCE(p.genero, '') as genero
            FROM pacientes p JOIN usuarios u ON p.usuario_id = u.id WHERE p.id = %s
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
                    paciente_nome=garantir_string(info[0]),
                    telefone=garantir_string(info[1]),
                    endereco=garantir_string(info[2]),
                    email=garantir_string(info[3]),
                    data_nascimento=info[4] if len(info) > 4 else None,
                    genero=garantir_string(info[5]) if len(info) > 5 else '',
                    user=session)
        
        return render_template('paciente/perfil.html', user=session)
    
    # ========== VISUALIZAR RECEITA (CORRIGIDA PARA TABELA RECEITA) ==========
    @paciente_bp.route('/receita/<int:receita_id>')
    @paciente_required
    def visualizar_receita(receita_id):
        paciente_id = obter_paciente_id()
        if not paciente_id:
            flash('Perfil de paciente não encontrado.', 'danger')
            return redirect(url_for('auth.logout'))
        
        cur = mysql.connection.cursor()
        
        # Query corrigida para buscar dados da receita e da consulta
        cur.execute("""
            SELECT 
                r.id, 
                r.consulta_id, 
                COALESCE(r.diagnostico, '') as diagnostico, 
                COALESCE(r.prescricao, '') as prescricao,
                COALESCE(r.recomendacoes, '') as recomendacoes,
                r.created_at,
                r.receita_pdf_path,
                r.pdf_gerado,
                r.data_geracao_pdf,
                c.data_hora,
                COALESCE(mu.nome, 'Médico') as medico_nome,
                COALESCE(m.especialidade, 'Clínico Geral') as especialidade,
                COALESCE(m.crm, '') as crm,
                COALESCE(p_u.nome, 'Paciente') as paciente_nome,
                TIMESTAMPDIFF(YEAR, p.data_nascimento, CURDATE()) as paciente_idade,
                COALESCE(p.genero, '') as paciente_sexo
            FROM receita r
            INNER JOIN consultas c ON r.consulta_id = c.id
            INNER JOIN medicos m ON c.medico_id = m.id
            INNER JOIN usuarios mu ON m.usuario_id = mu.id
            INNER JOIN pacientes p ON c.paciente_id = p.id
            INNER JOIN usuarios p_u ON p.usuario_id = p_u.id
            WHERE r.id = %s AND c.paciente_id = %s
        """, (receita_id, paciente_id))
        
        row = cur.fetchone()
        cur.close()
        
        if not row:
            flash('Receita não encontrada ou acesso não autorizado.', 'danger')
            return redirect(url_for('paciente.minhas_consultas'))
        
        # Processar os dados
        if isinstance(row, dict):
            receita = {
                'id': row.get('id'),
                'consulta_id': row.get('consulta_id'),
                'diagnostico': garantir_string(row.get('diagnostico', '')),
                'prescricao': garantir_string(row.get('prescricao', '')),
                'recomendacoes': garantir_string(row.get('recomendacoes', '')),
                'created_at': row.get('created_at'),
                'receita_pdf_path': row.get('receita_pdf_path'),
                'pdf_gerado': row.get('pdf_gerado', 0),
                'data_geracao_pdf': row.get('data_geracao_pdf'),
                'data_consulta': row.get('data_hora'),
                'medico_nome': garantir_string(row.get('medico_nome', 'Médico')),
                'especialidade': garantir_string(row.get('especialidade', 'Clínico Geral')),
                'crm': garantir_string(row.get('crm', '')),
                'paciente_nome': garantir_string(row.get('paciente_nome', 'Paciente')),
                'paciente_idade': row.get('paciente_idade'),
                'paciente_sexo': garantir_string(row.get('paciente_sexo', ''))
            }
        else:
            receita = {
                'id': row[0],
                'consulta_id': row[1],
                'diagnostico': garantir_string(row[2]) if len(row) > 2 else '',
                'prescricao': garantir_string(row[3]) if len(row) > 3 else '',
                'recomendacoes': garantir_string(row[4]) if len(row) > 4 else '',
                'created_at': row[5] if len(row) > 5 else None,
                'receita_pdf_path': row[6] if len(row) > 6 else None,
                'pdf_gerado': row[7] if len(row) > 7 else 0,
                'data_geracao_pdf': row[8] if len(row) > 8 else None,
                'data_consulta': row[9] if len(row) > 9 else None,
                'medico_nome': garantir_string(row[10]) if len(row) > 10 else 'Médico',
                'especialidade': garantir_string(row[11]) if len(row) > 11 else 'Clínico Geral',
                'crm': garantir_string(row[12]) if len(row) > 12 else '',
                'paciente_nome': garantir_string(row[13]) if len(row) > 13 else 'Paciente',
                'paciente_idade': row[14] if len(row) > 14 else None,
                'paciente_sexo': garantir_string(row[15]) if len(row) > 15 else ''
            }
        
        # Validar se consulta_id existe
        if not receita.get('consulta_id'):
            logger.error(f"Receita {receita_id} tem consulta_id = NULL")
            flash('Erro: Esta receita não está associada a uma consulta válida.', 'danger')
            return redirect(url_for('paciente.minhas_consultas'))
        
        # Adicionar campos adicionais para o template
        receita['validade_dias'] = 30  # Valor padrão
        receita['validade_data'] = (receita['created_at'] + timedelta(days=30)) if receita['created_at'] else None
        
        return render_template('paciente/visualizar_receita.html', receita=receita, user=session)
    
    # ========== GERAR PDF DA RECEITA ==========
    @paciente_bp.route('/receita/<int:receita_id>/gerar-pdf', methods=['POST'])
    @paciente_required
    def gerar_pdf_receita(receita_id):
        paciente_id = obter_paciente_id()
        if not paciente_id:
            return jsonify({'success': False, 'message': 'Perfil não encontrado'}), 400
        
        try:
            # Aqui você implementa a lógica de geração do PDF
            # Por enquanto, apenas marcamos como gerado
            cur = mysql.connection.cursor()
            cur.execute("""
                UPDATE receita 
                SET pdf_gerado = 1, 
                    data_geracao_pdf = NOW(),
                    receita_pdf_path = CONCAT('/pdfs/receitas/receita_', id, '.pdf')
                WHERE id = %s AND consulta_id IN (
                    SELECT id FROM consultas WHERE paciente_id = %s
                )
            """, (receita_id, paciente_id))
            mysql.connection.commit()
            cur.close()
            
            return jsonify({'success': True, 'message': 'PDF gerado com sucesso!'})
        except Exception as e:
            logger.error(f"Erro ao gerar PDF: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    return paciente_bp
