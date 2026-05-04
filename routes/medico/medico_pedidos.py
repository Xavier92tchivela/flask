# routes/medico/medico_pedidos.py
from flask import render_template, request, flash, redirect, url_for, session, jsonify
import json
import logging
import traceback
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def init_medico_pedidos(base, gemini_available=False):
    """Inicializa rotas de pedidos do médico"""
    
    medico_required = base['medico_required']
    obter_info_medico = base['obter_info_medico']
    execute_query = base['execute_query']
    formatar_data = base['formatar_data']
    calcular_idade = base['calcular_idade']
    
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
    
    # ===== FUNÇÃO AUXILIAR PARA EXTRAIR VALOR DE DICT OU TUPLE =====
    def get_valor(item, index, key=None):
        """Extrai valor de dict (por chave) ou tuple (por índice)"""
        if item is None:
            return None
        if isinstance(item, dict):
            if key:
                return item.get(key)
            # Tenta encontrar a chave pelo índice
            keys = list(item.keys())
            if index < len(keys):
                return item.get(keys[index])
            return None
        else:
            # É tupla/lista
            if index < len(item):
                return item[index]
            return None
    
    # ========== ROTA: PEDIDOS DE ANÁLISE ==========
    @medico_required
    def pedidos_analise():
        try:
            medico_info = obter_info_medico()
            
            if not medico_info:
                flash('Informações do médico não encontradas.', 'danger')
                return redirect(url_for('auth.login'))
            
            medico_id = medico_info.get('id')
            if not medico_id:
                flash('Complete seu cadastro no perfil.', 'warning')
                medico_id = -1
                medico_info['id'] = medico_id
            
            # Obter filtros da URL
            status_filter = request.args.get('status', '')
            urgencia_filter = request.args.get('urgencia', '')
            aprovacao_filter = request.args.get('status_aprovacao', '')
            mes = request.args.get('mes', '')
            ano = request.args.get('ano', datetime.now().strftime('%Y'))
            data_especifica = request.args.get('data', '')
            filtro = request.args.get('filtro', '')
            
            # Construir query base
            query = """
                SELECT 
                    pa.id,
                    pa.consulta_id,
                    pa.medico_id,
                    pa.paciente_id,
                    pa.analista_id,
                    pa.tipo_exame,
                    pa.descricao,
                    pa.observacoes,
                    pa.urgencia,
                    pa.status,
                    pa.data_solicitacao,
                    pa.data_conclusao,
                    pa.resultado_analise,
                    pa.diagnostico_analista,
                    pa.recomendacoes_analista,
                    pa.anexos,
                    pa.status_aprovacao,
                    pa.observacoes_medico,
                    pa.criado_em,
                    pa.atualizado_em
                FROM pedidos_analise pa
                WHERE 1=1
            """
            
            params = []
            
            # Aplicar filtros
            if filtro == 'hoje':
                hoje = datetime.now().date()
                query += " AND DATE(pa.data_solicitacao) = %s"
                params.append(hoje)
            elif filtro == 'pendentes':
                query += " AND pa.status = 'pendente'"
            elif filtro == 'em_analise':
                query += " AND pa.status = 'em_analise'"
            elif filtro == 'concluidos':
                query += " AND pa.status = 'concluido'"
            elif filtro == 'urgentes':
                query += " AND pa.urgencia IN ('urgente', 'alta')"
            
            if status_filter:
                query += " AND pa.status = %s"
                params.append(status_filter)
            if urgencia_filter:
                query += " AND pa.urgencia = %s"
                params.append(urgencia_filter)
            if aprovacao_filter:
                query += " AND pa.status_aprovacao = %s"
                params.append(aprovacao_filter)
            
            if mes:
                query += " AND MONTH(pa.data_solicitacao) = %s"
                params.append(mes)
            
            if ano:
                query += " AND YEAR(pa.data_solicitacao) = %s"
                params.append(ano)
            
            if data_especifica:
                query += " AND DATE(pa.data_solicitacao) = %s"
                params.append(data_especifica)
            
            query += " ORDER BY pa.data_solicitacao DESC"
            
            logger.info(f"Executando query: {query}")
            logger.info(f"Params: {params}")
            
            pedidos = execute_query(query, params, fetch=True)
            
            logger.info(f"Total de pedidos encontrados: {len(pedidos) if pedidos else 0}")
            
            # Dicionários para contagem
            meses_contagem = {1:0, 2:0, 3:0, 4:0, 5:0, 6:0, 7:0, 8:0, 9:0, 10:0, 11:0, 12:0}
            
            meses_nomes = {
                1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
                5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
                9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
            }
            
            meses_abreviados = {
                1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr',
                5: 'Mai', 6: 'Jun', 7: 'Jul', 8: 'Ago',
                9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
            }
            
            datas_dict = {}
            
            estatisticas = {
                'total': 0,
                'hoje': 0,
                'pendentes': 0,
                'em_analise': 0,
                'concluidos': 0,
                'urgentes': 0,
                'normais': 0,
                'cancelados': 0
            }
            
            hoje = datetime.now().date()
            hoje_str = hoje.strftime('%Y-%m-%d')
            
            pedidos_formatados = []
            if pedidos:
                for p in pedidos:
                    try:
                        # 🔧 CORREÇÃO: Funciona com dict ou tuple
                        if isinstance(p, dict):
                            id_pedido = p.get('id')
                            consulta_id = p.get('consulta_id')
                            pedido_medico_id = p.get('medico_id')
                            paciente_id = p.get('paciente_id')
                            analista_id = p.get('analista_id')
                            tipo_exame = p.get('tipo_exame') or 'Não especificado'
                            descricao = p.get('descricao') or ''
                            observacoes = p.get('observacoes') or ''
                            urgencia = p.get('urgencia') or 'normal'
                            status = p.get('status') or 'pendente'
                            data_solicitacao = p.get('data_solicitacao')
                            data_conclusao = p.get('data_conclusao')
                            resultado_analise = p.get('resultado_analise') or ''
                            diagnostico_analista = p.get('diagnostico_analista') or ''
                            recomendacoes_analista = p.get('recomendacoes_analista') or ''
                            anexos_json = p.get('anexos')
                            status_aprovacao = p.get('status_aprovacao') or 'pendente'
                            observacoes_medico = p.get('observacoes_medico') or ''
                            criado_em = p.get('criado_em')
                            atualizado_em = p.get('atualizado_em')
                        else:
                            # É tupla/lista
                            id_pedido = p[0] if len(p) > 0 else None
                            consulta_id = p[1] if len(p) > 1 else None
                            pedido_medico_id = p[2] if len(p) > 2 else None
                            paciente_id = p[3] if len(p) > 3 else None
                            analista_id = p[4] if len(p) > 4 else None
                            tipo_exame = p[5] if len(p) > 5 else 'Não especificado'
                            descricao = p[6] if len(p) > 6 else ''
                            observacoes = p[7] if len(p) > 7 else ''
                            urgencia = p[8] if len(p) > 8 else 'normal'
                            status = p[9] if len(p) > 9 else 'pendente'
                            data_solicitacao = p[10] if len(p) > 10 else None
                            data_conclusao = p[11] if len(p) > 11 else None
                            resultado_analise = p[12] if len(p) > 12 else ''
                            diagnostico_analista = p[13] if len(p) > 13 else ''
                            recomendacoes_analista = p[14] if len(p) > 14 else ''
                            anexos_json = p[15] if len(p) > 15 else None
                            status_aprovacao = p[16] if len(p) > 16 else 'pendente'
                            observacoes_medico = p[17] if len(p) > 17 else ''
                            criado_em = p[18] if len(p) > 18 else None
                            atualizado_em = p[19] if len(p) > 19 else None
                        
                        # Extrair informações da data
                        data_obj = None
                        data_iso = ''
                        data_br = ''
                        mes_pedido = None
                        ano_pedido = None
                        
                        if data_solicitacao:
                            try:
                                if isinstance(data_solicitacao, datetime):
                                    data_obj = data_solicitacao
                                else:
                                    data_obj = datetime.strptime(str(data_solicitacao), '%Y-%m-%d %H:%M:%S')
                                
                                data_iso = data_obj.strftime('%Y-%m-%d')
                                data_br = data_obj.strftime('%d/%m/%Y')
                                mes_pedido = data_obj.month
                                ano_pedido = data_obj.year
                                
                                if mes_pedido in meses_contagem:
                                    meses_contagem[mes_pedido] += 1
                                
                                if data_iso not in datas_dict:
                                    datas_dict[data_iso] = {
                                        'data_iso': data_iso,
                                        'data_br': data_br,
                                        'total': 0
                                    }
                                datas_dict[data_iso]['total'] += 1
                                
                                estatisticas['total'] += 1
                                
                                if data_iso == hoje_str:
                                    estatisticas['hoje'] += 1
                                
                                if status == 'pendente':
                                    estatisticas['pendentes'] += 1
                                elif status == 'em_analise':
                                    estatisticas['em_analise'] += 1
                                elif status == 'concluido':
                                    estatisticas['concluidos'] += 1
                                elif status == 'cancelado':
                                    estatisticas['cancelados'] += 1
                                
                                if urgencia in ['urgente', 'alta']:
                                    estatisticas['urgentes'] += 1
                                else:
                                    estatisticas['normais'] += 1
                                
                            except:
                                pass
                        
                        tem_resultado = (status == 'concluido' and status_aprovacao == 'pendente')
                        pertence_medico = (pedido_medico_id == medico_id)
                        esta_atribuido = (analista_id is not None and analista_id != 0)
                        
                        data_solicitacao_fmt = formatar_data(data_solicitacao) if data_solicitacao else ''
                        data_conclusao_fmt = formatar_data(data_conclusao) if data_conclusao else ''
                        
                        anexos = []
                        if anexos_json and isinstance(anexos_json, str):
                            try:
                                anexos = json.loads(anexos_json)
                            except:
                                anexos = []
                        
                        # Buscar nome do paciente
                        paciente_nome = f"Paciente {paciente_id}"
                        if paciente_id:
                            paciente_info = execute_query(
                                "SELECT u.nome FROM pacientes p JOIN usuarios u ON p.usuario_id = u.id WHERE p.id = %s",
                                (paciente_id,), fetch=True, one=True
                            )
                            if paciente_info:
                                paciente_nome = converter_bytes_para_string(get_valor(paciente_info, 0, 'nome'))
                        
                        # Buscar nome do médico
                        medico_nome = f"Médico {pedido_medico_id}"
                        if pedido_medico_id:
                            medico_info_db = execute_query(
                                "SELECT u.nome FROM medicos m JOIN usuarios u ON m.usuario_id = u.id WHERE m.id = %s",
                                (pedido_medico_id,), fetch=True, one=True
                            )
                            if medico_info_db:
                                medico_nome = converter_bytes_para_string(get_valor(medico_info_db, 0, 'nome'))
                        
                        # Buscar nome do analista
                        analista_nome = "Não atribuído"
                        if analista_id and analista_id != 0:
                            analista_info = execute_query(
                                "SELECT u.nome FROM analistas a JOIN usuarios u ON a.usuario_id = u.id WHERE a.id = %s",
                                (analista_id,), fetch=True, one=True
                            )
                            if analista_info:
                                analista_nome = converter_bytes_para_string(get_valor(analista_info, 0, 'nome'))
                        
                        pedidos_formatados.append({
                            'id': id_pedido,
                            'consulta_id': consulta_id,
                            'medico_id': pedido_medico_id,
                            'paciente_id': paciente_id,
                            'analista_id': analista_id,
                            'tipo_exame': converter_bytes_para_string(tipo_exame),
                            'descricao': converter_bytes_para_string(descricao),
                            'observacoes': converter_bytes_para_string(observacoes),
                            'urgencia': converter_bytes_para_string(urgencia),
                            'status': converter_bytes_para_string(status),
                            'data_solicitacao': data_solicitacao_fmt,
                            'data_conclusao': data_conclusao_fmt,
                            'resultado_analise': converter_bytes_para_string(resultado_analise),
                            'diagnostico_analista': converter_bytes_para_string(diagnostico_analista),
                            'recomendacoes_analista': converter_bytes_para_string(recomendacoes_analista),
                            'anexos': anexos,
                            'status_aprovacao': converter_bytes_para_string(status_aprovacao),
                            'observacoes_medico': converter_bytes_para_string(observacoes_medico),
                            'criado_em': formatar_data(criado_em) if criado_em else '',
                            'atualizado_em': formatar_data(atualizado_em) if atualizado_em else '',
                            'paciente_nome': paciente_nome,
                            'paciente_idade': '',
                            'paciente_genero': '',
                            'analista_nome': analista_nome,
                            'analista_especialidade': '',
                            'medico_nome': medico_nome,
                            'medico_crm': '',
                            'tem_resultado': tem_resultado,
                            'pertence_medico': pertence_medico,
                            'esta_atribuido': esta_atribuido,
                            'total_anexos': len(anexos),
                            'mes': mes_pedido,
                            'mes_nome': meses_nomes.get(mes_pedido, '') if mes_pedido else '',
                            'mes_abreviado': meses_abreviados.get(mes_pedido, '') if mes_pedido else '',
                            'data_iso': data_iso,
                            'data_br': data_br
                        })
                        
                    except Exception as e:
                        logger.error(f"Erro ao processar pedido: {e}")
                        logger.error(traceback.format_exc())
                        continue
                
                logger.info(f"Pedidos formatados com sucesso: {len(pedidos_formatados)}")
            
            # Ordenar datas
            datas_disponiveis = sorted(datas_dict.values(), key=lambda x: x['data_iso'], reverse=True)[:7]
            
            # 🔧 CORREÇÃO: Buscar anos disponíveis (corrigido para dict/tuple)
            anos_raw = execute_query("""
                SELECT DISTINCT YEAR(data_solicitacao) as ano
                FROM pedidos_analise
                WHERE medico_id = %s
                ORDER BY ano DESC
            """, (medico_id,), fetch=True) or []
            
            anos_disponiveis = []
            for a in anos_raw:
                if a:
                    ano = get_valor(a, 0, 'ano')
                    if ano:
                        anos_disponiveis.append(ano)
            
            if not anos_disponiveis:
                anos_disponiveis = [datetime.now().year]
            
            # Processar filtros
            mes_selecionado = None
            if mes and mes.isdigit():
                mes_selecionado = int(mes)
            
            ano_selecionado = datetime.now().year
            if ano and ano.isdigit():
                ano_selecionado = int(ano)
            
            # Aplicar filtro aos pedidos exibidos
            if filtro == 'hoje':
                pedidos_exibidos = [p for p in pedidos_formatados if p.get('data_iso') == hoje_str]
            elif filtro == 'pendentes':
                pedidos_exibidos = [p for p in pedidos_formatados if p['status'] == 'pendente']
            elif filtro == 'em_analise':
                pedidos_exibidos = [p for p in pedidos_formatados if p['status'] == 'em_analise']
            elif filtro == 'concluidos':
                pedidos_exibidos = [p for p in pedidos_formatados if p['status'] == 'concluido']
            elif filtro == 'urgentes':
                pedidos_exibidos = [p for p in pedidos_formatados if p['urgencia'] in ['urgente', 'alta']]
            else:
                pedidos_exibidos = pedidos_formatados
            
            return render_template('medico/pedidos_analise.html',
                                 pedidos=pedidos_exibidos,
                                 estatisticas=estatisticas,
                                 status_filter=status_filter,
                                 urgencia_filter=urgencia_filter,
                                 aprovacao_filter=aprovacao_filter,
                                 meses_contagem=meses_contagem,
                                 meses_nomes=meses_nomes,
                                 anos_disponiveis=anos_disponiveis,
                                 datas_disponiveis=datas_disponiveis,
                                 mes_selecionado=mes_selecionado,
                                 ano_selecionado=ano_selecionado,
                                 filtro_selecionado=filtro,
                                 user=session,
                                 medico=medico_info)
            
        except Exception as e:
            logger.error(f"Erro ao carregar pedidos: {e}")
            logger.error(traceback.format_exc())
            flash(f'Erro ao carregar pedidos: {str(e)}', 'danger')
            return redirect(url_for('medico.dashboard'))
    
    # ========== ROTA: NOVA ANÁLISE (FORMULÁRIO) ==========
    @medico_required
    def nova_analise():
        """Exibe o formulário para criar um novo pedido de análise"""
        try:
            print("\n" + "="*50)
            print("CARREGANDO NOVA ANÁLISE")
            print("="*50)
            
            medico_info = obter_info_medico()
            if not medico_info:
                flash('Médico não encontrado.', 'danger')
                return redirect(url_for('auth.login'))
            
            medico_id = medico_info.get('id')
            print(f"Médico ID: {medico_id}")
            
            # Buscar consultas do médico
            consultas_raw = execute_query("""
                SELECT c.id, u.nome, c.data_hora, c.paciente_id
                FROM consultas c
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE c.medico_id = %s AND c.status IN ('agendada', 'confirmada', 'realizada')
                ORDER BY c.data_hora DESC
            """, (medico_id,), fetch=True) or []
            
            print(f"Total de consultas encontradas: {len(consultas_raw)}")
            
            consultas_lista = []
            for c_raw in consultas_raw:
                if isinstance(c_raw, dict):
                    paciente_nome = converter_bytes_para_string(c_raw.get('nome', ''))
                    consultas_lista.append({
                        'id': c_raw.get('id'),
                        'paciente_nome': paciente_nome,
                        'data_hora': formatar_data(c_raw.get('data_hora')),
                        'paciente_id': c_raw.get('paciente_id')
                    })
                else:
                    num_fields = len(c_raw)
                    paciente_nome = converter_bytes_para_string(c_raw[1]) if num_fields > 1 else ''
                    consultas_lista.append({
                        'id': c_raw[0] if num_fields > 0 else None,
                        'paciente_nome': paciente_nome,
                        'data_hora': formatar_data(c_raw[2]) if num_fields > 2 else '',
                        'paciente_id': c_raw[3] if num_fields > 3 else None
                    })
            
            print(f"Consultas processadas: {len(consultas_lista)}")
            
            tipos_exame = [
                'Hemograma Completo', 'Glicemia em Jejum', 'Colesterol Total e Frações',
                'Triglicerídeos', 'Urina Tipo 1', 'Urocultura', 'Parcial de Urina',
                'Fezes (Parasitológico)', 'TSH', 'T4 Livre', 'PCR', 'VHS',
                'Raio-X', 'Ultrassonografia', 'Tomografia', 'Ressonância',
                'Biópsia', 'Eletrocardiograma', 'Ecocardiograma', 'Teste Ergométrico'
            ]
            
            return render_template('medico/nova_analise.html',
                                 consultas=consultas_lista,
                                 tipos_exame=tipos_exame,
                                 user=session,
                                 medico=medico_info)
            
        except Exception as e:
            logger.error(f"Erro ao carregar formulário: {e}")
            flash(f'Erro: {str(e)}', 'danger')
            return redirect(url_for('medico.pedidos_analise'))
    
    # ========== ROTA: SALVAR NOVA ANÁLISE ==========
    @medico_required
    def salvar_analise():
        try:
            medico_info = obter_info_medico()
            if not medico_info:
                flash('Médico não encontrado', 'danger')
                return redirect(url_for('medico.nova_analise'))
            
            medico_id = medico_info.get('id')
            if not medico_id:
                flash('Complete seu cadastro no perfil.', 'warning')
                return redirect(url_for('medico.perfil'))
            
            consulta_id = request.form.get('consulta_id')
            paciente_id = request.form.get('paciente_id')
            tipo_exame = request.form.get('tipo_exame')
            descricao = request.form.get('descricao')
            observacoes = request.form.get('observacoes')
            urgencia = request.form.get('urgencia', 'normal')
            
            if not consulta_id or not paciente_id or not tipo_exame:
                flash('Preencha todos os campos obrigatórios', 'danger')
                return redirect(url_for('medico.nova_analise'))
            
            check_consulta = execute_query("""
                SELECT id FROM consultas WHERE id = %s AND medico_id = %s
            """, (consulta_id, medico_id), fetch=True, one=True)
            
            if not check_consulta:
                flash('Consulta não encontrada.', 'danger')
                return redirect(url_for('medico.nova_analise'))
            
            execute_query("""
                INSERT INTO pedidos_analise 
                (consulta_id, medico_id, paciente_id, tipo_exame, descricao, 
                 observacoes, urgencia, status, data_solicitacao, status_aprovacao, criado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, NOW())
            """, (
                consulta_id, medico_id, paciente_id, tipo_exame, descricao,
                observacoes, urgencia, 'pendente', 'pendente'
            ))
            
            flash('Pedido de análise criado com sucesso!', 'success')
            return redirect(url_for('medico.pedidos_analise'))
            
        except Exception as e:
            logger.error(f"Erro: {e}")
            flash(f'Erro ao salvar análise: {str(e)}', 'danger')
            return redirect(url_for('medico.nova_analise'))
    
    # ========== ROTA: TESTE DE PEDIDOS ==========
    def test_pedidos():
        try:
            pedidos = execute_query("""
                SELECT id, medico_id, tipo_exame, status, data_solicitacao 
                FROM pedidos_analise 
                ORDER BY id DESC 
                LIMIT 20
            """, fetch=True)
            
            resultado = []
            if pedidos:
                for p in pedidos:
                    if isinstance(p, dict):
                        resultado.append({
                            'id': p.get('id'),
                            'medico_id': p.get('medico_id'),
                            'tipo_exame': p.get('tipo_exame'),
                            'status': p.get('status'),
                            'data_solicitacao': str(p.get('data_solicitacao')) if p.get('data_solicitacao') else ''
                        })
                    else:
                        resultado.append({
                            'id': p[0] if len(p) > 0 else None,
                            'medico_id': p[1] if len(p) > 1 else None,
                            'tipo_exame': p[2] if len(p) > 2 else None,
                            'status': p[3] if len(p) > 3 else None,
                            'data_solicitacao': str(p[4]) if len(p) > 4 and p[4] else ''
                        })
            
            return jsonify({
                'total': len(resultado),
                'pedidos': resultado,
                'mensagem': 'Use esta rota para verificar se os pedidos existem no banco'
            })
        except Exception as e:
            return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500
    
    # ========== ROTA: CRIAR PEDIDO PARA MIM ==========
    def criar_pedido_para_mim():
        try:
            medico_info = obter_info_medico()
            medico_id = medico_info.get('id')
            
            if not medico_id or medico_id < 0:
                flash('ID do médico inválido', 'danger')
                return redirect(url_for('medico.pedidos_analise'))
            
            paciente = execute_query("SELECT id FROM pacientes LIMIT 1", fetch=True, one=True)
            if not paciente:
                flash('Nenhum paciente encontrado. Crie um paciente primeiro.', 'danger')
                return redirect(url_for('medico.pedidos_analise'))
            
            paciente_id = get_valor(paciente, 0, 'id')
            
            analista = execute_query("SELECT id FROM analistas WHERE status = 'ativo' LIMIT 1", fetch=True, one=True)
            analista_id = get_valor(analista, 0, 'id') if analista else None
            
            execute_query("""
                INSERT INTO pedidos_analise 
                (medico_id, paciente_id, analista_id, tipo_exame, descricao, urgencia, status, data_solicitacao, status_aprovacao, criado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s, NOW())
            """, (
                medico_id, paciente_id, analista_id,
                'Pedido de Teste', f'Pedido criado automaticamente para teste pelo médico ID {medico_id}', 
                'normal', 'pendente', 'pendente'
            ))
            
            flash('✅ Pedido criado para você com sucesso!', 'success')
            return redirect(url_for('medico.pedidos_analise'))
            
        except Exception as e:
            logger.error(f"Erro ao criar pedido: {e}")
            flash(f'Erro: {str(e)}', 'danger')
            return redirect(url_for('medico.pedidos_analise'))
    
    # ========== ROTA: DETALHES DO PEDIDO ==========
    @medico_required
    def ver_detalhes_pedido(pedido_id):
        try:
            logger.info("=" * 60)
            logger.info(f"CARREGANDO DETALHES DO PEDIDO #{pedido_id}")
            logger.info("=" * 60)
            
            medico_info = obter_info_medico()
            if not medico_info:
                logger.error("Médico não encontrado na sessão")
                flash('Médico não encontrado.', 'danger')
                return redirect(url_for('auth.login'))
            
            medico_id = medico_info.get('id')
            
            pedido = execute_query("""
                SELECT 
                    pa.id,
                    pa.consulta_id,
                    pa.medico_id,
                    pa.paciente_id,
                    pa.analista_id,
                    pa.tipo_exame,
                    pa.descricao,
                    pa.instrucoes,
                    pa.observacoes,
                    pa.urgencia,
                    pa.status,
                    pa.data_solicitacao,
                    pa.data_conclusao,
                    pa.resultado_analise,
                    pa.diagnostico_analista,
                    pa.recomendacoes_analista,
                    pa.anexos,
                    pa.status_aprovacao,
                    pa.observacoes_medico,
                    pa.criado_em,
                    pa.atualizado_em
                FROM pedidos_analise pa
                WHERE pa.id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido:
                logger.error(f"Pedido #{pedido_id} não encontrado")
                flash('Pedido não encontrado.', 'danger')
                return redirect(url_for('medico.pedidos_analise'))
            
            # Extrair dados (dict ou tuple)
            if isinstance(pedido, dict):
                consulta_id = pedido.get('consulta_id')
                analista_id = pedido.get('analista_id')
                status = pedido.get('status')
                status_aprovacao = pedido.get('status_aprovacao')
                pedido_medico_id = pedido.get('medico_id')
                anexos_json = pedido.get('anexos')
                paciente_id = pedido.get('paciente_id')
            else:
                consulta_id = pedido[1] if len(pedido) > 1 else None
                analista_id = pedido[4] if len(pedido) > 4 else None
                status = pedido[10] if len(pedido) > 10 else None
                status_aprovacao = pedido[17] if len(pedido) > 17 else None
                pedido_medico_id = pedido[2] if len(pedido) > 2 else None
                anexos_json = pedido[16] if len(pedido) > 16 else None
                paciente_id = pedido[3] if len(pedido) > 3 else None
            
            # Processar anexos
            anexos = []
            if anexos_json and isinstance(anexos_json, str):
                try:
                    anexos = json.loads(anexos_json)
                except:
                    anexos = []
            
            # Buscar receitas
            receitas_lista = []
            if consulta_id:
                receitas = execute_query("""
                    SELECT id, diagnostico, prescricao, recomendacoes, status, created_at,
                           receita_pdf_path, pdf_gerado
                    FROM receita WHERE consulta_id = %s ORDER BY created_at DESC
                """, (consulta_id,), fetch=True)
                
                if receitas:
                    for r in receitas:
                        if isinstance(r, dict):
                            receitas_lista.append({
                                'id': r.get('id'),
                                'diagnostico': r.get('diagnostico') or '',
                                'prescricao': r.get('prescricao') or '',
                                'recomendacoes': r.get('recomendacoes') or '',
                                'status': r.get('status') or '',
                                'created_at': formatar_data(r.get('created_at')),
                                'receita_pdf_path': r.get('receita_pdf_path') or '',
                                'pdf_gerado': bool(r.get('pdf_gerado'))
                            })
                        else:
                            receitas_lista.append({
                                'id': r[0] if len(r) > 0 else None,
                                'diagnostico': r[1] if len(r) > 1 else '',
                                'prescricao': r[2] if len(r) > 2 else '',
                                'recomendacoes': r[3] if len(r) > 3 else '',
                                'status': r[4] if len(r) > 4 else '',
                                'created_at': formatar_data(r[5]) if len(r) > 5 else '',
                                'receita_pdf_path': r[6] if len(r) > 6 else '',
                                'pdf_gerado': bool(r[7]) if len(r) > 7 else False
                            })
            
            # Buscar sintomas
            sintomas_lista = []
            if consulta_id:
                sintomas_data = execute_query("""
                    SELECT sintomas FROM consultas WHERE id = %s
                """, (consulta_id,), fetch=True, one=True)
                
                if sintomas_data:
                    sintomas_raw = get_valor(sintomas_data, 0, 'sintomas')
                    if sintomas_raw:
                        sintomas_lista = [s.strip() for s in converter_bytes_para_string(sintomas_raw).split(',') if s.strip()]
            
            # Buscar sinais vitais
            sinais_vitais_dict = None
            if consulta_id:
                sinais_vitais = execute_query("""
                    SELECT id, pressao_arterial, frequencia_cardiaca, frequencia_respiratoria,
                           temperatura, saturacao_oxigenio, glicemia, data_afericao, observacoes
                    FROM sinais_vitais WHERE consulta_id = %s ORDER BY data_afericao DESC LIMIT 1
                """, (consulta_id,), fetch=True, one=True)
                
                if sinais_vitais:
                    if isinstance(sinais_vitais, dict):
                        sinais_vitais_dict = {
                            'id': sinais_vitais.get('id'),
                            'pressao_arterial': sinais_vitais.get('pressao_arterial') or '---',
                            'frequencia_cardiaca': sinais_vitais.get('frequencia_cardiaca'),
                            'frequencia_respiratoria': sinais_vitais.get('frequencia_respiratoria'),
                            'temperatura': float(sinais_vitais.get('temperatura')) if sinais_vitais.get('temperatura') else None,
                            'saturacao_oxigenio': sinais_vitais.get('saturacao_oxigenio'),
                            'glicemia': sinais_vitais.get('glicemia'),
                            'data_afericao': formatar_data(sinais_vitais.get('data_afericao')) if sinais_vitais.get('data_afericao') else '',
                            'observacoes': sinais_vitais.get('observacoes') or ''
                        }
                    else:
                        sinais_vitais_dict = {
                            'id': sinais_vitais[0] if len(sinais_vitais) > 0 else None,
                            'pressao_arterial': sinais_vitais[1] if len(sinais_vitais) > 1 else '---',
                            'frequencia_cardiaca': sinais_vitais[2] if len(sinais_vitais) > 2 else None,
                            'frequencia_respiratoria': sinais_vitais[3] if len(sinais_vitais) > 3 else None,
                            'temperatura': float(sinais_vitais[4]) if len(sinais_vitais) > 4 and sinais_vitais[4] else None,
                            'saturacao_oxigenio': sinais_vitais[5] if len(sinais_vitais) > 5 else None,
                            'glicemia': sinais_vitais[6] if len(sinais_vitais) > 6 else None,
                            'data_afericao': formatar_data(sinais_vitais[7]) if len(sinais_vitais) > 7 and sinais_vitais[7] else '',
                            'observacoes': sinais_vitais[8] if len(sinais_vitais) > 8 else ''
                        }
            
            tem_receita = len(receitas_lista) > 0
            pertence_medico = (pedido_medico_id == medico_id)
            tem_resultado = (status == 'concluido' and status_aprovacao == 'pendente')
            esta_atribuido = (analista_id is not None and analista_id != 0)
            
            # Buscar nome do paciente
            paciente_nome = f"Paciente {paciente_id}"
            if paciente_id:
                paciente_info = execute_query(
                    "SELECT u.nome, p.data_nascimento, p.genero FROM pacientes p JOIN usuarios u ON p.usuario_id = u.id WHERE p.id = %s",
                    (paciente_id,), fetch=True, one=True
                )
                if paciente_info:
                    paciente_nome = converter_bytes_para_string(get_valor(paciente_info, 0, 'nome'))
            
            return render_template('medico/detalhes_pedido.html',
                                 pedido=pedido,
                                 receitas=receitas_lista,
                                 sinais_vitais=sinais_vitais_dict,
                                 sintomas_lista=sintomas_lista,
                                 gemini_available=gemini_available,
                                 user=session,
                                 medico=medico_info)
            
        except Exception as e:
            logger.error(f"Erro ao carregar detalhes: {e}")
            flash('Erro ao carregar detalhes.', 'danger')
            return redirect(url_for('medico.pedidos_analise'))
    
    # ========== ROTA: REVISAR ANÁLISE ==========
    @medico_required
    def revisar_analise(pedido_id):
        try:
            medico_info = obter_info_medico()
            if not medico_info:
                flash('Médico não encontrado.', 'danger')
                return redirect(url_for('auth.login'))
            
            medico_id = medico_info.get('id')
            
            pedido = execute_query("""
                SELECT pa.id, pa.tipo_exame, pa.descricao, pa.resultado_analise,
                       pa.diagnostico_analista, pa.recomendacoes_analista,
                       pa.status_aprovacao, pa.observacoes_medico, pa.paciente_id
                FROM pedidos_analise pa
                WHERE pa.id = %s AND pa.medico_id = %s
            """, (pedido_id, medico_id), fetch=True, one=True)
            
            if not pedido:
                flash('Pedido não encontrado.', 'danger')
                return redirect(url_for('medico.pedidos_analise'))
            
            # Extrair dados
            if isinstance(pedido, dict):
                paciente_id = pedido.get('paciente_id')
                status_aprovacao = pedido.get('status_aprovacao')
                tipo_exame = pedido.get('tipo_exame')
                descricao = pedido.get('descricao')
                resultado_analise = pedido.get('resultado_analise')
                diagnostico_analista = pedido.get('diagnostico_analista')
                recomendacoes_analista = pedido.get('recomendacoes_analista')
            else:
                paciente_id = pedido[8] if len(pedido) > 8 else None
                status_aprovacao = pedido[6] if len(pedido) > 6 else 'pendente'
                tipo_exame = pedido[1] if len(pedido) > 1 else ''
                descricao = pedido[2] if len(pedido) > 2 else ''
                resultado_analise = pedido[3] if len(pedido) > 3 else ''
                diagnostico_analista = pedido[4] if len(pedido) > 4 else ''
                recomendacoes_analista = pedido[5] if len(pedido) > 5 else ''
            
            if status_aprovacao != 'pendente':
                flash('Este pedido já foi revisado.', 'warning')
                return redirect(url_for('medico.ver_detalhes_pedido', pedido_id=pedido_id))
            
            # Buscar nome do paciente
            paciente_nome = f"Paciente {paciente_id}"
            if paciente_id:
                paciente_info = execute_query(
                    "SELECT u.nome FROM pacientes p JOIN usuarios u ON p.usuario_id = u.id WHERE p.id = %s",
                    (paciente_id,), fetch=True, one=True
                )
                if paciente_info:
                    paciente_nome = converter_bytes_para_string(get_valor(paciente_info, 0, 'nome'))
            
            pedido_dict = {
                'id': pedido_id,
                'tipo_exame': converter_bytes_para_string(tipo_exame),
                'descricao': converter_bytes_para_string(descricao),
                'resultado_analise': converter_bytes_para_string(resultado_analise),
                'diagnostico_analista': converter_bytes_para_string(diagnostico_analista),
                'recomendacoes_analista': converter_bytes_para_string(recomendacoes_analista),
                'status_aprovacao': status_aprovacao,
                'observacoes_medico': '',
                'paciente_nome': paciente_nome
            }
            
            return render_template('medico/revisar_analise.html',
                                 pedido=pedido_dict,
                                 user=session,
                                 medico=medico_info)
            
        except Exception as e:
            logger.error(f"Erro ao carregar revisão: {e}")
            flash('Erro ao carregar revisão.', 'danger')
            return redirect(url_for('medico.pedidos_analise'))
    
    # ========== ROTA: SALVAR REVISÃO ==========
    @medico_required
    def salvar_revisao(pedido_id):
        try:
            medico_info = obter_info_medico()
            if not medico_info:
                return jsonify({'error': 'Não autorizado'}), 401
            
            medico_id = medico_info.get('id')
            
            check = execute_query("""
                SELECT id FROM pedidos_analise 
                WHERE id = %s AND medico_id = %s
            """, (pedido_id, medico_id), fetch=True, one=True)
            
            if not check:
                return jsonify({'error': 'Pedido não encontrado'}), 404
            
            status = request.form.get('status_aprovacao', 'aprovado')
            observacoes = request.form.get('observacoes_medico', '')
            
            execute_query("""
                UPDATE pedidos_analise 
                SET status_aprovacao = %s, observacoes_medico = %s,
                    atualizado_em = NOW()
                WHERE id = %s
            """, (status, observacoes, pedido_id))
            
            flash('Revisão salva com sucesso!', 'success')
            return redirect(url_for('medico.ver_detalhes_pedido', pedido_id=pedido_id))
            
        except Exception as e:
            logger.error(f"Erro ao salvar revisão: {e}")
            flash('Erro ao salvar revisão.', 'danger')
            return redirect(url_for('medico.revisar_analise', pedido_id=pedido_id))
    
    # ========== ROTA: CANCELAR PEDIDO ==========
    @medico_required
    def cancelar_pedido(pedido_id):
        try:
            medico_info = obter_info_medico()
            if not medico_info:
                flash('Médico não encontrado.', 'danger')
                return redirect(url_for('medico.pedidos_analise'))
            
            medico_id = medico_info.get('id')
            
            check = execute_query("""
                SELECT id FROM pedidos_analise 
                WHERE id = %s AND medico_id = %s AND status = 'pendente'
            """, (pedido_id, medico_id), fetch=True, one=True)
            
            if not check:
                flash('Pedido não encontrado ou não pode ser cancelado.', 'danger')
                return redirect(url_for('medico.pedidos_analise'))
            
            execute_query("""
                UPDATE pedidos_analise 
                SET status = 'cancelado', atualizado_em = NOW()
                WHERE id = %s
            """, (pedido_id,))
            
            flash('Pedido cancelado com sucesso!', 'success')
            return redirect(url_for('medico.pedidos_analise'))
            
        except Exception as e:
            logger.error(f"Erro ao cancelar pedido: {e}")
            flash('Erro ao cancelar pedido.', 'danger')
            return redirect(url_for('medico.pedidos_analise'))
    
    # ========== ROTA: ATRIBUIR PRÓXIMO PEDIDO ==========
    @medico_required
    def atribuir_proximo_pedido():
        try:
            medico_info = obter_info_medico()
            if not medico_info:
                flash('Médico não encontrado.', 'danger')
                return redirect(url_for('medico.pedidos_analise'))
            
            medico_id = medico_info.get('id')
            if not medico_id or medico_id < 0:
                flash('Complete seu cadastro no perfil.', 'warning')
                return redirect(url_for('medico.perfil'))
            
            pedido = execute_query("""
                SELECT id, tipo_exame, paciente_id, descricao
                FROM pedidos_analise 
                WHERE (analista_id IS NULL OR analista_id = 0)
                AND status = 'pendente'
                AND medico_id != %s
                ORDER BY 
                    CASE urgencia
                        WHEN 'urgente' THEN 1
                        WHEN 'alta' THEN 2
                        WHEN 'normal' THEN 3
                        WHEN 'baixa' THEN 4
                        ELSE 5
                    END,
                    data_solicitacao
                LIMIT 1
            """, (medico_id,), fetch=True, one=True)
            
            if not pedido:
                flash('Nenhum pedido disponível para atribuição no momento.', 'info')
                return redirect(url_for('medico.pedidos_analise'))
            
            pedido_id = get_valor(pedido, 0, 'id')
            
            analista = execute_query("""
                SELECT id FROM analistas WHERE status = 'ativo' ORDER BY RAND() LIMIT 1
            """, fetch=True, one=True)
            
            analista_id = get_valor(analista, 0, 'id') if analista else None
            
            if analista_id:
                execute_query("""
                    UPDATE pedidos_analise 
                    SET analista_id = %s, status = 'em_analise', atualizado_em = NOW()
                    WHERE id = %s
                """, (analista_id, pedido_id))
                
                flash(f'Pedido #{pedido_id} atribuído ao analista ID {analista_id}!', 'success')
            else:
                flash('Nenhum analista disponível no momento.', 'warning')
            
            return redirect(url_for('medico.ver_detalhes_pedido', pedido_id=pedido_id))
            
        except Exception as e:
            logger.error(f"Erro ao atribuir pedido: {e}")
            flash(f'Erro ao atribuir pedido: {str(e)}', 'danger')
            return redirect(url_for('medico.pedidos_analise'))
    
    # ========== ROTA: DETALHES DA CONSULTA PARA ANÁLISE ==========
    @medico_required
    def analise(consulta_id):
        return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
    
    # ========== ROTA: NOVA ANÁLISE COMPLETA ==========
    @medico_required
    def nova_analise_completa():
        return redirect(url_for('medico.nova_analise'))
    
    return {
        'routes': [
            {'rule': '/pedidos-analise', 'view_func': pedidos_analise, 'methods': ['GET']},
            {'rule': '/nova-analise', 'view_func': nova_analise, 'methods': ['GET']},
            {'rule': '/test-pedidos', 'view_func': test_pedidos, 'methods': ['GET']},
            {'rule': '/criar-pedido-para-mim', 'view_func': criar_pedido_para_mim, 'methods': ['POST']},
            {'rule': '/pedidos/<int:pedido_id>', 'view_func': ver_detalhes_pedido, 'methods': ['GET']},
            {'rule': '/revisar-analise/<int:pedido_id>', 'view_func': revisar_analise, 'methods': ['GET']},
            {'rule': '/salvar-revisao/<int:pedido_id>', 'view_func': salvar_revisao, 'methods': ['POST']},
            {'rule': '/pedidos/<int:pedido_id>/cancelar', 'view_func': cancelar_pedido, 'methods': ['POST']},
            {'rule': '/salvar-analise', 'view_func': salvar_analise, 'methods': ['POST']},
            {'rule': '/atribuir-proximo-pedido', 'view_func': atribuir_proximo_pedido, 'methods': ['GET']},
            {'rule': '/analise/<int:consulta_id>', 'view_func': analise, 'methods': ['GET']},
            {'rule': '/nova-analise-completa', 'view_func': nova_analise_completa, 'methods': ['GET']}
        ]
    }
