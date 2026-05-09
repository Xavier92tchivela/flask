# routes/analista/routes/analise.py - VERSÃO LIMPA SEM CONFLITOS
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
    
    def garantir_string(valor):
        if valor is None:
            return ''
        if isinstance(valor, bytes):
            try:
                return valor.decode('utf-8')
            except:
                return str(valor)
        return str(valor) if valor is not None else ''

    # ========== ROTA PRINCIPAL - ANALISAR PEDIDO ==========
    @bp.route('/analisar/<int:pedido_id>', methods=['GET', 'POST'])
    @analista_required
    def analisar_pedido(pedido_id):
        """Analisar um pedido específico"""
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
                    pa.consulta_id,
                    p.id as paciente_id
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                LEFT JOIN medicos m ON pa.medico_id = m.id
                LEFT JOIN usuarios m_u ON m.usuario_id = m_u.id
                WHERE pa.id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido_info:
                flash(f'Pedido #{pedido_id} não encontrado.', 'danger')
                return redirect(url_for('analista.pedidos'))
            
            # Montar dicionário do pedido (simplificado)
            if isinstance(pedido_info, dict):
                pedido = {
                    'id': pedido_info.get('id'),
                    'tipo_exame': garantir_string(pedido_info.get('tipo_exame')) or 'Não especificado',
                    'descricao': garantir_string(pedido_info.get('descricao')),
                    'observacoes': garantir_string(pedido_info.get('observacoes')),
                    'urgencia': garantir_string(pedido_info.get('urgencia')) or 'normal',
                    'status': garantir_string(pedido_info.get('status', 'pendente')),
                    'data_solicitacao': formatar_data(pedido_info.get('data_solicitacao')),
                    'data_conclusao': formatar_data(pedido_info.get('data_conclusao')),
                    'resultado_analise': garantir_string(pedido_info.get('resultado_analise')),
                    'diagnostico_analista': garantir_string(pedido_info.get('diagnostico_analista')),
                    'recomendacoes_analista': garantir_string(pedido_info.get('recomendacoes_analista')),
                    'paciente_nome': garantir_string(pedido_info.get('paciente_nome')) or 'Não informado',
                    'paciente_idade': calcular_idade(pedido_info.get('data_nascimento')) if pedido_info.get('data_nascimento') else '',
                    'paciente_genero': garantir_string(pedido_info.get('genero')),
                    'medico_nome': garantir_string(pedido_info.get('medico_nome')) or 'Não informado',
                    'medico_especialidade': garantir_string(pedido_info.get('medico_especialidade')),
                    'consulta_id': pedido_info.get('consulta_id'),
                }
            else:
                pedido = {
                    'id': pedido_info[0],
                    'tipo_exame': garantir_string(pedido_info[1]) or 'Não especificado',
                    'descricao': garantir_string(pedido_info[2]),
                    'observacoes': garantir_string(pedido_info[3]),
                    'urgencia': garantir_string(pedido_info[4]) or 'normal',
                    'status': garantir_string(pedido_info[5]) if len(pedido_info) > 5 else 'pendente',
                    'data_solicitacao': formatar_data(pedido_info[6]) if len(pedido_info) > 6 else '',
                    'data_conclusao': formatar_data(pedido_info[7]) if len(pedido_info) > 7 else '',
                    'resultado_analise': garantir_string(pedido_info[8]) if len(pedido_info) > 8 else '',
                    'diagnostico_analista': garantir_string(pedido_info[9]) if len(pedido_info) > 9 else '',
                    'recomendacoes_analista': garantir_string(pedido_info[10]) if len(pedido_info) > 10 else '',
                    'paciente_nome': garantir_string(pedido_info[12]) if len(pedido_info) > 12 else 'Não informado',
                    'paciente_idade': calcular_idade(pedido_info[13]) if len(pedido_info) > 13 and pedido_info[13] else '',
                    'paciente_genero': garantir_string(pedido_info[14]) if len(pedido_info) > 14 else '',
                    'medico_nome': garantir_string(pedido_info[15]) if len(pedido_info) > 15 else 'Não informado',
                    'medico_especialidade': garantir_string(pedido_info[16]) if len(pedido_info) > 16 else '',
                    'consulta_id': pedido_info[19] if len(pedido_info) > 19 else None,
                }
            
            # Buscar anexos
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
            
            # Processar POST - iniciar análise
            if request.method == 'POST' and request.form.get('acao') == 'iniciar_analise':
                execute_query("""
                    UPDATE pedidos_analise 
                    SET status = 'em_analise', atualizado_em = NOW()
                    WHERE id = %s
                """, (pedido_id,), commit=True)
                flash('Análise iniciada com sucesso!', 'success')
                pedido['status'] = 'em_analise'
            
            return render_template('analista/analisar_exame.html',
                                 user=session,
                                 pedido=pedido,
                                 anexos_pedido=anexos_list,
                                 diagnosticos_anteriores=[],
                                 gemini_available=gemini_available,
                                 MODEL_NAME=MODEL_NAME,
                                 now=datetime.now())
            
        except Exception as e:
            logger.error(f"[ERRO] {e}")
            logger.error(traceback.format_exc())
            flash('Erro ao carregar pedido para análise.', 'danger')
            return redirect(url_for('analista.pedidos'))

    # ========== ROTA API PARA ANÁLISE DE IMAGEM COM IA ==========
    @bp.route('/api/analisar_imagem/<int:pedido_id>', methods=['POST'])
    @analista_required
    def api_analisar_imagem(pedido_id):
        """API para analisar imagem com IA"""
        try:
            print(f"[DEBUG] API: Analisando imagem para pedido #{pedido_id}")
            
            if 'imagem' not in request.files:
                return jsonify({'success': False, 'error': 'Nenhuma imagem enviada'}), 400
            
            file = request.files['imagem']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'Nenhum arquivo selecionado'}), 400
            
            # Validar formato
            allowed = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
            ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
            if not ext or ext not in allowed:
                return jsonify({'success': False, 'error': 'Formato não suportado'}), 400
            
            # Validar tamanho
            file.seek(0, os.SEEK_END)
            file_length = file.tell()
            file.seek(0)
            
            if file_length > 10 * 1024 * 1024:
                return jsonify({'success': False, 'error': 'Arquivo muito grande (máx 10MB)'}), 400
            
            # Buscar informações do paciente
            paciente_info = execute_query("""
                SELECT u.nome, p.data_nascimento
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                WHERE pa.id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if paciente_info:
                if isinstance(paciente_info, dict):
                    paciente_nome = garantir_string(paciente_info.get('nome', 'Paciente'))
                else:
                    paciente_nome = garantir_string(paciente_info[0]) if len(paciente_info) > 0 else 'Paciente'
            else:
                paciente_nome = "Paciente"
            
            # Preparar contexto clínico
            contexto_clinico = f"Paciente: {paciente_nome}"
            tipo_analise = request.form.get('tipo_analise', 'completa')
            observacoes_analista = request.form.get('observacoes_analista', '')
            
            if observacoes_analista:
                contexto_clinico += f"\nObservações do analista: {observacoes_analista}"
            
            # Salvar imagem temporária e analisar
            temp_image_path = salvar_imagem_temporaria(file)
            if not temp_image_path:
                return jsonify({'success': False, 'error': 'Erro ao salvar imagem'}), 500
            
            diagnostico, error = analisar_imagem_com_gemini(temp_image_path, contexto_clinico)
            
            # Limpar arquivo temporário
            if temp_image_path and os.path.exists(temp_image_path):
                os.remove(temp_image_path)
            
            if error:
                return jsonify({
                    'success': False, 
                    'error': error, 
                    'diagnostico': None,
                    'warning': 'API Gemini com problemas. Use análise manual.',
                    'pedido_status': 'em_analise'
                }), 500
            
            # Salvar diagnóstico no banco
            if diagnostico:
                execute_query("""
                    UPDATE pedidos_analise 
                    SET resultado_analise = %s,
                        diagnostico_analista = %s,
                        status = 'concluido',
                        data_conclusao = NOW()
                    WHERE id = %s
                """, (
                    diagnostico[:2000] if diagnostico else '',
                    "Diagnóstico gerado por IA: " + diagnostico[:300] + ("..." if len(diagnostico) > 300 else ""),
                    pedido_id
                ), commit=True)
            
            return jsonify({
                'success': True, 
                'diagnostico': garantir_string(diagnostico), 
                'paciente': paciente_nome,
                'tipo_analise': tipo_analise,
                'timestamp': datetime.now().isoformat(),
                'pedido_status': 'concluido',
                'status_message': '✅ Diagnóstico gerado automaticamente por IA'
            })
            
        except Exception as e:
            logger.error(f"[ERRO] {e}")
            logger.error(traceback.format_exc())
            return jsonify({
                'success': False, 
                'error': f'Erro interno: {str(e)}',
                'diagnostico': None
            }), 500

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
            
            execute_query("""
                UPDATE pedidos_analise 
                SET resultado_analise = %s,
                    diagnostico_analista = %s,
                    recomendacoes_analista = %s,
                    status = 'concluido',
                    data_conclusao = NOW(),
                    atualizado_em = NOW()
                WHERE id = %s
            """, (resultado_analise, diagnostico_analista, recomendacoes_analista, pedido_id), commit=True)
            
            flash('Análise salva com sucesso!', 'success')
            return redirect(url_for('analista.pedidos'))
            
        except Exception as e:
            logger.error(f"[ERRO] {e}")
            flash('Erro ao salvar análise.', 'danger')
            return redirect(url_for('analista.analisar_pedido', pedido_id=pedido_id))

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

    print("[INFO] ROTAS DE ANALISE REGISTRADAS COM SUCESSO!")
    return
