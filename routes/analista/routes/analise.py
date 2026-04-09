# routes/analista/routes/analise.py
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
            
            analista_id = analista_info[0]
            
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
            
            pedido_id = pedido[0]
            
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
            
            # Buscar informações do analista
            analista_info = execute_query("""
                SELECT a.id, u.nome FROM analistas a
                JOIN usuarios u ON a.usuario_id = u.id
                WHERE u.id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                flash('Perfil de analista não encontrado.', 'danger')
                return redirect(url_for('auth.login'))
            
            analista_id = analista_info[0]
            session['analista_id'] = analista_id
            session['user_name'] = garantir_string(analista_info[1])
            
            # Buscar informações completas do pedido
            pedido_info = execute_query("""
                SELECT 
                    pa.id, pa.tipo_exame, pa.descricao, pa.observacoes,
                    pa.urgencia, pa.status, pa.data_solicitacao, pa.data_conclusao,
                    pa.resultado_analise, pa.diagnostico_analista, pa.recomendacoes_analista,
                    pa.observacoes_medico,
                    u.nome as paciente_nome, p.data_nascimento, p.genero,
                    m_u.nome as medico_nome, m.especialidade as medico_especialidade,
                    m.crm as medico_crm, m.id as medico_id,
                    pa.consulta_id, c.data_hora as consulta_data, c.observacoes as consulta_observacoes
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
            
            print(f"[OK] Pedido #{pedido_id} encontrado - Status: {garantir_string(pedido_info[5])}")
            
            # Extrair informações
            medico_id = pedido_info[18] if len(pedido_info) > 18 else None  # ID do médico
            consulta_id = pedido_info[19] if len(pedido_info) > 19 else None  # ID da consulta
            idade_paciente = calcular_idade(pedido_info[13]) if pedido_info[13] else ''
            
            # Preparar dicionário do pedido com conversão de bytes
            pedido = {
                'id': pedido_info[0],
                'tipo_exame': garantir_string(pedido_info[1]) or 'Não especificado',
                'descricao': garantir_string(pedido_info[2]),
                'observacoes': garantir_string(pedido_info[3]),
                'urgencia': garantir_string(pedido_info[4]) or 'normal',
                'status': garantir_string(pedido_info[5]) or 'pendente',
                'data_solicitacao': formatar_data(pedido_info[6]),
                'data_conclusao': formatar_data(pedido_info[7]),
                'resultado_analise': garantir_string(pedido_info[8]),
                'diagnostico_analista': garantir_string(pedido_info[9]),
                'recomendacoes_analista': garantir_string(pedido_info[10]),
                'observacoes_medico': garantir_string(pedido_info[11]),
                'paciente_nome': garantir_string(pedido_info[12]) or 'Não informado',
                'paciente_data_nascimento': formatar_data(pedido_info[13], '%d/%m/%Y') if pedido_info[13] else '',
                'paciente_idade': idade_paciente,
                'paciente_genero': garantir_string(pedido_info[14]),
                'medico_nome': garantir_string(pedido_info[15]) or 'Não informado',
                'medico_especialidade': garantir_string(pedido_info[16]),
                'medico_crm': garantir_string(pedido_info[17]),
                'medico_id': medico_id,
                'consulta_id': consulta_id,
                'consulta_data': formatar_data(pedido_info[20]) if len(pedido_info) > 20 and pedido_info[20] else '',
                'consulta_observacoes': garantir_string(pedido_info[21]) if len(pedido_info) > 21 else ''
            }
            
            # Se o pedido não tem analista, atribuir ao analista atual
            pedido_owner = execute_query("""
                SELECT analista_id FROM pedidos_analise WHERE id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if pedido_owner and (not pedido_owner[0] or pedido_owner[0] == 0):
                execute_query("""
                    UPDATE pedidos_analise 
                    SET analista_id = %s, status = 'em_analise', atualizado_em = NOW()
                    WHERE id = %s
                """, (analista_id, pedido_id), commit=True)
                pedido['status'] = 'em_analise'
                print(f"[INFO] Pedido #{pedido_id} atribuído ao analista {analista_id}")
            
            # Buscar anexos - COM TRATAMENTO DE ERRO
            anexos_list = []
            try:
                # Verificar se a tabela existe
                anexos = execute_query("""
                    SELECT id, filename, original_name, tipo, size, upload_date
                    FROM anexos_pedidos 
                    WHERE pedido_id = %s
                    ORDER BY upload_date DESC
                """, (pedido_id,), fetch=True)
                
                if anexos:
                    for anexo in anexos:
                        anexos_list.append({
                            'id': anexo[0],
                            'filename': garantir_string(anexo[1]),
                            'original_name': garantir_string(anexo[2]),
                            'type': garantir_string(anexo[3]) or 'unknown',
                            'size': anexo[4] if anexo[4] else 0,
                            'upload_date': formatar_data(anexo[5]) if anexo[5] else ''
                        })
            except Exception as e:
                logger.warning(f"Não foi possível buscar anexos: {e}")
                # Criar tabela se não existir
                criar_tabela_anexos()
            
            # Buscar diagnósticos anteriores
            diagnosticos_anteriores = []
            if pedido_info[12]:  # Se tem nome do paciente
                try:
                    diagnosticos_db = execute_query("""
                        SELECT d.diagnostico_final, d.criado_em, m_u.nome as medico_nome, m.especialidade
                        FROM diagnostico d
                        JOIN consultas c ON d.consulta_id = c.id
                        JOIN pacientes p ON c.paciente_id = p.id
                        JOIN usuarios u ON p.usuario_id = u.id
                        JOIN medicos m ON c.medico_id = m.id
                        JOIN usuarios m_u ON m.usuario_id = m_u.id
                        WHERE u.nome = %s AND d.diagnostico_final IS NOT NULL
                        ORDER BY d.criado_em DESC
                        LIMIT 5
                    """, (pedido_info[12],), fetch=True)
                    
                    if diagnosticos_db:
                        for diag in diagnosticos_db:
                            diagnosticos_anteriores.append({
                                'diagnostico': garantir_string(diag[0]),
                                'data_consulta': formatar_data(diag[1]),
                                'medico_nome': garantir_string(diag[2]),
                                'medico_especialidade': garantir_string(diag[3])
                            })
                except Exception as e:
                    logger.warning(f"Erro ao buscar diagnósticos anteriores: {e}")
            
            # Processar POST (iniciar análise ou concluir)
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
                
                elif acao == 'concluir':
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
                            # Salvar na tabela diagnostico
                            if consulta_id:
                                try:
                                    salvar_diagnostico_ia(
                                        consulta_id=consulta_id,
                                        tipo_exame=pedido_info[1] or '',
                                        descricao=pedido_info[2] or '',
                                        observacoes=pedido_info[3] or '',
                                        resultado=resultado_analise,
                                        diagnostico_ia=diagnostico_analista,
                                        status='concluido'
                                    )
                                except Exception as e:
                                    logger.warning(f"Erro ao salvar diagnóstico: {e}")
                            
                            # Notificar médico
                            if medico_id:
                                try:
                                    titulo = f"Diagnóstico disponível - {pedido_info[1] or 'Exame'}"
                                    mensagem = f"""
                                    O diagnóstico do exame {pedido_info[1] or ''} do paciente {pedido_info[12] or ''} está disponível.
                                    Resultado: {resultado_analise[:100]}...
                                    """
                                    criar_notificacao_medico(medico_id, pedido_id, titulo, mensagem, 'diagnostico')
                                except Exception as e:
                                    logger.warning(f"Erro ao notificar médico: {e}")
                            
                            flash('Análise concluída com sucesso! O médico foi notificado.', 'success')
                            print(f"[INFO] Pedido #{pedido_id} CONCLUIDO com sucesso")
                            return redirect(url_for('analista.pedidos'))
                        else:
                            flash('Erro ao salvar análise.', 'danger')
            
            # Renderizar template
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
            
            analista_id = analista_info[0]
            
            pedido = execute_query("""
                SELECT id, analista_id, status FROM pedidos_analise 
                WHERE id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido:
                return jsonify({'success': False, 'error': 'Pedido não encontrado'}), 404
            
            if pedido[1] != analista_id and pedido[2] != 'pendente':
                return jsonify({'success': False, 'error': 'Acesso negado a este pedido'}), 403
            
            if 'imagem' not in request.files:
                return jsonify({'success': False, 'error': 'Nenhuma imagem enviada'}), 400
            
            file = request.files['imagem']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'Nenhum arquivo selecionado'}), 400
            
            allowed = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'tiff', 'tif'}
            if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed:
                return jsonify({
                    'success': False, 
                    'error': 'Formato não suportado. Use: PNG, JPG, JPEG, GIF, BMP, WEBP, TIFF'
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
                paciente_nome, data_nascimento, genero, tipo_exame, descricao, observacoes, urgencia, consulta_id, medico_id, pedido_analista_id, pedido_status = paciente_info
                idade = calcular_idade(data_nascimento)
            else:
                paciente_nome = "Não informado"
                idade = ""
                genero = ""
                tipo_exame = "Não especificado"
                descricao = ""
                observacoes = ""
                urgencia = "normal"
                consulta_id = None
                medico_id = None
                pedido_analista_id = None
                pedido_status = 'pendente'
            
            if not pedido_analista_id or pedido_analista_id == 0:
                execute_query("""
                    UPDATE pedidos_analise 
                    SET analista_id = %s, status = 'em_analise', atualizado_em = NOW()
                    WHERE id = %s
                """, (analista_id, pedido_id), commit=True)
                pedido_status = 'em_analise'
            
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
                    diagnostico,
                    "Diagnóstico gerado por IA: " + diagnostico[:200] + ("..." if len(diagnostico) > 200 else ""),
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
                                formato_imagem=file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else None,
                                tamanho_imagem=file_length
                            )
                        except Exception as e:
                            logger.warning(f"Erro ao salvar diagnóstico IA: {e}")
                    
                    if medico_id:
                        try:
                            titulo = f"Diagnóstico gerado por IA - {tipo_exame or 'Exame'}"
                            mensagem = f"""
                            O diagnóstico do exame {tipo_exame or ''} do paciente {paciente_nome or ''} foi gerado automaticamente pela IA.
                            Status: EXAME CONCLUIDO
                            Diagnóstico preliminar: {diagnostico[:150]}...
                            Acesse sua área médica para ver o diagnóstico completo.
                            """
                            criar_notificacao_medico(medico_id, pedido_id, titulo, mensagem, 'diagnostico_ia')
                        except Exception as e:
                            logger.warning(f"Erro ao notificar médico: {e}")
            else:
                novo_status = pedido_status
        
            try:
                if os.path.exists(temp_image_path):
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
            
            # Garantir que todos os dados sejam strings antes de retornar JSON
            diagnostico_str = garantir_string(diagnostico)
            paciente_nome_str = garantir_string(paciente_nome)
            
            return jsonify({
                'success': True, 
                'diagnostico': diagnostico_str, 
                'contexto': contexto_clinico,
                'tipo_analise': tipo_analise, 
                'paciente': paciente_nome_str,
                'consulta_id': consulta_id, 
                'timestamp': datetime.now().isoformat(),
                'pedido_status': novo_status,
                'status_message': 'EXAME CONCLUIDO - Diagnóstico gerado automaticamente por IA' if novo_status == 'concluido' else 'Análise em andamento'
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

    print("[INFO] TODAS AS ROTAS DE ANALISE REGISTRADAS COM SUCESSO!")
    return