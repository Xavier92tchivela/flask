from flask import Blueprint, render_template, flash, redirect, url_for, session
from .utils import execute_query, enfermeiro_required, classificar_pressao

historico_bp = Blueprint('historico', __name__, url_prefix='/historico')

# Atributo para armazenar a conexão MySQL
historico_bp.mysql = None

def set_mysql(mysql_instance):
    historico_bp.mysql = mysql_instance


@historico_bp.route('/pacientes')
@enfermeiro_required
def historico_pacientes():
    """Lista todos os pacientes atendidos pelo enfermeiro"""
    enfermeiro_id = session['enfermeiro_id']
    
    pacientes = execute_query("""
        SELECT p.id, u.nome, u.email, u.telefone,
            COUNT(sv.id) as total,
            MAX(sv.data_afericao) as ultima,
            MIN(sv.data_afericao) as primeira
        FROM pacientes p
        JOIN usuarios u ON p.usuario_id = u.id
        LEFT JOIN consultas c ON p.id = c.paciente_id
        LEFT JOIN sinais_vitais sv ON c.id = sv.consulta_id AND sv.enfermeiro_id = %s
        GROUP BY p.id
        HAVING total > 0
        ORDER BY ultima DESC
    """, (enfermeiro_id,), fetch=True) or []
    
    return render_template('enfermeiro/historico/pacientes.html', 
                         pacientes=[{
                             'id': p[0], 'paciente_nome': p[1], 'email': p[2],
                             'telefone': p[3], 'total_afericoes': p[4],
                             'ultima_afericao': p[5], 'primeira_afericao': p[6]
                         } for p in pacientes])


@historico_bp.route('/pacientes/<int:paciente_id>')
@enfermeiro_required
def historico_paciente_detalhes(paciente_id):
    """Mostra histórico detalhado de um paciente específico"""
    enfermeiro_id = session['enfermeiro_id']
    
    # Dados do paciente
    paciente = execute_query("""
        SELECT p.id, u.nome, u.email, u.telefone,
               p.data_nascimento, p.genero, p.endereco
        FROM pacientes p
        JOIN usuarios u ON p.usuario_id = u.id
        WHERE p.id = %s
    """, (paciente_id,), fetch=True, one=True)
    
    if not paciente:
        flash('Paciente não encontrado.', 'danger')
        return redirect(url_for('enfermeiro.historico.historico_pacientes'))
    
    # Histórico de aferições
    afericoes = execute_query("""
        SELECT sv.id, sv.pressao_arterial, sv.frequencia_cardiaca,
               sv.frequencia_respiratoria, sv.temperatura,
               sv.saturacao_oxigenio, sv.glicemia, sv.peso,
               sv.data_afericao, sv.observacoes,
               c.data_hora as data_consulta, c.id as consulta_id
        FROM sinais_vitais sv
        JOIN consultas c ON sv.consulta_id = c.id
        WHERE sv.enfermeiro_id = %s AND c.paciente_id = %s
        ORDER BY sv.data_afericao DESC
    """, (enfermeiro_id, paciente_id), fetch=True) or []
    
    return render_template('enfermeiro/historico/paciente_detalhes.html',
        paciente={
            'id': paciente[0], 'nome': paciente[1], 'email': paciente[2],
            'telefone': paciente[3], 'data_nascimento': paciente[4],
            'genero': paciente[5], 'endereco': paciente[6]
        },
        afericoes=[{
            'id': a[0], 'pressao_arterial': a[1], 'frequencia_cardiaca': a[2],
            'frequencia_respiratoria': a[3], 'temperatura': a[4],
            'saturacao_oxigenio': a[5], 'glicemia': a[6], 'peso': a[7],
            'data_afericao': a[8], 'observacoes': a[9],
            'data_consulta': a[10], 'consulta_id': a[11]
        } for a in afericoes],
        classificar_pressao=classificar_pressao)