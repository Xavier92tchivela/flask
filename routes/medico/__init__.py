# routes/medico/__init__.py
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
import logging
import traceback
from .base import init_medico_base
from .medico_dashboard import init_medico_dashboard
from .medico_pedidos import init_medico_pedidos
from .medico_perfil import init_medico_perfil
from .medico_consultas import init_medico_consultas
from .medico_pacientes import init_medico_pacientes
from .medico_api import init_medico_api
from .medico_debug import init_medico_debug
from .medico_receitas import init_medico_receitas
from .medico_sinais_vitais import init_medico_sinais_vitais  # NOVO IMPORT
from .consulta import create_consulta_blueprint
from datetime import datetime
import json
import re

logger = logging.getLogger(__name__)

def init_medico(mysql, client, gemini_available, MODEL_NAME, app, receita_service=None):
    """
    Inicializa e retorna o blueprint completo do médico e enfermeira
    """
    try:
        print("\n" + "="*50)
        print("INICIALIZANDO BLUEPRINT MÉDICO E ENFERMEIRA")
        print("="*50)
        
        medico_bp = Blueprint('medico', __name__, url_prefix='/medico')
        
        # Inicializar funções base
        base = init_medico_base(mysql)
        
        # ===================== DECORATOR PARA PROFISSIONAL DE SAÚDE =====================
        def profissional_saude_required(f):
            """Decorator para permitir acesso a médicos e enfermeiras/enfermeiros"""
            from functools import wraps
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if 'user_id' not in session:
                    flash('Faça login para continuar.', 'warning')
                    return redirect(url_for('auth.login'))
                
                user_type = session.get('user_type')
                
                # Verificar se é médico ou enfermeira/enfermeiro
                if user_type not in ['medico', 'enfermeira', 'enfermeiro']:
                    flash('Acesso restrito a profissionais de saúde.', 'warning')
                    return redirect(url_for('dashboard'))
                
                return f(*args, **kwargs)
            return decorated_function
        
        # ===================== FUNÇÃO AUXILIAR =====================
        def decode_bytes(value):
            if value is None:
                return None
            if isinstance(value, (bytes, bytearray)):
                try:
                    return value.decode('utf-8')
                except:
                    return str(value)
            return value
        
        # ===================== ROTA: RECEITA DIGITAL (CRIAR) =====================
        @medico_bp.route('/consulta/<int:consulta_id>/receita-digital')
        @profissional_saude_required
        def criar_receita_digital(consulta_id):
            """Página para criar receita digital (médicos e enfermeiras)"""
            from utils.receitas_data import MEDICAMENTOS_POR_CONDICAO
            
            user_type = session.get('user_type')
            
            # Buscar informações do profissional
            if user_type == 'medico':
                profissional_info = base['obter_info_medico']()
                campo_identificador = 'crm'
                identificador_valor = profissional_info.get('crm', '') if profissional_info else ''
                tipo_profissional = 'Médico'
            else:
                profissional_info = base.get('obter_info_enfermeiro', lambda: None)()
                campo_identificador = 'registro_profissional'
                identificador_valor = profissional_info.get('registro_profissional', '') if profissional_info else ''
                tipo_profissional = 'Enfermeiro(a)'
            
            if not profissional_info:
                flash('Acesso não autorizado.', 'danger')
                return redirect(url_for('auth.login'))
            
            cursor = mysql.connection.cursor()
            
            # Verificar permissão da consulta
            if user_type == 'medico':
                cursor.execute("""
                    SELECT 
                        c.id, c.paciente_id, c.medico_id, c.status, c.data_hora,
                        c.observacoes, c.diagnostico_texto,
                        p_u.nome as paciente_nome, p.data_nascimento,
                        m_u.nome as medico_nome, m.especialidade, m.crm
                    FROM consultas c
                    JOIN pacientes p ON c.paciente_id = p.id
                    JOIN usuarios p_u ON p.usuario_id = p_u.id
                    JOIN medicos m ON c.medico_id = m.id
                    JOIN usuarios m_u ON m.usuario_id = m_u.id
                    WHERE c.id = %s AND c.medico_id = %s
                """, (consulta_id, profissional_info['id']))
            else:
                # Enfermeiras podem acessar consultas, mas sem modificar
                cursor.execute("""
                    SELECT 
                        c.id, c.paciente_id, c.medico_id, c.status, c.data_hora,
                        c.observacoes, c.diagnostico_texto,
                        p_u.nome as paciente_nome, p.data_nascimento,
                        m_u.nome as medico_nome, m.especialidade, m.crm
                    FROM consultas c
                    JOIN pacientes p ON c.paciente_id = p.id
                    JOIN usuarios p_u ON p.usuario_id = p_u.id
                    JOIN medicos m ON c.medico_id = m.id
                    JOIN usuarios m_u ON m.usuario_id = m_u.id
                    WHERE c.id = %s
                """, (consulta_id,))
            
            consulta_raw = cursor.fetchone()
            cursor.close()
            
            if not consulta_raw:
                flash('Consulta não encontrada.', 'danger')
                return redirect(url_for('medico.dashboard'))
            
            if isinstance(consulta_raw, dict):
                consulta = {
                    'id': consulta_raw.get('id'),
                    'paciente_id': consulta_raw.get('paciente_id'),
                    'medico_id': consulta_raw.get('medico_id'),
                    'status': consulta_raw.get('status'),
                    'data_hora': consulta_raw.get('data_hora').strftime('%d/%m/%Y %H:%M') if consulta_raw.get('data_hora') else '',
                    'observacoes': consulta_raw.get('observacoes'),
                    'diagnostico_texto': consulta_raw.get('diagnostico_texto'),
                    'paciente_nome': consulta_raw.get('paciente_nome'),
                    'paciente_data_nascimento': consulta_raw.get('data_nascimento'),
                    'medico_nome': consulta_raw.get('medico_nome'),
                    'medico_especialidade': consulta_raw.get('especialidade'),
                    'medico_crm': consulta_raw.get('crm')
                }
            else:
                consulta = {
                    'id': consulta_raw[0],
                    'paciente_id': consulta_raw[1],
                    'medico_id': consulta_raw[2],
                    'status': consulta_raw[3],
                    'data_hora': consulta_raw[4].strftime('%d/%m/%Y %H:%M') if consulta_raw[4] else '',
                    'observacoes': consulta_raw[5],
                    'diagnostico_texto': consulta_raw[6],
                    'paciente_nome': consulta_raw[7],
                    'paciente_data_nascimento': consulta_raw[8],
                    'medico_nome': consulta_raw[9],
                    'medico_especialidade': consulta_raw[10],
                    'medico_crm': consulta_raw[11]
                }
            
            # Adicionar informações do profissional responsável
            consulta['responsavel_tipo'] = tipo_profissional
            consulta['responsavel_nome'] = profissional_info.get('nome')
            consulta['responsavel_identificador'] = identificador_valor
            
            return render_template('medico/receita_digital.html',
                                  consulta=consulta,
                                  medicamentos_por_condicao=MEDICAMENTOS_POR_CONDICAO,
                                  profissional_tipo=user_type,
                                  datetime=datetime)
        
        # ===================== ROTA: SALVAR RECEITA AJAX =====================
        @medico_bp.route('/receita/salvar-ajax', methods=['POST'])
        @profissional_saude_required
        def salvar_receita_ajax():
            """Salva a receita via AJAX (médicos e enfermeiras)"""
            try:
                if 'user_id' not in session:
                    return jsonify({"success": False, "error": "Não autorizado"}), 401
                
                if request.is_json:
                    data = request.get_json()
                else:
                    data = request.form.to_dict()
                
                if not data:
                    return jsonify({"success": False, "error": "Nenhum dado recebido"}), 400
                
                consulta_id = data.get('consulta_id')
                diagnostico = data.get('diagnostico', '')
                observacoes = data.get('observacoes_geralis', '')
                receita_texto = data.get('receita_texto', '')
                
                user_type = session.get('user_type')
                profissional_nome = session.get('user_name', 'Profissional')
                
                prescricao_texto = receita_texto
                
                if not prescricao_texto:
                    medicamentos_json = data.get('medicamentos_json', '[]')
                    try:
                        medicamentos = json.loads(medicamentos_json) if medicamentos_json else []
                        if medicamentos:
                            prescricao_texto = ""
                            for i, med in enumerate(medicamentos, 1):
                                prescricao_texto += f"{i}. {med.get('nome', 'Medicamento')}"
                                if med.get('apresentacao'):
                                    prescricao_texto += f" - {med.get('apresentacao')}"
                                prescricao_texto += "\n"
                                if med.get('posologia'):
                                    prescricao_texto += f"   Posologia: {med.get('posologia')}\n"
                                if med.get('frequencia'):
                                    prescricao_texto += f"   Frequência: {med.get('frequencia')}\n"
                                if med.get('duracao'):
                                    prescricao_texto += f"   Duração: {med.get('duracao')}\n"
                                if med.get('quantidade'):
                                    prescricao_texto += f"   Quantidade: {med.get('quantidade')}\n"
                                prescricao_texto += "\n"
                    except:
                        pass
                
                # Adicionar cabeçalho com informações do profissional
                if prescricao_texto:
                    prescricao_texto = f"[Prescrição por: {profissional_nome} ({user_type}) - {datetime.now().strftime('%d/%m/%Y %H:%M')}]\n\n{prescricao_texto}"
                
                conn = mysql.connection
                cursor = conn.cursor()
                
                try:
                    cursor.execute("SELECT id FROM receita WHERE consulta_id = %s", (consulta_id,))
                    existing = cursor.fetchone()
                    
                    if existing:
                        existing_id = existing[0] if isinstance(existing, (list, tuple)) else existing.get('id')
                        cursor.execute("""
                            UPDATE receita 
                            SET diagnostico = %s,
                                prescricao = %s,
                                recomendacoes = %s,
                                profissional_tipo = %s,
                                profissional_nome = %s,
                                atualizado_em = NOW()
                            WHERE consulta_id = %s
                        """, (diagnostico, prescricao_texto, observacoes, user_type, profesional_nome, consulta_id))
                        receita_id = existing_id
                    else:
                        cursor.execute("""
                            INSERT INTO receita 
                            (consulta_id, diagnostico, prescricao, recomendacoes, 
                             profissional_tipo, profissional_nome, status, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, 'ativa', NOW())
                        """, (consulta_id, diagnostico, prescricao_texto, observacoes, 
                              user_type, profissional_nome))
                        receita_id = cursor.lastrowid
                    
                    conn.commit()
                    
                except Exception as db_error:
                    conn.rollback()
                    raise db_error
                finally:
                    cursor.close()
                
                redirect_url = url_for('medico.visualizar_receita_gerada', receita_id=receita_id, _external=False)
                
                return jsonify({
                    "success": True, 
                    "message": "Receita salva com sucesso",
                    "receita_id": receita_id,
                    "redirect_url": redirect_url
                })
                
            except Exception as e:
                logger.error(f"Erro ao salvar receita: {e}")
                logger.error(traceback.format_exc())
                return jsonify({"success": False, "error": str(e)}), 500
        
        # ===================== ROTA: VISUALIZAR RECEITA GERADA =====================
        @medico_bp.route('/receita/<int:receita_id>/visualizar')
        @profissional_saude_required
        def visualizar_receita_gerada(receita_id):
            """Visualiza uma receita já gerada (médicos e enfermeiras)"""
            try:
                if 'user_id' not in session:
                    flash('Faça login para acessar.', 'danger')
                    return redirect(url_for('auth.login'))
                
                cursor = mysql.connection.cursor()
                cursor.execute("""
                    SELECT r.*, c.paciente_id, c.medico_id
                    FROM receita r
                    JOIN consultas c ON r.consulta_id = c.id
                    WHERE r.id = %s
                """, (receita_id,))
                
                result = cursor.fetchone()
                cursor.close()
                
                if not result:
                    flash('Receita não encontrada.', 'danger')
                    return redirect(url_for('medico.dashboard'))
                
                if isinstance(result, dict):
                    row = result
                    consulta_id = row.get('consulta_id')
                    diagnostico = row.get('diagnostico')
                    prescricao = row.get('prescricao')
                    recomendacoes = row.get('recomendacoes')
                    profissional_tipo = row.get('profissional_tipo')
                    profissional_nome = row.get('profissional_nome')
                else:
                    consulta_id = result[1] if len(result) > 1 else None
                    diagnostico = result[2] if len(result) > 2 else None
                    prescricao = result[3] if len(result) > 3 else None
                    recomendacoes = result[4] if len(result) > 4 else None
                    profissional_tipo = result[8] if len(result) > 8 else None
                    profissional_nome = result[9] if len(result) > 9 else None
                
                cursor = mysql.connection.cursor()
                cursor.execute("SELECT paciente_id, medico_id FROM consultas WHERE id = %s", (consulta_id,))
                consulta_info = cursor.fetchone()
                
                paciente_id = None
                medico_id = None
                if consulta_info:
                    if isinstance(consulta_info, dict):
                        paciente_id = consulta_info.get('paciente_id')
                        medico_id = consulta_info.get('medico_id')
                    else:
                        paciente_id = consulta_info[0]
                        medico_id = consulta_info[1]
                
                cursor.execute("""
                    SELECT u.nome, p.data_nascimento
                    FROM pacientes p
                    JOIN usuarios u ON p.usuario_id = u.id
                    WHERE p.id = %s
                """, (paciente_id,))
                paciente_raw = cursor.fetchone()
                
                cursor.execute("""
                    SELECT u.nome, m.crm, m.especialidade
                    FROM medicos m
                    JOIN usuarios u ON m.usuario_id = u.id
                    WHERE m.id = %s
                """, (medico_id,))
                medico_raw = cursor.fetchone()
                cursor.close()
                
                paciente_nome = None
                paciente_idade = None
                if paciente_raw:
                    if isinstance(paciente_raw, dict):
                        paciente_nome = paciente_raw.get('nome')
                        data_nasc = paciente_raw.get('data_nascimento')
                    else:
                        paciente_nome = paciente_raw[0]
                        data_nasc = paciente_raw[1]
                    
                    if data_nasc:
                        hoje = datetime.now().date()
                        if isinstance(data_nasc, datetime):
                            birth_date = data_nasc.date()
                        else:
                            birth_date = data_nasc
                        idade = hoje.year - birth_date.year - ((hoje.month, hoje.day) < (birth_date.month, birth_date.day))
                        paciente_idade = f"{idade} anos"
                
                medico_nome = None
                medico_crm = None
                medico_especialidade = None
                if medico_raw:
                    if isinstance(medico_raw, dict):
                        medico_nome = medico_raw.get('nome')
                        medico_crm = medico_raw.get('crm')
                        medico_especialidade = medico_raw.get('especialidade')
                    else:
                        medico_nome = medico_raw[0]
                        medico_crm = medico_raw[1]
                        medico_especialidade = medico_raw[2]
                
                return render_template('medico/receita_gerada.html',
                                      receita_id=receita_id,
                                      receita=prescricao or '',
                                      observacoes_receita=recomendacoes or '',
                                      medicamentos=[],
                                      profissional_tipo=profissional_tipo,
                                      profissional_nome=profissional_nome,
                                      pedido={
                                          'id': consulta_id,
                                          'paciente_nome': paciente_nome or 'N/A',
                                          'paciente_idade': paciente_idade or 'N/A',
                                          'diagnostico_ia': diagnostico or '',
                                          'sintomas_lista': []
                                      },
                                      medico={
                                          'nome': medico_nome or 'Dr. Desconhecido',
                                          'crm': medico_crm or 'N/A',
                                          'especialidade': medico_especialidade or 'N/A'
                                      },
                                      gemini_available=True,
                                      datetime=datetime,
                                      pdf_path=None)
                
            except Exception as e:
                logger.error(f"Erro ao visualizar receita: {e}")
                logger.error(traceback.format_exc())
                flash('Erro ao carregar receita.', 'danger')
                return redirect(url_for('medico.dashboard'))
        
        # ===================== ROTA: LISTAR TODAS AS RECEITAS =====================
        @medico_bp.route('/receitas')
        @profissional_saude_required
        def listar_receitas():
            """Lista todas as receitas (médicos e enfermeiras)"""
            try:
                if 'user_id' not in session:
                    flash('Faça login para acessar.', 'danger')
                    return redirect(url_for('auth.login'))
                
                user_type = session.get('user_type')
                user_id = session.get('user_id')
                
                cursor = mysql.connection.cursor()
                
                if user_type == 'medico':
                    # Médico vê apenas suas receitas
                    medico_info = base['obter_info_medico']()
                    if not medico_info:
                        flash('Médico não encontrado.', 'danger')
                        return redirect(url_for('auth.login'))
                    
                    cursor.execute("""
                        SELECT 
                            r.id,
                            r.consulta_id,
                            r.diagnostico,
                            r.prescricao,
                            r.created_at,
                            r.profissional_tipo,
                            r.profissional_nome,
                            c.data_hora as consulta_data,
                            u.nome as paciente_nome
                        FROM receita r
                        JOIN consultas c ON r.consulta_id = c.id
                        JOIN pacientes p ON c.paciente_id = p.id
                        JOIN usuarios u ON p.usuario_id = u.id
                        WHERE c.medico_id = %s
                        ORDER BY r.created_at DESC
                    """, (medico_info['id'],))
                else:
                    # Enfermeira vê todas as receitas que ajudou a criar
                    cursor.execute("""
                        SELECT 
                            r.id,
                            r.consulta_id,
                            r.diagnostico,
                            r.prescricao,
                            r.created_at,
                            r.profissional_tipo,
                            r.profissional_nome,
                            c.data_hora as consulta_data,
                            u.nome as paciente_nome
                        FROM receita r
                        JOIN consultas c ON r.consulta_id = c.id
                        JOIN pacientes p ON c.paciente_id = p.id
                        JOIN usuarios u ON p.usuario_id = u.id
                        WHERE r.profissional_nome = %s OR r.profissional_tipo = 'enfermeira'
                        ORDER BY r.created_at DESC
                    """, (session.get('user_name', ''),))
                
                receitas = cursor.fetchall()
                cursor.close()
                
                receitas_lista = []
                for rec in receitas:
                    receitas_lista.append({
                        'id': rec[0],
                        'consulta_id': rec[1],
                        'diagnostico': rec[2][:100] + '...' if rec[2] and len(rec[2]) > 100 else rec[2],
                        'created_at': rec[4].strftime('%d/%m/%Y %H:%M') if rec[4] else '',
                        'consulta_data': rec[7].strftime('%d/%m/%Y %H:%M') if rec[7] else '',
                        'paciente_nome': rec[8] if len(rec) > 8 else 'N/A',
                        'profissional_tipo': rec[5] if len(rec) > 5 else 'N/A',
                        'profissional_nome': rec[6] if len(rec) > 6 else 'N/A'
                    })
                
                return render_template('medico/listar_receitas.html',
                                      receitas=receitas_lista,
                                      user=session,
                                      user_type=user_type)
                
            except Exception as e:
                logger.error(f"Erro ao listar receitas: {e}")
                logger.error(traceback.format_exc())
                flash('Erro ao carregar lista de receitas.', 'danger')
                return redirect(url_for('medico.dashboard'))
        
        # ===================== ROTA: HISTÓRICO DO PACIENTE =====================
        @medico_bp.route('/historico/paciente/<int:paciente_id>')
        @profissional_saude_required
        def historico_paciente(paciente_id):
            """Visualiza o histórico médico completo do paciente"""
            try:
                # Buscar informações do paciente
                paciente_result = base['execute_query']("""
                    SELECT p.id, p.data_nascimento, p.genero, p.telefone, p.endereco,
                           u.nome, u.email
                    FROM pacientes p
                    JOIN usuarios u ON p.usuario_id = u.id
                    WHERE p.id = %s
                """, (paciente_id,), fetch=True, one=True)
                
                if not paciente_result:
                    flash('Paciente não encontrado.', 'danger')
                    return redirect(url_for('medico.consultas'))
                
                # Converter paciente para dict
                if isinstance(paciente_result, dict):
                    paciente = paciente_result
                else:
                    paciente = {
                        'id': paciente_result[0] if len(paciente_result) > 0 else None,
                        'data_nascimento': paciente_result[1] if len(paciente_result) > 1 else None,
                        'genero': decode_bytes(paciente_result[2]) if len(paciente_result) > 2 else '',
                        'telefone': decode_bytes(paciente_result[3]) if len(paciente_result) > 3 else '',
                        'endereco': decode_bytes(paciente_result[4]) if len(paciente_result) > 4 else '',
                        'nome': decode_bytes(paciente_result[5]) if len(paciente_result) > 5 else '',
                        'email': decode_bytes(paciente_result[6]) if len(paciente_result) > 6 else ''
                    }
                
                # Calcular idade
                from datetime import date
                idade = None
                data_nasc = paciente.get('data_nascimento')
                if data_nasc:
                    try:
                        if isinstance(data_nasc, datetime):
                            data_nasc = data_nasc.date()
                        elif isinstance(data_nasc, str):
                            data_nasc = datetime.strptime(data_nasc, '%Y-%m-%d').date()
                        hoje = date.today()
                        idade = hoje.year - data_nasc.year
                        if (hoje.month, hoje.day) < (data_nasc.month, data_nasc.day):
                            idade -= 1
                    except:
                        pass
                
                # Buscar consultas do paciente
                consultas = base['execute_query']("""
                    SELECT c.id, c.data_hora, c.status, c.observacoes, c.sintomas,
                           m_u.nome as medico_nome, m.especialidade
                    FROM consultas c
                    JOIN medicos m ON c.medico_id = m.id
                    JOIN usuarios m_u ON m.usuario_id = m_u.id
                    WHERE c.paciente_id = %s
                    ORDER BY c.data_hora DESC
                """, (paciente_id,), fetch=True) or []
                
                # Buscar receitas
                receitas = base['execute_query']("""
                    SELECT r.id, r.created_at, r.diagnostico, r.prescricao, r.recomendacoes
                    FROM receita r
                    JOIN consultas c ON r.consulta_id = c.id
                    WHERE c.paciente_id = %s
                    ORDER BY r.created_at DESC
                """, (paciente_id,), fetch=True) or []
                
                # Buscar exames/pedidos
                exames = base['execute_query']("""
                    SELECT pa.id, pa.tipo_exame, pa.status, pa.data_solicitacao, 
                           pa.resultado_analise, pa.diagnostico_analista
                    FROM pedidos_analise pa
                    JOIN consultas c ON pa.consulta_id = c.id
                    WHERE c.paciente_id = %s
                    ORDER BY pa.data_solicitacao DESC
                """, (paciente_id,), fetch=True) or []
                
                # Buscar sinais vitais
                sinais_vitais = base['execute_query']("""
                    SELECT sv.pressao_arterial, sv.frequencia_cardiaca, sv.frequencia_respiratoria,
                           sv.temperatura, sv.saturacao_oxigenio, sv.glicemia, sv.peso,
                           sv.data_afericao, sv.observacoes, u.nome as enfermeiro_nome
                    FROM sinais_vitais sv
                    JOIN consultas c ON sv.consulta_id = c.id
                    LEFT JOIN usuarios u ON sv.enfermeiro_id = u.id
                    WHERE c.paciente_id = %s
                    ORDER BY sv.data_afericao DESC
                    LIMIT 20
                """, (paciente_id,), fetch=True) or []
                
                return render_template('medico/historico_paciente.html',
                                     paciente=paciente,
                                     idade=idade,
                                     consultas=consultas,
                                     receitas=receitas,
                                     exames=exames,
                                     sinais_vitais=sinais_vitais)
                                 
            except Exception as e:
                logger.error(f"Erro ao carregar histórico: {e}")
                flash(f'Erro ao carregar histórico: {str(e)}', 'danger')
                return redirect(url_for('medico.consultas'))
        
        # ===================== ROTA: SINAIS VITAIS PARA MÉDICO =====================
        @medico_bp.route('/consulta/<int:consulta_id>/sinais-vitais', methods=['GET', 'POST'])
        @profissional_saude_required
        def medico_sinais_vitais(consulta_id):
            """Médico registra sinais vitais"""
            try:
                medico_id = session.get('medico_id')
                
                # Buscar dados da consulta
                consulta = base['execute_query']("""
                    SELECT c.id, c.paciente_id, c.status, c.data_hora,
                           u.nome as paciente_nome,
                           p.data_nascimento,
                           p.genero
                    FROM consultas c
                    JOIN pacientes p ON c.paciente_id = p.id
                    JOIN usuarios u ON p.usuario_id = u.id
                    WHERE c.id = %s AND c.medico_id = %s
                """, (consulta_id, medico_id), fetch=True, one=True)
                
                if not consulta:
                    flash('Consulta não encontrada.', 'danger')
                    return redirect(url_for('medico.consultas'))
                
                # Converter para dict se for tuple
                if not isinstance(consulta, dict):
                    consulta = {
                        'id': consulta[0] if len(consulta) > 0 else None,
                        'paciente_id': consulta[1] if len(consulta) > 1 else None,
                        'status': decode_bytes(consulta[2]) if len(consulta) > 2 else '',
                        'data_hora': consulta[3] if len(consulta) > 3 else None,
                        'paciente_nome': decode_bytes(consulta[4]) if len(consulta) > 4 else '',
                        'data_nascimento': consulta[5] if len(consulta) > 5 else None,
                        'genero': decode_bytes(consulta[6]) if len(consulta) > 6 else ''
                    }
                
                # Calcular idade
                idade = None
                data_nasc = consulta.get('data_nascimento')
                if data_nasc:
                    try:
                        if isinstance(data_nasc, datetime):
                            data_nasc = data_nasc.date()
                        elif isinstance(data_nasc, str):
                            data_nasc = datetime.strptime(data_nasc, '%Y-%m-%d').date()
                        from datetime import date
                        hoje = date.today()
                        idade = hoje.year - data_nasc.year
                        if (hoje.month, hoje.day) < (data_nasc.month, data_nasc.day):
                            idade -= 1
                    except:
                        pass
                
                if request.method == 'POST':
                    # Coletar dados do formulário
                    pressao_arterial = request.form.get('pressao_arterial')
                    frequencia_cardiaca = request.form.get('frequencia_cardiaca')
                    frequencia_respiratoria = request.form.get('frequencia_respiratoria')
                    temperatura = request.form.get('temperatura')
                    saturacao_oxigenio = request.form.get('saturacao_oxigenio')
                    glicemia = request.form.get('glicemia')
                    peso = request.form.get('peso')
                    observacoes = request.form.get('observacoes')
                    
                    # Validar pressão arterial
                    if pressao_arterial:
                        pressao_arterial = pressao_arterial.replace('/', 'x')
                        if not re.match(r'^\d{2,3}x\d{2,3}$', pressao_arterial):
                            flash('Formato de pressão arterial inválido. Use: 120/80 ou 120x80', 'danger')
                            return redirect(url_for('medico.medico_sinais_vitais', consulta_id=consulta_id))
                    
                    # Inserir sinais vitais
                    base['execute_query']("""
                        INSERT INTO sinais_vitais 
                        (consulta_id, pressao_arterial, frequencia_cardiaca, frequencia_respiratoria,
                         temperatura, saturacao_oxigenio, glicemia, peso, observacoes, data_afericao)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """, (consulta_id, pressao_arterial, frequencia_cardiaca or None, 
                          frequencia_respiratoria or None, temperatura or None, 
                          saturacao_oxigenio or None, glicemia or None, peso or None, 
                          observacoes or None), commit=True)
                    
                    flash('Sinais vitais registrados com sucesso!', 'success')
                    return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
                
                return render_template('medico/sinais_vitais.html',
                                     consulta=consulta,
                                     consulta_id=consulta_id,
                                     idade=idade)
                                     
            except Exception as e:
                logger.error(f"Erro ao registrar sinais vitais: {e}")
                flash(f'Erro ao registrar sinais vitais: {str(e)}', 'danger')
                return redirect(url_for('medico.consultas'))
        
        # ===================== LISTA DE MÓDULOS EXISTENTES =====================
        modules = [
            init_medico_dashboard(base),
            init_medico_pedidos(base, gemini_available),
            init_medico_perfil(base),
            init_medico_consultas(base),
            init_medico_pacientes(mysql, base),
            init_medico_api(mysql, base),
            init_medico_debug(base),
            init_medico_sinais_vitais(base),  # NOVO MÓDULO
        ]
        
        # Inicializar módulo de receitas
        if receita_service:
            try:
                receitas_module = init_medico_receitas(mysql, base, receita_service, gemini_available)
                modules.append(receitas_module)
                logger.info(f"Módulo de receitas inicializado com sucesso!")
            except Exception as e:
                logger.error(f"Erro ao inicializar módulo de receitas: {e}")
        
        # Registrar rotas dos módulos
        total_rotas = 0
        for idx, module in enumerate(modules):
            logger.info(f"Registrando rotas do módulo {idx+1}/{len(modules)} - {len(module['routes'])} rotas")
            for route in module['routes']:
                medico_bp.add_url_rule(**route)
                total_rotas += 1
        
        logger.info(f"Total de {total_rotas} rotas registradas no blueprint médico")
        
        # Registrar blueprint de consultas detalhadas
        try:
            consulta_detalhes_bp = create_consulta_blueprint(mysql)
            medico_bp.register_blueprint(consulta_detalhes_bp)
            logger.info("Blueprint de consultas detalhadas registrado")
        except Exception as e:
            logger.error(f"Erro ao registrar blueprint de consultas: {e}")
        
        # Exportar funções
        medico_bp.obter_info_medico = base['obter_info_medico']
        medico_bp.execute_query = base['execute_query']
        medico_bp.formatar_data = base['formatar_data']
        medico_bp.calcular_idade = base['calcular_idade']
        
        # Rota de debug
        @medico_bp.route('/debug-rotas')
        def debug_rotas():
            output = "<h1>🔍 Rotas disponíveis em 'medico':</h1>"
            output += "<style>table { border-collapse: collapse; width: 100%; } th, td { border: 1px solid #ddd; padding: 8px; } th { background-color: #4CAF50; color: white; }</style>"
            output += "<tr><th>Endpoint</th><th>URL</th><th>Métodos</th></table>"
            for rule in app.url_map.iter_rules():
                if str(rule).startswith('/medico/'):
                    output += f"<tr><td style='font-family: monospace;'>{rule.endpoint}</td><td>{rule}</td><td>{', '.join(rule.methods)}</td></tr>"
            output += "</table><br><a href='/medico/dashboard'>Voltar ao Dashboard</a>"
            return output
        
        logger.info("Blueprint médico inicializado com sucesso!")
        print("="*50)
        
        return medico_bp
        
    except Exception as e:
        logger.error(f"Erro ao inicializar blueprint médico: {e}")
        logger.error(traceback.format_exc())
        raise

__all__ = ['init_medico']
