from datetime import datetime, timedelta
from flask import render_template, request, flash, redirect, url_for, session
import traceback

def init_medico_consultas(base):
    """
    Inicializa rotas de consultas do médico
    
    Args:
        base: Dicionário com funções base
    
    Returns:
        Dicionário com as rotas do módulo
    """
    
    medico_required = base['medico_required']
    obter_info_medico = base['obter_info_medico']
    execute_query = base['execute_query']
    formatar_data = base['formatar_data']
    
    # ===== FUNÇÃO AUXILIAR PARA CONVERTER BYTES =====
    def converter_bytes_para_string(valor):
        """Converte bytes para string se necessário"""
        if valor is None:
            return ''
        if isinstance(valor, bytes):
            try:
                return valor.decode('utf-8', errors='ignore')
            except:
                return str(valor)
        return str(valor) if valor else ''
    
    def consulta_para_dict(consulta):
        """
        Converte consulta (dict ou tuple) para dicionário padronizado
        
        Suporta:
        - Dicionário: {'id': 1, 'paciente_nome': 'João', ...}
        - Tupla: (id, paciente_nome, data_nascimento, genero, telefone, email, data_hora, status, observacoes, sintomas)
        """
        # Se for dicionário, usa diretamente
        if isinstance(consulta, dict):
            return {
                'id': consulta.get('id'),
                'paciente_nome': converter_bytes_para_string(consulta.get('paciente_nome', '')),
                'data_nascimento': consulta.get('data_nascimento'),
                'genero': consulta.get('genero'),
                'telefone': converter_bytes_para_string(consulta.get('telefone', '')),
                'email': converter_bytes_para_string(consulta.get('email', '')),
                'data_hora': consulta.get('data_hora'),
                'status': consulta.get('status'),
                'observacoes': converter_bytes_para_string(consulta.get('observacoes', '')),
                'sintomas': converter_bytes_para_string(consulta.get('sintomas', ''))
            }
        
        # Se for tupla, acessa por índice
        if isinstance(consulta, (tuple, list)):
            return {
                'id': consulta[0] if len(consulta) > 0 else None,
                'paciente_nome': converter_bytes_para_string(consulta[1]) if len(consulta) > 1 else '',
                'data_nascimento': consulta[2] if len(consulta) > 2 else None,
                'genero': consulta[3] if len(consulta) > 3 else None,
                'telefone': converter_bytes_para_string(consulta[4]) if len(consulta) > 4 else '',
                'email': converter_bytes_para_string(consulta[5]) if len(consulta) > 5 else '',
                'data_hora': consulta[6] if len(consulta) > 6 else None,
                'status': consulta[7] if len(consulta) > 7 else None,
                'observacoes': converter_bytes_para_string(consulta[8]) if len(consulta) > 8 else '',
                'sintomas': converter_bytes_para_string(consulta[9]) if len(consulta) > 9 else ''
            }
        
        # Fallback: retorna vazio
        return {}
    
    @medico_required
    def consultas():
        """Lista todas as consultas do médico com filtros"""
        try:
            print("="*50)
            print("CARREGANDO CONSULTAS")
            print("="*50)
            
            medico_info = obter_info_medico()
            if not medico_info:
                flash('Informações do médico não encontradas.', 'danger')
                return redirect(url_for('medico.dashboard'))
            
            medico_id = medico_info.get('id')
            print(f"Médico ID: {medico_id}")
            
            # Obter filtros da URL
            status = request.args.get('status', '')
            periodo = request.args.get('periodo', '')
            busca = request.args.get('busca', '')
            dia_semana = request.args.get('dia_semana', '')
            mes = request.args.get('mes', '')
            ano = request.args.get('ano', datetime.now().strftime('%Y'))
            data_especifica = request.args.get('data', '')
            data_inicio = request.args.get('data_inicio', '')
            data_fim = request.args.get('data_fim', '')
            
            # Construir query base
            query = """
                SELECT 
                    c.id,
                    u.nome as paciente_nome,
                    p.data_nascimento,
                    p.genero,
                    p.telefone,
                    u.email,
                    c.data_hora,
                    c.status,
                    c.observacoes,
                    c.sintomas
                FROM consultas c
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE c.medico_id = %s
            """
            params = [medico_id]
            
            # Aplicar filtros
            if status:
                query += " AND c.status = %s"
                params.append(status)
            
            if dia_semana:
                dias_map = {
                    'Segunda': 'Monday', 'Segunda-feira': 'Monday',
                    'Terça': 'Tuesday', 'Terça-feira': 'Tuesday',
                    'Quarta': 'Wednesday', 'Quarta-feira': 'Wednesday',
                    'Quinta': 'Thursday', 'Quinta-feira': 'Thursday',
                    'Sexta': 'Friday', 'Sexta-feira': 'Friday',
                    'Sábado': 'Saturday', 'Sabado': 'Saturday',
                    'Domingo': 'Sunday'
                }
                dia_ingles = dias_map.get(dia_semana, dia_semana)
                query += " AND DAYNAME(c.data_hora) = %s"
                params.append(dia_ingles)
            
            if mes and mes.isdigit():
                query += " AND MONTH(c.data_hora) = %s"
                params.append(int(mes))
            
            if ano and ano.isdigit():
                query += " AND YEAR(c.data_hora) = %s"
                params.append(int(ano))
            
            if data_especifica:
                query += " AND DATE(c.data_hora) = %s"
                params.append(data_especifica)
            
            if data_inicio:
                query += " AND DATE(c.data_hora) >= %s"
                params.append(data_inicio)
            
            if data_fim:
                query += " AND DATE(c.data_hora) <= %s"
                params.append(data_fim)
            
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
                    query += " AND DATE(c.data_hora) >= %s"
                    params.append(inicio_mes)
            
            if busca:
                query += " AND u.nome LIKE %s"
                params.append(f"%{busca}%")
            
            query += " ORDER BY c.data_hora DESC"
            
            # Executar query
            consultas_raw = execute_query(query, params, fetch=True) or []
            print(f"Total de consultas encontradas: {len(consultas_raw)}")
            print(f"Tipo do primeiro resultado: {type(consultas_raw[0]) if consultas_raw else 'Nenhum'}")
            
            # Processar consultas
            consultas = []
            meses_contagem = {1:0, 2:0, 3:0, 4:0, 5:0, 6:0, 7:0, 8:0, 9:0, 10:0, 11:0, 12:0}
            dias_contagem = {
                'Segunda': 0, 'Terça': 0, 'Quarta': 0, 
                'Quinta': 0, 'Sexta': 0, 'Sábado': 0, 'Domingo': 0
            }
            
            meses_nomes = {
                1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
                5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
                9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
            }
            
            datas_dict = {}
            dias_map_pt = {
                'Monday': 'Segunda', 'Tuesday': 'Terça', 'Wednesday': 'Quarta',
                'Thursday': 'Quinta', 'Friday': 'Sexta', 'Saturday': 'Sábado',
                'Sunday': 'Domingo'
            }
            status_class_map = {
                'agendada': 'warning',
                'realizada': 'success',
                'cancelada': 'danger',
                'confirmada': 'info',
                'pendente': 'secondary'
            }
            
            for c_raw in consultas_raw:
                # Converter para dicionário padronizado
                c = consulta_para_dict(c_raw)
                
                # Calcular idade
                idade = None
                if c.get('data_nascimento'):
                    try:
                        data_nasc = c['data_nascimento']
                        if isinstance(data_nasc, str):
                            data_nasc = datetime.strptime(data_nasc, '%Y-%m-%d')
                        idade = datetime.now().year - data_nasc.year
                        if datetime.now().month < data_nasc.month or (datetime.now().month == data_nasc.month and datetime.now().day < data_nasc.day):
                            idade -= 1
                    except Exception as e:
                        print(f"Erro ao calcular idade: {e}")
                
                # Processar sintomas
                sintomas_lista = []
                if c.get('sintomas'):
                    sintomas_lista = [s.strip() for s in c['sintomas'].split(',') if s.strip()]
                
                # Extrair informações da data
                data_consulta_obj = None
                dia_semana_pt = ''
                hora_consulta = ''
                data_consulta = ''
                data_iso = ''
                mes_consulta = None
                ano_consulta = None
                
                if c.get('data_hora'):
                    try:
                        data_hora = c['data_hora']
                        if isinstance(data_hora, str):
                            data_consulta_obj = datetime.strptime(data_hora, '%Y-%m-%d %H:%M:%S')
                        elif isinstance(data_hora, datetime):
                            data_consulta_obj = data_hora
                        
                        if data_consulta_obj:
                            dia_semana_ingles = data_consulta_obj.strftime('%A')
                            dia_semana_pt = dias_map_pt.get(dia_semana_ingles, '')
                            hora_consulta = data_consulta_obj.strftime('%H:%M')
                            data_consulta = data_consulta_obj.strftime('%d/%m/%Y')
                            data_iso = data_consulta_obj.strftime('%Y-%m-%d')
                            mes_consulta = data_consulta_obj.month
                            ano_consulta = data_consulta_obj.year
                            
                            if mes_consulta in meses_contagem:
                                meses_contagem[mes_consulta] += 1
                            if dia_semana_pt in dias_contagem:
                                dias_contagem[dia_semana_pt] += 1
                            
                            if data_iso not in datas_dict:
                                datas_dict[data_iso] = {
                                    'data_iso': data_iso,
                                    'data_br': data_consulta,
                                    'dia_semana': dia_semana_pt,
                                    'dia_semana_abreviado': dia_semana_pt[:3] if dia_semana_pt else '',
                                    'total': 0
                                }
                            datas_dict[data_iso]['total'] += 1
                    except Exception as e:
                        print(f"Erro ao processar data: {e}")
                
                # Determinar gênero
                genero = c.get('genero', '')
                if genero == 'M':
                    genero_texto = 'Masculino'
                elif genero == 'F':
                    genero_texto = 'Feminino'
                else:
                    genero_texto = genero or 'Não informado'
                
                consultas.append({
                    'id': c.get('id'),
                    'paciente_nome': c.get('paciente_nome') or 'Nome não disponível',
                    'paciente_idade': f"{idade} anos" if idade else "Idade não informada",
                    'paciente_genero': genero_texto,
                    'paciente_telefone': c.get('telefone') or 'Não informado',
                    'paciente_email': c.get('email') or 'Não informado',
                    'data_hora': formatar_data(c.get('data_hora'), '%d/%m/%Y %H:%M') if c.get('data_hora') else 'Data não disponível',
                    'data_consulta': data_consulta,
                    'hora_consulta': hora_consulta,
                    'dia_semana': dia_semana_pt,
                    'mes': mes_consulta,
                    'mes_nome': meses_nomes.get(mes_consulta, '') if mes_consulta else '',
                    'ano': ano_consulta,
                    'status': c.get('status') or 'desconhecido',
                    'observacoes': c.get('observacoes', ''),
                    'sintomas_lista': sintomas_lista,
                    'tem_sintomas': len(sintomas_lista) > 0,
                    'status_class': status_class_map.get(c.get('status'), 'secondary')
                })
            
            # Ordenar datas
            datas_disponiveis = sorted(datas_dict.values(), key=lambda x: x['data_iso'], reverse=True)[:7]
            
            # Buscar anos disponíveis
            anos_raw = execute_query("""
                SELECT DISTINCT YEAR(data_hora) as ano
                FROM consultas
                WHERE medico_id = %s
                ORDER BY ano DESC
            """, (medico_id,), fetch=True) or []
            
            anos_disponiveis = []
            for a in anos_raw:
                if isinstance(a, dict):
                    ano_val = a.get('ano')
                elif isinstance(a, (tuple, list)):
                    ano_val = a[0] if a else None
                else:
                    ano_val = a
                if ano_val:
                    anos_disponiveis.append(ano_val)
            
            if not anos_disponiveis:
                anos_disponiveis = [datetime.now().year]
            
            # Processar filtros
            mes_selecionado = None
            if mes and mes.isdigit():
                mes_selecionado = int(mes)
            
            ano_selecionado = datetime.now().year
            if ano and ano.isdigit():
                ano_selecionado = int(ano)
            
            print(f"Renderizando template com {len(consultas)} consultas")
            
            return render_template('medico/consultas.html',
                                 consultas=consultas,
                                 medico={'nome': medico_info.get('nome', 'Médico')},
                                 total_consultas=len(consultas),
                                 meses_contagem=meses_contagem,
                                 meses_nomes=meses_nomes,
                                 anos_disponiveis=anos_disponiveis,
                                 mes_selecionado=mes_selecionado,
                                 ano_selecionado=ano_selecionado,
                                 dias_contagem=dias_contagem,
                                 datas_disponiveis=datas_disponiveis,
                                 request=request,
                                 user=session)
            
        except Exception as e:
            print(f"ERRO AO CARREGAR CONSULTAS: {e}")
            print(traceback.format_exc())
            flash(f'Erro ao carregar consultas: {str(e)}', 'danger')
            return redirect(url_for('medico.dashboard'))
    
    # Retornar o dicionário com as rotas
    return {
        'routes': [
            {'rule': '/consultas', 'view_func': consultas, 'methods': ['GET']}
        ]
    }

# Exportar a função
__all__ = ['init_medico_consultas']
