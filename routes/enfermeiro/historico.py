# routes/enfermeiro/historico.py

from flask import Blueprint, render_template, flash, redirect, url_for, session
from .utils import execute_query, enfermeiro_required, classificar_pressao, decode_bytes
import logging

logger = logging.getLogger(__name__)

# ===================== NOME CORRETO DO BLUEPRINT =====================
historico_bp = Blueprint('historico', __name__, url_prefix='/historico')

# Atributo para armazenar a conexão MySQL
historico_bp.mysql = None

def set_mysql(mysql_instance):
    """Configura a conexão MySQL para este módulo"""
    historico_bp.mysql = mysql_instance
    from .utils import set_mysql as set_utils_mysql
    set_utils_mysql(mysql_instance)


@historico_bp.route('/pacientes')
@enfermeiro_required
def historico_pacientes():
    """Lista todos os pacientes atendidos pelo enfermeiro"""
    enfermeiro_id = session.get('enfermeiro_id')
    
    pacientes = execute_query("""
        SELECT 
            p.id, 
            u.nome, 
            u.email, 
            u.telefone,
            COUNT(sv.id) as total,
            MAX(sv.data_afericao) as ultima,
            MIN(sv.data_afericao) as primeira
        FROM pacientes p
        JOIN usuarios u ON p.usuario_id = u.id
        LEFT JOIN consultas c ON p.id = c.paciente_id
        LEFT JOIN sinais_vitais sv ON c.id = sv.consulta_id AND sv.enfermeiro_id = %s
        GROUP BY p.id, u.nome, u.email, u.telefone
        HAVING total > 0
        ORDER BY ultima DESC
    """, (enfermeiro_id,), fetch=True) or []
    
    # Converter para lista de dicionários
    pacientes_lista = []
    for p in pacientes:
        pacientes_lista.append({
            'id': p.get('id'),
            'paciente_nome': decode_bytes(p.get('nome')),
            'email': decode_bytes(p.get('email')),
            'telefone': decode_bytes(p.get('telefone')),
            'total_afericoes': p.get('total', 0),
            'ultima_afericao': p.get('ultima'),
            'primeira_afericao': p.get('primeira')
        })
    
    return render_template('enfermeiro/historico/pacientes.html', 
                         pacientes=pacientes_lista)


@historico_bp.route('/pacientes/<int:paciente_id>')
@enfermeiro_required
def historico_paciente_detalhes(paciente_id):
    """Mostra histórico detalhado de um paciente específico"""
    enfermeiro_id = session.get('enfermeiro_id')
    
    # Dados do paciente
    paciente = execute_query("""
        SELECT 
            p.id, 
            u.nome, 
            u.email, 
            u.telefone,
            p.data_nascimento, 
            p.genero, 
            p.endereco
        FROM pacientes p
        JOIN usuarios u ON p.usuario_id = u.id
        WHERE p.id = %s
    """, (paciente_id,), fetch=True, one=True)
    
    if not paciente:
        flash('Paciente não encontrado.', 'danger')
        return redirect(url_for('enfermeiro.historico.historico_pacientes'))
    
    # Histórico de aferições
    afericoes = execute_query("""
        SELECT 
            sv.id, 
            sv.pressao_arterial, 
            sv.frequencia_cardiaca,
            sv.frequencia_respiratoria, 
            sv.temperatura,
            sv.saturacao_oxigenio, 
            sv.glicemia, 
            sv.peso,
            sv.data_afericao, 
            sv.observacoes,
            c.data_hora as data_consulta, 
            c.id as consulta_id
        FROM sinais_vitais sv
        JOIN consultas c ON sv.consulta_id = c.id
        WHERE sv.enfermeiro_id = %s AND c.paciente_id = %s
        ORDER BY sv.data_afericao DESC
    """, (enfermeiro_id, paciente_id), fetch=True) or []
    
    # Converter afericoes para lista de dicionários
    afericoes_lista = []
    for a in afericoes:
        afericoes_lista.append({
            'id': a.get('id'),
            'pressao_arterial': decode_bytes(a.get('pressao_arterial')),
            'frequencia_cardiaca': a.get('frequencia_cardiaca'),
            'frequencia_respiratoria': a.get('frequencia_respiratoria'),
            'temperatura': a.get('temperatura'),
            'saturacao_oxigenio': a.get('saturacao_oxigenio'),
            'glicemia': a.get('glicemia'),
            'peso': a.get('peso'),
            'data_afericao': a.get('data_afericao'),
            'observacoes': decode_bytes(a.get('observacoes')),
            'data_consulta': a.get('data_consulta'),
            'consulta_id': a.get('consulta_id')
        })
    
    return render_template('enfermeiro/historico/paciente_detalhes.html',
        paciente={
            'id': paciente.get('id'),
            'nome': decode_bytes(paciente.get('nome')),
            'email': decode_bytes(paciente.get('email')),
            'telefone': decode_bytes(paciente.get('telefone')),
            'data_nascimento': paciente.get('data_nascimento'),
            'genero': decode_bytes(paciente.get('genero')),
            'endereco': decode_bytes(paciente.get('endereco'))
        },
        afericoes=afericoes_lista,
        classificar_pressao=classificar_pressao)
