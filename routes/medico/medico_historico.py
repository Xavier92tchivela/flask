from flask import Blueprint, render_template, session, flash, redirect, url_for
from utils.database import execute_query

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
            from datetime import date
            idade = None
            if paciente.get('data_nascimento'):
                try:
                    data_nasc = paciente['data_nascimento']
                    if isinstance(data_nasc, str):
                        from datetime import datetime
                        data_nasc = datetime.strptime(data_nasc, '%Y-%m-%d').date()
                    hoje = date.today()
                    idade = hoje.year - data_nasc.year
                    if (hoje.month, hoje.day) < (data_nasc.month, data_nasc.day):
                        idade -= 1
                except:
                    pass
            
            # Buscar consultas do paciente com este médico
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
                SELECT r.id, r.created_at, r.diagnostico, r.prescricao, r.recomendacoes,
                       c.data_hora as consulta_data
                FROM receita r
                JOIN consultas c ON r.consulta_id = c.id
                WHERE c.paciente_id = %s
                ORDER BY r.created_at DESC
            """, (paciente_id,), fetch=True) or []
            
            # Buscar exames/pedidos
            exames = execute_query("""
                SELECT pa.id, pa.tipo_exame, pa.status, pa.data_solicitacao, 
                       pa.resultado_analise, pa.diagnostico_analista, pa.data_conclusao,
                       c.data_hora as consulta_data
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
