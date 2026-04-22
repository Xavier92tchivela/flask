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
        """Obtém o ID do paciente logado - CORRIGIDO"""
        if 'user_id' not in session or session.get('user_type') != 'paciente':
            return None
        
        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT id FROM pacientes WHERE usuario_id = %s", (session['user_id'],))
            result = cur.fetchone()
            cur.close()
            
            if result:
                # Resultado é um dicionário (DictCursor)
                return result['id']
            return None
        except Exception as e:
            print(f"Erro ao obter paciente_id: {e}")
            return None
    
    # ========== ROTA: DASHBOARD ==========
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
        paciente_data_nasc = formatar_data(paciente_info['data_nascimento'], '%d/%m/%Y') if paciente_info and paciente_info.get('data_nascimento') else None
        paciente_genero = garantir_string(paciente_info['genero']) if paciente_info else None
        paciente_telefone = garantir_string(paciente_info['telefone']) if paciente_info else None
        paciente_endereco = garantir_string(paciente_info['endereco']) if paciente_info else None
        paciente_email = garantir_string(paciente_info['email']) if paciente_info else None
        
        # Buscar consultas
        cur.execute("""
            SELECT c.id, m_u.nome as medico_nome, m.especialidade, 
                   c.data_hora, c.status
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
            FROM consultas 
            WHERE paciente_id = %s
        """, (paciente_id,))
        stats_row = cur.fetchone()
        
        consultas_agendadas = stats_row['agendadas'] if stats_row and stats_row['agendadas'] else 0
        consultas_realizadas = stats_row['realizadas'] if stats_row and stats_row['realizadas'] else 0
        consultas_canceladas = stats_row['canceladas'] if stats_row and stats_row['canceladas'] else 0
        total_consultas = stats_row['total'] if stats_row and stats_row['total'] else 0
        
        cur.execute("SELECT COUNT(*) as total FROM consultas WHERE paciente_id = %s AND DATE(data_hora) = CURDATE()", (paciente_id,))
        consultas_hoje = cur.fetchone()['total'] if cur.fetchone() else 0
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
                    'cancelada': 'danger',
                    'confirmada': 'info'
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
    
    return paciente_bp
