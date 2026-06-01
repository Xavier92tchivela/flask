"""
Blueprint de consultas - Versão estável
"""

from flask import Blueprint, jsonify, redirect, url_for, flash, render_template, session, request
from datetime import datetime, date
import logging
import traceback

logger = logging.getLogger(__name__)

def create_consulta_blueprint(mysql):
    """Cria e retorna o blueprint de consultas"""
    
    consulta_bp = Blueprint('consulta', __name__, url_prefix='/consulta')
    
    # ========== FUNÇÕES AUXILIARES ==========
    def convert_bytes_to_str(data):
        if isinstance(data, bytes):
            return data.decode('utf-8')
        elif isinstance(data, (list, tuple)):
            return [convert_bytes_to_str(item) for item in data]
        elif isinstance(data, dict):
            return {key: convert_bytes_to_str(value) for key, value in data.items()}
        return data

    def execute_query(query, params=None, fetch=False, one=False):
        try:
            cur = mysql.connection.cursor()
            if params:
                cleaned_params = convert_bytes_to_str(params)
                cur.execute(query, cleaned_params)
            else:
                cur.execute(query)
            
            if fetch:
                result = cur.fetchall()
                cur.close()
                converted_result = convert_bytes_to_str(result)
                if one and converted_result:
                    return converted_result[0]
                return converted_result
            else:
                mysql.connection.commit()
                cur.close()
                return True
        except Exception as e:
            logger.error(f"Database error: {e}")
            return None
    
    def formatar_data(data, formato='%d/%m/%Y %H:%M'):
        if not data:
            return ''
        if isinstance(data, datetime):
            return data.strftime(formato)
        return str(data)
    
    def obter_medico_id():
        if session.get('user_type') != 'medico':
            return None
        try:
            medico = execute_query(
                "SELECT id FROM medicos WHERE usuario_id = %s",
                (session['user_id'],), fetch=True, one=True
            )
            if medico:
                return medico[0] if isinstance(medico, (tuple, list)) else medico.get('id')
            return None
        except:
            return None
    
    def obter_paciente_id():
        if session.get('user_type') != 'paciente':
            return None
        try:
            paciente = execute_query(
                "SELECT id FROM pacientes WHERE usuario_id = %s",
                (session['user_id'],), fetch=True, one=True
            )
            if paciente:
                return paciente[0] if isinstance(paciente, (tuple, list)) else paciente.get('id')
            return None
        except:
            return None
    
    def processar_sintomas(sintomas_raw):
        if not sintomas_raw:
            return []
        return [s.strip() for s in str(sintomas_raw).split(',') if s.strip()]
    
    # ========== ROTA PRINCIPAL ==========
    @consulta_bp.route('/<int:consulta_id>')
    def detalhes_consulta(consulta_id):
        """Detalhes de uma consulta específica"""
        
        if 'user_id' not in session:
            flash('Por favor, faça login.', 'warning')
            return redirect(url_for('auth.login'))
        
        usuario_tipo = session.get('user_type')
        
        try:
            # Query simplificada
            query = """
                SELECT 
                    c.id,
                    c.status,
                    c.observacoes,
                    c.data_hora,
                    m_u.nome as medico_nome,
                    m.especialidade,
                    m.crm,
                    m_u.email as medico_email,
                    p_u.nome as paciente_nome,
                    p.data_nascimento,
                    p.genero,
                    p.telefone as paciente_telefone,
                    p.endereco as paciente_endereco,
                    p.id as paciente_id,
                    m.id as medico_id,
                    p_u.email as paciente_email,
                    c.sintomas
                FROM consultas c 
                JOIN medicos m ON c.medico_id = m.id 
                JOIN usuarios m_u ON m.usuario_id = m_u.id 
                JOIN pacientes p ON c.paciente_id = p.id 
                JOIN usuarios p_u ON p.usuario_id = p_u.id 
                WHERE c.id = %s
            """
            
            consulta_raw = execute_query(query, (consulta_id,), fetch=True, one=True)
            
            if not consulta_raw:
                flash('Consulta não encontrada.', 'danger')
                if usuario_tipo == 'medico':
                    return redirect(url_for('medico.consultas'))
                return redirect(url_for('auth.index'))
            
            # Extrair dados
            if isinstance(consulta_raw, dict):
                consulta_data = consulta_raw
            else:
                # Converter tuple para dict
                consulta_data = {
                    'id': consulta_raw[0],
                    'status': str(consulta_raw[1]) if len(consulta_raw) > 1 else '',
                    'observacoes': str(consulta_raw[2]) if len(consulta_raw) > 2 and consulta_raw[2] else '',
                    'data_hora': formatar_data(consulta_raw[3]) if len(consulta_raw) > 3 else '',
                    'medico_nome': str(consulta_raw[4]) if len(consulta_raw) > 4 else '',
                    'especialidade': str(consulta_raw[5]) if len(consulta_raw) > 5 else '',
                    'crm': str(consulta_raw[6]) if len(consulta_raw) > 6 else '',
                    'medico_email': str(consulta_raw[7]) if len(consulta_raw) > 7 else '',
                    'paciente_nome': str(consulta_raw[8]) if len(consulta_raw) > 8 else '',
                    'data_nascimento': consulta_raw[9] if len(consulta_raw) > 9 else None,
                    'genero': str(consulta_raw[10]) if len(consulta_raw) > 10 else 'Não informado',
                    'paciente_telefone': str(consulta_raw[11]) if len(consulta_raw) > 11 else 'Não informado',
                    'paciente_endereco': str(consulta_raw[12]) if len(consulta_raw) > 12 else 'Não informado',
                    'paciente_id': consulta_raw[13] if len(consulta_raw) > 13 else None,
                    'medico_id': consulta_raw[14] if len(consulta_raw) > 14 else None,
                    'paciente_email': str(consulta_raw[15]) if len(consulta_raw) > 15 else '',
                    'sintomas_raw': str(consulta_raw[16]) if len(consulta_raw) > 16 else '',
                }
            
            # Calcular idade
            idade = None
            if consulta_data.get('data_nascimento'):
                try:
                    data_nasc = consulta_data['data_nascimento']
                    if isinstance(data_nasc, str):
                        data_nasc = datetime.strptime(data_nasc, '%Y-%m-%d').date()
                    elif isinstance(data_nasc, datetime):
                        data_nasc = data_nasc.date()
                    
                    hoje = date.today()
                    idade_calc = hoje.year - data_nasc.year
                    if (hoje.month, hoje.day) < (data_nasc.month, data_nasc.day):
                        idade_calc -= 1
                    idade = idade_calc
                except:
                    pass
            
            # Processar sintomas
            sintomas = processar_sintomas(consulta_data.get('sintomas_raw', ''))
            
            # Status class
            status_class_map = {
                'agendada': 'warning',
                'realizada': 'success',
                'cancelada': 'danger',
                'confirmada': 'info'
            }
            
            consulta = {
                'id': consulta_data.get('id'),
                'status': consulta_data.get('status', ''),
                'observacoes': consulta_data.get('observacoes', ''),
                'data_hora': consulta_data.get('data_hora', ''),
                'medico_nome': consulta_data.get('medico_nome', ''),
                'especialidade': consulta_data.get('especialidade', ''),
                'crm': consulta_data.get('crm', ''),
                'medico_email': consulta_data.get('medico_email', ''),
                'paciente_nome': consulta_data.get('paciente_nome', ''),
                'paciente_idade': f"{idade} anos" if idade else None,
                'genero': consulta_data.get('genero', ''),
                'paciente_telefone': consulta_data.get('paciente_telefone', ''),
                'paciente_endereco': consulta_data.get('paciente_endereco', ''),
                'paciente_id': consulta_data.get('paciente_id'),
                'medico_id': consulta_data.get('medico_id'),
                'paciente_email': consulta_data.get('paciente_email', ''),
                'status_class': status_class_map.get(consulta_data.get('status', ''), 'secondary')
            }
            
            # Verificar permissão
            tem_acesso = False
            if usuario_tipo == 'admin':
                tem_acesso = True
            elif usuario_tipo == 'medico':
                medico_id = obter_medico_id()
                if consulta.get('medico_id') and medico_id and int(consulta.get('medico_id')) == int(medico_id):
                    tem_acesso = True
            elif usuario_tipo == 'paciente':
                paciente_id = obter_paciente_id()
                if consulta.get('paciente_id') and paciente_id and int(consulta.get('paciente_id')) == int(paciente_id):
                    tem_acesso = True
            elif usuario_tipo == 'enfermeiro':
                tem_acesso = True
            
            if not tem_acesso:
                flash('Sem permissão para acessar esta consulta.', 'danger')
                return redirect(url_for('medico.dashboard'))
            
            return render_template('consulta/detalhes_consulta.html',
                                 consulta=consulta,
                                 sintomas=sintomas,
                                 usuario_tipo=usuario_tipo,
                                 user=session,
                                 agora=datetime.now().strftime('%d/%m/%Y %H:%M'))
        
        except Exception as e:
            logger.error(f"Erro: {e}")
            traceback.print_exc()
            flash('Erro ao carregar consulta.', 'danger')
            return redirect(url_for('medico.consultas'))
    
    return consulta_bp
