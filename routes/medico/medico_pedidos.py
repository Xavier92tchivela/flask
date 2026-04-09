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
            
            # Aplicar filtros baseados na categoria
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
            
            # Filtros por mês e ano
            if mes:
                query += " AND MONTH(pa.data_solicitacao) = %s"
                params.append(mes)
            
            if ano:
                query += " AND YEAR(pa.data_solicitacao) = %s"
                params.append(ano)
            
            # Filtro por data específica
            if data_especifica:
                query += " AND DATE(pa.data_solicitacao) = %s"
                params.append(data_especifica)
            
            query += " ORDER BY pa.data_solicitacao DESC"
            
            logger.info(f"Executando query: {query}")
            logger.info(f"Params: {params}")
            
            pedidos = execute_query(query, params, fetch=True)
            
            logger.info(f"Total de pedidos encontrados: {len(pedidos) if pedidos else 0}")
            
            # Dicionários para contagem por mês
            meses_contagem = {1:0, 2:0, 3:0, 4:0, 5:0, 6:0, 7:0, 8:0, 9:0, 10:0, 11:0, 12:0}
            
            # Nomes dos meses
            meses_nomes = {
                1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
                5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
                9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
            }
            
            # Nomes dos meses abreviados
            meses_abreviados = {
                1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr',
                5: 'Mai', 6: 'Jun', 7: 'Jul', 8: 'Ago',
                9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
            }
            
            # Dicionário para coletar datas disponíveis
            datas_dict = {}
            
            # Estatísticas
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
                        id_pedido = p[0]
                        consulta_id = p[1]
                        pedido_medico_id = p[2]
                        paciente_id = p[3]
                        analista_id = p[4]
                        tipo_exame = p[5] or 'Não especificado'
                        descricao = p[6] or ''
                        observacoes = p[7] or ''
                        urgencia = p[8] or 'normal'
                        status = p[9] or 'pendente'
                        data_solicitacao = p[10]
                        data_conclusao = p[11]
                        resultado_analise = p[12] or ''
                        diagnostico_analista = p[13] or ''
                        recomendacoes_analista = p[14] or ''
                        anexos_json = p[15]
                        status_aprovacao = p[16] or 'pendente'
                        observacoes_medico = p[17] or ''
                        criado_em = p[18]
                        atualizado_em = p[19]
                        
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
                                
                                # Contagens por mês
                                if mes_pedido in meses_contagem:
                                    meses_contagem[mes_pedido] += 1
                                
                                # Coletar datas para o filtro
                                if data_iso not in datas_dict:
                                    datas_dict[data_iso] = {
                                        'data_iso': data_iso,
                                        'data_br': data_br,
                                        'total': 0
                                    }
                                datas_dict[data_iso]['total'] += 1
                                
                                # Estatísticas
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
                        
                        paciente_nome = f"Paciente {paciente_id}"
                        if paciente_id:
                            paciente_info = execute_query(
                                "SELECT u.nome FROM pacientes p JOIN usuarios u ON p.usuario_id = u.id WHERE p.id = %s",
                                (paciente_id,), fetch=True, one=True
                            )
                            if paciente_info:
                                paciente_nome = converter_bytes_para_string(paciente_info[0])
                        
                        medico_nome = f"Médico {pedido_medico_id}"
                        if pedido_medico_id:
                            medico_info_db = execute_query(
                                "SELECT u.nome FROM medicos m JOIN usuarios u ON m.usuario_id = u.id WHERE m.id = %s",
                                (pedido_medico_id,), fetch=True, one=True
                            )
                            if medico_info_db:
                                medico_nome = converter_bytes_para_string(medico_info_db[0])
                        
                        analista_nome = "Não atribuído"
                        if analista_id and analista_id != 0:
                            analista_info = execute_query(
                                "SELECT u.nome FROM analistas a JOIN usuarios u ON a.usuario_id = u.id WHERE a.id = %s",
                                (analista_id,), fetch=True, one=True
                            )
                            if analista_info:
                                analista_nome = converter_bytes_para_string(analista_info[0])
                        
                        pedidos_formatados.append({
                            'id': id_pedido,
                            'consulta_id': consulta_id,
                            'medico_id': pedido_medico_id,
                            'paciente_id': paciente_id,
                            'analista_id': analista_id,
                            'tipo_exame': tipo_exame,
                            'descricao': descricao,
                            'observacoes': observacoes,
                            'urgencia': urgencia,
                            'status': status,
                            'data_solicitacao': data_solicitacao_fmt,
                            'data_conclusao': data_conclusao_fmt,
                            'resultado_analise': resultado_analise,
                            'diagnostico_analista': diagnostico_analista,
                            'recomendacoes_analista': recomendacoes_analista,
                            'anexos': anexos,
                            'status_aprovacao': status_aprovacao,
                            'observacoes_medico': observacoes_medico,
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
            
            # Ordenar datas e pegar as mais recentes (últimas 7)
            datas_disponiveis = sorted(datas_dict.values(), key=lambda x: x['data_iso'], reverse=True)[:7]
            
            # Buscar anos disponíveis
            anos_raw = execute_query("""
                SELECT DISTINCT YEAR(data_solicitacao) as ano
                FROM pedidos_analise
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
            medico_info = obter_info_medico()
            if not medico_info:
                flash('Médico não encontrado.', 'danger')
                return redirect(url_for('auth.login'))
            
            medico_id = medico_info.get('id')
            
            # Buscar consultas do médico para selecionar
            consultas = execute_query("""
                SELECT c.id, u.nome, c.data_hora, c.paciente_id
                FROM consultas c
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE c.medico_id = %s AND c.status IN ('agendada', 'confirmada', 'realizada')
                ORDER BY c.data_hora DESC
            """, (medico_id,), fetch=True) or []
            
            consultas_lista = []
            for c in consultas:
                paciente_nome = converter_bytes_para_string(c[1])
                consultas_lista.append({
                    'id': c[0],
                    'paciente_nome': paciente_nome,
                    'data_hora': formatar_data(c[2]),
                    'paciente_id': c[3]
                })
            
            # Tipos de exame comuns
            tipos_exame = [
                'Hemograma Completo',
                'Glicemia em Jejum',
                'Colesterol Total e Frações',
                'Triglicerídeos',
                'Urina Tipo 1',
                'Urocultura',
                'Parcial de Urina',
                'Fezes (Parasitológico)',
                'TSH',
                'T4 Livre',
                'PCR',
                'VHS',
                'Raio-X',
                'Ultrassonografia',
                'Tomografia',
                'Ressonância',
                'Biópsia',
                'Eletrocardiograma',
                'Ecocardiograma',
                'Teste Ergométrico'
            ]
            
            return render_template('medico/nova_analise.html',
                                 consultas=consultas_lista,
                                 tipos_exame=tipos_exame,
                                 user=session,
                                 medico=medico_info)
            
        except Exception as e:
            logger.error(f"Erro ao carregar formulário: {e}")
            logger.error(traceback.format_exc())
            flash(f'Erro ao carregar formulário: {str(e)}', 'danger')
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
                    resultado.append({
                        'id': p[0],
                        'medico_id': p[1],
                        'tipo_exame': p[2],
                        'status': p[3],
                        'data_solicitacao': str(p[4]) if p[4] else ''
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
            
            paciente_id = paciente[0]
            
            analista = execute_query("SELECT id FROM analistas WHERE status = 'ativo' LIMIT 1", fetch=True, one=True)
            analista_id = analista[0] if analista else None
            
            result = execute_query("""
                INSERT INTO pedidos_analise 
                (medico_id, paciente_id, analista_id, tipo_exame, descricao, urgencia, status, data_solicitacao, status_aprovacao, criado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s, NOW())
            """, (
                medico_id, 
                paciente_id, 
                analista_id,
                'Pedido de Teste', 
                f'Pedido criado automaticamente para teste pelo médico ID {medico_id}', 
                'normal', 
                'pendente', 
                'pendente'
            ))
            
            if result:
                flash('✅ Pedido criado para você com sucesso!', 'success')
            else:
                flash('❌ Erro ao criar pedido', 'danger')
            
            return redirect(url_for('medico.pedidos_analise'))
            
        except Exception as e:
            logger.error(f"Erro ao criar pedido: {e}")
            logger.error(traceback.format_exc())
            flash(f'Erro: {str(e)}', 'danger')
            return redirect(url_for('medico.pedidos_analise'))
    
    # ========== ROTA: DETALHES DO PEDIDO (COM SINTOMAS E SINAIS VITAIS) ==========
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
            
            logger.info(f"Médico logado: ID={medico_info.get('id')}, Nome={medico_info.get('nome')}")
            
            medico_id = medico_info.get('id')
            
            # Buscar pedido
            logger.info(f"Buscando pedido #{pedido_id} no banco de dados...")
            
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
                logger.error(f"Pedido #{pedido_id} não encontrado no banco de dados")
                flash('Pedido não encontrado.', 'danger')
                return redirect(url_for('medico.pedidos_analise'))
            
            logger.info(f"Pedido encontrado: ID={pedido[0]}, Status={pedido[10]}, Consulta ID={pedido[1]}")
            
            # Processar anexos
            anexos = []
            if pedido[16] and isinstance(pedido[16], str):
                try:
                    anexos = json.loads(pedido[16])
                    logger.info(f"Anexos processados: {len(anexos)} arquivos")
                except Exception as e:
                    logger.error(f"Erro ao processar anexos: {e}")
                    anexos = []
            
            # Buscar receitas
            receitas_lista = []
            if pedido[1]:  # consulta_id
                logger.info(f"Buscando receitas para consulta #{pedido[1]}...")
                
                receitas = execute_query("""
                    SELECT 
                        id, 
                        diagnostico, 
                        prescricao, 
                        recomendacoes, 
                        status, 
                        created_at,
                        receita_pdf_path, 
                        pdf_gerado
                    FROM receita 
                    WHERE consulta_id = %s
                    ORDER BY created_at DESC
                """, (pedido[1],), fetch=True)
                
                if receitas:
                    logger.info(f"Encontradas {len(receitas)} receitas")
                    for r in receitas:
                        receitas_lista.append({
                            'id': r[0],
                            'diagnostico': r[1] or '',
                            'prescricao': r[2] or '',
                            'recomendacoes': r[3] or '',
                            'status': r[4] or '',
                            'created_at': formatar_data(r[5]),
                            'receita_pdf_path': r[6] or '',
                            'pdf_gerado': bool(r[7])
                        })
                else:
                    logger.info("Nenhuma receita encontrada para esta consulta")
            
            # ===== BUSCAR SINTOMAS DA CONSULTA =====
            sintomas_lista = []
            if pedido[1]:  # consulta_id
                logger.info(f"Buscando sintomas para consulta #{pedido[1]}...")
                sintomas_data = execute_query("""
                    SELECT sintomas FROM consultas WHERE id = %s
                """, (pedido[1],), fetch=True, one=True)
                
                if sintomas_data and sintomas_data[0]:
                    sintomas_raw = converter_bytes_para_string(sintomas_data[0])
                    sintomas_lista = [s.strip() for s in sintomas_raw.split(',') if s.strip()]
                    logger.info(f"Encontrados {len(sintomas_lista)} sintomas")
            
            # ===== BUSCAR SINAIS VITAIS DA CONSULTA =====
            sinais_vitais_dict = None
            if pedido[1]:  # consulta_id
                logger.info(f"Buscando sinais vitais para consulta #{pedido[1]}...")
                sinais_vitais = execute_query("""
                    SELECT 
                        id,
                        pressao_arterial,
                        frequencia_cardiaca,
                        frequencia_respiratoria,
                        temperatura,
                        saturacao_oxigenio,
                        glicemia,
                        data_afericao,
                        observacoes
                    FROM sinais_vitais 
                    WHERE consulta_id = %s
                    ORDER BY data_afericao DESC
                    LIMIT 1
                """, (pedido[1],), fetch=True, one=True)
                
                if sinais_vitais:
                    logger.info(f"Sinais vitais encontrados para consulta #{pedido[1]}")
                    
                    # Função para classificar os sinais vitais
                    def classificar_sinais_vitais(sv):
                        classificacoes = {}
                        
                        # Classificar Pressão Arterial
                        if sv[1]:  # pressao_arterial
                            try:
                                # Formato esperado: "120/80"
                                pa_parts = sv[1].split('/')
                                if len(pa_parts) == 2:
                                    sistolica = int(pa_parts[0].strip())
                                    diastolica = int(pa_parts[1].strip())
                                    
                                    if sistolica < 90 or diastolica < 60:
                                        classificacoes['pa'] = {'classificacao': 'Baixa', 'status': 'warning'}
                                    elif sistolica > 140 or diastolica > 90:
                                        classificacoes['pa'] = {'classificacao': 'Elevada', 'status': 'danger'}
                                    else:
                                        classificacoes['pa'] = {'classificacao': 'Normal', 'status': 'success'}
                            except:
                                classificacoes['pa'] = {'classificacao': 'Indefinido', 'status': 'secondary'}
                        
                        # Classificar Frequência Cardíaca (bpm)
                        if sv[2]:  # frequencia_cardiaca
                            fc = sv[2]
                            if fc < 60:
                                classificacoes['fc'] = {'classificacao': 'Bradicardia', 'status': 'warning'}
                            elif fc > 100:
                                classificacoes['fc'] = {'classificacao': 'Taquicardia', 'status': 'danger'}
                            else:
                                classificacoes['fc'] = {'classificacao': 'Normal', 'status': 'success'}
                        
                        # Classificar Frequência Respiratória (rpm)
                        if sv[3]:  # frequencia_respiratoria
                            fr = sv[3]
                            if fr < 12:
                                classificacoes['fr'] = {'classificacao': 'Baixa', 'status': 'warning'}
                            elif fr > 20:
                                classificacoes['fr'] = {'classificacao': 'Elevada', 'status': 'danger'}
                            else:
                                classificacoes['fr'] = {'classificacao': 'Normal', 'status': 'success'}
                        
                        # Classificar Temperatura (°C)
                        if sv[4]:  # temperatura
                            temp = float(sv[4])
                            if temp < 35.5:
                                classificacoes['temp'] = {'classificacao': 'Hipotermia', 'status': 'warning'}
                            elif temp > 37.8:
                                classificacoes['temp'] = {'classificacao': 'Febre', 'status': 'danger'}
                            else:
                                classificacoes['temp'] = {'classificacao': 'Normal', 'status': 'success'}
                        
                        # Classificar Saturação de Oxigênio (%)
                        if sv[5]:  # saturacao_oxigenio
                            spo2 = sv[5]
                            if spo2 < 90:
                                classificacoes['spo2'] = {'classificacao': 'Crítico', 'status': 'danger'}
                            elif spo2 < 95:
                                classificacoes['spo2'] = {'classificacao': 'Baixo', 'status': 'warning'}
                            else:
                                classificacoes['spo2'] = {'classificacao': 'Normal', 'status': 'success'}
                        
                        # Classificar Glicemia (mg/dL)
                        if sv[6]:  # glicemia
                            glic = sv[6]
                            if glic < 70:
                                classificacoes['glicemia'] = {'classificacao': 'Hipoglicemia', 'status': 'warning'}
                            elif glic > 126:
                                classificacoes['glicemia'] = {'classificacao': 'Hiperglicemia', 'status': 'danger'}
                            else:
                                classificacoes['glicemia'] = {'classificacao': 'Normal', 'status': 'success'}
                        
                        return classificacoes
                    
                    # Processar sinais vitais
                    sinais_vitais_dict = {
                        'id': sinais_vitais[0],
                        'pressao_arterial': sinais_vitais[1] or '---',
                        'frequencia_cardiaca': sinais_vitais[2],
                        'frequencia_respiratoria': sinais_vitais[3],
                        'temperatura': float(sinais_vitais[4]) if sinais_vitais[4] else None,
                        'saturacao_oxigenio': sinais_vitais[5],
                        'glicemia': sinais_vitais[6],
                        'data_afericao': formatar_data(sinais_vitais[7]) if sinais_vitais[7] else '',
                        'observacoes': sinais_vitais[8] or '',
                        'classificacoes': classificar_sinais_vitais(sinais_vitais)
                    }
                    logger.info(f"Sinais vitais processados: PA={sinais_vitais_dict['pressao_arterial']}, FC={sinais_vitais_dict['frequencia_cardiaca']}")
                else:
                    logger.info(f"Nenhum sinal vital encontrado para consulta #{pedido[1]}")
            
            tem_receita = len(receitas_lista) > 0
            
            pedido_medico_id = pedido[2]
            pertence_medico = (pedido_medico_id == medico_id)
            
            analista_id = pedido[4]
            esta_atribuido = (analista_id is not None and analista_id != 0)
            
            status = pedido[10]
            status_aprovacao = pedido[17]
            tem_resultado = (status == 'concluido' and status_aprovacao == 'pendente')
            
            paciente_nome = f"Paciente {pedido[3]}"
            paciente_idade = ''
            paciente_genero = ''
            
            if pedido[3]:
                paciente_info = execute_query(
                    "SELECT u.nome, p.data_nascimento, p.genero FROM pacientes p JOIN usuarios u ON p.usuario_id = u.id WHERE p.id = %s",
                    (pedido[3],), fetch=True, one=True
                )
                if paciente_info:
                    paciente_nome = converter_bytes_para_string(paciente_info[0])
                    if paciente_info[1]:
                        idade = calcular_idade(paciente_info[1])
                        paciente_idade = idade if idade else ''
                    paciente_genero = paciente_info[2] or ''
            
            medico_nome = f"Médico {pedido_medico_id}"
            if pedido_medico_id:
                medico_info_db = execute_query(
                    "SELECT u.nome FROM medicos m JOIN usuarios u ON m.usuario_id = u.id WHERE m.id = %s",
                    (pedido_medico_id,), fetch=True, one=True
                )
                if medico_info_db:
                    medico_nome = converter_bytes_para_string(medico_info_db[0])
            
            analista_nome = "Não atribuído"
            analista_especialidade = ''
            if analista_id and analista_id != 0:
                analista_info = execute_query(
                    "SELECT u.nome, a.especialidade FROM analistas a JOIN usuarios u ON a.usuario_id = u.id WHERE a.id = %s",
                    (analista_id,), fetch=True, one=True
                )
                if analista_info:
                    analista_nome = converter_bytes_para_string(analista_info[0])
                    analista_especialidade = analista_info[1] or ''
            
            pedido_dict = {
                'id': pedido[0],
                'consulta_id': pedido[1],
                'medico_id': pedido_medico_id,
                'paciente_id': pedido[3],
                'analista_id': analista_id,
                'tipo_exame': pedido[5] or 'Não especificado',
                'descricao': pedido[6] or '',
                'instrucoes': pedido[7] or '',
                'observacoes': pedido[8] or '',
                'urgencia': pedido[9] or 'normal',
                'status': status,
                'data_solicitacao': formatar_data(pedido[11]) if pedido[11] else '',
                'data_conclusao': formatar_data(pedido[12]) if pedido[12] else '',
                'resultado_analise': pedido[13] or '',
                'diagnostico_analista': pedido[14] or '',
                'recomendacoes_analista': pedido[15] or '',
                'anexos': anexos,
                'status_aprovacao': status_aprovacao,
                'observacoes_medico': pedido[18] or '',
                'criado_em': formatar_data(pedido[19]) if pedido[19] else '',
                'atualizado_em': formatar_data(pedido[20]) if pedido[20] else '',
                'paciente_nome': paciente_nome,
                'paciente_idade': paciente_idade,
                'paciente_genero': paciente_genero,
                'analista_nome': analista_nome,
                'analista_especialidade': analista_especialidade,
                'medico_nome': medico_nome,
                'tem_receita': tem_receita,
                'tem_resultado': tem_resultado,
                'pertence_medico': pertence_medico,
                'esta_atribuido': esta_atribuido,
                'total_anexos': len(anexos),
                'sintomas_lista': sintomas_lista
            }
            
            logger.info(f"Renderizando template com {len(receitas_lista)} receitas, {len(sintomas_lista)} sintomas e sinais vitais")
            
            return render_template('medico/detalhes_pedido.html',
                                 pedido=pedido_dict,
                                 receitas=receitas_lista,
                                 sinais_vitais=sinais_vitais_dict,
                                 gemini_available=gemini_available,
                                 user=session,
                                 medico=medico_info)
            
        except Exception as e:
            logger.error(f"Erro ao carregar detalhes: {e}")
            logger.error(traceback.format_exc())
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
                SELECT 
                    pa.id, 
                    pa.tipo_exame, 
                    pa.descricao, 
                    pa.resultado_analise,
                    pa.diagnostico_analista, 
                    pa.recomendacoes_analista,
                    pa.status_aprovacao, 
                    pa.observacoes_medico,
                    pa.paciente_id
                FROM pedidos_analise pa
                WHERE pa.id = %s AND pa.medico_id = %s
            """, (pedido_id, medico_id), fetch=True, one=True)
            
            if not pedido:
                flash('Pedido não encontrado.', 'danger')
                return redirect(url_for('medico.pedidos_analise'))
            
            if pedido[6] != 'pendente':
                flash('Este pedido já foi revisado.', 'warning')
                return redirect(url_for('medico.ver_detalhes_pedido', pedido_id=pedido_id))
            
            paciente_nome = f"Paciente {pedido[8]}"
            if pedido[8]:
                paciente_info = execute_query(
                    "SELECT u.nome FROM pacientes p JOIN usuarios u ON p.usuario_id = u.id WHERE p.id = %s",
                    (pedido[8],), fetch=True, one=True
                )
                if paciente_info:
                    paciente_nome = converter_bytes_para_string(paciente_info[0])
            
            pedido_dict = {
                'id': pedido[0],
                'tipo_exame': pedido[1] or 'Não especificado',
                'descricao': pedido[2] or '',
                'resultado_analise': pedido[3] or '',
                'diagnostico_analista': pedido[4] or '',
                'recomendacoes_analista': pedido[5] or '',
                'status_aprovacao': pedido[6] or 'pendente',
                'observacoes_medico': pedido[7] or '',
                'paciente_nome': paciente_nome
            }
            
            return render_template('medico/revisar_analise.html',
                                 pedido=pedido_dict,
                                 user=session,
                                 medico=medico_info)
            
        except Exception as e:
            logger.error(f"Erro ao carregar revisão: {e}")
            logger.error(traceback.format_exc())
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
            
            analista = execute_query("""
                SELECT id FROM analistas 
                WHERE status = 'ativo' 
                ORDER BY RAND() LIMIT 1
            """, fetch=True, one=True)
            
            analista_id = analista[0] if analista else None
            
            if analista_id:
                execute_query("""
                    UPDATE pedidos_analise 
                    SET analista_id = %s, status = 'em_analise', atualizado_em = NOW()
                    WHERE id = %s
                """, (analista_id, pedido[0]))
                
                flash(f'Pedido #{pedido[0]} atribuído ao analista ID {analista_id}!', 'success')
            else:
                flash('Nenhum analista disponível no momento.', 'warning')
            
            return redirect(url_for('medico.ver_detalhes_pedido', pedido_id=pedido[0]))
            
        except Exception as e:
            logger.error(f"Erro ao atribuir pedido: {e}")
            logger.error(traceback.format_exc())
            flash(f'Erro ao atribuir pedido: {str(e)}', 'danger')
            return redirect(url_for('medico.pedidos_analise'))
    
    # ========== ROTA: DETALHES DA CONSULTA PARA ANÁLISE ==========
    @medico_required
    def analise(consulta_id):
        """Redireciona para os detalhes da consulta"""
        return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id))
    
    # ========== ROTA: NOVA ANÁLISE COMPLETA (REDIRECIONAMENTO) ==========
    @medico_required
    def nova_analise_completa():
        """Redireciona para o formulário de nova análise"""
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