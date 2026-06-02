from flask import Blueprint, render_template, session, flash, redirect, url_for
from datetime import datetime, date

def init_medico_historico(base):
    """Inicializa rotas de histórico do médico"""
    
    medico_required = base['medico_required']
    execute_query = base['execute_query']
    
    # ========== FUNÇÃO AUXILIAR PARA DECODIFICAR BYTES ==========
    def decode_bytes_value(value):
        """Decodifica bytes para string de forma segura"""
        if value is None:
            return ''
        if isinstance(value, bytes):
            try:
                return value.decode('utf-8')
            except:
                return str(value)
        return str(value) if value else ''
    
    # ========== FUNÇÃO PARA DECODIFICAR DICIONÁRIO OU TUPLA ==========
    def decode_data(data):
        """Decodifica recursivamente bytes em estruturas de dados"""
        if data is None:
            return None
        if isinstance(data, bytes):
            try:
                return data.decode('utf-8')
            except:
                return str(data)
        if isinstance(data, dict):
            return {key: decode_data(value) for key, value in data.items()}
        if isinstance(data, (list, tuple)):
            return [decode_data(item) for item in data]
        return data
    
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
            
            # Decodificar paciente
            paciente = decode_data(paciente_raw)
            
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
                       m_u.nome as medico_nome, m.especialidade
                FROM consultas c
                JOIN medicos m ON c.medico_id = m.id
                JOIN usuarios m_u ON m.usuario_id = m_u.id
                WHERE c.paciente_id = %s
                ORDER BY c.data_hora DESC
            """, (paciente_id,), fetch=True) or []
            
            # Decodificar consultas
            consultas = []
            for c in consultas_raw:
                if isinstance(c, dict):
                    consultas.append({
                        'id': c.get('id'),
                        'data_hora': decode_bytes_value(c.get('data_hora')),
                        'status': decode_bytes_value(c.get('status')),
                        'observacoes': decode_bytes_value(c.get('observacoes')),
                        'sintomas': decode_bytes_value(c.get('sintomas')),
                        'medico_nome': decode_bytes_value(c.get('medico_nome')),
                        'especialidade': decode_bytes_value(c.get('especialidade'))
                    })
                else:
                    consultas.append({
                        'id': c[0] if len(c) > 0 else None,
                        'data_hora': decode_bytes_value(c[1]) if len(c) > 1 else '',
                        'status': decode_bytes_value(c[2]) if len(c) > 2 else '',
                        'observacoes': decode_bytes_value(c[3]) if len(c) > 3 else '',
                        'sintomas': decode_bytes_value(c[4]) if len(c) > 4 else '',
                        'medico_nome': decode_bytes_value(c[5]) if len(c) > 5 else '',
                        'especialidade': decode_bytes_value(c[6]) if len(c) > 6 else ''
                    })
            
            # Buscar receitas
            receitas_raw = execute_query("""
                SELECT r.id, r.created_at, r.diagnostico, r.prescricao, r.recomendacoes
                FROM receita r
                JOIN consultas c ON r.consulta_id = c.id
                WHERE c.paciente_id = %s
                ORDER BY r.created_at DESC
            """, (paciente_id,), fetch=True) or []
            
            # Decodificar receitas
            receitas = []
            for r in receitas_raw:
                if isinstance(r, dict):
                    receitas.append({
                        'id': r.get('id'),
                        'created_at': decode_bytes_value(r.get('created_at')),
                        'diagnostico': decode_bytes_value(r.get('diagnostico')),
                        'prescricao': decode_bytes_value(r.get('prescricao')),
                        'recomendacoes': decode_bytes_value(r.get('recomendacoes'))
                    })
                else:
                    receitas.append({
                        'id': r[0] if len(r) > 0 else None,
                        'created_at': decode_bytes_value(r[1]) if len(r) > 1 else '',
                        'diagnostico': decode_bytes_value(r[2]) if len(r) > 2 else '',
                        'prescricao': decode_bytes_value(r[3]) if len(r) > 3 else '',
                        'recomendacoes': decode_bytes_value(r[4]) if len(r) > 4 else ''
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
            
            # Decodificar exames
            exames = []
            for e in exames_raw:
                if isinstance(e, dict):
                    exames.append({
                        'id': e.get('id'),
                        'tipo_exame': decode_bytes_value(e.get('tipo_exame')),
                        'status': decode_bytes_value(e.get('status')),
                        'data_solicitacao': decode_bytes_value(e.get('data_solicitacao')),
                        'resultado_analise': decode_bytes_value(e.get('resultado_analise')),
                        'diagnostico_analista': decode_bytes_value(e.get('diagnostico_analista'))
                    })
                else:
                    exames.append({
                        'id': e[0] if len(e) > 0 else None,
                        'tipo_exame': decode_bytes_value(e[1]) if len(e) > 1 else '',
                        'status': decode_bytes_value(e[2]) if len(e) > 2 else '',
                        'data_solicitacao': decode_bytes_value(e[3]) if len(e) > 3 else '',
                        'resultado_analise': decode_bytes_value(e[4]) if len(e) > 4 else '',
                        'diagnostico_analista': decode_bytes_value(e[5]) if len(e) > 5 else ''
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
            
            # Decodificar sinais vitais
            sinais_vitais = []
            for s in sinais_vitais_raw:
                if isinstance(s, dict):
                    sinais_vitais.append({
                        'pressao_arterial': decode_bytes_value(s.get('pressao_arterial')),
                        'frequencia_cardiaca': decode_bytes_value(s.get('frequencia_cardiaca')),
                        'frequencia_respiratoria': decode_bytes_value(s.get('frequencia_respiratoria')),
                        'temperatura': decode_bytes_value(s.get('temperatura')),
                        'saturacao_oxigenio': decode_bytes_value(s.get('saturacao_oxigenio')),
                        'glicemia': decode_bytes_value(s.get('glicemia')),
                        'peso': decode_bytes_value(s.get('peso')),
                        'data_afericao': decode_bytes_value(s.get('data_afericao')),
                        'observacoes': decode_bytes_value(s.get('observacoes')),
                        'enfermeiro_nome': decode_bytes_value(s.get('enfermeiro_nome'))
                    })
                else:
                    sinais_vitais.append({
                        'pressao_arterial': decode_bytes_value(s[0]) if len(s) > 0 else '',
                        'frequencia_cardiaca': decode_bytes_value(s[1]) if len(s) > 1 else '',
                        'frequencia_respiratoria': decode_bytes_value(s[2]) if len(s) > 2 else '',
                        'temperatura': decode_bytes_value(s[3]) if len(s) > 3 else '',
                        'saturacao_oxigenio': decode_bytes_value(s[4]) if len(s) > 4 else '',
                        'glicemia': decode_bytes_value(s[5]) if len(s) > 5 else '',
                        'peso': decode_bytes_value(s[6]) if len(s) > 6 else '',
                        'data_afericao': decode_bytes_value(s[7]) if len(s) > 7 else '',
                        'observacoes': decode_bytes_value(s[8]) if len(s) > 8 else '',
                        'enfermeiro_nome': decode_bytes_value(s[9]) if len(s) > 9 else ''
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
