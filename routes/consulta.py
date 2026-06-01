"""
Blueprint de consultas - Versão completa com suporte a sinais vitais
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
    
    def obter_enfermeiro_id():
        if session.get('user_type') not in ['enfermeiro', 'enfermeira']:
            return None
        try:
            enfermeiro = execute_query(
                "SELECT id FROM enfermeiros WHERE usuario_id = %s",
                (session['user_id'],), fetch=True, one=True
            )
            if enfermeiro:
                return enfermeiro[0] if isinstance(enfermeiro, (tuple, list)) else enfermeiro.get('id')
            return None
        except:
            return None
    
    def processar_sintomas(sintomas_raw):
        if not sintomas_raw:
            return []
        return [s.strip() for s in str(sintomas_raw).split(',') if s.strip()]
    
    def obter_sinais_vitais(consulta_id):
        """Busca sinais vitais da consulta"""
        try:
            query = """
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
                    u.nome as profissional_nome
                FROM sinais_vitais sv
                LEFT JOIN usuarios u ON sv.enfermeiro_id = u.id
                WHERE sv.consulta_id = %s
                ORDER BY sv.data_afericao DESC
            """
            
            sinais = execute_query(query, (consulta_id,), fetch=True) or []
            
            resultados = []
            for s in sinais:
                resultados.append({
                    'id': s[0],
                    'pressao_arterial': str(s[1]) if s[1] else '',
                    'frequencia_cardiaca': str(s[2]) if s[2] else '',
                    'frequencia_respiratoria': str(s[3]) if s[3] else '',
                    'temperatura': float(s[4]) if s[4] else None,
                    'saturacao_oxigenio': str(s[5]) if s[5] else '',
                    'glicemia': str(s[6]) if s[6] else '',
                    'peso': float(s[7]) if s[7] else None,
                    'data_afericao': s[8].strftime('%d/%m/%Y %H:%M') if s[8] else '',
                    'observacoes': str(s[9]) if s[9] else '',
                    'profissional_nome': str(s[10]) if s[10] else 'Sistema'
                })
            
            return resultados
        except Exception as e:
            logger.error(f"Erro ao obter sinais vitais: {e}")
            return []
    
    # ========== ROTA PRINCIPAL ==========
    @consulta_bp.route('/<int:consulta_id>')
    def detalhes_consulta(consulta_id):
        """Detalhes de uma consulta específica"""
        
        if 'user_id' not in session:
            flash('Por favor, faça login.', 'warning')
            return redirect(url_for('auth.login'))
        
        usuario_tipo = session.get('user_type')
        
        try:
            # Query para buscar consulta
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
            
            # Converter para dict
            if isinstance(consulta_raw, dict):
                consulta_data = consulta_raw
            else:
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
            
            # Buscar sinais vitais
            sinais_vitais = obter_sinais_vitais(consulta_id)
            
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
            elif usuario_tipo in ['enfermeiro', 'enfermeira']:
                tem_acesso = True
            
            if not tem_acesso:
                flash('Sem permissão para acessar esta consulta.', 'danger')
                return redirect(url_for('medico.dashboard'))
            
            # Verificar internação existente
            internacao_existente = None
            if consulta.get('paciente_id'):
                internacao_existente = execute_query(
                    "SELECT id FROM internacoes_pacientes WHERE paciente_id = %s AND status = 'ativa'",
                    (consulta.get('paciente_id'),), fetch=True, one=True
                )
            
            return render_template('consulta/detalhes_consulta.html',
                                 consulta=consulta,
                                 sintomas=sintomas,
                                 sinais_vitais=sinais_vitais,
                                 internacao_existente=internacao_existente,
                                 usuario_tipo=usuario_tipo,
                                 user=session,
                                 agora=datetime.now().strftime('%d/%m/%Y %H:%M'))
        
        except Exception as e:
            logger.error(f"Erro: {e}")
            traceback.print_exc()
            flash('Erro ao carregar consulta.', 'danger')
            return redirect(url_for('medico.consultas'))
    
    # ========== ROTA PARA REGISTRAR SINAIS VITAIS (FORMULÁRIO) ==========
    @consulta_bp.route('/<int:consulta_id>/sinais-vitais')
    def form_sinais_vitais(consulta_id):
        """Formulário para registrar sinais vitais"""
        if 'user_id' not in session:
            flash('Faça login para continuar.', 'warning')
            return redirect(url_for('auth.login'))
        
        usuario_tipo = session.get('user_type')
        if usuario_tipo not in ['medico', 'enfermeiro', 'enfermeira']:
            flash('Acesso restrito a profissionais de saúde.', 'danger')
            return redirect(url_for('dashboard'))
        
        # Buscar dados da consulta
        consulta = execute_query("""
            SELECT c.id, c.paciente_id, p_u.nome as paciente_nome
            FROM consultas c
            JOIN pacientes p ON c.paciente_id = p.id
            JOIN usuarios p_u ON p.usuario_id = p_u.id
            WHERE c.id = %s
        """, (consulta_id,), fetch=True, one=True)
        
        if not consulta:
            flash('Consulta não encontrada.', 'danger')
            return redirect(url_for('medico.consultas'))
        
        # Converter para dict
        if isinstance(consulta, (tuple, list)):
            consulta_dict = {
                'id': consulta[0],
                'paciente_id': consulta[1],
                'paciente_nome': str(consulta[2]) if len(consulta) > 2 else ''
            }
        else:
            consulta_dict = consulta
        
        return render_template('consulta/sinais_vitais_form.html',
                             consulta=consulta_dict,
                             consulta_id=consulta_id)
    
    # ========== ROTA PARA SALVAR SINAIS VITAIS ==========
    @consulta_bp.route('/<int:consulta_id>/sinais-vitais/salvar', methods=['POST'])
    def salvar_sinais_vitais(consulta_id):
        """Salvar sinais vitais"""
        if 'user_id' not in session:
            flash('Não autorizado.', 'danger')
            return redirect(url_for('auth.login'))
        
        try:
            # Pegar dados do formulário
            pressao_arterial = request.form.get('pressao_arterial')
            frequencia_cardiaca = request.form.get('frequencia_cardiaca')
            frequencia_respiratoria = request.form.get('frequencia_respiratoria')
            temperatura = request.form.get('temperatura')
            saturacao_oxigenio = request.form.get('saturacao_oxigenio')
            glicemia = request.form.get('glicemia')
            peso = request.form.get('peso')
            observacoes = request.form.get('observacoes', '')
            
            # Converter valores vazios para None
            pressao_arterial = pressao_arterial if pressao_arterial else None
            frequencia_cardiaca = frequencia_cardiaca if frequencia_cardiaca else None
            frequencia_respiratoria = frequencia_respiratoria if frequencia_respiratoria else None
            temperatura = temperatura if temperatura else None
            saturacao_oxigenio = saturacao_oxigenio if saturacao_oxigenio else None
            glicemia = glicemia if glicemia else None
            peso = peso if peso else None
            
            # Inserir no banco
            execute_query("""
                INSERT INTO sinais_vitais 
                (consulta_id, pressao_arterial, frequencia_cardiaca, frequencia_respiratoria, 
                 temperatura, saturacao_oxigenio, glicemia, peso, observacoes, data_afericao)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (consulta_id, pressao_arterial, frequencia_cardiaca, 
                  frequencia_respiratoria, temperatura, saturacao_oxigenio, 
                  glicemia, peso, observacoes))
            
            flash('Sinais vitais registrados com sucesso!', 'success')
            return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
            
        except Exception as e:
            logger.error(f"Erro ao salvar sinais vitais: {e}")
            flash('Erro ao registrar sinais vitais.', 'danger')
            return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
    
    # ========== ROTA PARA CONFIRMAR CONSULTA ==========
    @consulta_bp.route('/<int:consulta_id>/confirmar', methods=['POST'])
    def confirmar_consulta(consulta_id):
        if 'user_id' not in session or session.get('user_type') not in ['medico', 'admin']:
            flash('Não autorizado.', 'danger')
            return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
        
        try:
            execute_query(
                "UPDATE consultas SET status = 'confirmada' WHERE id = %s",
                (consulta_id,)
            )
            flash(f'Consulta #{consulta_id} confirmada com sucesso!', 'success')
        except Exception as e:
            logger.error(f"Erro ao confirmar consulta: {e}")
            flash(f'Erro ao confirmar consulta: {str(e)}', 'danger')
        
        return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
    
    # ========== ROTA PARA CANCELAR CONSULTA ==========
    @consulta_bp.route('/<int:consulta_id>/cancelar', methods=['POST'])
    def cancelar_consulta(consulta_id):
        if 'user_id' not in session:
            flash('Não autorizado.', 'danger')
            return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
        
        try:
            execute_query(
                "UPDATE consultas SET status = 'cancelada' WHERE id = %s",
                (consulta_id,)
            )
            flash(f'Consulta #{consulta_id} cancelada com sucesso!', 'success')
        except Exception as e:
            logger.error(f"Erro ao cancelar consulta: {e}")
            flash(f'Erro ao cancelar consulta: {str(e)}', 'danger')
        
        return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
    
    # ========== ROTA PARA REALIZAR CONSULTA ==========
    @consulta_bp.route('/<int:consulta_id>/realizar', methods=['POST'])
    def realizar_consulta(consulta_id):
        if 'user_id' not in session or session.get('user_type') != 'medico':
            flash('Não autorizado.', 'danger')
            return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
        
        try:
            medico_id = obter_medico_id()
            consulta = execute_query(
                "SELECT medico_id FROM consultas WHERE id = %s",
                (consulta_id,), fetch=True, one=True
            )
            if not consulta or consulta[0] != medico_id:
                flash('Permissão negada.', 'danger')
                return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
            
            execute_query(
                "UPDATE consultas SET status = 'realizada' WHERE id = %s",
                (consulta_id,)
            )
            flash(f'Consulta #{consulta_id} realizada com sucesso!', 'success')
        except Exception as e:
            logger.error(f"Erro ao realizar consulta: {e}")
            flash(f'Erro ao realizar consulta: {str(e)}', 'danger')
        
        return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
    
    # ========== ROTAS PARA RECEITA DIGITAL ==========
    @consulta_bp.route('/<int:consulta_id>/receita-digital')
    def receita_digital(consulta_id):
        if 'user_id' not in session or session.get('user_type') != 'medico':
            flash('Acesso não autorizado.', 'danger')
            return redirect(url_for('auth.login'))
        
        medico_id = obter_medico_id()
        
        # Buscar consulta
        consulta = execute_query("""
            SELECT c.id, c.paciente_id, p_u.nome as paciente_nome
            FROM consultas c
            JOIN pacientes p ON c.paciente_id = p.id
            JOIN usuarios p_u ON p.usuario_id = p_u.id
            WHERE c.id = %s AND c.medico_id = %s
        """, (consulta_id, medico_id), fetch=True, one=True)
        
        if not consulta:
            flash('Consulta não encontrada ou você não tem permissão.', 'danger')
            return redirect(url_for('medico.consultas'))
        
        # Converter para dict
        if isinstance(consulta, (tuple, list)):
            consulta_dict = {
                'id': consulta[0],
                'paciente_id': consulta[1],
                'paciente_nome': str(consulta[2]) if len(consulta) > 2 else ''
            }
        else:
            consulta_dict = consulta
        
        return render_template('medico/receita_digital.html',
                              consulta=consulta_dict,
                              consulta_id=consulta_id,
                              medico_id=medico_id)

    @consulta_bp.route('/<int:consulta_id>/receita-digital/salvar', methods=['POST'])
    def salvar_receita_digital(consulta_id):
        if 'user_id' not in session or session.get('user_type') != 'medico':
            flash('Acesso não autorizado.', 'danger')
            return redirect(url_for('auth.login'))
        
        try:
            diagnostico = request.form.get('diagnostico')
            medicamentos = request.form.get('medicamentos')
            posologia = request.form.get('posologia')
            duracao = request.form.get('duracao')
            observacoes = request.form.get('observacoes', '')
            
            # Montar prescrição
            prescricao = f"Medicamento: {medicamentos}\nPosologia: {posologia}\nDuração: {duracao}\nObservações: {observacoes}"
            
            execute_query("""
                INSERT INTO receita 
                (consulta_id, diagnostico, prescricao, recomendacoes, status, created_at)
                VALUES (%s, %s, %s, %s, 'ativa', NOW())
            """, (consulta_id, diagnostico, prescricao, observacoes))
            
            flash('Receita digital gerada com sucesso!', 'success')
            return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
            
        except Exception as e:
            logger.error(f"Erro ao salvar receita: {e}")
            flash('Erro ao gerar receita.', 'danger')
            return redirect(url_for('consulta.receita_digital', consulta_id=consulta_id))
    
    return consulta_bp
