from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, send_file, current_app
import pymysql
pymysql.install_as_MySQLdb()
import os
from datetime import datetime, timedelta, date
import traceback
import logging
from functools import wraps
import re
import uuid

logger = logging.getLogger(__name__)

def init_paciente(mysql, app):
    """Inicializa e retorna o blueprint do paciente"""
    
    paciente_bp = Blueprint('paciente', __name__, url_prefix='/paciente')
    
    # ========== FUNÇÃO PARA CONVERTER BYTES ==========
    def garantir_string(valor):
        if valor is None:
            return ''
        if isinstance(valor, bytes):
            try:
                return valor.decode('utf-8')
            except:
                return str(valor)
        if isinstance(valor, (int, float)):
            return str(valor)
        return str(valor) if valor is not None else ''
    
    # ========== DECORATOR ==========
    def paciente_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session or session.get('user_type') != 'paciente':
                flash('Acesso restrito a pacientes.', 'warning')
                return redirect('/login')
            return f(*args, **kwargs)
        return decorated_function
    
    # ========== FUNÇÕES AUXILIARES ==========
    def formatar_data(data, formato='%d/%m/%Y %H:%M'):
        if not data:
            return ''
        if isinstance(data, datetime):
            return data.strftime(formato)
        elif isinstance(data, date):
            return data.strftime(formato)
        return str(data)
    
    def obter_paciente_id():
        if 'user_id' not in session or session.get('user_type') != 'paciente':
            return None
        try:
            cur = mysql.connection.cursor()
            user_id = session['user_id']
            cur.execute("SELECT id FROM pacientes WHERE usuario_id = %s", (user_id,))
            result = cur.fetchone()
            cur.close()
            if result:
                return result['id']
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO pacientes (usuario_id) VALUES (%s)", (user_id,))
            mysql.connection.commit()
            cur.close()
            cur = mysql.connection.cursor()
            cur.execute("SELECT id FROM pacientes WHERE usuario_id = %s", (user_id,))
            result = cur.fetchone()
            cur.close()
            return result['id'] if result else None
        except Exception as e:
            print(f"Erro ao obter paciente_id: {e}")
            return None
    
    # ========== ROTA: DASHBOARD (VERSÃO SIMPLIFICADA FUNCIONAL) ==========
    @paciente_bp.route('/dashboard')
    @paciente_required
    def dashboard():
        paciente_id = obter_paciente_id()
        if not paciente_id:
            flash('Perfil de paciente não encontrado.', 'danger')
            return redirect('/logout')
        
        cur = mysql.connection.cursor()
        
        # Buscar informações do paciente
        cur.execute("""
            SELECT p_u.nome, p.data_nascimento, p.genero, p.telefone, p.endereco, p_u.email
            FROM pacientes p 
            JOIN usuarios p_u ON p.usuario_id = p_u.id 
            WHERE p.id = %s
        """, (paciente_id,))
        paciente_info = cur.fetchone()
        
        paciente_nome = garantir_string(paciente_info['nome']) if paciente_info else session.get('user_name', 'Paciente')
        paciente_data_nasc = formatar_data(paciente_info.get('data_nascimento'), '%d/%m/%Y') if paciente_info else None
        paciente_genero = garantir_string(paciente_info.get('genero')) if paciente_info else None
        paciente_telefone = garantir_string(paciente_info.get('telefone')) if paciente_info else None
        paciente_endereco = garantir_string(paciente_info.get('endereco')) if paciente_info else None
        paciente_email = garantir_string(paciente_info.get('email')) if paciente_info else None
        
        # Buscar consultas
        cur.execute("""
            SELECT c.id, m_u.nome as medico_nome, m.especialidade, c.data_hora, c.status
            FROM consultas c 
            JOIN medicos m ON c.medico_id = m.id 
            JOIN usuarios m_u ON m.usuario_id = m_u.id 
            WHERE c.paciente_id = %s 
            ORDER BY c.data_hora DESC 
            LIMIT 10
        """, (paciente_id,))
        consultas_raw = cur.fetchall()
        
        # Contar consultas por status
        cur.execute("""
            SELECT 
                SUM(CASE WHEN status = 'agendada' THEN 1 ELSE 0 END) as agendadas,
                SUM(CASE WHEN status = 'realizada' THEN 1 ELSE 0 END) as realizadas,
                SUM(CASE WHEN status = 'cancelada' THEN 1 ELSE 0 END) as canceladas,
                COUNT(*) as total
            FROM consultas WHERE paciente_id = %s
        """, (paciente_id,))
        stats_row = cur.fetchone()
        
        consultas_agendadas = stats_row['agendadas'] if stats_row and stats_row['agendadas'] else 0
        consultas_realizadas = stats_row['realizadas'] if stats_row and stats_row['realizadas'] else 0
        consultas_canceladas = stats_row['canceladas'] if stats_row and stats_row['canceladas'] else 0
        total_consultas = stats_row['total'] if stats_row and stats_row['total'] else 0
        
        cur.execute("SELECT COUNT(*) as total FROM consultas WHERE paciente_id = %s AND DATE(data_hora) = CURDATE()", (paciente_id,))
        result_hoje = cur.fetchone()
        consultas_hoje = result_hoje['total'] if result_hoje else 0
        cur.close()
        
        consultas = []
        for c in consultas_raw:
            status = garantir_string(c['status'])
            consultas.append({
                'id': c['id'],
                'medico_nome': garantir_string(c['medico_nome']),
                'especialidade': garantir_string(c['especialidade']),
                'data_hora': formatar_data(c['data_hora']),
                'status': status,
                'status_class': {
                    'agendada': 'warning',
                    'realizada': 'success',
                    'cancelada': 'danger'
                }.get(status, 'secondary')
            })
        
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
                               paciente_id=paciente_id,
                               paciente_nome=paciente_nome,
                               paciente_data_nasc=paciente_data_nasc,
                               paciente_genero=paciente_genero,
                               paciente_telefone=paciente_telefone,
                               paciente_endereco=paciente_endereco,
                               paciente_email=paciente_email,
                               user=session)
    
    # ========== ROTA: MINHAS CONSULTAS ==========
    @paciente_bp.route('/consultas')
    @paciente_required
    def minhas_consultas():
        paciente_id = obter_paciente_id()
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT c.id, m_u.nome, m.especialidade, c.data_hora, c.status
            FROM consultas c 
            JOIN medicos m ON c.medico_id = m.id
            JOIN usuarios m_u ON m.usuario_id = m_u.id
            WHERE c.paciente_id = %s 
            ORDER BY c.data_hora DESC
        """, (paciente_id,))
        consultas_raw = cur.fetchall()
        cur.close()
        
        consultas = []
        for c in consultas_raw:
            status = garantir_string(c['status'])
            consultas.append({
                'id': c['id'],
                'medico_nome': garantir_string(c['nome']),
                'especialidade': garantir_string(c['especialidade']),
                'data_hora': formatar_data(c['data_hora']),
                'status': status,
                'status_class': {
                    'agendada': 'warning',
                    'realizada': 'success',
                    'cancelada': 'danger'
                }.get(status, 'secondary')
            })
        
        return render_template('paciente/consultas.html', consultas=consultas, user=session)
    
    # ========== ROTA: PERFIL ==========
    @paciente_bp.route('/perfil', methods=['GET', 'POST'])
    @paciente_required
    def perfil():
        paciente_id = obter_paciente_id()
        
        if request.method == 'POST':
            telefone = request.form.get('telefone', '')
            endereco = request.form.get('endereco', '')
            data_nascimento = request.form.get('data_nascimento')
            genero = request.form.get('genero', '')
            
            try:
                cur = mysql.connection.cursor()
                cur.execute("""
                    UPDATE pacientes 
                    SET telefone=%s, endereco=%s, data_nascimento=%s, genero=%s
                    WHERE id=%s
                """, (telefone, endereco, data_nascimento, genero, paciente_id))
                mysql.connection.commit()
                cur.close()
                flash('Perfil atualizado com sucesso!', 'success')
            except Exception as e:
                logger.error(f"Erro ao atualizar perfil: {e}")
                flash('Erro ao atualizar perfil.', 'danger')
            
            return redirect(url_for('paciente.perfil'))
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT p_u.nome, p.data_nascimento, p.genero, p.telefone, p.endereco, p_u.email
            FROM pacientes p 
            JOIN usuarios p_u ON p.usuario_id = p_u.id 
            WHERE p.id = %s
        """, (paciente_id,))
        info = cur.fetchone()
        cur.close()
        
        return render_template('paciente/perfil.html',
                               paciente_nome=garantir_string(info['nome']) if info else '',
                               data_nascimento=info['data_nascimento'] if info else None,
                               genero=garantir_string(info['genero']) if info else '',
                               telefone=garantir_string(info['telefone']) if info else '',
                               endereco=garantir_string(info['endereco']) if info else '',
                               email=garantir_string(info['email']) if info else '',
                               user=session)
    
    # ========== ROTA: AGENDAR CONSULTA ==========
    @paciente_bp.route('/agendar', methods=['GET'])
    @paciente_required
    def agendar_consulta():
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT m.id, u.nome, m.especialidade
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
                'id': m['id'],
                'nome': garantir_string(m['nome']),
                'especialidade': garantir_string(m['especialidade'])
            })
        
        return render_template('paciente/agendar_consulta.html', medicos=medicos, user=session)
    
    # ========== ROTA: DETALHES CONSULTA ==========
    @paciente_bp.route('/consultas/<int:consulta_id>')
    @paciente_required
    def detalhes_consulta(consulta_id):
        paciente_id = obter_paciente_id()
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT c.id, m_u.nome, m.especialidade, c.data_hora, c.status, c.observacoes
            FROM consultas c 
            JOIN medicos m ON c.medico_id = m.id
            JOIN usuarios m_u ON m.usuario_id = m_u.id
            WHERE c.id = %s AND c.paciente_id = %s
        """, (consulta_id, paciente_id))
        
        row = cur.fetchone()
        cur.close()
        
        if not row:
            flash('Consulta não encontrada.', 'danger')
            return redirect(url_for('paciente.minhas_consultas'))
        
        consulta = {
            'id': row['id'],
            'medico_nome': garantir_string(row['nome']),
            'especialidade': garantir_string(row['especialidade']),
            'data_hora': formatar_data(row['data_hora']),
            'status': garantir_string(row['status']),
            'observacoes': garantir_string(row['observacoes']) if row.get('observacoes') else ''
        }
        
        status_class = {
            'agendada': 'warning',
            'realizada': 'success',
            'cancelada': 'danger'
        }.get(consulta['status'], 'secondary')
        
        return render_template('paciente/detalhes_consulta.html',
                               consulta=consulta,
                               status_class=status_class,
                               user=session)
    
    return paciente_bp
