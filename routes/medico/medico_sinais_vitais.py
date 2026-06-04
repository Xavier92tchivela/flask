# routes/medico/medico_sinais_vitais.py
from flask import render_template, request, flash, redirect, url_for, session, jsonify
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)

def init_medico_sinais_vitais(base):
    """
    Inicializa rotas de sinais vitais para o médico
    
    Args:
        base: Dicionário com funções base
    
    Returns:
        Dicionário com as rotas do módulo
    """
    
    medico_required = base['medico_required']
    execute_query = base['execute_query']
    formatar_data = base['formatar_data']
    
    def decode_value(val):
        if val is None:
            return ''
        if isinstance(val, bytes):
            try:
                return val.decode('utf-8')
            except:
                return str(val)
        return str(val) if val else ''
    
    @medico_required
    def listar_sinais_vitais():
        """Lista todos os sinais vitais das consultas do médico"""
        try:
            medico_id = session.get('medico_id')
            
            # Buscar sinais vitais das consultas do médico
            sinais = execute_query("""
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
                    u.nome as paciente_nome,
                    p.id as paciente_id,
                    c.id as consulta_id,
                    c.data_hora as consulta_data,
                    COALESCE(eu.nome, 'Médico') as responsavel_nome
                FROM sinais_vitais sv
                JOIN consultas c ON sv.consulta_id = c.id
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                LEFT JOIN enfermeiros e ON sv.enfermeiro_id = e.id
                LEFT JOIN usuarios eu ON e.usuario_id = eu.id
                WHERE c.medico_id = %s
                ORDER BY sv.data_afericao DESC
            """, (medico_id,), fetch=True) or []
            
            # Processar resultados
            resultados = []
            for s in sinais:
                resultados.append({
                    'id': s[0],
                    'pressao_arterial': decode_value(s[1]),
                    'frequencia_cardiaca': s[2],
                    'frequencia_respiratoria': s[3],
                    'temperatura': float(s[4]) if s[4] else None,
                    'saturacao_oxigenio': s[5],
                    'glicemia': s[6],
                    'peso': float(s[7]) if s[7] else None,
                    'data_afericao': s[8].strftime('%d/%m/%Y %H:%M') if s[8] else '',
                    'observacoes': decode_value(s[9]),
                    'paciente_nome': decode_value(s[10]),
                    'paciente_id': s[11],
                    'consulta_id': s[12],
                    'consulta_data': s[13].strftime('%d/%m/%Y %H:%M') if s[13] else '',
                    'responsavel_nome': decode_value(s[14])
                })
            
            return render_template('medico/sinais_vitais/listar.html',
                                 sinais=resultados,
                                 formatar_data=formatar_data)
        except Exception as e:
            logger.error(f"Erro ao listar sinais vitais: {e}")
            flash('Erro ao carregar lista de sinais vitais.', 'danger')
            return redirect(url_for('medico.dashboard'))
    
    @medico_required
    def registrar_sinais_vitais(consulta_id):
        """Médico registra sinais vitais para uma consulta"""
        try:
            medico_id = session.get('medico_id')
            
            # Buscar dados da consulta
            consulta = execute_query("""
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
                    'status': decode_value(consulta[2]) if len(consulta) > 2 else '',
                    'data_hora': consulta[3] if len(consulta) > 3 else None,
                    'paciente_nome': decode_value(consulta[4]) if len(consulta) > 4 else '',
                    'data_nascimento': consulta[5] if len(consulta) > 5 else None,
                    'genero': decode_value(consulta[6]) if len(consulta) > 6 else ''
                }
            
            # Calcular idade
            idade = None
            data_nasc = consulta.get('data_nascimento')
            if data_nasc:
                try:
                    if isinstance(data_nasc, datetime):
                        data_nasc = data_nasc.date()
                    elif isinstance(data_nasc, str):
                        from datetime import datetime as dt
                        data_nasc = dt.strptime(data_nasc, '%Y-%m-%d').date()
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
                        return redirect(url_for('medico.registrar_sinais_vitais', consulta_id=consulta_id))
                
                # Inserir sinais vitais
                execute_query("""
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
            
            return render_template('medico/sinais_vitais/registrar.html',
                                 consulta=consulta,
                                 consulta_id=consulta_id,
                                 idade=idade)
                                 
        except Exception as e:
            logger.error(f"Erro ao registrar sinais vitais: {e}")
            flash(f'Erro ao registrar sinais vitais: {str(e)}', 'danger')
            return redirect(url_for('medico.consultas'))
    
    @medico_required
    def detalhes_sinais_vitais(sinal_id):
        """Ver detalhes de um registro de sinais vitais"""
        try:
            medico_id = session.get('medico_id')
            
            sinal = execute_query("""
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
                    u.nome as paciente_nome,
                    p.id as paciente_id,
                    c.id as consulta_id,
                    c.data_hora as consulta_data,
                    COALESCE(eu.nome, 'Médico') as responsavel_nome
                FROM sinais_vitais sv
                JOIN consultas c ON sv.consulta_id = c.id
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                LEFT JOIN enfermeiros e ON sv.enfermeiro_id = e.id
                LEFT JOIN usuarios eu ON e.usuario_id = eu.id
                WHERE sv.id = %s AND c.medico_id = %s
            """, (sinal_id, medico_id), fetch=True, one=True)
            
            if not sinal:
                flash('Registro não encontrado.', 'danger')
                return redirect(url_for('medico.listar_sinais_vitais'))
            
            # Converter para dict se for tuple
            if not isinstance(sinal, dict):
                sinal = {
                    'id': sinal[0],
                    'pressao_arterial': decode_value(sinal[1]),
                    'frequencia_cardiaca': sinal[2],
                    'frequencia_respiratoria': sinal[3],
                    'temperatura': float(sinal[4]) if sinal[4] else None,
                    'saturacao_oxigenio': sinal[5],
                    'glicemia': sinal[6],
                    'peso': float(sinal[7]) if sinal[7] else None,
                    'data_afericao': sinal[8].strftime('%d/%m/%Y %H:%M') if sinal[8] else '',
                    'observacoes': decode_value(sinal[9]),
                    'paciente_nome': decode_value(sinal[10]),
                    'paciente_id': sinal[11],
                    'consulta_id': sinal[12],
                    'consulta_data': sinal[13].strftime('%d/%m/%Y %H:%M') if sinal[13] else '',
                    'responsavel_nome': decode_value(sinal[14])
                }
            
            return render_template('medico/sinais_vitais/detalhes.html',
                                 sinal=sinal)
        except Exception as e:
            logger.error(f"Erro ao verificar sinal vital: {e}")
            flash('Erro ao carregar detalhes.', 'danger')
            return redirect(url_for('medico.listar_sinais_vitais'))
    
    @medico_required
    def sinais_vitais_paciente(paciente_id):
        """Histórico de sinais vitais de um paciente específico"""
        try:
            medico_id = session.get('medico_id')
            
            # Buscar paciente
            paciente = execute_query("""
                SELECT p.id, u.nome, p.data_nascimento, p.genero
                FROM pacientes p
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE p.id = %s
            """, (paciente_id,), fetch=True, one=True)
            
            if not paciente:
                flash('Paciente não encontrado.', 'danger')
                return redirect(url_for('medico.dashboard'))
            
            # Buscar sinais vitais do paciente
            sinais = execute_query("""
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
                    c.id as consulta_id,
                    c.data_hora as consulta_data,
                    COALESCE(eu.nome, 'Médico') as responsavel_nome
                FROM sinais_vitais sv
                JOIN consultas c ON sv.consulta_id = c.id
                LEFT JOIN enfermeiros e ON sv.enfermeiro_id = e.id
                LEFT JOIN usuarios eu ON e.usuario_id = eu.id
                WHERE c.paciente_id = %s AND c.medico_id = %s
                ORDER BY sv.data_afericao DESC
            """, (paciente_id, medico_id), fetch=True) or []
            
            resultados = []
            for s in sinais:
                resultados.append({
                    'id': s[0],
                    'pressao_arterial': decode_value(s[1]),
                    'frequencia_cardiaca': s[2],
                    'frequencia_respiratoria': s[3],
                    'temperatura': float(s[4]) if s[4] else None,
                    'saturacao_oxigenio': s[5],
                    'glicemia': s[6],
                    'peso': float(s[7]) if s[7] else None,
                    'data_afericao': s[8].strftime('%d/%m/%Y %H:%M') if s[8] else '',
                    'observacoes': decode_value(s[9]),
                    'consulta_id': s[10],
                    'consulta_data': s[11].strftime('%d/%m/%Y %H:%M') if s[11] else '',
                    'responsavel_nome': decode_value(s[12])
                })
            
            # Converter paciente para dict
            if not isinstance(paciente, dict):
                paciente = {
                    'id': paciente[0],
                    'nome': decode_value(paciente[1]),
                    'data_nascimento': paciente[2],
                    'genero': decode_value(paciente[3])
                }
            
            return render_template('medico/sinais_vitais/paciente.html',
                                 paciente=paciente,
                                 sinais=resultados)
        except Exception as e:
            logger.error(f"Erro ao carregar histórico do paciente: {e}")
            flash('Erro ao carregar histórico.', 'danger')
            return redirect(url_for('medico.dashboard'))
    
    return {
        'routes': [
            {'rule': '/sinais-vitais', 'view_func': listar_sinais_vitais, 'methods': ['GET']},
            {'rule': '/sinais-vitais/registrar/<int:consulta_id>', 'view_func': registrar_sinais_vitais, 'methods': ['GET', 'POST']},
            {'rule': '/sinais-vitais/<int:sinal_id>', 'view_func': detalhes_sinais_vitais, 'methods': ['GET']},
            {'rule': '/sinais-vitais/paciente/<int:paciente_id>', 'view_func': sinais_vitais_paciente, 'methods': ['GET']}
        ]
    }
