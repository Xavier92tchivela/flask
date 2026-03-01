# routes/medico/routes/receitas.py
from flask import render_template, session, flash, redirect, url_for, request, jsonify, send_file
import logging
import traceback
import os
from datetime import datetime

logger = logging.getLogger(__name__)

def register_receitas_routes(bp, medico_required, execute_query, receita_service, formatar_data, calcular_idade):
    
    @bp.route('/receitas')
    @medico_required
    def listar_receitas():
        """Lista todas as receitas do médico"""
        try:
            medico_id = session.get('medico_id')
            receitas = receita_service.listar_receitas_medico(medico_id)
            return render_template('medico/receitas.html', receitas=receitas)
        except Exception as e:
            logger.error(f"Erro ao listar receitas: {e}")
            flash('Erro ao carregar receitas.', 'danger')
            return redirect(url_for('medico.dashboard'))

    @bp.route('/receita/<int:receita_id>')
    @medico_required
    def ver_receita(receita_id):
        """Visualizar uma receita específica"""
        try:
            medico_id = session.get('medico_id')
            receita = receita_service.buscar_receita_por_id(receita_id, medico_id)
            
            if not receita:
                flash('Receita não encontrada.', 'danger')
                return redirect(url_for('medico.listar_receitas'))
            
            # Buscar informações adicionais
            consulta_info = execute_query("""
                SELECT c.paciente_id, c.data_hora, p_u.nome as paciente_nome
                FROM consultas c
                LEFT JOIN pacientes p ON c.paciente_id = p.id
                LEFT JOIN usuarios p_u ON p.usuario_id = p_u.id
                WHERE c.id = %s
            """, (receita[1],), fetch=True, one=True)
            
            return render_template('medico/ver_receita.html',
                                 receita=receita,
                                 consulta=consulta_info,
                                 agora=datetime.now())
            
        except Exception as e:
            logger.error(f"Erro ao ver receita: {e}")
            flash('Erro ao carregar receita.', 'danger')
            return redirect(url_for('medico.listar_receitas'))

    @bp.route('/receita/<int:receita_id>/editar', methods=['GET', 'POST'])
    @medico_required
    def editar_receita(receita_id):
        """Editar uma receita existente"""
        try:
            medico_id = session.get('medico_id')
            
            if request.method == 'POST':
                diagnostico = request.form.get('diagnostico', '').strip()
                prescricao = request.form.get('prescricao', '').strip()
                recomendacoes = request.form.get('recomendacoes', '').strip()
                
                if not diagnostico or not prescricao:
                    flash('Diagnóstico e prescrição são obrigatórios.', 'warning')
                    return redirect(url_for('medico.editar_receita', receita_id=receita_id))
                
                # Atualizar receita
                result = execute_query("""
                    UPDATE receita 
                    SET diagnostico = %s,
                        prescricao = %s,
                        recomendacoes = %s,
                        status = 'ativa'
                    WHERE id = %s AND EXISTS (
                        SELECT 1 FROM consultas c 
                        WHERE c.id = receita.consulta_id AND c.medico_id = %s
                    )
                """, (diagnostico, prescricao, recomendacoes, receita_id, medico_id), commit=True)
                
                if result:
                    flash('Receita atualizada com sucesso!', 'success')
                    return redirect(url_for('medico.ver_receita', receita_id=receita_id))
                else:
                    flash('Erro ao atualizar receita.', 'danger')
                    return redirect(url_for('medico.listar_receitas'))
            
            # GET - carregar formulário com dados atuais
            receita = receita_service.buscar_receita_por_id(receita_id, medico_id)
            
            if not receita:
                flash('Receita não encontrada.', 'danger')
                return redirect(url_for('medico.listar_receitas'))
            
            return render_template('medico/editar_receita.html',
                                 receita=receita,
                                 agora=datetime.now())
            
        except Exception as e:
            logger.error(f"Erro ao editar receita: {e}")
            flash('Erro ao processar edição.', 'danger')
            return redirect(url_for('medico.listar_receitas'))

    @bp.route('/receita/<int:receita_id>/pdf')
    @medico_required
    def download_receita_pdf(receita_id):
        """Download do PDF da receita"""
        try:
            medico_id = session.get('medico_id')
            
            # Buscar caminho do PDF
            pdf_path, paciente_nome = receita_service.get_pdf_receita_path(receita_id, medico_id)
            
            if not pdf_path or not os.path.exists(pdf_path):
                # Se PDF não existe, gerar novamente
                logger.info(f"PDF não encontrado para receita {receita_id}. Gerando novamente...")
                
                # Buscar dados da receita
                receita = receita_service.buscar_receita_por_id(receita_id, medico_id)
                if not receita:
                    flash('Receita não encontrada.', 'danger')
                    return redirect(url_for('medico.listar_receitas'))
                
                # Buscar informações do paciente e médico
                consulta_info = execute_query("""
                    SELECT 
                        p_u.nome as paciente_nome,
                        p.data_nascimento,
                        p.genero,
                        m_u.nome as medico_nome,
                        m.especialidade,
                        m.crm
                    FROM consultas c
                    JOIN pacientes p ON c.paciente_id = p.id
                    JOIN usuarios p_u ON p.usuario_id = p_u.id
                    JOIN medicos m ON c.medico_id = m.id
                    JOIN usuarios m_u ON m.usuario_id = m_u.id
                    WHERE c.id = %s
                """, (receita[1],), fetch=True, one=True)
                
                if consulta_info:
                    paciente_info = {
                        'nome': consulta_info[0],
                        'idade': calcular_idade(consulta_info[1]),
                        'genero': consulta_info[2]
                    }
                    medico_info = {
                        'nome': consulta_info[3],
                        'especialidade': consulta_info[4],
                        'crm': consulta_info[5]
                    }
                    
                    receita_data = {
                        'prescricao': receita[3],
                        'recomendacoes': receita[4],
                        'diagnostico_resumo': receita[2]
                    }
                    
                    # Gerar PDF
                    pdf_path, pdf_bytes, erro = receita_service.gerar_pdf_receita(
                        receita_id, receita_data, paciente_info, medico_info
                    )
                    
                    if erro or not pdf_path:
                        flash(f'Erro ao gerar PDF: {erro}', 'danger')
                        return redirect(url_for('medico.ver_receita', receita_id=receita_id))
                    
                    # Obter novo caminho
                    pdf_path, paciente_nome = receita_service.get_pdf_receita_path(receita_id, medico_id)
            
            # Enviar arquivo
            return send_file(
                pdf_path,
                as_attachment=True,
                download_name=f"receita_{paciente_nome.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf",
                mimetype='application/pdf'
            )
            
        except Exception as e:
            logger.error(f"Erro ao baixar PDF: {e}")
            flash('Erro ao baixar PDF.', 'danger')
            return redirect(url_for('medico.ver_receita', receita_id=receita_id))

    @bp.route('/gerar_receita/<int:pedido_id>')
    @medico_required
    def gerar_receita(pedido_id):
        """Gerar receita baseada no diagnóstico do pedido"""
        try:
            medico_id = session.get('medico_id')
            
            # Buscar informações do pedido, consulta, paciente e diagnóstico
            pedido_info = execute_query("""
                SELECT 
                    pa.id, pa.consulta_id, pa.tipo_exame, pa.descricao,
                    pa.observacoes, pa.resultado_analise, pa.diagnostico_analista,
                    pa.recomendacoes_analista,
                    c.id as consulta_id,
                    c.sintomas,
                    c.observacoes as consulta_observacoes,
                    p.id as paciente_id,
                    p_u.nome as paciente_nome,
                    p.data_nascimento,
                    p.genero,
                    m.id as medico_id,
                    m_u.nome as medico_nome,
                    m.especialidade,
                    m.crm
                FROM pedidos_analise pa
                JOIN consultas c ON pa.consulta_id = c.id
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios p_u ON p.usuario_id = p_u.id
                JOIN medicos m ON c.medico_id = m.id
                JOIN usuarios m_u ON m.usuario_id = m_u.id
                WHERE pa.id = %s AND c.medico_id = %s
            """, (pedido_id, medico_id), fetch=True, one=True)
            
            if not pedido_info:
                flash('Pedido não encontrado.', 'danger')
                return redirect(url_for('medico.pedidos_analise'))
            
            # Extrair dados
            consulta_id = pedido_info[1]
            diagnostico_completo = f"""
            TIPO DE EXAME: {pedido_info[2] or 'Não especificado'}
            
            DESCRIÇÃO: {pedido_info[3] or 'Não informada'}
            
            OBSERVAÇÕES: {pedido_info[4] or 'Nenhuma'}
            
            RESULTADO DA ANÁLISE:
            {pedido_info[5] or 'Não disponível'}
            
            DIAGNÓSTICO DO ANALISTA:
            {pedido_info[6] or 'Não disponível'}
            
            RECOMENDAÇÕES DO ANALISTA:
            {pedido_info[7] or 'Nenhuma'}
            
            OBSERVAÇÕES DA CONSULTA:
            {pedido_info[10] or 'Nenhuma'}
            """
            
            # Extrair sintomas
            sintomas = pedido_info[9]
            
            paciente_info = {
                'nome': pedido_info[12],
                'idade': calcular_idade(pedido_info[13]),
                'genero': pedido_info[14]
            }
            
            medico_info = {
                'nome': pedido_info[16],
                'especialidade': pedido_info[17],
                'crm': pedido_info[18]
            }
            
            # Gerar receita com IA
            receita_data, erro = receita_service.gerar_receita_ia(
                diagnostico_completo, 
                paciente_info, 
                medico_info,
                sintomas
            )
            
            if erro:
                flash(f'Erro ao gerar receita: {erro}', 'danger')
                return redirect(url_for('medico.ver_detalhes_pedido', pedido_id=pedido_id))
            
            # Salvar no banco
            receita_id = receita_service.salvar_receita_no_banco(
                consulta_id=consulta_id,
                diagnostico=diagnostico_completo,
                prescricao=receita_data['prescricao'],
                recomendacoes=receita_data['recomendacoes'],
                medico_id=medico_id
            )
            
            if not receita_id:
                flash('Erro ao salvar receita no banco.', 'danger')
                return redirect(url_for('medico.ver_detalhes_pedido', pedido_id=pedido_id))
            
            # Gerar PDF
            pdf_path, pdf_bytes, erro_pdf = receita_service.gerar_pdf_receita(
                receita_id, receita_data, paciente_info, medico_info
            )
            
            if erro_pdf:
                flash(f'Receita salva, mas erro ao gerar PDF: {erro_pdf}', 'warning')
            
            flash('Receita gerada com sucesso!', 'success')
            
            # 🔥 CORREÇÃO AQUI: usar o endpoint correto
            # ANTES (ERRADO): redirect(url_for('medico.detalhes_consulta', consulta_id=consulta_id))
            # DEPOIS (CORRETO):
            return redirect(url_for('medico.consulta.detalhes_consulta', consulta_id=consulta_id))
            
        except Exception as e:
            logger.error(f"Erro ao gerar receita: {e}")
            logger.error(traceback.format_exc())
            flash(f'Erro ao gerar receita: {str(e)}', 'danger')
            return redirect(url_for('medico.ver_detalhes_pedido', pedido_id=pedido_id))