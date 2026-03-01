# routes/medico/medico_receitas.py - VERSÃO COMPLETA CORRIGIDA COM PESO

from flask import render_template, request, flash, redirect, url_for, session, jsonify, send_file
import os
import logging
import traceback
import json
from datetime import datetime

logger = logging.getLogger(__name__)

def init_medico_receitas(mysql, base, receita_service, gemini_available=False):
    """Inicializa rotas de receitas do médico"""
    
    execute_query = base['execute_query']
    formatar_data = base['formatar_data']
    calcular_idade = base['calcular_idade']
    obter_info_medico = base['obter_info_medico']
    medico_required = base['medico_required']
    
    # ========== ROTA: GERAR RECEITA (COM SINAIS VITAIS E PESO) ==========
    @medico_required
    def gerar_receita(pedido_id):
        try:
            logger.info("=" * 60)
            logger.info(f"INICIANDO GERAÇÃO DE RECEITA PARA PEDIDO #{pedido_id}")
            logger.info("=" * 60)
            
            medico_info = obter_info_medico()
            if not medico_info:
                logger.error("Médico não encontrado na sessão")
                flash('Informações do médico não encontradas.', 'danger')
                return redirect(url_for('auth.login'))
            
            if not isinstance(medico_info, dict):
                logger.error(f"medico_info não é um dicionário: {type(medico_info)}")
                flash('Erro nas informações do médico.', 'danger')
                return redirect(url_for('auth.login'))
            
            medico_id = medico_info.get('id')
            logger.info(f"Médico ID: {medico_id}, Nome: {medico_info.get('nome')}")
            
            if not medico_id or medico_id < 0:
                logger.warning("Médico sem ID válido")
                flash('Complete seu cadastro no perfil.', 'warning')
                return redirect(url_for('medico.perfil'))
            
            # Verificar se Gemini está disponível
            if not gemini_available:
                logger.warning("Gemini não está disponível")
                flash('Gemini AI não está disponível no momento.', 'warning')
                return redirect(url_for('medico.ver_detalhes_pedido', pedido_id=pedido_id))
            
            # Buscar pedido
            logger.info(f"Buscando pedido #{pedido_id} no banco de dados...")
            
            pedido_query = """
                SELECT pa.id, pa.tipo_exame, pa.descricao, pa.observacoes,
                       pa.diagnostico_analista, pa.resultado_analise, pa.recomendacoes_analista,
                       pa.status_aprovacao, pa.consulta_id, pa.observacoes_medico,
                       COALESCE(p_u.nome, 'Não informado') as paciente_nome,
                       p.data_nascimento, p.genero, p.telefone, p.endereco, p.id as paciente_id
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios p_u ON p.usuario_id = p_u.id
                WHERE pa.id = %s AND pa.medico_id = %s AND pa.status = 'concluido'
            """
            
            pedido = execute_query(pedido_query, (pedido_id, medico_id), fetch=True, one=True)
            
            if not pedido:
                logger.error(f"Pedido #{pedido_id} não encontrado ou não está concluído")
                flash('Pedido não encontrado ou não está concluído.', 'danger')
                return redirect(url_for('medico.ver_detalhes_pedido', pedido_id=pedido_id))
            
            logger.info(f"Pedido encontrado: Status Aprovação={pedido[7]}, Consulta ID={pedido[8]}")
            
            if pedido[7] != 'aprovado':
                logger.warning(f"Pedido não aprovado: {pedido[7]}")
                flash('Apenas pedidos aprovados podem gerar receita.', 'warning')
                return redirect(url_for('medico.ver_detalhes_pedido', pedido_id=pedido_id))
            
            # Buscar diagnóstico e sinais vitais
            consulta_id = pedido[8]
            logger.info(f"Consulta ID: {consulta_id}")
            
            diagnostico_completo = ""
            fonte_diagnostico = ""
            
            # ===== BUSCAR SINAIS VITAIS (CORRIGIDO COM PESO) =====
            sinais_vitais = None
            if consulta_id:
                logger.info(f"Buscando sinais vitais para consulta #{consulta_id}...")
                sinais_query = """
                    SELECT id, pressao_arterial, frequencia_cardiaca, frequencia_respiratoria,
                           temperatura, saturacao_oxigenio, glicemia, peso, data_afericao, observacoes
                    FROM sinais_vitais
                    WHERE consulta_id = %s
                    ORDER BY data_afericao DESC
                    LIMIT 1
                """
                sinais_data = execute_query(sinais_query, (consulta_id,), fetch=True, one=True)
                
                if sinais_data:
                    logger.info("✅ SINAIS VITAIS ENCONTRADOS!")
                    logger.info(f"   PA: {sinais_data[1]}")
                    logger.info(f"   FC: {sinais_data[2]}")
                    logger.info(f"   Peso: {sinais_data[7]} kg")
                    
                    # Classificar cada sinal vital
                    from routes.consulta import (
                        classificar_pressao_arterial, classificar_frequencia_cardiaca,
                        classificar_frequencia_respiratoria, classificar_temperatura,
                        classificar_saturacao_oxigenio, classificar_glicemia
                    )
                    
                    sinais_vitais = {
                        'id': sinais_data[0],
                        'pressao_arterial': sinais_data[1],
                        'pa_classificacao': classificar_pressao_arterial(sinais_data[1]) if sinais_data[1] else None,
                        'frequencia_cardiaca': sinais_data[2],
                        'fc_classificacao': classificar_frequencia_cardiaca(sinais_data[2]) if sinais_data[2] else None,
                        'frequencia_respiratoria': sinais_data[3],
                        'fr_classificacao': classificar_frequencia_respiratoria(sinais_data[3]) if sinais_data[3] else None,
                        'temperatura': float(sinais_data[4]) if sinais_data[4] else None,
                        'temp_classificacao': classificar_temperatura(sinais_data[4]) if sinais_data[4] else None,
                        'saturacao_oxigenio': sinais_data[5],
                        'spo2_classificacao': classificar_saturacao_oxigenio(sinais_data[5]) if sinais_data[5] else None,
                        'glicemia': sinais_data[6],
                        'glicemia_classificacao': classificar_glicemia(sinais_data[6]) if sinais_data[6] else None,
                        'peso': float(sinais_data[7]) if sinais_data[7] else None,
                        'data_afericao': formatar_data(sinais_data[8], '%d/%m/%Y %H:%M') if sinais_data[8] else '',
                        'observacoes': sinais_data[9] or ''
                    }
                    logger.info(f"Sinais vitais processados: PA={sinais_vitais['pressao_arterial']}, "
                              f"FC={sinais_vitais['frequencia_cardiaca']}, "
                              f"Peso={sinais_vitais['peso']} kg")
                else:
                    logger.warning("❌ Nenhum sinal vital encontrado para esta consulta")
            
            # ===== BUSCAR SINTOMAS DO PACIENTE =====
            sintomas_lista = []
            sintomas_texto = ""
            if consulta_id:
                logger.info(f"Buscando sintomas para consulta #{consulta_id}...")
                sintomas_data = execute_query("""
                    SELECT sintomas FROM consultas WHERE id = %s
                """, (consulta_id,), fetch=True, one=True)
                
                if sintomas_data and sintomas_data[0]:
                    sintomas_lista = [s.strip() for s in sintomas_data[0].split(',') if s.strip()]
                    sintomas_texto = ", ".join(sintomas_lista)
                    logger.info(f"Encontrados {len(sintomas_lista)} sintomas: {sintomas_texto[:100]}...")
            
            # ===== BUSCAR DIAGNÓSTICO =====
            if consulta_id:
                logger.info(f"Buscando diagnóstico para consulta #{consulta_id}...")
                
                diagnostico_data = execute_query("""
                    SELECT tipo_exame, descricao, observacoes, resultado,
                           diagnostico_preliminar, diagnostico_final, status
                    FROM diagnostico WHERE consulta_id = %s ORDER BY id DESC LIMIT 1
                """, (consulta_id,), fetch=True, one=True)
                
                if diagnostico_data:
                    logger.info("Diagnóstico encontrado na tabela diagnostico")
                    campos = []
                    if diagnostico_data[0] and str(diagnostico_data[0]).strip():
                        campos.append(f"TIPO DE EXAME:\n{diagnostico_data[0]}")
                    if diagnostico_data[1] and str(diagnostico_data[1]).strip():
                        campos.append(f"DESCRIÇÃO:\n{diagnostico_data[1]}")
                    if diagnostico_data[2] and str(diagnostico_data[2]).strip():
                        campos.append(f"OBSERVAÇÕES:\n{diagnostico_data[2]}")
                    if diagnostico_data[3] and str(diagnostico_data[3]).strip():
                        campos.append(f"RESULTADO:\n{diagnostico_data[3]}")
                    if diagnostico_data[4] and str(diagnostico_data[4]).strip():
                        campos.append(f"DIAGNÓSTICO PRELIMINAR:\n{diagnostico_data[4]}")
                    if diagnostico_data[5] and str(diagnostico_data[5]).strip():
                        campos.append(f"DIAGNÓSTICO FINAL:\n{diagnostico_data[5]}")
                    
                    if campos:
                        diagnostico_completo = "\n\n---\n\n".join(campos)
                        fonte_diagnostico = "Tabela diagnostico"
                        logger.info(f"Diagnóstico construído com {len(campos)} campos")
            
            # Se não encontrou diagnóstico, usar dados do pedido
            if not diagnostico_completo:
                logger.info("Usando dados do pedido para diagnóstico")
                campos = []
                if pedido[4] and str(pedido[4]).strip():
                    campos.append(f"DIAGNÓSTICO DO ANALISTA:\n{pedido[4]}")
                if pedido[5] and str(pedido[5]).strip():
                    campos.append(f"RESULTADO DA ANÁLISE:\n{pedido[5]}")
                if pedido[6] and str(pedido[6]).strip():
                    campos.append(f"RECOMENDAÇÕES DO ANALISTA:\n{pedido[6]}")
                if pedido[2] and str(pedido[2]).strip():
                    campos.append(f"DESCRIÇÃO DO EXAME:\n{pedido[2]}")
                if pedido[3] and str(pedido[3]).strip():
                    campos.append(f"OBSERVAÇÕES DO PEDIDO:\n{pedido[3]}")
                if pedido[9] and str(pedido[9]).strip():
                    campos.append(f"OBSERVAÇÕES DO MÉDICO:\n{pedido[9]}")
                
                if campos:
                    diagnostico_completo = "\n\n---\n\n".join(campos)
                    fonte_diagnostico = "Tabela pedidos_analise"
                    logger.info(f"Diagnóstico construído com {len(campos)} campos do pedido")
                else:
                    diagnostico_completo = "Diagnóstico não disponível."
                    fonte_diagnostico = "Nenhuma fonte"
                    logger.warning("Nenhum diagnóstico encontrado")
            
            # Adicionar sintomas ao diagnóstico completo
            if sintomas_lista:
                diagnostico_completo += f"\n\n---\n\n**SINTOMAS RELATADOS PELO PACIENTE:**\n"
                for sintoma in sintomas_lista:
                    diagnostico_completo += f"• {sintoma}\n"
                logger.info("Sintomas adicionados ao diagnóstico")
            
            # Calcular idade
            idade = ''
            if pedido[11]:
                try:
                    data_nasc = pedido[11]
                    if isinstance(data_nasc, str):
                        data_nasc = datetime.strptime(data_nasc[:10], '%Y-%m-%d')
                    hoje = datetime.now()
                    idade_calc = hoje.year - data_nasc.year
                    if (hoje.month, hoje.day) < (data_nasc.month, data_nasc.day):
                        idade_calc -= 1
                    idade = f"{idade_calc} anos"
                    logger.info(f"Idade calculada: {idade}")
                except Exception as e:
                    logger.error(f"Erro ao calcular idade: {e}")
                    idade = ''
            
            pedido_info = {
                'id': str(pedido[0]), 
                'tipo_exame': str(pedido[1] or 'Não especificado'),
                'descricao': str(pedido[2] or ''), 
                'observacoes': str(pedido[3] or ''),
                'diagnostico_analista': str(pedido[4] or ''),
                'resultado_analise': str(pedido[5] or ''),
                'recomendacoes_analista': str(pedido[6] or ''),
                'status_aprovacao': str(pedido[7]), 
                'consulta_id': str(consulta_id) if consulta_id else '',
                'observacoes_medico': str(pedido[9] or ''),
                'paciente_nome': str(pedido[10] or 'Não informado'),
                'paciente_data_nascimento': formatar_data(pedido[11], '%d/%m/%Y') if pedido[11] else '',
                'paciente_idade': idade, 
                'paciente_genero': str(pedido[12] or ''),
                'paciente_telefone': str(pedido[13] or ''),
                'paciente_endereco': str(pedido[14] or ''),
                'paciente_id': str(pedido[15]), 
                'medico_nome': str(medico_info.get('nome', '')),
                'medico_especialidade': str(medico_info.get('especialidade', '')),
                'medico_crm': str(medico_info.get('crm', '')),
                'diagnostico_completo': diagnostico_completo,
                'fonte_diagnostico': fonte_diagnostico,
                'sintomas_lista': sintomas_lista,
                'sintomas_texto': sintomas_texto,
                'sinais_vitais': sinais_vitais
            }
            
            logger.info(f"Pedido info preparado: Paciente={pedido_info['paciente_nome']}, Consulta ID={pedido_info['consulta_id']}")
            logger.info(f"Sintomas incluídos: {len(sintomas_lista)}")
            logger.info(f"Sinais Vitais incluídos: {bool(sinais_vitais)}")
            
            if request.method == 'POST':
                logger.info("Processando POST - Salvando receita")
                
                if not pedido_info['consulta_id']:
                    logger.error("Consulta ID não encontrado")
                    flash('Este pedido não possui consulta vinculada.', 'danger')
                    return redirect(url_for('medico.ver_detalhes_pedido', pedido_id=pedido_id))
                
                if not diagnostico_completo or len(diagnostico_completo.strip()) < 50:
                    logger.warning(f"Diagnóstico insuficiente: {len(diagnostico_completo.strip()) if diagnostico_completo else 0} caracteres")
                    flash('Diagnóstico insuficiente.', 'warning')
                    return redirect(url_for('medico.gerar_receita', pedido_id=pedido_id))
                
                medico_info_completo = {
                    'id': str(medico_info.get('id', '')),
                    'nome': str(medico_info.get('nome', 'Dr. Não Informado')),
                    'especialidade': str(medico_info.get('especialidade', 'Clínico Geral')),
                    'crm': str(medico_info.get('crm', 'CRM não informado')),
                    'usuario_id': str(medico_info.get('usuario_id', '')),
                    'email': str(medico_info.get('email', ''))
                }
                
                paciente_ia_info = {
                    'nome': pedido_info['paciente_nome'],
                    'idade': pedido_info['paciente_idade'],
                    'genero': pedido_info['paciente_genero']
                }
                
                # LOG PARA VERIFICAR OS SINAIS VITAIS ANTES DE ENVIAR
                logger.info("=" * 50)
                logger.info("🔍 SINAIS VITAIS SENDO ENVIADOS PARA IA:")
                if sinais_vitais:
                    logger.info(json.dumps({
                        'pressao_arterial': sinais_vitais.get('pressao_arterial'),
                        'frequencia_cardiaca': sinais_vitais.get('frequencia_cardiaca'),
                        'peso': sinais_vitais.get('peso')
                    }, indent=2))
                else:
                    logger.warning("⚠️ NENHUM sinal vital disponível!")
                logger.info("=" * 50)
                
                logger.info("Chamando receita_service.gerar_receita_ia com SINAIS VITAIS...")
                receita_data, error = receita_service.gerar_receita_ia(
                    diagnostico=diagnostico_completo,
                    paciente_info=paciente_ia_info,
                    medico_info=medico_info_completo,
                    sintomas=sintomas_lista,
                    sinais_vitais=sinais_vitais
                )
                
                if error or not receita_data:
                    logger.error(f"Erro ao gerar receita com IA: {error}")
                    flash(f'Erro ao gerar receita: {error}', 'danger')
                    return redirect(url_for('medico.gerar_receita', pedido_id=pedido_id))
                
                logger.info("✅ Receita gerada com sucesso pela IA")
                logger.info(f"Prescrição: {receita_data['prescricao'][:100]}...")
                
                logger.info("Salvando receita no banco de dados...")
                receita_id = receita_service.salvar_receita_no_banco(
                    consulta_id=pedido_info['consulta_id'],
                    diagnostico=diagnostico_completo,
                    prescricao=receita_data['prescricao'],
                    recomendacoes=receita_data['recomendacoes'],
                    medico_id=medico_id
                )
                
                if not receita_id:
                    logger.error("Falha ao salvar receita no banco - retornou None ou False")
                    flash('Erro ao salvar receita no banco de dados.', 'danger')
                    return redirect(url_for('medico.gerar_receita', pedido_id=pedido_id))
                
                logger.info(f"Receita salva com ID: {receita_id}")
                
                logger.info("Gerando PDF da receita...")
                pdf_path, pdf_bytes, pdf_error = receita_service.gerar_pdf_receita(
                    receita_id, receita_data, paciente_ia_info, medico_info_completo
                )
                
                if pdf_error:
                    logger.warning(f"Erro ao gerar PDF: {pdf_error}")
                    flash(f'Receita gerada, mas erro no PDF: {pdf_error}', 'warning')
                else:
                    logger.info(f"PDF gerado com sucesso: {pdf_path}")
                    flash('Receita gerada e salva com sucesso!', 'success')
                
                return render_template('medico/receita_gerada.html',
                                     receita=receita_data['receita_completa'],
                                     pedido=pedido_info,
                                     receita_id=receita_id,
                                     pdf_path=pdf_path,
                                     user=session,
                                     medico=medico_info,
                                     sinais_vitais=sinais_vitais)
            
            logger.info("Renderizando página de confirmação (GET)")
            return render_template('medico/confirmar_gerar_receita.html',
                                 pedido=pedido_info,
                                 user=session,
                                 medico=medico_info,
                                 diagnostico_completo=diagnostico_completo,
                                 fonte_diagnostico=fonte_diagnostico,
                                 gemini_available=gemini_available,
                                 sintomas_lista=sintomas_lista,
                                 sinais_vitais=sinais_vitais)
            
        except Exception as e:
            logger.error(f"Erro ao gerar receita: {e}")
            logger.error(traceback.format_exc())
            flash(f'Erro ao gerar receita: {str(e)}', 'danger')
            return redirect(url_for('medico.ver_detalhes_pedido', pedido_id=pedido_id))
    
    # ========== ROTA: VER RECEITA ==========
    @medico_required
    def ver_receita(receita_id):
        try:
            logger.info(f"Verificando receita #{receita_id}")
            
            medico_info = obter_info_medico()
            if not medico_info:
                flash('Informações do médico não encontradas.', 'danger')
                return redirect(url_for('auth.login'))
            
            medico_id = medico_info.get('id')
            
            receita = receita_service.buscar_receita_por_id(receita_id, medico_id)
            
            if not receita:
                logger.error(f"Receita #{receita_id} não encontrada")
                flash('Receita não encontrada.', 'danger')
                return redirect(url_for('medico.dashboard'))
            
            logger.info(f"Receita encontrada: Paciente={receita[11]}")
            
            idade = calcular_idade(receita[12]) if receita[12] else ''
            
            receita_info = {
                'id': receita[0], 
                'consulta_id': receita[1],
                'diagnostico': receita[2] or '', 
                'prescricao': receita[3] or '',
                'recomendacoes': receita[4] or '', 
                'status': receita[5] or '',
                'created_at': formatar_data(receita[6]),
                'receita_pdf_path': receita[7] or '', 
                'pdf_gerado': bool(receita[8]),
                'data_geracao_pdf': formatar_data(receita[9]),
                'paciente_id': receita[10], 
                'paciente_nome': receita[11] or 'Não informado',
                'paciente_data_nascimento': formatar_data(receita[12], '%d/%m/%Y') if receita[12] else '',
                'paciente_idade': idade, 
                'paciente_genero': receita[13] or '',
                'paciente_telefone': receita[14] or '', 
                'medico_id': receita[15]
            }
            
            # Buscar sinais vitais da consulta
            sinais_vitais = None
            if receita[1]:  # consulta_id
                sinais_query = """
                    SELECT pressao_arterial, frequencia_cardiaca, frequencia_respiratoria,
                           temperatura, saturacao_oxigenio, glicemia, peso, data_afericao, observacoes
                    FROM sinais_vitais
                    WHERE consulta_id = %s
                    ORDER BY data_afericao DESC
                    LIMIT 1
                """
                sinais_data = execute_query(sinais_query, (receita[1],), fetch=True, one=True)
                
                if sinais_data:
                    sinais_vitais = {
                        'pressao_arterial': sinais_data[0],
                        'frequencia_cardiaca': sinais_data[1],
                        'frequencia_respiratoria': sinais_data[2],
                        'temperatura': sinais_data[3],
                        'saturacao_oxigenio': sinais_data[4],
                        'glicemia': sinais_data[5],
                        'peso': float(sinais_data[6]) if sinais_data[6] else None,
                        'data_afericao': formatar_data(sinais_data[7], '%d/%m/%Y %H:%M') if sinais_data[7] else '',
                        'observacoes': sinais_data[8] or ''
                    }
            
            return render_template('medico/ver_receita.html',
                                 receita=receita_info,
                                 user=session,
                                 medico=medico_info,
                                 gemini_available=gemini_available,
                                 sinais_vitais=sinais_vitais)
            
        except Exception as e:
            logger.error(f"Erro ao ver receita: {e}")
            logger.error(traceback.format_exc())
            flash(f'Erro ao carregar receita: {str(e)}', 'danger')
            return redirect(url_for('medico.dashboard'))
    
    # ========== ROTA: DOWNLOAD PDF ==========
    @medico_required
    def download_receita_pdf(receita_id):
        try:
            logger.info(f"Download PDF da receita #{receita_id}")
            
            medico_info = obter_info_medico()
            if not medico_info:
                return jsonify({'error': 'Não autorizado'}), 401
            
            medico_id = medico_info.get('id')
            
            pdf_path, paciente_nome = receita_service.get_pdf_receita_path(receita_id, medico_id)
            
            if not pdf_path or not os.path.exists(pdf_path):
                logger.error(f"PDF não encontrado: {pdf_path}")
                flash('PDF não encontrado.', 'danger')
                return redirect(url_for('medico.ver_receita', receita_id=receita_id))
            
            filename = f"Receita_{paciente_nome.replace(' ', '_')}.pdf"
            logger.info(f"Enviando arquivo: {filename}")
            
            return send_file(
                pdf_path,
                as_attachment=True,
                download_name=filename,
                mimetype='application/pdf'
            )
            
        except Exception as e:
            logger.error(f"Erro ao baixar PDF: {e}")
            logger.error(traceback.format_exc())
            flash('Erro ao baixar PDF.', 'danger')
            return redirect(url_for('medico.ver_receita', receita_id=receita_id))
    
    # ========== ROTA: MINHAS RECEITAS ==========
    @medico_required
    def minhas_receitas():
        try:
            logger.info("Listando receitas do médico")
            
            medico_info = obter_info_medico()
            if not medico_info:
                flash('Informações do médico não encontradas.', 'danger')
                return redirect(url_for('auth.login'))
            
            medico_id = medico_info.get('id')
            if not medico_id or medico_id < 0:
                flash('Complete seu cadastro no perfil.', 'warning')
                return redirect(url_for('medico.perfil'))
            
            receitas_db = receita_service.listar_receitas_medico(medico_id)
            
            receitas_lista = []
            if receitas_db:
                logger.info(f"Encontradas {len(receitas_db)} receitas")
                for r in receitas_db:
                    idade = calcular_idade(r[11]) if r[11] else ''
                    receitas_lista.append({
                        'id': r[0], 
                        'consulta_id': r[1],
                        'diagnostico': r[2] or '', 
                        'prescricao': r[3] or '',
                        'recomendacoes': r[4] or '', 
                        'status': r[5] or '',
                        'created_at': formatar_data(r[6]),
                        'receita_pdf_path': r[7] or '', 
                        'pdf_gerado': bool(r[8]),
                        'data_geracao_pdf': formatar_data(r[9]),
                        'paciente_nome': r[10] or 'Não informado',
                        'paciente_idade': idade, 
                        'paciente_genero': r[12] or '',
                        'consulta_data': formatar_data(r[13])
                    })
            else:
                logger.info("Nenhuma receita encontrada")
            
            return render_template('medico/minhas_receitas.html',
                                 receitas=receitas_lista,
                                 user=session,
                                 medico=medico_info,
                                 gemini_available=gemini_available)
            
        except Exception as e:
            logger.error(f"Erro ao carregar receitas: {e}")
            logger.error(traceback.format_exc())
            flash(f'Erro ao carregar receitas: {str(e)}', 'danger')
            return redirect(url_for('medico.dashboard'))
    
    # ========== ROTA: GERAR PDF RECEITA (rota auxiliar) ==========
    @medico_required
    def gerar_pdf_receita_rota(receita_id):
        try:
            logger.info(f"Gerando PDF para receita #{receita_id} (rota auxiliar)")
            
            medico_info = obter_info_medico()
            if not medico_info:
                flash('Informações do médico não encontradas.', 'danger')
                return redirect(url_for('auth.login'))
            
            medico_id = medico_info.get('id')
            
            receita = receita_service.buscar_receita_por_id(receita_id, medico_id)
            
            if not receita:
                logger.error(f"Receita #{receita_id} não encontrada")
                flash('Receita não encontrada.', 'danger')
                return redirect(url_for('medico.dashboard'))
            
            idade = calcular_idade(receita[12]) if receita[12] else ''
            
            receita_data = {
                'diagnostico_resumo': receita[2] or '',
                'prescricao': receita[3] or '',
                'recomendacoes': receita[4] or '',
                'receita_completa': f"{receita[2] or ''}\n\n{receita[3] or ''}\n\n{receita[4] or ''}"
            }
            
            paciente_info = {
                'nome': receita[11] or 'Não informado',
                'idade': idade,
                'genero': receita[13] or ''
            }
            
            medico_info_completo = {
                'id': str(medico_info.get('id', '')),
                'nome': str(medico_info.get('nome', 'Dr. Não Informado')),
                'especialidade': str(medico_info.get('especialidade', 'Clínico Geral')),
                'crm': str(medico_info.get('crm', 'CRM não informado')),
                'usuario_id': str(medico_info.get('usuario_id', '')),
                'email': str(medico_info.get('email', ''))
            }
            
            logger.info("Chamando gerar_pdf_receita...")
            pdf_path, pdf_bytes, error = receita_service.gerar_pdf_receita(
                receita_id, receita_data, paciente_info, medico_info_completo
            )
            
            if error:
                logger.error(f"Erro ao gerar PDF: {error}")
                flash(f'Erro ao gerar PDF: {error}', 'danger')
                return redirect(url_for('medico.ver_receita', receita_id=receita_id))
            
            filename = f"Receita_{paciente_info['nome'].replace(' ', '_')}.pdf"
            logger.info(f"PDF gerado com sucesso: {filename}")
            
            return send_file(
                pdf_path,
                as_attachment=True,
                download_name=filename,
                mimetype='application/pdf'
            )
            
        except Exception as e:
            logger.error(f"Erro ao gerar PDF: {e}")
            logger.error(traceback.format_exc())
            flash(f'Erro ao gerar PDF: {str(e)}', 'danger')
            return redirect(url_for('medico.ver_receita', receita_id=receita_id))
    
    # ========== ROTA: EDITAR RECEITA ==========
    @medico_required
    def editar_receita(receita_id):
        """Editar uma receita existente"""
        try:
            logger.info(f"Editando receita #{receita_id}")
            
            medico_info = obter_info_medico()
            if not medico_info:
                flash('Informações do médico não encontradas.', 'danger')
                return redirect(url_for('auth.login'))
            
            medico_id = medico_info.get('id')
            
            # Buscar receita
            receita = receita_service.buscar_receita_por_id(receita_id, medico_id)
            
            if not receita:
                logger.error(f"Receita #{receita_id} não encontrada")
                flash('Receita não encontrada.', 'danger')
                return redirect(url_for('medico.minhas_receitas'))
            
            if request.method == 'POST':
                # Atualizar receita
                diagnostico = request.form.get('diagnostico', '')
                prescricao = request.form.get('prescricao', '')
                recomendacoes = request.form.get('recomendacoes', '')
                
                # Verificar se a receita pertence ao médico
                check = execute_query("""
                    SELECT r.id FROM receita r
                    JOIN consultas c ON r.consulta_id = c.id
                    WHERE r.id = %s AND c.medico_id = %s
                """, (receita_id, medico_id), fetch=True, one=True)
                
                if not check:
                    flash('Você não tem permissão para editar esta receita.', 'danger')
                    return redirect(url_for('medico.minhas_receitas'))
                
                # Atualizar no banco
                result = execute_query("""
                    UPDATE receita 
                    SET diagnostico = %s,
                        prescricao = %s,
                        recomendacoes = %s,
                        status = 'ativa'
                    WHERE id = %s
                """, (diagnostico, prescricao, recomendacoes, receita_id))
                
                if result:
                    logger.info(f"Receita #{receita_id} atualizada com sucesso")
                    flash('Receita atualizada com sucesso!', 'success')
                    return redirect(url_for('medico.ver_receita', receita_id=receita_id))
                else:
                    logger.error(f"Erro ao atualizar receita #{receita_id}")
                    flash('Erro ao atualizar receita.', 'danger')
            
            # Preparar dados para o template
            idade = calcular_idade(receita[12]) if receita[12] else ''
            
            receita_info = {
                'id': receita[0],
                'consulta_id': receita[1],
                'diagnostico': receita[2] or '',
                'prescricao': receita[3] or '',
                'recomendacoes': receita[4] or '',
                'status': receita[5] or '',
                'created_at': formatar_data(receita[6]),
                'paciente_nome': receita[11] or 'Não informado',
                'paciente_idade': idade,
                'paciente_genero': receita[13] or ''
            }
            
            # Buscar sinais vitais da consulta
            sinais_vitais = None
            if receita[1]:  # consulta_id
                sinais_query = """
                    SELECT pressao_arterial, frequencia_cardiaca, frequencia_respiratoria,
                           temperatura, saturacao_oxigenio, glicemia, peso, data_afericao, observacoes
                    FROM sinais_vitais
                    WHERE consulta_id = %s
                    ORDER BY data_afericao DESC
                    LIMIT 1
                """
                sinais_data = execute_query(sinais_query, (receita[1],), fetch=True, one=True)
                
                if sinais_data:
                    sinais_vitais = {
                        'pressao_arterial': sinais_data[0],
                        'frequencia_cardiaca': sinais_data[1],
                        'frequencia_respiratoria': sinais_data[2],
                        'temperatura': sinais_data[3],
                        'saturacao_oxigenio': sinais_data[4],
                        'glicemia': sinais_data[5],
                        'peso': float(sinais_data[6]) if sinais_data[6] else None,
                        'data_afericao': formatar_data(sinais_data[7], '%d/%m/%Y %H:%M') if sinais_data[7] else '',
                        'observacoes': sinais_data[8] or ''
                    }
            
            return render_template('medico/editar_receita.html',
                                 receita=receita_info,
                                 user=session,
                                 medico=medico_info,
                                 gemini_available=gemini_available,
                                 sinais_vitais=sinais_vitais)
            
        except Exception as e:
            logger.error(f"Erro ao editar receita: {e}")
            logger.error(traceback.format_exc())
            flash(f'Erro ao editar receita: {str(e)}', 'danger')
            return redirect(url_for('medico.ver_receita', receita_id=receita_id))
    
    # ========== RETORNO DAS ROTAS ==========
    return {
        'routes': [
            {'rule': '/pedidos/<int:pedido_id>/gerar-receita', 'view_func': gerar_receita, 'methods': ['GET', 'POST']},
            {'rule': '/receita/<int:receita_id>', 'view_func': ver_receita, 'methods': ['GET']},
            {'rule': '/receita/<int:receita_id>/download', 'view_func': download_receita_pdf, 'methods': ['GET']},
            {'rule': '/receita/<int:receita_id>/gerar-pdf', 'view_func': gerar_pdf_receita_rota, 'methods': ['GET']},
            {'rule': '/receita/<int:receita_id>/editar', 'view_func': editar_receita, 'methods': ['GET', 'POST']},
            {'rule': '/minhas-receitas', 'view_func': minhas_receitas, 'methods': ['GET']}
        ]
    }

# 👈 EXPORTAR A FUNÇÃO COM O NOME CORRETO
__all__ = ['init_medico_receitas']