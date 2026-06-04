# routes/medico/medico_sinais_vitais.py
from flask import render_template, request, flash, redirect, url_for, session
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)

def init_medico_sinais_vitais(base):
    """Inicializa rotas de sinais vitais para o médico"""
    
    medico_required = base['medico_required']
    execute_query = base['execute_query']
    
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
    def registrar_sinais_vitais(consulta_id):
        """Médico registra sinais vitais para uma consulta"""
        try:
            medico_id = session.get('medico_id')
            
            # Buscar dados da consulta
            consulta = execute_query("""
                SELECT c.id, c.paciente_id, u.nome as paciente_nome,
                       p.data_nascimento, p.genero
                FROM consultas c
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE c.id = %s AND c.medico_id = %s
            """, (consulta_id, medico_id), fetch=True, one=True)
            
            if not consulta:
                flash('Consulta não encontrada.', 'danger')
                return redirect(url_for('medico.consultas'))
            
            # Converter para dict
            if isinstance(consulta, dict):
                consulta_dict = consulta
            else:
                consulta_dict = {
                    'id': consulta[0],
                    'paciente_id': consulta[1],
                    'paciente_nome': decode_value(consulta[2]),
                    'data_nascimento': consulta[3] if len(consulta) > 3 else None,
                    'genero': decode_value(consulta[4]) if len(consulta) > 4 else ''
                }
            
            # Calcular idade
            idade = None
            data_nasc = consulta_dict.get('data_nascimento')
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
                pressao_arterial = request.form.get('pressao_arterial')
                frequencia_cardiaca = request.form.get('frequencia_cardiaca')
                frequencia_respiratoria = request.form.get('frequencia_respiratoria')
                temperatura = request.form.get('temperatura')
                saturacao_oxigenio = request.form.get('saturacao_oxigenio')
                glicemia = request.form.get('glicemia')
                peso = request.form.get('peso')
                observacoes = request.form.get('observacoes')
                
                if pressao_arterial:
                    pressao_arterial = pressao_arterial.replace('/', 'x')
                    if not re.match(r'^\d{2,3}x\d{2,3}$', pressao_arterial):
                        flash('Formato de pressão arterial inválido. Use: 120/80 ou 120x80', 'danger')
                        return redirect(url_for('medico.registrar_sinais_vitais', consulta_id=consulta_id))
                
                # SEM commit=True - a função já faz commit automaticamente
                execute_query("""
                    INSERT INTO sinais_vitais 
                    (consulta_id, pressao_arterial, frequencia_cardiaca, frequencia_respiratoria,
                     temperatura, saturacao_oxigenio, glicemia, peso, observacoes, data_afericao)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (consulta_id, pressao_arterial or None, frequencia_cardiaca or None, 
                      frequencia_respiratoria or None, temperatura or None, 
                      saturacao_oxigenio or None, glicemia or None, peso or None, 
                      observacoes or None))
                
                flash('Sinais vitais registrados com sucesso!', 'success')
                return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
            
            return render_template('medico/sinais_vitais.html',
                                 consulta=consulta_dict,
                                 consulta_id=consulta_id,
                                 idade=idade)
                                 
        except Exception as e:
            logger.error(f"Erro ao registrar sinais vitais: {e}")
            flash(f'Erro ao registrar sinais vitais: {str(e)}', 'danger')
            return redirect(url_for('medico.consultas'))
    
    return {
        'routes': [
            {'rule': '/consulta/<int:consulta_id>/sinais-vitais', 
             'view_func': registrar_sinais_vitais, 
             'methods': ['GET', 'POST']}
        ]
    }
