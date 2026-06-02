from flask import Blueprint, render_template, session, flash, redirect, url_for
from datetime import datetime, date

def init_medico_historico(base):
    """Inicializa rotas de histórico do médico"""
    
    medico_required = base['medico_required']
    execute_query = base['execute_query']
    
    @medico_required
    def historico_paciente(paciente_id):
        """Visualiza o histórico médico completo do paciente"""
        try:
            # Buscar informações do paciente
            paciente = execute_query("""
                SELECT p.id, p.data_nascimento, p.genero, p.telefone, p.endereco,
                       u.nome, u.email
                FROM pacientes p
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE p.id = %s
            """, (paciente_id,), fetch=True, one=True)
            
            if not paciente:
                flash('Paciente não encontrado.', 'danger')
                return redirect(url_for('medico.consultas'))
            
            # Calcular idade
            idade = None
            data_nasc = paciente.get('data_nascimento') if isinstance(paciente, dict) else paciente[1] if len(paciente) > 1 else None
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
            
            # Converter paciente para dict se for tuple
            if not isinstance(paciente, dict):
                paciente = {
                    'id': paciente[0] if len(paciente) > 0 else None,
                    'data_nascimento': paciente[1] if len(paciente) > 1 else None,
                    'genero': paciente[2] if len(paciente) > 2 else '',
                    'telefone': paciente[3] if len(paciente) > 3 else '',
                    'endereco': paciente[4] if len(paciente) > 4 else '',
                    'nome': paciente[5] if len(paciente) > 5 else '',
                    'email': paciente[6] if len(paciente) > 6 else ''
                }
            
            # Buscar consultas do paciente
            consultas = execute_query("""
                SELECT c.id, c.data_hora, c.status, c.observacoes, c.sintomas,
                       m_u.nome as medico_nome, m.especialidade
                FROM consultas c
                JOIN medicos m ON c.medico_id = m.id
                JOIN usuarios m_u ON m.usuario_id = m_u.id
                WHERE c.paciente_id = %s
                ORDER BY c.data_hora DESC
            """, (paciente_id,), fetch=True) or []
            
            # Buscar receitas
            receitas = execute_query("""
                SELECT r.id, r.created_at, r.diagnostico, r.prescricao, r.recomendacoes
                FROM receita r
                JOIN consultas c ON r.consulta_id = c.id
                WHERE c.paciente_id = %s
                ORDER BY r.created_at DESC
            """, (paciente_id,), fetch=True) or []
            
            # Buscar exames/pedidos
            exames = execute_query("""
                SELECT pa.id, pa.tipo_exame, pa.status, pa.data_solicitacao, 
                       pa.resultado_analise, pa.diagnostico_analista
                FROM pedidos_analise pa
                JOIN consultas c ON pa.consulta_id = c.id
                WHERE c.paciente_id = %s
                ORDER BY pa.data_solicitacao DESC
            """, (paciente_id,), fetch=True) or []
            
            # Buscar sinais vitais
            sinais_vitais = execute_query("""
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
            flash(f'Erro ao carregar histórico: {str(e)}', 'danger')
            return redirect(url_for('medico.consultas'))
    
    return {
        'routes': [
            {'rule': '/historico/paciente/<int:paciente_id>', 
             'view_func': historico_paciente, 
             'methods': ['GET']}
        ]
    }
