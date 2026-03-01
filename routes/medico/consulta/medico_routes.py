# routes/medico/consulta/medico_routes.py
from datetime import datetime, timedelta
from flask import render_template, request, flash, redirect, url_for, session
from .decorators import medico_required
from .utils import execute_query, formatar_data, obter_medico_id, processar_sintomas, mapear_dia_semana, mapear_mes

def register_medico_routes(bp, mysql):
    
    @bp.route('/medico/consultas')
    @medico_required
    def medico_consultas():
        """Lista todas as consultas do médico logado com filtros"""
        try:
            # Obter ID do médico logado
            medico_id = obter_medico_id(mysql, session)
            
            if not medico_id:
                flash('Perfil de médico não encontrado.', 'danger')
                return redirect(url_for('medico.dashboard'))
            
            # Obter filtros da URL
            status = request.args.get('status', '')
            periodo = request.args.get('periodo', '')
            busca = request.args.get('busca', '')
            dia_semana = request.args.get('dia_semana', '')
            mes = request.args.get('mes', '')
            ano = request.args.get('ano', datetime.now().strftime('%Y'))
            
            # Construir query base - CORRIGIDA conforme a estrutura da tabela
            query = """
                SELECT 
                    c.id,
                    p_u.nome as paciente_nome,
                    p.data_nascimento,
                    p.genero,
                    p.telefone as paciente_telefone,
                    p_u.email as paciente_email,
                    c.data_hora,
                    c.status,
                    c.observacoes,
                    c.sintomas,
                    DAYNAME(c.data_hora) as dia_semana,
                    DATE(c.data_hora) as data_consulta,
                    TIME(c.data_hora) as hora_consulta,
                    MONTH(c.data_hora) as mes,
                    YEAR(c.data_hora) as ano
                FROM consultas c
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios p_u ON p.usuario_id = p_u.id
                WHERE c.medico_id = %s
            """
            params = [medico_id]
            
            # Aplicar filtros
            if status:
                query += " AND c.status = %s"
                params.append(status)
            
            if dia_semana:
                query += " AND DAYNAME(c.data_hora) = %s"
                params.append(dia_semana)
            
            if mes:
                query += " AND MONTH(c.data_hora) = %s"
                params.append(mes)
            
            if ano:
                query += " AND YEAR(c.data_hora) = %s"
                params.append(ano)
            
            if periodo:
                hoje = datetime.now().date()
                
                if periodo == 'hoje':
                    query += " AND DATE(c.data_hora) = %s"
                    params.append(hoje)
                elif periodo == 'semana':
                    inicio_semana = hoje - timedelta(days=hoje.weekday())
                    fim_semana = inicio_semana + timedelta(days=6)
                    query += " AND DATE(c.data_hora) BETWEEN %s AND %s"
                    params.extend([inicio_semana, fim_semana])
                elif periodo == 'mes':
                    inicio_mes = hoje.replace(day=1)
                    fim_mes = (inicio_mes + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                    query += " AND DATE(c.data_hora) BETWEEN %s AND %s"
                    params.extend([inicio_mes, fim_mes])
            
            if busca:
                query += " AND p_u.nome LIKE %s"
                params.append(f"%{busca}%")
            
            query += " ORDER BY c.data_hora DESC"
            
            # Executar query
            consultas_raw = execute_query(mysql, query, params, True) or []
            
            # Processar resultados
            consultas = []
            meses_contagem = {1:0, 2:0, 3:0, 4:0, 5:0, 6:0, 7:0, 8:0, 9:0, 10:0, 11:0, 12:0}
            dias_contagem = {
                'Segunda': 0, 'Terça': 0, 'Quarta': 0, 
                'Quinta': 0, 'Sexta': 0, 'Sábado': 0, 'Domingo': 0
            }
            
            for c in consultas_raw:
                # Verificar se a consulta tem dados válidos
                if not c or len(c) < 15:
                    continue
                
                # Calcular idade
                idade = None
                if c[2]:  # data_nascimento
                    try:
                        if isinstance(c[2], datetime):
                            data_nasc = c[2]
                        else:
                            data_nasc = datetime.strptime(str(c[2]), '%Y-%m-%d')
                        idade = datetime.now().year - data_nasc.year
                        if datetime.now().month < data_nasc.month or (datetime.now().month == data_nasc.month and datetime.now().day < data_nasc.day):
                            idade -= 1
                    except:
                        idade = None
                
                # Processar sintomas
                sintomas_lista = []
                if c[9]:  # sintomas
                    sintomas_lista = processar_sintomas(c[9])
                
                # Mapear dia da semana
                dia_semana_pt = ''
                if c[10]:  # dia_semana
                    dia_semana_pt = mapear_dia_semana(c[10])
                    if dia_semana_pt in dias_contagem:
                        dias_contagem[dia_semana_pt] += 1
                
                # Mapear mês
                mes_num = None
                if len(c) > 13 and c[13]:  # mes
                    try:
                        mes_num = int(c[13])
                        if mes_num in meses_contagem:
                            meses_contagem[mes_num] += 1
                    except:
                        pass
                
                # Formatar data da consulta
                data_consulta = ''
                if len(c) > 11 and c[11]:  # data_consulta
                    try:
                        if isinstance(c[11], datetime):
                            data_consulta = c[11].strftime('%d/%m/%Y')
                        else:
                            data_consulta = str(c[11])
                    except:
                        data_consulta = ''
                
                # Formatar hora
                hora_consulta = ''
                if len(c) > 12 and c[12]:  # hora_consulta
                    try:
                        hora_consulta = str(c[12])[:5]  # Pegar apenas HH:MM
                    except:
                        hora_consulta = ''
                
                consultas.append({
                    'id': c[0],
                    'paciente_nome': c[1] or 'Nome não disponível',
                    'paciente_idade': f"{idade} anos" if idade else "Idade não informada",
                    'paciente_genero': 'Masculino' if c[3] == 'M' else 'Feminino' if c[3] == 'F' else (c[3] or 'Não informado'),
                    'paciente_telefone': c[4] or 'Não informado',
                    'paciente_email': c[5] or 'Não informado',
                    'data_hora': formatar_data(c[6]) if c[6] else 'Data não disponível',
                    'status': c[7] or 'desconhecido',
                    'observacoes': c[8] or '',
                    'sintomas_lista': sintomas_lista,
                    'tem_sintomas': len(sintomas_lista) > 0,
                    'dia_semana': dia_semana_pt,
                    'data_consulta': data_consulta,
                    'hora_consulta': hora_consulta,
                    'mes': mes_num,
                    'mes_nome': mapear_mes(mes_num) if mes_num else '',
                    'ano': c[14] if len(c) > 14 and c[14] else '',
                    'status_class': {
                        'agendada': 'warning',
                        'realizada': 'success',
                        'cancelada': 'danger',
                        'confirmada': 'info'
                    }.get(c[7], 'secondary')
                })
            
            # Buscar anos disponíveis
            anos_raw = execute_query(mysql, """
                SELECT DISTINCT YEAR(data_hora) as ano
                FROM consultas
                WHERE medico_id = %s
                ORDER BY ano DESC
            """, (medico_id,), True) or []
            
            anos_disponiveis = []
            for a in anos_raw:
                if a and a[0]:
                    anos_disponiveis.append(a[0])
            
            if not anos_disponiveis:
                anos_disponiveis = [datetime.now().year]
            
            # Buscar informações do médico
            medico_info = execute_query(mysql, """
                SELECT u.nome, m.especialidade 
                FROM medicos m
                JOIN usuarios u ON m.usuario_id = u.id
                WHERE m.id = %s
            """, (medico_id,), True)
            
            medico_nome = medico_info[0][0] if medico_info and medico_info[0] and medico_info[0][0] else 'Médico'
            medico_especialidade = medico_info[0][1] if medico_info and medico_info[0] and len(medico_info[0]) > 1 else ''
            
            # Estatísticas
            total_consultas = len(consultas)
            
            # Valores padrão para o template
            mes_selecionado = None
            if mes:
                try:
                    mes_selecionado = int(mes)
                except:
                    mes_selecionado = None
            
            ano_selecionado = datetime.now().year
            if ano:
                try:
                    ano_selecionado = int(ano)
                except:
                    ano_selecionado = datetime.now().year
            
            return render_template('medico/consultas.html',
                                 consultas=consultas,
                                 medico={'nome': medico_nome, 'especialidade': medico_especialidade},
                                 total_consultas=total_consultas,
                                 meses_contagem=meses_contagem,
                                 anos_disponiveis=anos_disponiveis,
                                 mes_selecionado=mes_selecionado,
                                 ano_selecionado=ano_selecionado,
                                 dias_contagem=dias_contagem,
                                 user=session)
            
        except Exception as e:
            print(f"Erro ao carregar consultas: {e}")
            
            import traceback
            traceback.print_exc()
            flash(f'Erro ao carregar consultas: {str(e)}', 'danger')
            return redirect(url_for('medico.dashboard'))