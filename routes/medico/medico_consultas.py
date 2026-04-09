# routes/medico/medico_consultas.py
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
    
    def converter_toda_lista(consultas_lista):
        """Converte todos os campos da lista de consultas para string"""
        if not consultas_lista:
            return []
        
        resultado = []
        for consulta in consultas_lista:
            nova_consulta = {}
            for chave, valor in consulta.items():
                if isinstance(valor, bytes):
                    nova_consulta[chave] = converter_bytes_para_string(valor)
                elif isinstance(valor, list):
                    # Se for lista, converte cada item
                    nova_consulta[chave] = [converter_bytes_para_string(item) if isinstance(item, bytes) else item for item in valor]
                elif isinstance(valor, dict):
                    # Se for dicionário, converte recursivamente
                    nova_consulta[chave] = {k: converter_bytes_para_string(v) if isinstance(v, bytes) else v for k, v in valor.items()}
                else:
                    nova_consulta[chave] = valor
            resultado.append(nova_consulta)
        
        return resultado
    
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
                query += " AND DAYNAME(c.data_hora) = %s"
                params.append(dia_semana)
            
            if mes:
                query += " AND MONTH(c.data_hora) = %s"
                params.append(mes)
            
            if ano:
                query += " AND YEAR(c.data_hora) = %s"
                params.append(ano)
            
            if data_especifica:
                query += " AND DATE(c.data_hora) = %s"
                params.append(data_especifica)
            
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
                query += " AND u.nome LIKE %s"
                params.append(f"%{busca}%")
            
            query += " ORDER BY c.data_hora DESC"
            
            # Executar query
            consultas_raw = execute_query(query, params, fetch=True) or []
            print(f"Total de consultas encontradas: {len(consultas_raw)}")
            
            # Processar consultas
            consultas = []
            meses_contagem = {1:0, 2:0, 3:0, 4:0, 5:0, 6:0, 7:0, 8:0, 9:0, 10:0, 11:0, 12:0}
            dias_contagem = {
                'Segunda': 0, 'Terça': 0, 'Quarta': 0, 
                'Quinta': 0, 'Sexta': 0, 'Sábado': 0, 'Domingo': 0
            }
            
            # Dicionários para nomes (para o template)
            meses_nomes = {
                1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
                5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
                9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
            }
            
            dias_nomes = {
                'Monday': 'Segunda-feira',
                'Tuesday': 'Terça-feira',
                'Wednesday': 'Quarta-feira',
                'Thursday': 'Quinta-feira',
                'Friday': 'Sexta-feira',
                'Saturday': 'Sábado',
                'Sunday': 'Domingo'
            }
            
            # Mapear dias da semana (abreviados)
            dias_map = {
                'Monday': 'Segunda',
                'Tuesday': 'Terça',
                'Wednesday': 'Quarta',
                'Thursday': 'Quinta',
                'Friday': 'Sexta',
                'Saturday': 'Sábado',
                'Sunday': 'Domingo'
            }
            
            # Mapear meses (abreviados)
            meses_abreviados = {
                1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr',
                5: 'Mai', 6: 'Jun', 7: 'Jul', 8: 'Ago',
                9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
            }
            
            # Dicionário para coletar datas disponíveis
            datas_dict = {}
            
            for c in consultas_raw:
                # ===== CONVERSÃO DE BYTES =====
                # Converter observacoes (campo 8)
                observacoes = converter_bytes_para_string(c[8])
                
                # Converter sintomas (campo 9)
                sintomas_raw = converter_bytes_para_string(c[9])
                
                # Calcular idade
                idade = None
                if c[2]:
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
                
                # Processar sintomas (agora é string)
                sintomas_lista = []
                if sintomas_raw:
                    sintomas_lista = [s.strip() for s in sintomas_raw.split(',') if s.strip()]
                
                # Extrair informações da data
                data_consulta_obj = None
                dia_semana_pt = ''
                hora_consulta = ''
                data_consulta = ''
                data_iso = ''
                mes_consulta = None
                ano_consulta = None
                
                if c[6]:
                    try:
                        if isinstance(c[6], datetime):
                            data_consulta_obj = c[6]
                        else:
                            data_consulta_obj = datetime.strptime(str(c[6]), '%Y-%m-%d %H:%M:%S')
                        
                        # Dia da semana
                        dia_semana_ingles = data_consulta_obj.strftime('%A')
                        dia_semana_pt = dias_map.get(dia_semana_ingles, '')
                        
                        # Hora
                        hora_consulta = data_consulta_obj.strftime('%H:%M')
                        
                        # Data
                        data_consulta = data_consulta_obj.strftime('%d/%m/%Y')
                        data_iso = data_consulta_obj.strftime('%Y-%m-%d')
                        
                        # Mês e ano
                        mes_consulta = data_consulta_obj.month
                        ano_consulta = data_consulta_obj.year
                        
                        # Contagens
                        if mes_consulta in meses_contagem:
                            meses_contagem[mes_consulta] += 1
                        if dia_semana_pt in dias_contagem:
                            dias_contagem[dia_semana_pt] += 1
                        
                        # Coletar datas para o filtro
                        if data_iso not in datas_dict:
                            datas_dict[data_iso] = {
                                'data_iso': data_iso,
                                'data_br': data_consulta,
                                'dia_semana': dia_semana_pt,
                                'dia_semana_abreviado': dia_semana_pt[:3],
                                'total': 0
                            }
                        datas_dict[data_iso]['total'] += 1
                            
                    except Exception as e:
                        print(f"Erro ao processar data: {e}")
                
                consultas.append({
                    'id': c[0],
                    'paciente_nome': c[1] or 'Nome não disponível',
                    'paciente_idade': f"{idade} anos" if idade else "Idade não informada",
                    'paciente_genero': 'Masculino' if c[3] == 'M' else 'Feminino' if c[3] == 'F' else (c[3] or 'Não informado'),
                    'paciente_telefone': c[4] or 'Não informado',
                    'paciente_email': c[5] or 'Não informado',
                    'data_hora': formatar_data(c[6], '%d/%m/%Y %H:%M') if c[6] else 'Data não disponível',
                    'data_consulta': data_consulta,
                    'hora_consulta': hora_consulta,
                    'dia_semana': dia_semana_pt,
                    'mes': mes_consulta,
                    'mes_nome': meses_nomes.get(mes_consulta, '') if mes_consulta else '',
                    'mes_abreviado': meses_abreviados.get(mes_consulta, '') if mes_consulta else '',
                    'ano': ano_consulta,
                    'status': c[7] or 'desconhecido',
                    'observacoes': observacoes,
                    'sintomas_lista': sintomas_lista,
                    'tem_sintomas': len(sintomas_lista) > 0,
                    'status_class': {
                        'agendada': 'warning',
                        'realizada': 'success',
                        'cancelada': 'danger',
                        'confirmada': 'info'
                    }.get(c[7], 'secondary')
                })
            
            # CONVERTER TODA A LISTA PARA GARANTIR QUE NÃO HAJA BYTES
            consultas = converter_toda_lista(consultas)
            
            # Ordenar datas e pegar as mais recentes (últimas 7)
            datas_disponiveis = sorted(datas_dict.values(), key=lambda x: x['data_iso'], reverse=True)[:7]
            
            # Buscar anos disponíveis
            anos_raw = execute_query("""
                SELECT DISTINCT YEAR(data_hora) as ano
                FROM consultas
                WHERE medico_id = %s
                ORDER BY ano DESC
            """, (medico_id,), fetch=True) or []
            
            anos_disponiveis = [a[0] for a in anos_raw if a and a[0]]
            if not anos_disponiveis:
                anos_disponiveis = [datetime.now().year]
            
            # Processar filtros da URL
            mes_selecionado = None
            if mes and mes.isdigit():
                mes_selecionado = int(mes)
            
            ano_selecionado = datetime.now().year
            if ano and ano.isdigit():
                ano_selecionado = int(ano)
            
            print(f"Renderizando template com {len(consultas)} consultas")
            print(f"Datas disponíveis: {len(datas_disponiveis)}")
            
            return render_template('medico/consultas.html',
                                 consultas=consultas,
                                 medico={'nome': medico_info.get('nome', 'Médico')},
                                 total_consultas=len(consultas),
                                 meses_contagem=meses_contagem,
                                 meses_nomes=meses_nomes,
                                 dias_nomes=dias_nomes,
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