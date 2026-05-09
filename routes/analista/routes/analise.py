"""Rotas de análise de exames para analista"""
from flask import render_template, session, flash, redirect, url_for, request, jsonify
from datetime import datetime
import os
import base64
import traceback
import logging

logger = logging.getLogger(__name__)

def register_analise_routes(bp, analista_required, execute_query, formatar_data, calcular_idade,
                           analisar_imagem_com_gemini, salvar_imagem_temporaria, preparar_contexto_clinico,
                           criar_notificacao_medico, salvar_diagnostico_ia, gemini_available, MODEL_NAME):
    
    print("[INFO] REGISTRANDO ROTAS DE ANALISE - Gemini disponivel: {0}".format(gemini_available))
    
    # ===== FUNÇÕES AUXILIARES =====
    def garantir_string(valor):
        """Converte qualquer valor para string, especialmente bytes"""
        if valor is None:
            return ''
        if isinstance(valor, bytes):
            try:
                return valor.decode('utf-8')
            except:
                return str(valor)
        if isinstance(valor, (int, float)):
            return str(valor)
        return str(valor) if valor is not None else ''

    def criar_tabela_anexos():
        """Cria a tabela de anexos se não existir"""
        try:
            execute_query("""
                CREATE TABLE IF NOT EXISTS anexos_pedidos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    pedido_id INT NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    original_name VARCHAR(255) NOT NULL,
                    tipo VARCHAR(100),
                    size INT,
                    upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_pedido_id (pedido_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """, commit=True)
            logger.info("✅ Tabela anexos_pedidos criada/verificada com sucesso")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao criar tabela anexos_pedidos: {e}")
            return False

    # Tentar criar a tabela de anexos
    criar_tabela_anexos()
    
    @bp.route('/proximo-pedido')
    @analista_required
    def proximo_pedido():
        """Atribuir próximo pedido pendente ao analista"""
        try:
            print("[DEBUG] Acessando proximo pedido")
            user_id = session.get('user_id')
            
            analista_info = execute_query("""
                SELECT a.id FROM analistas a
                WHERE a.usuario_id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                flash('Perfil de analista não encontrado.', 'danger')
                return redirect(url_for('auth.login'))
            
            if isinstance(analista_info, dict):
                analista_id = analista_info.get('id')
            else:
                analista_id = analista_info[0] if len(analista_info) > 0 else None
            
            pedido = execute_query("""
                SELECT id FROM pedidos_analise 
                WHERE (analista_id IS NULL OR analista_id = 0)
                AND status = 'pendente'
                ORDER BY 
                    CASE urgencia 
                        WHEN 'urgente' THEN 1
                        WHEN 'alta' THEN 2
                        WHEN 'normal' THEN 3
                        ELSE 4
                    END,
                    data_solicitacao ASC
                LIMIT 1
            """, fetch=True, one=True)
            
            if not pedido:
                flash('Não há pedidos pendentes disponíveis.', 'info')
                return redirect(url_for('analista.dashboard'))
            
            pedido_id = pedido[0] if isinstance(pedido, (list, tuple)) else pedido.get('id')
            
            result = execute_query("""
                UPDATE pedidos_analise 
                SET analista_id = %s, status = 'em_analise', atualizado_em = NOW()
                WHERE id = %s
            """, (analista_id, pedido_id), commit=True)
            
            if result is not None:
                flash(f'Pedido #{pedido_id} atribuído a você!', 'success')
                return redirect(url_for('analista.analisar_pedido', pedido_id=pedido_id))
            else:
                flash('Erro ao atribuir pedido.', 'danger')
                return redirect(url_for('analista.dashboard'))
            
        except Exception as e:
            logger.error(f"[ERRO] {e}")
            flash('Erro ao buscar próximo pedido.', 'danger')
            return redirect(url_for('analista.dashboard'))

    # ========== ROTA PRINCIPAL - ANALISAR PEDIDO ==========
    @bp.route('/analisar/<int:pedido_id>', methods=['GET', 'POST'])
    @analista_required
    def analisar_pedido(pedido_id):
        """Analisar um pedido específico"""
        print(f"[DEBUG] Acessando análise do pedido #{pedido_id}")
        
        try:
            user_id = session.get('user_id')
            
            analista_info = execute_query("""
                SELECT a.id, u.nome FROM analistas a
                JOIN usuarios u ON a.usuario_id = u.id
                WHERE u.id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                flash('Perfil de analista não encontrado.', 'danger')
                return redirect(url_for('auth.login'))
            
            if isinstance(analista_info, dict):
                analista_id = analista_info.get('id')
                analista_nome = analista_info.get('nome')
            else:
                analista_id = analista_info[0] if len(analista_info) > 0 else None
                analista_nome = analista_info[1] if len(analista_info) > 1 else 'Analista'
            
            session['analista_id'] = analista_id
            session['user_name'] = garantir_string(analista_nome)
            
            pedido_info = execute_query("""
                SELECT 
                    pa.id, pa.tipo_exame, pa.descricao, pa.observacoes,
                    pa.urgencia, pa.status, pa.data_solicitacao, pa.data_conclusao,
                    pa.resultado_analise, pa.diagnostico_analista, pa.recomendacoes_analista,
                    pa.observacoes_medico,
                    u.nome as paciente_nome, p.data_nascimento, p.genero,
                    m_u.nome as medico_nome, m.especialidade as medico_especialidade,
                    m.crm as medico_crm, m.id as medico_id,
                    pa.consulta_id, c.data_hora as consulta_data, c.observacoes as consulta_observacoes,
                    p.id as paciente_id
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                LEFT JOIN medicos m ON pa.medico_id = m.id
                LEFT JOIN usuarios m_u ON m.usuario_id = m_u.id
                LEFT JOIN consultas c ON pa.consulta_id = c.id
                WHERE pa.id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido_info:
                flash(f'Pedido #{pedido_id} não encontrado.', 'danger')
                return redirect(url_for('analista.pedidos'))
            
            if isinstance(pedido_info, dict):
                pedido_status = garantir_string(pedido_info.get('status', 'pendente'))
                medico_id = pedido_info.get('medico_id')
                consulta_id = pedido_info.get('consulta_id')
                paciente_nome = pedido_info.get('paciente_nome')
                data_nascimento = pedido_info.get('data_nascimento')
                paciente_id = pedido_info.get('paciente_id')
            else:
                pedido_status = garantir_string(pedido_info[5]) if len(pedido_info) > 5 else 'pendente'
                medico_id = pedido_info[18] if len(pedido_info) > 18 else None
                consulta_id = pedido_info[19] if len(pedido_info) > 19 else None
                paciente_nome = pedido_info[12] if len(pedido_info) > 12 else None
                data_nascimento = pedido_info[13] if len(pedido_info) > 13 else None
                paciente_id = pedido_info[22] if len(pedido_info) > 22 else None
            
            print(f"[OK] Pedido #{pedido_id} encontrado - Status: {pedido_status}")
            
            idade_paciente = calcular_idade(data_nascimento) if data_nascimento else ''
            
            if isinstance(pedido_info, dict):
                pedido = {
                    'id': pedido_info.get('id'),
                    'tipo_exame': garantir_string(pedido_info.get('tipo_exame')) or 'Não especificado',
                    'descricao': garantir_string(pedido_info.get('descricao')),
                    'observacoes': garantir_string(pedido_info.get('observacoes')),
                    'urgencia': garantir_string(pedido_info.get('urgencia')) or 'normal',
                    'status': pedido_status,
                    'data_solicitacao': formatar_data(pedido_info.get('data_solicitacao')),
                    'data_conclusao': formatar_data(pedido_info.get('data_conclusao')),
                    'resultado_analise': garantir_string(pedido_info.get('resultado_analise')),
                    'diagnostico_analista': garantir_string(pedido_info.get('diagnostico_analista')),
                    'recomendacoes_analista': garantir_string(pedido_info.get('recomendacoes_analista')),
                    'observacoes_medico': garantir_string(pedido_info.get('observacoes_medico')),
                    'paciente_nome': garantir_string(paciente_nome) or 'Não informado',
                    'paciente_data_nascimento': formatar_data(data_nascimento, '%d/%m/%Y') if data_nascimento else '',
                    'paciente_idade': idade_paciente,
                    'paciente_genero': garantir_string(pedido_info.get('genero')),
                    'paciente_id': paciente_id,
                    'medico_nome': garantir_string(pedido_info.get('medico_nome')) or 'Não informado',
                    'medico_especialidade': garantir_string(pedido_info.get('medico_especialidade')),
                    'medico_crm': garantir_string(pedido_info.get('medico_crm')),
                    'medico_id': medico_id,
                    'consulta_id': consulta_id,
                    'consulta_data': formatar_data(pedido_info.get('consulta_data')) if pedido_info.get('consulta_data') else '',
                    'consulta_observacoes': garantir_string(pedido_info.get('consulta_observacoes')) if pedido_info.get('consulta_observacoes') else ''
                }
            else:
                pedido = {
                    'id': pedido_info[0],
                    'tipo_exame': garantir_string(pedido_info[1]) or 'Não especificado',
                    'descricao': garantir_string(pedido_info[2]),
                    'observacoes': garantir_string(pedido_info[3]),
                    'urgencia': garantir_string(pedido_info[4]) or 'normal',
                    'status': pedido_status,
                    'data_solicitacao': formatar_data(pedido_info[6]),
                    'data_conclusao': formatar_data(pedido_info[7]),
                    'resultado_analise': garantir_string(pedido_info[8]),
                    'diagnostico_analista': garantir_string(pedido_info[9]),
                    'recomendacoes_analista': garantir_string(pedido_info[10]),
                    'observacoes_medico': garantir_string(pedido_info[11]),
                    'paciente_nome': garantir_string(pedido_info[12]) or 'Não informado',
                    'paciente_data_nascimento': formatar_data(pedido_info[13], '%d/%m/%Y') if len(pedido_info) > 13 and pedido_info[13] else '',
                    'paciente_idade': idade_paciente,
                    'paciente_genero': garantir_string(pedido_info[14]) if len(pedido_info) > 14 else '',
                    'paciente_id': paciente_id,
                    'medico_nome': garantir_string(pedido_info[15]) or 'Não informado',
                    'medico_especialidade': garantir_string(pedido_info[16]) if len(pedido_info) > 16 else '',
                    'medico_crm': garantir_string(pedido_info[17]) if len(pedido_info) > 17 else '',
                    'medico_id': medico_id,
                    'consulta_id': consulta_id,
                    'consulta_data': formatar_data(pedido_info[20]) if len(pedido_info) > 20 and pedido_info[20] else '',
                    'consulta_observacoes': garantir_string(pedido_info[21]) if len(pedido_info) > 21 else ''
                }
            
            pedido_owner = execute_query("""
                SELECT analista_id FROM pedidos_analise WHERE id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if pedido_owner:
                owner_value = pedido_owner[0] if isinstance(pedido_owner, (list, tuple)) else pedido_owner.get('analista_id')
                if not owner_value or owner_value == 0:
                    execute_query("""
                        UPDATE pedidos_analise 
                        SET analista_id = %s, status = 'em_analise', atualizado_em = NOW()
                        WHERE id = %s
                    """, (analista_id, pedido_id), commit=True)
                    pedido['status'] = 'em_analise'
                    print(f"[INFO] Pedido #{pedido_id} atribuído ao analista {analista_id}")
            
            anexos_list = []
            try:
                anexos = execute_query("""
                    SELECT id, filename, original_name, tipo, size, upload_date
                    FROM anexos_pedidos 
                    WHERE pedido_id = %s
                    ORDER BY upload_date DESC
                """, (pedido_id,), fetch=True)
                
                if anexos:
                    for anexo in anexos:
                        if isinstance(anexo, dict):
                            anexos_list.append({
                                'id': anexo.get('id'),
                                'filename': garantir_string(anexo.get('filename')),
                                'original_name': garantir_string(anexo.get('original_name')),
                                'type': garantir_string(anexo.get('tipo')) or 'unknown',
                                'size': anexo.get('size', 0),
                                'upload_date': formatar_data(anexo.get('upload_date')) if anexo.get('upload_date') else ''
                            })
                        else:
                            anexos_list.append({
                                'id': anexo[0],
                                'filename': garantir_string(anexo[1]),
                                'original_name': garantir_string(anexo[2]),
                                'type': garantir_string(anexo[3]) or 'unknown',
                                'size': anexo[4] if len(anexo) > 4 else 0,
                                'upload_date': formatar_data(anexo[5]) if len(anexo) > 5 and anexo[5] else ''
                            })
            except Exception as e:
                logger.warning(f"Não foi possível buscar anexos: {e}")
                criar_tabela_anexos()
            
            diagnosticos_anteriores = []
            if pedido.get('paciente_nome') and pedido['paciente_nome'] != 'Não informado':
                try:
                    diagnosticos_db = execute_query("""
                        SELECT diagnostico_final, criado_em FROM diagnostico 
                        WHERE consulta_id IN (
                            SELECT id FROM consultas WHERE paciente_id = %s
                        )
                        ORDER BY criado_em DESC LIMIT 5
                    """, (paciente_id,), fetch=True)
                    
                    if diagnosticos_db:
                        for diag in diagnosticos_db:
                            if isinstance(diag, dict):
                                diagnosticos_anteriores.append({
                                    'diagnostico': garantir_string(diag.get('diagnostico_final')),
                                    'data_consulta': formatar_data(diag.get('criado_em')),
                                })
                            else:
                                diagnosticos_anteriores.append({
                                    'diagnostico': garantir_string(diag[0]) if len(diag) > 0 else '',
                                    'data_consulta': formatar_data(diag[1]) if len(diag) > 1 else '',
                                })
                except Exception as e:
                    logger.warning(f"Erro ao buscar diagnósticos anteriores: {e}")
            
            if request.method == 'POST':
                acao = request.form.get('acao', '')
                
                if acao == 'iniciar_analise':
                    result = execute_query("""
                        UPDATE pedidos_analise 
                        SET status = 'em_analise', atualizado_em = NOW()
                        WHERE id = %s
                    """, (pedido_id,), commit=True)
                    
                    if result is not None:
                        flash('Análise iniciada com sucesso!', 'success')
                        pedido['status'] = 'em_analise'
                        print(f"[INFO] Pedido #{pedido_id} marcado como EM ANALISE")
                
                elif acao == 'editar':
                    resultado_analise = request.form.get('resultado_analise', '').strip()
                    diagnostico_analista = request.form.get('diagnostico_analista', '').strip()
                    recomendacoes_analista = request.form.get('recomendacoes_analista', '').strip()
                    
                    if not resultado_analise or not diagnostico_analista:
                        flash('Resultado e diagnóstico são obrigatórios.', 'warning')
                    else:
                        result = execute_query("""
                            UPDATE pedidos_analise 
                            SET resultado_analise = %s,
                                diagnostico_analista = %s,
                                recomendacoes_analista = %s,
                                status = 'concluido',
                                data_conclusao = NOW(),
                                atualizado_em = NOW()
                            WHERE id = %s
                        """, (
                            resultado_analise, diagnostico_analista, recomendacoes_analista, pedido_id
                        ), commit=True)
                        
                        if result is not None:
                            if pedido.get('consulta_id'):
                                try:
                                    salvar_diagnostico_ia(
                                        consulta_id=pedido['consulta_id'],
                                        tipo_exame=pedido.get('tipo_exame', ''),
                                        descricao=pedido.get('descricao', ''),
                                        observacoes=pedido.get('observacoes', ''),
                                        resultado=resultado_analise,
                                        diagnostico_ia=diagnostico_analista,
                                        status='concluido'
                                    )
                                except Exception as e:
                                    logger.warning(f"Erro ao salvar diagnóstico: {e}")
                            
                            flash('Análise concluída com sucesso!', 'success')
                            print(f"[INFO] Pedido #{pedido_id} CONCLUIDO com sucesso")
                            return redirect(url_for('analista.pedidos'))
                        else:
                            flash('Erro ao salvar análise.', 'danger')
            
            return render_template('analista/analisar_exame.html',
                                 user=session,
                                 pedido=pedido,
                                 anexos_pedido=anexos_list,
                                 diagnosticos_anteriores=diagnosticos_anteriores,
                                 gemini_available=gemini_available,
                                 MODEL_NAME=MODEL_NAME,
                                 now=datetime.now())
            
        except Exception as e:
            logger.error(f"[ERRO] {e}")
            logger.error(traceback.format_exc())
            flash('Erro ao carregar pedido para análise.', 'danger')
            return redirect(url_for('analista.pedidos'))

    # ========== ROTA PARA SALVAR ANÁLISE MANUAL ==========
    @bp.route('/salvar-analise-manual/<int:pedido_id>', methods=['POST'])
    @analista_required
    def salvar_analise_manual(pedido_id):
        """Salvar análise manual"""
        try:
            resultado_analise = request.form.get('resultado_analise', '').strip()
            diagnostico_analista = request.form.get('diagnostico_analista', '').strip()
            recomendacoes_analista = request.form.get('recomendacoes_analista', '').strip()
            
            if not resultado_analise or not diagnostico_analista:
                flash('Resultado e diagnóstico são obrigatórios.', 'warning')
                return redirect(url_for('analista.analisar_pedido', pedido_id=pedido_id))
            
            result = execute_query("""
                UPDATE pedidos_analise 
                SET resultado_analise = %s,
                    diagnostico_analista = %s,
                    recomendacoes_analista = %s,
                    status = 'concluido',
                    data_conclusao = NOW(),
                    atualizado_em = NOW()
                WHERE id = %s
            """, (
                resultado_analise, diagnostico_analista, recomendacoes_analista, pedido_id
            ), commit=True)
            
            if result is not None:
                flash('Análise salva com sucesso!', 'success')
            else:
                flash('Erro ao salvar análise.', 'danger')
                
            return redirect(url_for('analista.pedidos'))
            
        except Exception as e:
            logger.error(f"[ERRO] {e}")
            flash('Erro ao salvar análise.', 'danger')
            return redirect(url_for('analista.analisar_pedido', pedido_id=pedido_id))

    # ========== ROTA API PARA ANÁLISE DE IMAGEM ==========
    @bp.route('/api/analisar_imagem/<int:pedido_id>', methods=['POST'])
    @analista_required
    def api_analisar_imagem(pedido_id):
        """API para analisar imagem com IA"""
        try:
            print(f"[DEBUG] API: Analisando imagem para pedido #{pedido_id}")
            
            user_id = session.get('user_id')
            
            analista_info = execute_query("""
                SELECT a.id FROM analistas a
                WHERE a.usuario_id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                return jsonify({'success': False, 'error': 'Analista não encontrado'}), 404
            
            if isinstance(analista_info, dict):
                analista_id = analista_info.get('id')
            else:
                analista_id = analista_info[0] if len(analista_info) > 0 else None
            
            pedido = execute_query("""
                SELECT id, analista_id, status FROM pedidos_analise 
                WHERE id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido:
                return jsonify({'success': False, 'error': 'Pedido não encontrado'}), 404
            
            pedido_analista = pedido[1] if isinstance(pedido, (list, tuple)) else pedido.get('analista_id')
            pedido_status = pedido[2] if isinstance(pedido, (list, tuple)) else pedido.get('status')
            
            if pedido_analista != analista_id and pedido_status != 'pendente':
                return jsonify({'success': False, 'error': 'Acesso negado a este pedido'}), 403
            
            if 'imagem' not in request.files:
                return jsonify({'success': False, 'error': 'Nenhuma imagem enviada'}), 400
            
            file = request.files['imagem']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'Nenhum arquivo selecionado'}), 400
            
            allowed = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
            ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
            if not ext or ext not in allowed:
                return jsonify({
                    'success': False, 
                    'error': 'Formato não suportado. Use: PNG, JPG, JPEG, GIF, BMP, WEBP'
                }), 400
            
            file.seek(0, os.SEEK_END)
            file_length = file.tell()
            file.seek(0)
            
            if file_length > 10 * 1024 * 1024:
                return jsonify({'success': False, 'error': 'Arquivo muito grande (máx 10MB)'}), 400
            
            tipo_analise = request.form.get('tipo_analise', 'completa')
            observacoes_analista = request.form.get('observacoes_analista', '')
            
            paciente_info = execute_query("""
                SELECT 
                    u.nome, p.data_nascimento, p.genero,
                    pa.tipo_exame, pa.descricao, pa.observacoes,
                    pa.urgencia, pa.consulta_id, pa.medico_id,
                    pa.analista_id, pa.status
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                WHERE pa.id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if paciente_info:
                if isinstance(paciente_info, dict):
                    paciente_nome = garantir_string(paciente_info.get('nome', 'Não informado'))
                    data_nascimento = paciente_info.get('data_nascimento')
                    genero = garantir_string(paciente_info.get('genero', ''))
                    tipo_exame = garantir_string(paciente_info.get('tipo_exame', 'Não especificado'))
                    descricao = garantir_string(paciente_info.get('descricao', ''))
                    observacoes = garantir_string(paciente_info.get('observacoes', ''))
                    urgencia = garantir_string(paciente_info.get('urgencia', 'normal'))
                    consulta_id = paciente_info.get('consulta_id')
                    medico_id = paciente_info.get('medico_id')
                else:
                    paciente_nome = garantir_string(paciente_info[0]) if len(paciente_info) > 0 else 'Não informado'
                    data_nascimento = paciente_info[1] if len(paciente_info) > 1 else None
                    genero = garantir_string(paciente_info[2]) if len(paciente_info) > 2 else ''
                    tipo_exame = garantir_string(paciente_info[3]) if len(paciente_info) > 3 else 'Não especificado'
                    descricao = garantir_string(paciente_info[4]) if len(paciente_info) > 4 else ''
                    observacoes = garantir_string(paciente_info[5]) if len(paciente_info) > 5 else ''
                    urgencia = garantir_string(paciente_info[6]) if len(paciente_info) > 6 else 'normal'
                    consulta_id = paciente_info[7] if len(paciente_info) > 7 else None
                    medico_id = paciente_info[8] if len(paciente_info) > 8 else None
            else:
                paciente_nome = "Não informado"
                data_nascimento = None
                genero = ""
                tipo_exame = "Não especificado"
                descricao = ""
                observacoes = ""
                urgencia = "normal"
                consulta_id = None
                medico_id = None
            
            idade = calcular_idade(data_nascimento) if data_nascimento else ''
            
            contexto_clinico = preparar_contexto_clinico([
                None, tipo_exame, descricao, observacoes, urgencia, 
                None, None, None, None, None, None, None,
                paciente_nome, data_nascimento, genero
            ], observacoes_analista)
            
            temp_image_path = salvar_imagem_temporaria(file)
            if not temp_image_path:
                return jsonify({'success': False, 'error': 'Erro ao salvar imagem'}), 500
            
            diagnostico, error = analisar_imagem_com_gemini(temp_image_path, contexto_clinico)
            
            novo_status = pedido_status
            
            if diagnostico and not error:
                result = execute_query("""
                    UPDATE pedidos_analise 
                    SET resultado_analise = %s,
                        diagnostico_analista = %s,
                        recomendacoes_analista = 'Diagnóstico gerado automaticamente por IA. Verificar se necessário.',
                        status = 'concluido',
                        data_conclusao = NOW(),
                        atualizado_em = NOW()
                    WHERE id = %s
                """, (
                    diagnostico[:2000],
                    "Diagnóstico gerado por IA: " + diagnostico[:300] + ("..." if len(diagnostico) > 300 else ""),
                    pedido_id
                ), commit=True)
                
                if result is not None:
                    logger.info(f"[OK] Pedido #{pedido_id} marcado como CONCLUIDO")
                    novo_status = 'concluido'
                    
                    if consulta_id:
                        try:
                            with open(temp_image_path, 'rb') as img_file:
                                imagem_base64 = base64.b64encode(img_file.read()).decode('utf-8')
                        except Exception:
                            imagem_base64 = None
                        
                        try:
                            salvar_diagnostico_ia(
                                consulta_id=consulta_id, tipo_exame=tipo_exame,
                                descricao=descricao, observacoes=observacoes,
                                resultado=diagnostico, diagnostico_ia=diagnostico,
                                status='concluido', imagem_path=temp_image_path,
                                imagem_base64=imagem_base64,
                                formato_imagem=ext,
                                tamanho_imagem=file_length
                            )
                        except Exception as e:
                            logger.warning(f"Erro ao salvar diagnóstico IA: {e}")
                    
                    if medico_id:
                        try:
                            titulo = f"Diagnóstico gerado por IA - {tipo_exame}"
                            mensagem = f"O diagnóstico do exame {tipo_exame} do paciente {paciente_nome} foi gerado automaticamente pela IA."
                            criar_notificacao_medico(medico_id, pedido_id, titulo[:255], mensagem[:500], 'diagnostico_ia')
                        except Exception as e:
                            logger.warning(f"Erro ao notificar médico: {e}")
            
            try:
                if temp_image_path and os.path.exists(temp_image_path):
                    os.remove(temp_image_path)
            except:
                pass
            
            if error:
                return jsonify({
                    'success': False, 
                    'error': error, 
                    'diagnostico': None,
                    'warning': 'API Gemini com problemas. Use análise manual.',
                    'pedido_status': novo_status
                }), 500
            
            return jsonify({
                'success': True, 
                'diagnostico': garantir_string(diagnostico), 
                'contexto': contexto_clinico,
                'tipo_analise': tipo_analise, 
                'paciente': garantir_string(paciente_nome),
                'consulta_id': consulta_id, 
                'timestamp': datetime.now().isoformat(),
                'pedido_status': novo_status,
                'status_message': '✅ EXAME CONCLUÍDO - Diagnóstico gerado automaticamente por IA' if novo_status == 'concluido' else 'Análise em andamento'
            })
            
        except Exception as e:
            logger.error(f"[ERRO] {e}")
            logger.error(traceback.format_exc())
            return jsonify({
                'success': False, 
                'error': f'Erro interno: {str(e)}',
                'diagnostico': None, 
                'warning': 'Erro no servidor. Verifique os logs.',
                'pedido_status': pedido_status if 'pedido_status' in locals() else 'em_analise'
            }), 500

    # ========== ROTA API STATUS GEMINI ==========
    @bp.route('/api/gemini-status')
    @analista_required
    def api_gemini_status():
        """API para verificar status do Gemini"""
        try:
            return jsonify({
                'success': True,
                'gemini_available': gemini_available,
                'model_name': MODEL_NAME or 'Nenhum',
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ========== ROTA PARA BAIXAR ANEXO ==========
    @bp.route('/download_anexo/<int:pedido_id>/<filename>')
    @analista_required
    def download_anexo(pedido_id, filename):
        """Download de anexo"""
        try:
            flash('Funcionalidade de download em desenvolvimento', 'info')
            return redirect(url_for('analista.analisar_pedido', pedido_id=pedido_id))
        except Exception as e:
            logger.error(f"Erro no download: {e}")
            flash('Erro ao baixar arquivo', 'danger')
            return redirect(url_for('analista.analisar_pedido', pedido_id=pedido_id))

    # ========== ROTA PARA MINHAS ANÁLISES ==========
    @bp.route('/minhas-analises')
    @analista_required
    def minhas_analises():
        """Listar análises do analista"""
        try:
            user_id = session.get('user_id')
            
            analista_info = execute_query("""
                SELECT a.id FROM analistas a WHERE a.usuario_id = %s
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                flash('Perfil de analista não encontrado', 'danger')
                return redirect(url_for('analista.dashboard'))
            
            analista_id = analista_info[0] if isinstance(analista_info, (list, tuple)) else analista_info.get('id')
            
            analises = execute_query("""
                SELECT id, tipo_exame, paciente_nome, data_conclusao, status
                FROM pedidos_analise
                WHERE analista_id = %s AND status = 'concluido'
                ORDER BY data_conclusao DESC
            """, (analista_id,), fetch=True)
            
            return render_template('analista/minhas_analises.html',
                                 user=session,
                                 analises=analises or [])
        except Exception as e:
            logger.error(f"Erro: {e}")
            flash('Erro ao carregar análises', 'danger')
            return redirect(url_for('analista.dashboard'))

    # ========== ROTA PARA PEDIDOS ==========
    @bp.route('/pedidos')
    @analista_required
    def pedidos():
        """Listar pedidos do analista"""
        try:
            user_id = session.get('user_id')
            
            analista_info = execute_query("""
                SELECT a.id FROM analistas a WHERE a.usuario_id = %s
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                flash('Perfil de analista não encontrado', 'danger')
                return redirect(url_for('analista.dashboard'))
            
            analista_id = analista_info[0] if isinstance(analista_info, (list, tuple)) else analista_info.get('id')
            
            pedidos_lista = execute_query("""
                SELECT id, tipo_exame, paciente_nome, urgencia, status, data_solicitacao                FROM pedidos_analise
                WHERE analista_id = %s
                ORDER BY 
                    CASE status WHEN 'pendente' THEN 1 WHEN 'em_analise' THEN 2 WHEN 'concluido' THEN 3 ELSE 4 END,
                    data_solicitacao DESC
            """, (analista_id,), fetch=True)
            
            return render_template('analista/pedidos_lista.html',
                                 user=session,
                                 pedidos=pedidos_lista or [])
        except Exception as e:
            logger.error(f"Erro: {e}")
            flash('Erro ao carregar pedidos', 'danger')
            return redirect(url_for('analista.dashboard'))

    # ========== ROTA PARA DASHBOARD ==========
    @bp.route('/dashboard')
    @analista_required
    def dashboard():
        """Dashboard do analista"""
        try:
            user_id = session.get('user_id')
            
            stats = execute_query("""
                SELECT 
                    COUNT(CASE WHEN status = 'pendente' THEN 1 END) as pendentes,
                    COUNT(CASE WHEN status = 'em_analise' THEN 1 END) as em_analise,
                    COUNT(CASE WHEN status = 'concluido' THEN 1 END) as concluidos
                FROM pedidos_analise
                WHERE analista_id IN (SELECT id FROM analistas WHERE usuario_id = %s)
            """, (user_id,), fetch=True, one=True)
            
            if stats:
                if isinstance(stats, dict):
                    pendentes = stats.get('pendentes', 0)
                    em_analise = stats.get('em_analise', 0)
                    concluidos = stats.get('concluidos', 0)
                else:
                    pendentes = stats[0] if len(stats) > 0 else 0
                    em_analise = stats[1] if len(stats) > 1 else 0
                    concluidos = stats[2] if len(stats) > 2 else 0
            else:
                pendentes = em_analise = concluidos = 0
            
            return render_template('analista/dashboard.html',
                                 user=session,
                                 gemini_available=gemini_available,
                                 pendentes=pendentes,
                                 em_analise=em_analise,
                                 concluidos=concluidos)
        except Exception as e:
            logger.error(f"Erro: {e}")
            flash('Erro ao carregar dashboard', 'danger')
            return redirect(url_for('auth.login'))

    print("[INFO] TODAS AS ROTAS DE ANALISE REGISTRADAS COM SUCESSO!")
    return
