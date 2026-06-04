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
            paciente_result = execute_query("""
                SELECT p.id, p.data_nascimento, p.genero, p.telefone, p.endereco,
                       u.nome, u.email
                FROM pacientes p
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE p.id = %s
            """, (paciente_id,), fetch=True, one=True)
            
            if not paciente_result:
                flash('Paciente não encontrado.', 'danger')
                return redirect(url_for('medico.consultas'))
            
            # Converter paciente - FORÇANDO string com decode manual
            if isinstance(paciente_result, dict):
                paciente = {
                    'id': paciente_result.get('id'),
                    'data_nascimento': paciente_result.get('data_nascimento'),
                    'genero': _safe_str(paciente_result.get('genero')),
                    'telefone': _safe_str(paciente_result.get('telefone')),
                    'endereco': _safe_str(paciente_result.get('endereco')),
                    'nome': _safe_str(paciente_result.get('nome')),
                    'email': _safe_str(paciente_result.get('email'))
                }
            else:
                paciente = {
                    'id': paciente_result[0] if len(paciente_result) > 0 else None,
                    'data_nascimento': paciente_result[1] if len(paciente_result) > 1 else None,
                    'genero': _safe_str(paciente_result[2]) if len(paciente_result) > 2 else '',
                    'telefone': _safe_str(paciente_result[3]) if len(paciente_result) > 3 else '',
                    'endereco': _safe_str(paciente_result[4]) if len(paciente_result) > 4 else '',
                    'nome': _safe_str(paciente_result[5]) if len(paciente_result) > 5 else '',
                    'email': _safe_str(paciente_result[6]) if len(paciente_result) > 6 else ''
                }
            
            # Calcular idade
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
            
            # Buscar consultas
            consultas_raw = execute_query("""
                SELECT 
                    c.id, 
                    DATE_FORMAT(c.data_hora, '%%d/%%m/%%Y %%H:%%i') as data_hora,
                    c.status, 
                    c.observacoes, 
                    c.sintomas,
                    c.diagnostico_final,
                    c.diagnostico_ia,
                    m_u.nome as medico_nome, 
                    m.especialidade
                FROM consultas c
                JOIN medicos m ON c.medico_id = m.id
                JOIN usuarios m_u ON m.usuario_id = m_u.id
                WHERE c.paciente_id = %s
                ORDER BY c.data_hora DESC
            """, (paciente_id,), fetch=True) or []
            
            consultas = []
            for row in consultas_raw:
                if isinstance(row, dict):
                    consultas.append({
                        'id': row.get('id'),
                        'data_hora': row.get('data_hora', ''),
                        'status': row.get('status', ''),
                        'observacoes': row.get('observacoes', ''),
                        'sintomas': row.get('sintomas', ''),
                        'diagnostico_final': row.get('diagnostico_final', ''),
                        'diagnostico_ia': row.get('diagnostico_ia', ''),
                        'medico_nome': row.get('medico_nome', ''),
                        'especialidade': row.get('especialidade', '')
                    })
                else:
                    consultas.append({
                        'id': row[0] if len(row) > 0 else None,
                        'data_hora': row[1] if len(row) > 1 else '',
                        'status': row[2] if len(row) > 2 else '',
                        'observacoes': row[3] if len(row) > 3 else '',
                        'sintomas': row[4] if len(row) > 4 else '',
                        'diagnostico_final': row[5] if len(row) > 5 else '',
                        'diagnostico_ia': row[6] if len(row) > 6 else '',
                        'medico_nome': row[7] if len(row) > 7 else '',
                        'especialidade': row[8] if len(row) > 8 else ''
                    })
            
            # Buscar receitas
            receitas_raw = execute_query("""
                SELECT 
                    r.id, 
                    DATE_FORMAT(r.created_at, '%%d/%%m/%%Y %%H:%%i') as created_at,
                    r.diagnostico, 
                    r.prescricao, 
                    r.recomendacoes,
                    r.profissional_tipo,
                    r.profissional_nome
                FROM receita r
                JOIN consultas c ON r.consulta_id = c.id
                WHERE c.paciente_id = %s
                ORDER BY r.created_at DESC
            """, (paciente_id,), fetch=True) or []
            
            receitas = []
            for row in receitas_raw:
                if isinstance(row, dict):
                    receitas.append({
                        'id': row.get('id'),
                        'created_at': row.get('created_at', ''),
                        'diagnostico': row.get('diagnostico', ''),
                        'prescricao': row.get('prescricao', ''),
                        'recomendacoes': row.get('recomendacoes', ''),
                        'profissional_tipo': row.get('profissional_tipo', ''),
                        'profissional_nome': row.get('profissional_nome', '')
                    })
                else:
                    receitas.append({
                        'id': row[0] if len(row) > 0 else None,
                        'created_at': row[1] if len(row) > 1 else '',
                        'diagnostico': row[2] if len(row) > 2 else '',
                        'prescricao': row[3] if len(row) > 3 else '',
                        'recomendacoes': row[4] if len(row) > 4 else '',
                        'profissional_tipo': row[5] if len(row) > 5 else '',
                        'profissional_nome': row[6] if len(row) > 6 else ''
                    })
            
            # Buscar exames
            exames_raw = execute_query("""
                SELECT 
                    pa.id, 
                    pa.tipo_exame, 
                    pa.status, 
                    DATE_FORMAT(pa.data_solicitacao, '%%d/%%m/%%Y') as data_solicitacao,
                    pa.resultado_analise, 
                    pa.diagnostico_analista
                FROM pedidos_analise pa
                JOIN consultas c ON pa.consulta_id = c.id
                WHERE c.paciente_id = %s
                ORDER BY pa.data_solicitacao DESC
            """, (paciente_id,), fetch=True) or []
            
            exames = []
            for row in exames_raw:
                if isinstance(row, dict):
                    exames.append({
                        'id': row.get('id'),
                        'tipo_exame': row.get('tipo_exame', ''),
                        'status': row.get('status', ''),
                        'data_solicitacao': row.get('data_solicitacao', ''),
                        'resultado_analise': row.get('resultado_analise', ''),
                        'diagnostico_analista': row.get('diagnostico_analista', '')
                    })
                else:
                    exames.append({
                        'id': row[0] if len(row) > 0 else None,
                        'tipo_exame': row[1] if len(row) > 1 else '',
                        'status': row[2] if len(row) > 2 else '',
                        'data_solicitacao': row[3] if len(row) > 3 else '',
                        'resultado_analise': row[4] if len(row) > 4 else '',
                        'diagnostico_analista': row[5] if len(row) > 5 else ''
                    })
            
            return render_template('medico/historico_paciente.html',
                                 paciente=paciente,
                                 idade=idade,
                                 consultas=consultas,
                                 receitas=receitas,
                                 exames=exames,
                                 sinais_vitais=[])
                                 
        except Exception as e:
            print(f"ERRO: {e}")
            import traceback
            traceback.print_exc()
            flash(f'Erro ao carregar histórico: {str(e)}', 'danger')
            return redirect(url_for('medico.consultas'))
    
    # Função auxiliar segura
    def _safe_str(value):
        if value is None:
            return ''
        if isinstance(value, bytes):
            try:
                return value.decode('utf-8')
            except:
                return str(value)
        if isinstance(value, str):
            return value
        return str(value)
    
    return {
        'routes': [
            {'rule': '/historico/paciente/<int:paciente_id>', 
             'view_func': historico_paciente, 
             'methods': ['GET']}
        ]
    }
