from flask import Blueprint, render_template, session, flash, redirect, url_for
from datetime import datetime, date

def init_medico_historico(base):
    """Inicializa rotas de histórico do médico"""
    
    medico_required = base['medico_required']
    execute_query = base['execute_query']
    
    # ========== FUNÇÃO SIMPLIFICADA PARA CONVERTER BYTES ==========
    def to_str(value):
        """Converte bytes para string de forma segura"""
        if value is None:
            return ''
        if isinstance(value, bytes):
            try:
                return value.decode('utf-8')
            except:
                return str(value)
        return str(value) if value else ''
    
    @medico_required
    def historico_paciente(paciente_id):
        """Visualiza o histórico médico completo do paciente"""
        try:
            # Buscar informações do paciente
            paciente_raw = execute_query("""
                SELECT p.id, p.data_nascimento, p.genero, p.telefone, p.endereco,
                       u.nome, u.email
                FROM pacientes p
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE p.id = %s
            """, (paciente_id,), fetch=True, one=True)
            
            if not paciente_raw:
                flash('Paciente não encontrado.', 'danger')
                return redirect(url_for('medico.consultas'))
            
            # Converter paciente para dict
            if isinstance(paciente_raw, dict):
                paciente = {
                    'id': paciente_raw.get('id'),
                    'data_nascimento': paciente_raw.get('data_nascimento'),
                    'genero': to_str(paciente_raw.get('genero')),
                    'telefone': to_str(paciente_raw.get('telefone')),
                    'endereco': to_str(paciente_raw.get('endereco')),
                    'nome': to_str(paciente_raw.get('nome')),
                    'email': to_str(paciente_raw.get('email'))
                }
            else:
                paciente = {
                    'id': paciente_raw[0] if len(paciente_raw) > 0 else None,
                    'data_nascimento': paciente_raw[1] if len(paciente_raw) > 1 else None,
                    'genero': to_str(paciente_raw[2]) if len(paciente_raw) > 2 else '',
                    'telefone': to_str(paciente_raw[3]) if len(paciente_raw) > 3 else '',
                    'endereco': to_str(paciente_raw[4]) if len(paciente_raw) > 4 else '',
                    'nome': to_str(paciente_raw[5]) if len(paciente_raw) > 5 else '',
                    'email': to_str(paciente_raw[6]) if len(paciente_raw) > 6 else ''
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
            
            # Buscar consultas do paciente
            consultas_raw = execute_query("""
                SELECT c.id, c.data_hora, c.status, c.observacoes, c.sintomas,
                       c.diagnostico_final, c.diagnostico_ia,
                       m_u.nome as medico_nome, m.especialidade
                FROM consultas c
                JOIN medicos m ON c.medico_id = m.id
                JOIN usuarios m_u ON m.usuario_id = m_u.id
                WHERE c.paciente_id = %s
                ORDER BY c.data_hora DESC
            """, (paciente_id,), fetch=True) or []
            
            # Processar consultas
            consultas = []
            for c in consultas_raw:
                if isinstance(c, dict):
                    consultas.append({
                        'id': c.get('id'),
                        'data_hora': to_str(c.get('data_hora')),
                        'status': to_str(c.get('status')),
                        'observacoes': to_str(c.get('observacoes')),
                        'sintomas': to_str(c.get('sintomas')),
                        'diagnostico_final': to_str(c.get('diagnostico_final')),
                        'diagnostico_ia': to_str(c.get('diagnostico_ia')),
                        'medico_nome': to_str(c.get('medico_nome')),
                        'especialidade': to_str(c.get('especialidade'))
                    })
                else:
                    consultas.append({
                        'id': c[0] if len(c) > 0 else None,
                        'data_hora': to_str(c[1]) if len(c) > 1 else '',
                        'status': to_str(c[2]) if len(c) > 2 else '',
                        'observacoes': to_str(c[3]) if len(c) > 3 else '',
                        'sintomas': to_str(c[4]) if len(c) > 4 else '',
                        'diagnostico_final': to_str(c[5]) if len(c) > 5 else '',
                        'diagnostico_ia': to_str(c[6]) if len(c) > 6 else '',
                        'medico_nome': to_str(c[7]) if len(c) > 7 else '',
                        'especialidade': to_str(c[8]) if len(c) > 8 else ''
                    })
            
            # Buscar receitas
            receitas_raw = execute_query("""
                SELECT r.id, r.created_at, r.diagnostico, r.prescricao, r.recomendacoes,
                       r.profissional_tipo, r.profissional_nome
                FROM receita r
                JOIN consultas c ON r.consulta_id = c.id
                WHERE c.paciente_id = %s
                ORDER BY r.created_at DESC
            """, (paciente_id,), fetch=True) or []
            
            # Processar receitas
            receitas = []
            for r in receitas_raw:
                if isinstance(r, dict):
                    receitas.append({
                        'id': r.get('id'),
                        'created_at': to_str(r.get('created_at')),
                        'diagnostico': to_str(r.get('diagnostico')),
                        'prescricao': to_str(r.get('prescricao')),
                        'recomendacoes': to_str(r.get('recomendacoes')),
                        'profissional_tipo': to_str(r.get('profissional_tipo')),
                        'profissional_nome': to_str(r.get('profissional_nome'))
                    })
                else:
                    receitas.append({
                        'id': r[0] if len(r) > 0 else None,
                        'created_at': to_str(r[1]) if len(r) > 1 else '',
                        'diagnostico': to_str(r[2]) if len(r) > 2 else '',
                        'prescricao': to_str(r[3]) if len(r) > 3 else '',
                        'recomendacoes': to_str(r[4]) if len(r) > 4 else '',
                        'profissional_tipo': to_str(r[5]) if len(r) > 5 else '',
                        'profissional_nome': to_str(r[6]) if len(r) > 6 else ''
                    })
            
            # Buscar exames/pedidos
            exames_raw = execute_query("""
                SELECT pa.id, pa.tipo_exame, pa.status, pa.data_solicitacao, 
                       pa.resultado_analise, pa.diagnostico_analista
                FROM pedidos_analise pa
                JOIN consultas c ON pa.consulta_id = c.id
                WHERE c.paciente_id = %s
                ORDER BY pa.data_solicitacao DESC
            """, (paciente_id,), fetch=True) or []
            
            # Processar exames
            exames = []
            for e in exames_raw:
                if isinstance(e, dict):
                    exames.append({
                        'id': e.get('id'),
                        'tipo_exame': to_str(e.get('tipo_exame')),
                        'status': to_str(e.get('status')),
                        'data_solicitacao': to_str(e.get('data_solicitacao')),
                        'resultado_analise': to_str(e.get('resultado_analise')),
                        'diagnostico_analista': to_str(e.get('diagnostico_analista'))
                    })
                else:
                    exames.append({
                        'id': e[0] if len(e) > 0 else None,
                        'tipo_exame': to_str(e[1]) if len(e) > 1 else '',
                        'status': to_str(e[2]) if len(e) > 2 else '',
                        'data_solicitacao': to_str(e[3]) if len(e) > 3 else '',
                        'resultado_analise': to_str(e[4]) if len(e) > 4 else '',
                        'diagnostico_analista': to_str(e[5]) if len(e) > 5 else ''
                    })
            
            # Buscar sinais vitais
            sinais_vitais_raw = execute_query("""
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
            
            # Processar sinais vitais
            sinais_vitais = []
            for s in sinais_vitais_raw:
                if isinstance(s, dict):
                    sinais_vitais.append({
                        'pressao_arterial': to_str(s.get('pressao_arterial')),
                        'frequencia_cardiaca': to_str(s.get('frequencia_cardiaca')),
                        'frequencia_respiratoria': to_str(s.get('frequencia_respiratoria')),
                        'temperatura': to_str(s.get('temperatura')),
                        'saturacao_oxigenio': to_str(s.get('saturacao_oxigenio')),
                        'glicemia': to_str(s.get('glicemia')),
                        'peso': to_str(s.get('peso')),
                        'data_afericao': to_str(s.get('data_afericao')),
                        'observacoes': to_str(s.get('observacoes')),
                        'enfermeiro_nome': to_str(s.get('enfermeiro_nome'))
                    })
                else:
                    sinais_vitais.append({
                        'pressao_arterial': to_str(s[0]) if len(s) > 0 else '',
                        'frequencia_cardiaca': to_str(s[1]) if len(s) > 1 else '',
                        'frequencia_respiratoria': to_str(s[2]) if len(s) > 2 else '',
                        'temperatura': to_str(s[3]) if len(s) > 3 else '',
                        'saturacao_oxigenio': to_str(s[4]) if len(s) > 4 else '',
                        'glicemia': to_str(s[5]) if len(s) > 5 else '',
                        'peso': to_str(s[6]) if len(s) > 6 else '',
                        'data_afericao': to_str(s[7]) if len(s) > 7 else '',
                        'observacoes': to_str(s[8]) if len(s) > 8 else '',
                        'enfermeiro_nome': to_str(s[9]) if len(s) > 9 else ''
                    })
            
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
