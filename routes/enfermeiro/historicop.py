# routes/enfermeiro/historico.py
from flask import Blueprint, render_template, session, request, jsonify, flash, redirect, url_for
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

historico_bp = Blueprint('historico', __name__, url_prefix='/historico')

_mysql = None

def set_mysql(mysql_instance):
    global _mysql
    _mysql = mysql_instance

def execute_query(query, params=None, fetch=False, one=False, commit=False):
    try:
        if _mysql is None:
            return None if fetch else False
        cur = _mysql.connection.cursor()
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        if fetch:
            if one:
                result = cur.fetchone()
            else:
                result = cur.fetchall()
            cur.close()
            return result
        if commit:
            _mysql.connection.commit()
        cur.close()
        return True if commit else None
    except Exception as e:
        logger.error(f"Database error: {e}")
        if commit and _mysql:
            _mysql.connection.rollback()
        return None if fetch else False

def decode_bytes(value):
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode('utf-8')
        except:
            return str(value)
    return value


@historico_bp.route('/paciente/<int:paciente_id>')
def historico_paciente(paciente_id):
    """Histórico completo do paciente"""
    if 'user_id' not in session or session.get('user_type') != 'enfermeiro':
        flash('Acesso restrito a enfermeiros', 'danger')
        return redirect(url_for('enfermeiro.dashboard.index'))
    
    try:
        # Buscar dados do paciente
        paciente = execute_query("""
            SELECT p.id, p.numero_prontuario, p.data_nascimento, p.genero,
                   u.nome, u.email, u.telefone, u.endereco
            FROM pacientes p
            JOIN usuarios u ON p.usuario_id = u.id
            WHERE p.id = %s
        """, (paciente_id,), fetch=True, one=True)
        
        if not paciente:
            flash('Paciente não encontrado', 'danger')
            return redirect(url_for('enfermeiro.dashboard.index'))
        
        # Calcular idade
        idade = None
        if paciente.get('data_nascimento'):
            hoje = datetime.now()
            data_nasc = paciente['data_nascimento']
            if isinstance(data_nasc, datetime):
                data_nasc = data_nasc.date()
            idade = hoje.year - data_nasc.year
            if (hoje.month, hoje.day) < (data_nasc.month, data_nasc.day):
                idade -= 1
        
        paciente_dados = {
            'id': paciente.get('id'),
            'prontuario': paciente.get('numero_prontuario'),
            'nome': decode_bytes(paciente.get('nome')),
            'email': decode_bytes(paciente.get('email')),
            'telefone': decode_bytes(paciente.get('telefone')),
            'endereco': decode_bytes(paciente.get('endereco')),
            'genero': decode_bytes(paciente.get('genero')),
            'idade': idade,
            'data_nascimento': paciente.get('data_nascimento').strftime('%d/%m/%Y') if paciente.get('data_nascimento') else None
        }
        
        # Buscar histórico de consultas
        consultas = execute_query("""
            SELECT 
                c.id,
                c.data_hora,
                c.status,
                c.sintomas,
                d.diagnostico_final,
                d.diagnostico_preliminar,
                r.prescricao,
                r.recomendacoes,
                m.id as medico_id,
                u_med.nome as medico_nome,
                m.especialidade
            FROM consultas c
            LEFT JOIN diagnostico d ON c.id = d.consulta_id
            LEFT JOIN receita r ON c.id = r.consulta_id
            JOIN medicos m ON c.medico_id = m.id
            JOIN usuarios u_med ON m.usuario_id = u_med.id
            WHERE c.paciente_id = %s
            ORDER BY c.data_hora DESC
        """, (paciente_id,), fetch=True)
        
        consultas_lista = []
        for cons in consultas:
            consultas_lista.append({
                'id': cons.get('id'),
                'data_hora': cons.get('data_hora'),
                'status': decode_bytes(cons.get('status')),
                'sintomas': decode_bytes(cons.get('sintomas')),
                'diagnostico_final': decode_bytes(cons.get('diagnostico_final')),
                'diagnostico_preliminar': decode_bytes(cons.get('diagnostico_preliminar')),
                'prescricao': decode_bytes(cons.get('prescricao')),
                'recomendacoes': decode_bytes(cons.get('recomendacoes')),
                'medico_nome': decode_bytes(cons.get('medico_nome')),
                'medico_especialidade': decode_bytes(cons.get('especialidade'))
            })
        
        # Buscar histórico de triagens
        triagens = execute_query("""
            SELECT 
                c.id,
                c.data_hora,
                c.status_triagem,
                c.sintomas,
                c.observacoes
            FROM consultas c
            WHERE c.paciente_id = %s 
              AND c.status_triagem IS NOT NULL
            ORDER BY c.data_hora DESC
        """, (paciente_id,), fetch=True)
        
        triagens_lista = []
        for triagem in triagens:
            triagens_lista.append({
                'id': triagem.get('id'),
                'data_hora': triagem.get('data_hora'),
                'status_triagem': decode_bytes(triagem.get('status_triagem')),
                'sintomas': decode_bytes(triagem.get('sintomas')),
                'observacoes': decode_bytes(triagem.get('observacoes'))
            })
        
        # Buscar histórico de sinais vitais
        sinais_vitais = execute_query("""
            SELECT 
                sv.id,
                sv.data_afericao,
                sv.pressao_arterial,
                sv.frequencia_cardiaca,
                sv.frequencia_respiratoria,
                sv.temperatura,
                sv.saturacao_oxigenio,
                sv.glicemia,
                sv.peso,
                sv.observacoes
            FROM sinais_vitais sv
            LEFT JOIN consultas c ON sv.consulta_id = c.id
            WHERE c.paciente_id = %s
            ORDER BY sv.data_afericao DESC
        """, (paciente_id,), fetch=True)
        
        sinais_lista = []
        for sv in sinais_vitais:
            sinais_lista.append({
                'id': sv.get('id'),
                'data_afericao': sv.get('data_afericao'),
                'pressao_arterial': decode_bytes(sv.get('pressao_arterial')),
                'frequencia_cardiaca': sv.get('frequencia_cardiaca'),
                'frequencia_respiratoria': sv.get('frequencia_respiratoria'),
                'temperatura': sv.get('temperatura'),
                'saturacao_oxigenio': sv.get('saturacao_oxigenio'),
                'glicemia': sv.get('glicemia'),
                'peso': sv.get('peso'),
                'observacoes': decode_bytes(sv.get('observacoes'))
            })
        
        # Estatísticas
        total_consultas = len(consultas_lista)
        total_triagens = len(triagens_lista)
        total_sinais = len(sinais_lista)
        total_diagnosticos = sum(1 for c in consultas_lista if c['diagnostico_final'] or c['diagnostico_preliminar'])
        total_receitas = sum(1 for c in consultas_lista if c['prescricao'])
        
        return render_template('enfermeiro/historico_paciente.html',
            paciente=paciente_dados,
            consultas=consultas_lista,
            triagens=triagens_lista,
            sinais_vitais=sinais_lista,
            total_consultas=total_consultas,
            total_triagens=total_triagens,
            total_sinais=total_sinais,
            total_diagnosticos=total_diagnosticos,
            total_receitas=total_receitas,
            user=session
        )
        
    except Exception as e:
        logger.error(f"Erro ao carregar histórico do paciente: {e}")
        import traceback
        traceback.print_exc()
        flash('Erro ao carregar histórico do paciente', 'danger')
        return redirect(url_for('enfermeiro.dashboard.index'))


@historico_bp.route('/buscar')
def buscar_pacientes():
    """Buscar pacientes para histórico"""
    if 'user_id' not in session or session.get('user_type') != 'enfermeiro':
        return jsonify({'error': 'Não autorizado'}), 401
    
    termo = request.args.get('termo', '')
    
    if not termo or len(termo) < 2:
        return jsonify({'pacientes': []})
    
    pacientes = execute_query("""
        SELECT p.id, u.nome, p.numero_prontuario, u.telefone
        FROM pacientes p
        JOIN usuarios u ON p.usuario_id = u.id
        WHERE u.nome LIKE %s OR p.numero_prontuario LIKE %s OR u.email LIKE %s
        LIMIT 10
    """, (f'%{termo}%', f'%{termo}%', f'%{termo}%'), fetch=True)
    
    pacientes_lista = []
    for p in pacientes:
        pacientes_lista.append({
            'id': p.get('id'),
            'nome': decode_bytes(p.get('nome')),
            'prontuario': p.get('numero_prontuario'),
            'telefone': decode_bytes(p.get('telefone'))
        })
    
    return jsonify({'pacientes': pacientes_lista})
