# routes/medico/consulta/editar.py
from datetime import datetime, timedelta
from flask import render_template, request, flash, redirect, url_for, session
from .decorators import login_required
from .utils import execute_query

def register_editar_routes(bp, mysql):
    
    @bp.route('/<int:consulta_id>/editar', methods=['GET', 'POST'])
    @login_required
    def editar_consulta(consulta_id):
        """Editar uma consulta existente"""
        usuario_tipo = session.get('user_type')
        
        # Apenas admin e médicos podem editar consultas
        if usuario_tipo not in ['admin', 'medico']:
            flash('Acesso não autorizado.', 'danger')
            return redirect(url_for('auth.index'))
        
        # Função para obter detalhes da consulta
        def obter_detalhes_consulta_completa(cid):
            try:
                consulta = execute_query(mysql, """
                    SELECT 
                        c.id,
                        m_u.nome as medico_nome,
                        m.especialidade,
                        m.crm,
                        c.data_hora,
                        c.status,
                        c.observacoes,
                        c.receita,
                        p_u.nome as paciente_nome,
                        p.data_nascimento,
                        p.genero,
                        p.telefone as paciente_telefone,
                        p.endereco,
                        m_u.email as medico_email,
                        m.telefone as medico_telefone,
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
                """, (cid,), True)
                
                if not consulta:
                    return None
                
                c = consulta[0]
                
                # Processar sintomas
                sintomas_lista = []
                if len(c) > 18 and c[18]:
                    sintomas_lista = [s.strip() for s in c[18].split(',') if s.strip()]
                
                # Formatar data_hora para o formato do input
                data_hora_formatada = ""
                if c[4]:
                    if isinstance(c[4], datetime):
                        data_hora_formatada = c[4].strftime('%Y-%m-%dT%H:%M')
                    else:
                        try:
                            data_hora_formatada = datetime.strptime(str(c[4]), '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%dT%H:%M')
                        except:
                            data_hora_formatada = ""
                
                return {
                    'id': c[0],
                    'medico_nome': c[1],
                    'especialidade': c[2],
                    'crm': c[3],
                    'data_hora': c[4],
                    'data_hora_formatada': data_hora_formatada,
                    'status': c[5],
                    'observacoes': c[6] or '',
                    'receita': c[7] or '',
                    'paciente_nome': c[8],
                    'paciente_id': c[15],
                    'medico_id': c[16],
                    'sintomas_raw': c[18] if len(c) > 18 else '',
                    'sintomas_lista': sintomas_lista,
                    'status_class': {
                        'agendada': 'warning',
                        'realizada': 'success',
                        'cancelada': 'danger',
                        'confirmada': 'info'
                    }.get(c[5], 'secondary')
                }
            except Exception as e:
                print(f"Erro ao obter detalhes: {e}")
                return None
        
        consulta = obter_detalhes_consulta_completa(consulta_id)
        
        if not consulta:
            flash('Consulta não encontrada.', 'danger')
            return redirect(url_for('auth.index'))
        
        if request.method == 'POST':
            try:
                data_hora = request.form.get('data_hora')
                status = request.form.get('status')
                observacoes = request.form.get('observacoes', '')
                receita = request.form.get('receita', '')
                
                # Atualizar consulta
                if data_hora:
                    data_hora_obj = datetime.strptime(data_hora, '%Y-%m-%dT%H:%M')
                    data_hora_mysql = data_hora_obj.strftime('%Y-%m-%d %H:%M:%S')
                    
                    execute_query(mysql, """
                        UPDATE consultas 
                        SET data_hora = %s, status = %s, observacoes = %s, receita = %s
                        WHERE id = %s
                    """, (data_hora_mysql, status, observacoes, receita, consulta_id))
                else:
                    execute_query(mysql, """
                        UPDATE consultas 
                        SET status = %s, observacoes = %s, receita = %s
                        WHERE id = %s
                    """, (status, observacoes, receita, consulta_id))
                
                flash('Consulta atualizada com sucesso!', 'success')
                return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
                
            except Exception as e:
                flash(f'Erro ao atualizar consulta: {str(e)}', 'danger')
                return redirect(url_for('consulta.editar_consulta', consulta_id=consulta_id))
        
        # GET: Mostrar formulário de edição
        
        # Obter lista de médicos (apenas para admin)
        medicos = []
        if usuario_tipo == 'admin':
            medicos = execute_query(mysql, """
                SELECT m.id, u.nome, m.especialidade 
                FROM medicos m 
                JOIN usuarios u ON m.usuario_id = u.id 
                WHERE u.ativo = TRUE
                ORDER BY u.nome
            """, fetch=True) or []
        
        # Obter lista de pacientes (apenas para admin)
        pacientes = []
        if usuario_tipo == 'admin':
            pacientes = execute_query(mysql, """
                SELECT p.id, u.nome 
                FROM pacientes p 
                JOIN usuarios u ON p.usuario_id = u.id 
                WHERE u.ativo = TRUE
                ORDER BY u.nome
            """, fetch=True) or []
        
        # Status disponíveis
        status_options = [
            ('agendada', 'Agendada'),
            ('confirmada', 'Confirmada'),
            ('realizada', 'Realizada'),
            ('cancelada', 'Cancelada')
        ]
        
        # Calcular datas disponíveis (próximos 30 dias)
        hoje = datetime.now()
        datas_disponiveis = []
        for i in range(1, 31):
            data = hoje + timedelta(days=i)
            if data.weekday() < 5:  # Segunda a Sexta
                datas_disponiveis.append(data.strftime('%Y-%m-%d'))
        
        return render_template('consulta/editar.html',
                             consulta=consulta,
                             medicos=medicos,
                             pacientes=pacientes,
                             status_options=status_options,
                             datas_disponiveis=datas_disponiveis,
                             usuario_tipo=usuario_tipo,
                             user=session)