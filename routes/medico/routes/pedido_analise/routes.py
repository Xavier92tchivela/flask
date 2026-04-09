# routes/pedido_analise/routes.py - COMPLETO
from flask import render_template, request, jsonify, redirect, url_for, flash, session
from datetime import datetime, timedelta
import json
import logging
import traceback

from .decorators import medico_required
from .utils import (
    execute_query, formatar_data, calcular_idade, buscar_sinais_vitais,
    processar_anexos, init_utils, get_medico_id
)

logger = logging.getLogger(__name__)

def register_routes(bp, mysql, app):
    """Registra todas as rotas do blueprint"""
    
    # Inicializar utilitários
    init_utils(app)
    
    # ==============================
    # ROTA: NOVO PEDIDO DE ANÁLISE
    # ==============================
    @bp.route('/novo')
    @medico_required
    def novo_pedido():
        """Página para criar novo pedido de análise"""
        try:
            user_id = session['user_id']
            medico_id = get_medico_id(mysql, user_id)
            
            if not medico_id:
                flash('Médico não encontrado.', 'danger')
                return redirect(url_for('medico.dashboard'))
            
            # Buscar consultas recentes COM SINAIS VITAIS
            consultas = execute_query(mysql, """
                SELECT 
                    c.id,
                    c.data_hora,
                    c.status,
                    u.nome as paciente_nome,
                    p.data_nascimento,
                    p.genero,
                    p.id as paciente_id,
                    c.observacoes,
                    (SELECT COUNT(*) FROM sinais_vitais sv WHERE sv.consulta_id = c.id) as tem_sinais
                FROM consultas c
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE c.medico_id = %s 
                AND c.status IN ('realizada', 'agendada')
                ORDER BY c.data_hora DESC
                LIMIT 15
            """, (medico_id,), fetch=True)
            
            # BUSCAR ANALISTAS
            analistas = execute_query(mysql, """
                SELECT 
                    a.id,
                    COALESCE(u.nome, CONCAT('Analista ', a.id)) as nome,
                    COALESCE(a.especialidade, 'Geral') as especialidade,
                    COALESCE(a.registro_profissional, '') as registro,
                    a.status,
                    COALESCE(a.telefone, '') as telefone,
                    COALESCE(a.is_supervisor, 0) as is_supervisor,
                    a.carga_horaria_semanal,
                    a.data_contratacao,
                    (SELECT COUNT(*) 
                     FROM pedidos_analise pa 
                     WHERE pa.analista_id = a.id 
                     AND pa.status IN ('pendente', 'em_analise')) as pedidos_ativos
                FROM analistas a
                LEFT JOIN usuarios u ON a.usuario_id = u.id
                WHERE a.status = 'ativo'
                ORDER BY nome
            """, fetch=True)
            
            print(f"[DEBUG] Analistas encontrados: {len(analistas) if analistas else 0}")
            
            # Tipos de exame
            tipos_exame = [
                'Biópsia', 'Exame de Sangue Completo', 'Hemograma', 'Glicemia',
                'Colesterol Total', 'Triglicerídeos', 'Urina Tipo 1', 'Urocultura',
                'Coprocultura', 'Parasitológico', 'Radiografia', 'Ultrassonografia',
                'Tomografia Computadorizada', 'Ressonância Magnética', 'Eletrocardiograma',
                'Endoscopia', 'Colonoscopia', 'Citologia', 'Histopatologia',
                'Imunohistoquímica', 'Biópsia de Pele', 'Biópsia de Mama',
                'Papanicolau', 'Exame Microbiológico', 'Teste Genético',
                'Marcador Tumoral', 'Outro'
            ]
            
            # Preparar consultas
            consultas_list = []
            if consultas:
                for c in consultas:
                    idade = calcular_idade(c[4]) if c[4] else None
                    consultas_list.append({
                        'id': c[0],
                        'data_hora': formatar_data(c[1]),
                        'status': c[2],
                        'paciente_nome': c[3] or 'Paciente',
                        'data_nascimento': formatar_data(c[4], '%d/%m/%Y') if c[4] else '',
                        'idade': idade,
                        'genero': c[5],
                        'paciente_id': c[6],
                        'observacoes': c[7] or '',
                        'tem_sinais': c[8] if len(c) > 8 else 0
                    })
            
            # Consulta pré-selecionada
            consulta_id_param = request.args.get('consulta_id')
            consulta_selecionada = None
            sinais_consulta = None
            
            if consulta_id_param and consulta_id_param.isdigit():
                consulta_id_int = int(consulta_id_param)
                for consulta in consultas_list:
                    if consulta['id'] == consulta_id_int:
                        consulta_selecionada = consulta
                        # Buscar sinais vitais da consulta selecionada
                        sinais_consulta = buscar_sinais_vitais(mysql, consulta_id_int)
                        break
            
            return render_template('medico/novo_pedido_analise.html',
                                  consultas=consultas_list,
                                  analistas=analistas,
                                  tipos_exame=tipos_exame,
                                  consulta_selecionada=consulta_selecionada,
                                  sinais_consulta=sinais_consulta,
                                  formatar_data=formatar_data,
                                  calcular_idade=calcular_idade,
                                  now=datetime.now(),
                                  user=session)
            
        except Exception as e:
            logger.error(f"Erro ao carregar novo pedido: {e}")
            logger.error(traceback.format_exc())
            flash('Erro ao carregar dados.', 'danger')
            return redirect(url_for('medico.dashboard'))
    
    # ==============================
    # ROTA: CRIAR PEDIDO (PRINCIPAL)
    # ==============================
    @bp.route('/criar', methods=['POST'])
    @medico_required
    def criar_pedido():
        """Criar um novo pedido de análise"""
        try:
            user_id = session['user_id']
            
            # Obter dados do formulário
            paciente_id = request.form.get('paciente_id')
            consulta_id = request.form.get('consulta_id') or None
            tipo_exame = request.form.get('tipo_exame')
            descricao = request.form.get('descricao')
            observacoes = request.form.get('observacoes', '')
            urgencia = request.form.get('urgencia', 'normal')
            analista_id = request.form.get('analista_id') or None
            incluir_sinais = request.form.get('incluir_sinais') == '1'
            
            # Se tipo_exame for "outro", usar o campo outro_exame
            outro_exame = request.form.get('outro_exame', '')
            if tipo_exame == 'outro' and outro_exame:
                tipo_exame = outro_exame
            
            # Validações
            if not paciente_id or not tipo_exame or not descricao.strip():
                flash('Preencha todos os campos obrigatórios.', 'danger')
                return redirect(url_for('pedido_analise.novo_pedido'))
            
            # Obter ID do médico
            medico_id = get_medico_id(mysql, user_id)
            
            if not medico_id:
                flash('Médico não encontrado.', 'danger')
                return redirect(url_for('medico.dashboard'))
            
            # Buscar sinais vitais se solicitado
            observacoes_adicionais = observacoes
            if incluir_sinais and consulta_id:
                sinais = buscar_sinais_vitais(mysql, int(consulta_id))
                if sinais:
                    # Adicionar sinais vitais às observações
                    sinais_texto = f"""
SINAIS VITAIS DO PACIENTE:
• Pressão Arterial: {sinais.get('pressao_arterial', 'N/I')} ({sinais.get('pa_classificacao', 'N/I')})
• Frequência Cardíaca: {sinais.get('frequencia_cardiaca', 'N/I')} bpm ({sinais.get('fc_classificacao', 'N/I')})
• Frequência Respiratória: {sinais.get('frequencia_respiratoria', 'N/I')} rpm ({sinais.get('fr_classificacao', 'N/I')})
• Temperatura: {sinais.get('temperatura', 'N/I')} °C ({sinais.get('temp_classificacao', 'N/I')})
• Saturação O2: {sinais.get('saturacao_oxigenio', 'N/I')}% ({sinais.get('spo2_classificacao', 'N/I')})
• Glicemia: {sinais.get('glicemia', 'N/I')} mg/dL ({sinais.get('glicemia_classificacao', 'N/I')})
• Peso: {sinais.get('peso', 'N/I')} kg
Data da aferição: {sinais.get('data_afericao', 'N/I')}
"""
                    if sinais.get('observacoes'):
                        sinais_texto += f"Obs. dos sinais: {sinais.get('observacoes')}\n"
                    
                    observacoes_adicionais = observacoes + "\n\n" + sinais_texto
                    logger.info(f"Sinais vitais incluídos no pedido #{consulta_id}")
            
            # Processar analista
            analista_atribuido = None
            
            if analista_id and analista_id != 'auto':
                analista_check = execute_query(mysql,
                    "SELECT id FROM analistas WHERE id = %s AND status = 'ativo'",
                    (analista_id,), fetch=True, one=True
                )
                if analista_check:
                    analista_atribuido = analista_check[0]
            
            if not analista_atribuido:
                # Atribuição automática - escolher o analista com menos pedidos ativos
                analista_auto = execute_query(mysql, """
                    SELECT 
                        a.id,
                        (SELECT COUNT(*) 
                         FROM pedidos_analise pa 
                         WHERE pa.analista_id = a.id 
                         AND pa.status IN ('pendente', 'em_analise')) as pedidos_ativos
                    FROM analistas a
                    WHERE a.status = 'ativo'
                    ORDER BY pedidos_ativos, a.id
                    LIMIT 1
                """, fetch=True, one=True)
                
                if analista_auto:
                    analista_atribuido = analista_auto[0]
                    print(f"[DEBUG] Analista atribuído automaticamente: ID {analista_atribuido}")
                else:
                    flash('Nenhum analista disponível no momento.', 'warning')
            
            # Processar anexos
            anexos_json = processar_anexos(request)
            
            # INSEÇÃO - conforme estrutura da tabela pedidos_analise
            pedido_id = execute_query(mysql, """
                INSERT INTO pedidos_analise 
                (consulta_id, medico_id, paciente_id, analista_id, tipo_exame, 
                 descricao, observacoes, urgencia, status, data_solicitacao,
                 status_aprovacao, anexos, criado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pendente', NOW(), 
                        'pendente', %s, NOW())
            """, (
                consulta_id, medico_id, paciente_id, analista_atribuido, tipo_exame,
                descricao.strip(), 
                observacoes_adicionais.strip() if observacoes_adicionais else None,
                urgencia,
                anexos_json
            ), commit=True)
            
            if pedido_id:
                # Registrar log
                execute_query(mysql, """
                    INSERT INTO logs 
                    (usuario_id, acao, tabela_afetada, registro_id, detalhes, data_registro)
                    VALUES (%s, 'criar', 'pedidos_analise', %s, %s, NOW())
                """, (
                    user_id,
                    pedido_id,
                    json.dumps({
                        'tipo_exame': tipo_exame,
                        'urgencia': urgencia,
                        'paciente_id': paciente_id,
                        'analista_id': analista_atribuido,
                        'incluiu_sinais': incluir_sinais
                    })
                ), commit=True)
                
                flash('Pedido de análise criado com sucesso!', 'success')
                print(f"[SUCCESS] Pedido criado: ID {pedido_id}")
                return redirect(url_for('pedido_analise.meus_pedidos'))
            else:
                flash('Erro ao salvar pedido no banco de dados.', 'danger')
                return redirect(url_for('pedido_analise.novo_pedido'))
            
        except Exception as e:
            logger.error(f"Erro ao criar pedido: {e}")
            logger.error(traceback.format_exc())
            flash('Erro interno ao processar pedido.', 'danger')
            return redirect(url_for('pedido_analise.novo_pedido'))
    
    # ==============================
    # ROTA: MEUS PEDIDOS - VERSÃO CORRIGIDA
    # ==============================
    @bp.route('/meus-pedidos')
    @medico_required
    def meus_pedidos():
        """Lista todos os pedidos do médico"""
        try:
            user_id = session['user_id']
            medico_id = get_medico_id(mysql, user_id)
            
            if not medico_id:
                flash('Médico não encontrado.', 'danger')
                return redirect(url_for('medico.dashboard'))
            
            # Filtros
            status_filter = request.args.get('status', '')
            urgencia_filter = request.args.get('urgencia', '')
            
            # Construir query base
            query = """
                SELECT 
                    pa.id,
                    pa.tipo_exame,
                    pa.status,
                    pa.urgencia,
                    pa.data_solicitacao,
                    pa.data_conclusao,
                    up.nome as paciente_nome,
                    COALESCE(
                        (SELECT ua.nome FROM usuarios ua 
                         JOIN analistas a ON ua.id = a.usuario_id 
                         WHERE a.id = pa.analista_id),
                        'Não atribuído'
                    ) as analista_nome,
                    pa.status_aprovacao,
                    p.id as paciente_id,
                    c.id as consulta_id,
                    (SELECT COUNT(*) FROM sinais_vitais sv WHERE sv.consulta_id = c.id) as tem_sinais
                FROM pedidos_analise pa
                JOIN pacientes p ON pa.paciente_id = p.id
                JOIN usuarios up ON p.usuario_id = up.id
                LEFT JOIN consultas c ON pa.consulta_id = c.id
                WHERE pa.medico_id = %s
            """
            
            params = [medico_id]
            
            # Adicionar filtros
            conditions = []
            if status_filter:
                conditions.append("pa.status = %s")
                params.append(status_filter)
            
            if urgencia_filter:
                conditions.append("pa.urgencia = %s")
                params.append(urgencia_filter)
            
            if conditions:
                query += " AND " + " AND ".join(conditions)
            
            query += " ORDER BY pa.data_solicitacao DESC LIMIT 50"
            
            # Executar query
            pedidos = execute_query(mysql, query, params, fetch=True)
            
            # Preparar dados para o template
            pedidos_list = []
            
            if pedidos:
                for p in pedidos:
                    pedidos_list.append({
                        'id': p[0],
                        'tipo_exame': p[1],
                        'status': p[2],
                        'urgencia': p[3],
                        'data_solicitacao': formatar_data(p[4]),
                        'data_conclusao': formatar_data(p[5]),
                        'paciente_nome': p[6],
                        'analista_nome': p[7],
                        'status_aprovacao': p[8],
                        'paciente_id': p[9],
                        'consulta_id': p[10] if len(p) > 10 else None,
                        'tem_sinais': p[11] if len(p) > 11 else 0
                    })
            
            # ESTATÍSTICAS COMPLETAS
            total_pedidos_result = execute_query(mysql,
                "SELECT COUNT(*) FROM pedidos_analise WHERE medico_id = %s",
                (medico_id,), fetch=True, one=True
            )
            total_pedidos = total_pedidos_result[0] if total_pedidos_result else 0
            
            pedidos_pendentes_result = execute_query(mysql,
                "SELECT COUNT(*) FROM pedidos_analise WHERE medico_id = %s AND status = 'pendente'",
                (medico_id,), fetch=True, one=True
            )
            pedidos_pendentes = pedidos_pendentes_result[0] if pedidos_pendentes_result else 0
            
            pedidos_em_analise_result = execute_query(mysql,
                "SELECT COUNT(*) FROM pedidos_analise WHERE medico_id = %s AND status = 'em_analise'",
                (medico_id,), fetch=True, one=True
            )
            pedidos_em_analise = pedidos_em_analise_result[0] if pedidos_em_analise_result else 0
            
            pedidos_concluidos_result = execute_query(mysql,
                "SELECT COUNT(*) FROM pedidos_analise WHERE medico_id = %s AND status = 'concluido'",
                (medico_id,), fetch=True, one=True
            )
            pedidos_concluidos = pedidos_concluidos_result[0] if pedidos_concluidos_result else 0
            
            pedidos_cancelados_result = execute_query(mysql,
                "SELECT COUNT(*) FROM pedidos_analise WHERE medico_id = %s AND status = 'cancelado'",
                (medico_id,), fetch=True, one=True
            )
            pedidos_cancelados = pedidos_cancelados_result[0] if pedidos_cancelados_result else 0
            
            # DEBUG
            print(f"[DEBUG MEUS PEDIDOS] Total: {total_pedidos}")
            print(f"[DEBUG MEUS PEDIDOS] Pendentes: {pedidos_pendentes}")
            print(f"[DEBUG MEUS PEDIDOS] Em análise: {pedidos_em_analise}")
            print(f"[DEBUG MEUS PEDIDOS] Concluídos: {pedidos_concluidos}")
            print(f"[DEBUG MEUS PEDIDOS] Cancelados: {pedidos_cancelados}")
            print(f"[DEBUG MEUS PEDIDOS] Pedidos na lista: {len(pedidos_list)}")
            
            return render_template('medico/meus_pedidos.html',
                                  pedidos=pedidos_list,
                                  total_pedidos=total_pedidos,
                                  pedidos_pendentes=pedidos_pendentes,
                                  pedidos_em_analise=pedidos_em_analise,
                                  pedidos_concluidos=pedidos_concluidos,
                                  pedidos_cancelados=pedidos_cancelados,
                                  now=datetime.now(),
                                  user=session)
            
        except Exception as e:
            logger.error(f"Erro ao carregar meus pedidos: {e}")
            logger.error(traceback.format_exc())
            flash('Erro ao carregar pedidos.', 'danger')
            return redirect(url_for('medico.dashboard'))
    
    # ==============================
    # ROTA: VER DETALHES DO PEDIDO
    # ==============================
    @bp.route('/pedido/<int:pedido_id>')
    @medico_required
    def ver_pedido(pedido_id):
        """Ver detalhes de um pedido específico"""
        try:
            user_id = session['user_id']
            
            # Verificar se o médico tem acesso a este pedido
            pedido_result = execute_query(mysql, """
                SELECT pa.*, m.usuario_id as medico_usuario_id
                FROM pedidos_analise pa
                JOIN medicos m ON pa.medico_id = m.id
                WHERE pa.id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido_result or pedido_result[-1] != user_id:
                flash('Pedido não encontrado ou acesso negado.', 'danger')
                return redirect(url_for('pedido_analise.meus_pedidos'))
            
            # Buscar informações completas do pedido
            pedido_info = execute_query(mysql, """
                SELECT 
                    pa.id,
                    pa.medico_id,
                    pa.paciente_id,
                    pa.consulta_id,
                    pa.analista_id,
                    pa.tipo_exame,
                    pa.urgencia,
                    pa.descricao,
                    pa.observacoes,
                    pa.observacoes_medico,
                    pa.anexos,
                    pa.status,
                    pa.status_aprovacao,
                    pa.data_solicitacao,
                    pa.data_conclusao,
                    pa.resultado_analise,
                    pa.diagnostico_analista,
                    pa.recomendacoes_analista,
                    pa.criado_em,
                    pa.atualizado_em,
                    up.nome as paciente_nome,
                    COALESCE(
                        (SELECT ua.nome FROM usuarios ua 
                         JOIN analistas a ON ua.id = a.usuario_id 
                         WHERE a.id = pa.analista_id),
                        'Não atribuído'
                    ) as analista_nome,
                    um.nome as medico_nome,
                    m.especialidade as medico_especialidade,
                    m.crm as medico_crm,
                    p.data_nascimento,
                    p.genero,
                    p.endereco,
                    p.telefone as paciente_telefone,
                    c.data_hora as consulta_data,
                    c.observacoes as consulta_observacoes
                FROM pedidos_analise pa
                JOIN pacientes p ON pa.paciente_id = p.id
                JOIN usuarios up ON p.usuario_id = up.id
                JOIN medicos m ON pa.medico_id = m.id
                JOIN usuarios um ON m.usuario_id = um.id
                LEFT JOIN consultas c ON pa.consulta_id = c.id
                WHERE pa.id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido_info:
                flash('Pedido não encontrado.', 'danger')
                return redirect(url_for('pedido_analise.meus_pedidos'))
            
            # Converter para dicionário
            pedido_dict = {
                'id': pedido_info[0],
                'medico_id': pedido_info[1],
                'paciente_id': pedido_info[2],
                'consulta_id': pedido_info[3],
                'analista_id': pedido_info[4],
                'tipo_exame': pedido_info[5],
                'urgencia': pedido_info[6],
                'descricao': pedido_info[7],
                'observacoes': pedido_info[8],
                'observacoes_medico': pedido_info[9],
                'anexos': pedido_info[10],
                'status': pedido_info[11],
                'status_aprovacao': pedido_info[12],
                'data_solicitacao': pedido_info[13],
                'data_conclusao': pedido_info[14],
                'resultado_analise': pedido_info[15],
                'diagnostico_analista': pedido_info[16],
                'recomendacoes_analista': pedido_info[17],
                'criado_em': pedido_info[18],
                'atualizado_em': pedido_info[19],
                'paciente_nome': pedido_info[20],
                'analista_nome': pedido_info[21],
                'medico_nome': pedido_info[22],
                'medico_especialidade': pedido_info[23],
                'medico_crm': pedido_info[24],
                'data_nascimento': pedido_info[25],
                'genero': pedido_info[26],
                'endereco': pedido_info[27],
                'paciente_telefone': pedido_info[28],
                'consulta_data': pedido_info[29],
                'consulta_observacoes': pedido_info[30]
            }
            
            # Calcular idade do paciente
            if pedido_dict.get('data_nascimento'):
                pedido_dict['idade'] = calcular_idade(pedido_dict['data_nascimento'])
            
            # Processar anexos
            anexos_list = []
            if pedido_dict.get('anexos'):
                try:
                    anexos_list = json.loads(pedido_dict['anexos'])
                except:
                    anexos_list = []
            
            # Buscar sinais vitais da consulta
            sinais_vitais = None
            if pedido_dict.get('consulta_id'):
                sinais_vitais = buscar_sinais_vitais(mysql, pedido_dict['consulta_id'])
            
            return render_template('medico/ver_pedido.html',
                                  pedido=pedido_dict,
                                  anexos=anexos_list,
                                  sinais_vitais=sinais_vitais,
                                  formatar_data=formatar_data,
                                  now=datetime.now(),
                                  user=session)
            
        except Exception as e:
            logger.error(f"Erro ao ver pedido: {e}")
            logger.error(traceback.format_exc())
            flash('Erro ao carregar pedido.', 'danger')
            return redirect(url_for('pedido_analise.meus_pedidos'))
    
    # ==============================
    # ROTA: CANCELAR PEDIDO
    # ==============================
    @bp.route('/cancelar/<int:pedido_id>', methods=['POST'])
    @medico_required
    def cancelar_pedido(pedido_id):
        """Cancelar um pedido de análise"""
        try:
            user_id = session['user_id']
            
            # Verificar se o médico tem acesso
            pedido_check = execute_query(mysql, """
                SELECT pa.id, pa.status, m.usuario_id
                FROM pedidos_analise pa
                JOIN medicos m ON pa.medico_id = m.id
                WHERE pa.id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido_check or pedido_check[2] != user_id:
                flash('Pedido não encontrado ou acesso negado.', 'danger')
                return redirect(url_for('pedido_analise.meus_pedidos'))
            
            # Verificar se pode ser cancelado
            if pedido_check[1] not in ['pendente', 'em_analise']:
                flash('Este pedido não pode ser cancelado no seu estado atual.', 'warning')
                return redirect(url_for('pedido_analise.ver_pedido', pedido_id=pedido_id))
            
            # Atualizar status
            result = execute_query(mysql, """
                UPDATE pedidos_analise 
                SET status = 'cancelado', atualizado_em = NOW()
                WHERE id = %s
            """, (pedido_id,), commit=True)
            
            if result is not None:
                # Registrar log
                execute_query(mysql, """
                    INSERT INTO logs 
                    (usuario_id, acao, tabela_afetada, registro_id, detalhes, data_registro)
                    VALUES (%s, 'cancelar', 'pedidos_analise', %s, %s, NOW())
                """, (
                    user_id,
                    pedido_id,
                    json.dumps({'status_anterior': pedido_check[1]})
                ), commit=True)
                
                flash('Pedido cancelado com sucesso!', 'success')
            else:
                flash('Erro ao cancelar pedido.', 'danger')
            
            return redirect(url_for('pedido_analise.meus_pedidos'))
            
        except Exception as e:
            logger.error(f"Erro ao cancelar pedido: {e}")
            flash('Erro ao cancelar pedido.', 'danger')
            return redirect(url_for('pedido_analise.ver_pedido', pedido_id=pedido_id))
    
    # ==============================
    # ROTA: DEBUG ANALISTAS
    # ==============================
    @bp.route('/debug-analistas')
    @medico_required
    def debug_analistas():
        """Debug: verificar analistas"""
        try:
            # Query idêntica à que você testou
            analistas = execute_query(mysql, """
                SELECT 
                    a.id,
                    u.nome,
                    a.especialidade,
                    a.registro_profissional,
                    a.status,
                    a.carga_horaria_semanal,
                    a.is_supervisor,
                    a.telefone,
                    a.data_contratacao,
                    (SELECT COUNT(*) 
                     FROM pedidos_analise pa 
                     WHERE pa.analista_id = a.id 
                     AND pa.status IN ('pendente', 'em_analise')) as pedidos_ativos
                FROM analistas a
                LEFT JOIN usuarios u ON a.usuario_id = u.id
                WHERE a.status = 'ativo'
                ORDER BY u.nome
            """, fetch=True)
            
            return render_template('debug_analistas.html',
                                  analistas=analistas,
                                  total=len(analistas) if analistas else 0,
                                  user=session)
            
        except Exception as e:
            return f"Erro: {str(e)}"
    
    # ==============================
    # ROTA: API ESTATÍSTICAS
    # ==============================
    @bp.route('/api/estatisticas')
    @medico_required
    def api_estatisticas():
        """API para estatísticas dos pedidos"""
        try:
            user_id = session['user_id']
            
            medico_result = execute_query(mysql,
                "SELECT id FROM medicos WHERE usuario_id = %s",
                (user_id,), fetch=True, one=True
            )
            
            if not medico_result:
                return jsonify({'error': 'Médico não encontrado'}), 404
            
            medico_id = medico_result[0]
            
            # Estatísticas gerais
            estatisticas = execute_query(mysql, """
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'pendente' THEN 1 ELSE 0 END) as pendentes,
                    SUM(CASE WHEN status = 'em_analise' THEN 1 ELSE 0 END) as em_analise,
                    SUM(CASE WHEN status = 'concluido' THEN 1 ELSE 0 END) as concluidos,
                    SUM(CASE WHEN status = 'cancelado' THEN 1 ELSE 0 END) as cancelados
                FROM pedidos_analise 
                WHERE medico_id = %s
            """, (medico_id,), fetch=True, one=True)
            
            # Pedidos por urgência
            por_urgencia = execute_query(mysql, """
                SELECT 
                    urgencia,
                    COUNT(*) as quantidade
                FROM pedidos_analise 
                WHERE medico_id = %s
                GROUP BY urgencia
            """, (medico_id,), fetch=True)
            
            urgencia_dict = {}
            if por_urgencia:
                for urgencia, quantidade in por_urgencia:
                    urgencia_dict[urgencia] = quantidade
            
            return jsonify({
                'total': estatisticas[0] or 0,
                'pendentes': estatisticas[1] or 0,
                'em_analise': estatisticas[2] or 0,
                'concluidos': estatisticas[3] or 0,
                'cancelados': estatisticas[4] or 0,
                'por_urgencia': urgencia_dict
            })
            
        except Exception as e:
            logger.error(f"Erro na API estatísticas: {e}")
            return jsonify({'error': str(e)}), 500
    
    # ==============================
    # ROTA: SOLICITAR ANÁLISE (CONSULTA ESPECÍFICA)
    # ==============================
    @bp.route('/solicitar-analise/<int:consulta_id>')
    @medico_required
    def solicitar_analise(consulta_id):
        """Página para solicitar análise de uma consulta específica"""
        try:
            user_id = session['user_id']
            
            # Obter ID do médico
            medico_id = get_medico_id(mysql, user_id)
            
            if not medico_id:
                flash('Médico não encontrado.', 'danger')
                return redirect(url_for('medico.dashboard'))
            
            # Buscar dados da consulta
            consulta = execute_query(mysql, """
                SELECT 
                    c.id,
                    c.data_hora,
                    c.status,
                    c.observacoes,
                    p.id as paciente_id,
                    u.nome as paciente_nome,
                    p.data_nascimento,
                    p.genero,
                    (SELECT COUNT(*) FROM sinais_vitais sv WHERE sv.consulta_id = c.id) as tem_sinais
                FROM consultas c
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE c.id = %s AND c.medico_id = %s
            """, (consulta_id, medico_id), fetch=True, one=True)
            
            if not consulta:
                flash('Consulta não encontrada ou não pertence a você.', 'danger')
                return redirect(url_for('medico.consultas'))
            
            # Converter para dicionário
            consulta_dict = {
                'id': consulta[0],
                'data_hora': consulta[1],
                'status': consulta[2],
                'observacoes': consulta[3],
                'paciente_id': consulta[4],
                'paciente_nome': consulta[5],
                'data_nascimento': consulta[6],
                'genero': consulta[7],
                'tem_sinais': consulta[8] if len(consulta) > 8 else 0
            }
            
            # Buscar sinais vitais da consulta
            sinais_vitais = buscar_sinais_vitais(mysql, consulta_id)
            
            # Buscar analistas
            analistas = execute_query(mysql, """
                SELECT 
                    a.id,
                    COALESCE(u.nome, CONCAT('Analista ', a.id)) as nome,
                    COALESCE(a.especialidade, 'Geral') as especialidade,
                    COALESCE(a.registro_profissional, '') as registro,
                    a.status,
                    COALESCE(a.telefone, '') as telefone,
                    COALESCE(a.is_supervisor, 0) as is_supervisor,
                    a.carga_horaria_semanal,
                    a.data_contratacao,
                    (SELECT COUNT(*) 
                     FROM pedidos_analise pa 
                     WHERE pa.analista_id = a.id 
                     AND pa.status IN ('pendente', 'em_analise')) as pedidos_ativos
                FROM analistas a
                LEFT JOIN usuarios u ON a.usuario_id = u.id
                WHERE a.status = 'ativo'
                ORDER BY nome
            """, fetch=True)
            
            # Buscar histórico de exames
            historico_exames = execute_query(mysql, """
                SELECT 
                    tipo_exame,
                    status,
                    data_solicitacao
                FROM pedidos_analise 
                WHERE paciente_id = %s
                ORDER BY data_solicitacao DESC
                LIMIT 5
            """, (consulta_dict['paciente_id'],), fetch=True)
            
            return render_template('medico/solicitar_analise.html',
                                  consulta=consulta_dict,
                                  analistas=analistas,
                                  historico_exames=historico_exames,
                                  sinais_vitais=sinais_vitais,
                                  formatar_data=formatar_data,
                                  user=session)
            
        except Exception as e:
            logger.error(f"Erro ao carregar solicitar análise: {e}")
            logger.error(traceback.format_exc())
            flash('Erro ao carregar dados da consulta.', 'danger')
            return redirect(url_for('medico.consultas'))