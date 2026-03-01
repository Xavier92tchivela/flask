# routes/medico/consulta/agendamento.py
from datetime import datetime, timedelta
from flask import render_template, request, flash, redirect, url_for,session
from .decorators import login_required
from .utils import execute_query, obter_paciente_id

def register_agendamento_routes(bp, mysql):
    
    @bp.route('/agendar', methods=['GET', 'POST'])
    @login_required
    def agendar_consulta():
        """Agendar nova consulta"""
        usuario_tipo = session.get('user_type')
        
        # Determinar paciente_id
        if usuario_tipo == 'paciente':
            paciente_id = obter_paciente_id(mysql, session)
            if not paciente_id:
                flash('Perfil de paciente não encontrado.', 'danger')
                return redirect(url_for('auth.logout'))
        elif usuario_tipo == 'admin':
            paciente_id = request.form.get('paciente_id') if request.method == 'POST' else None
        else:
            flash('Apenas pacientes e administradores podem agendar consultas.', 'danger')
            return redirect(url_for('auth.login'))
        
        if request.method == 'POST':
            try:
                medico_id = request.form['medico_id']
                data_hora = request.form['data_hora']
                observacoes = request.form.get('observacoes', '')
                sintomas = request.form.get('sintomas', '')
                
                if usuario_tipo == 'admin' and not paciente_id:
                    paciente_id = request.form['paciente_id']
                
                if not medico_id or not data_hora:
                    flash('Preencha todos os campos obrigatórios.', 'danger')
                    return redirect(url_for('consulta.agendar_consulta'))
                
                data_hora_obj = datetime.strptime(data_hora, '%Y-%m-%dT%H:%M')
                data_hora_mysql = data_hora_obj.strftime('%Y-%m-%d %H:%M:%S')
                
                # Verificar conflitos
                conflito = execute_query(mysql,
                    """SELECT id FROM consultas 
                    WHERE medico_id = %s AND data_hora = %s AND status != 'cancelada'""",
                    (medico_id, data_hora_mysql), True
                )
                
                if conflito:
                    flash('Horário indisponível.', 'danger')
                    return redirect(url_for('consulta.agendar_consulta'))
                
                # Inserir consulta
                execute_query(mysql,
                    """INSERT INTO consultas 
                    (paciente_id, medico_id, data_hora, status, observacoes, sintomas) 
                    VALUES (%s, %s, %s, %s, %s, %s)""",
                    (paciente_id, medico_id, data_hora_mysql, 'agendada', observacoes, sintomas)
                )
                
                flash('Consulta agendada com sucesso!', 'success')
                
                if usuario_tipo == 'paciente':
                    return redirect(url_for('paciente.minhas_consultas'))
                else:
                    return redirect(url_for('admin.consultas'))
                    
            except Exception as e:
                flash(f'Erro ao agendar: {str(e)}', 'danger')
                return redirect(url_for('consulta.agendar_consulta'))
        
        # GET - mostrar formulário
        medicos = execute_query(mysql,
            """SELECT m.id, u.nome, m.especialidade 
            FROM medicos m 
            JOIN usuarios u ON m.usuario_id = u.id 
            WHERE u.ativo = TRUE
            ORDER BY u.nome""",
            fetch=True
        ) or []
        
        pacientes = []
        if usuario_tipo == 'admin':
            pacientes = execute_query(mysql,
                """SELECT p.id, u.nome 
                FROM pacientes p 
                JOIN usuarios u ON p.usuario_id = u.id 
                WHERE u.ativo = TRUE
                ORDER BY u.nome""",
                fetch=True
            ) or []
        
        # Datas e horários disponíveis
        hoje = datetime.now()
        datas_disponiveis = []
        for i in range(1, 31):
            data = hoje + timedelta(days=i)
            if data.weekday() < 5:
                datas_disponiveis.append(data.strftime('%Y-%m-%d'))
        
        horarios_disponiveis = []
        for hora in range(8, 18):
            horarios_disponiveis.append(f"{hora:02d}:00")
            horarios_disponiveis.append(f"{hora:02d}:30")
        
        return render_template('consulta/agendar.html',
                             medicos=medicos,
                             pacientes=pacientes,
                             datas_disponiveis=datas_disponiveis,
                             horarios_disponiveis=horarios_disponiveis,
                             usuario_tipo=usuario_tipo,
                             user=session)