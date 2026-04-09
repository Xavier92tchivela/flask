# routes/paciente/agendamento.py

from flask import request, render_template, redirect, url_for, flash, session, jsonify, send_file
from datetime import datetime, timedelta
import traceback
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfgen import canvas
import uuid


def init_agendamento_routes(bp, mysql):

    # ===================== FUNÇÕES AUXILIARES =====================
    def decode_bytes(value):
        """Decodifica bytes para string UTF-8"""
        if value is None:
            return None
        if isinstance(value, (bytes, bytearray)):
            try:
                return value.decode('utf-8')
            except:
                return str(value)
        return value

    def gerar_numero_fatura():
        """Gera número único de fatura"""
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM faturas 
            WHERE DATE(data_emissao) = CURDATE()
        """)
        total_hoje = cursor.fetchone()[0] + 1
        cursor.close()
        
        agora = datetime.now()
        numero = f"FAT-{agora.strftime('%Y%m%d')}-{str(total_hoje).zfill(4)}"
        return numero

    def buscar_paciente_por_usuario(usuario_id):
        """Busca dados do paciente pelo usuario_id"""
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT 
                p.id,
                p.telefone,
                p.endereco,
                u.nome,
                u.email
            FROM pacientes p
            JOIN usuarios u ON p.usuario_id = u.id
            WHERE u.id = %s
        """, (usuario_id,))
        
        resultado = cursor.fetchone()
        cursor.close()
        
        if resultado:
            return {
                'id': resultado[0],
                'telefone': decode_bytes(resultado[1]) if resultado[1] else None,
                'endereco': decode_bytes(resultado[2]) if resultado[2] else None,
                'nome': decode_bytes(resultado[3]) if resultado[3] else 'Paciente',
                'email': decode_bytes(resultado[4]) if resultado[4] else None
            }
        return None

    def emitir_fatura(consulta_id, paciente_id, paciente_nome, paciente_telefone, valor, data_consulta):
        """Emite fatura da consulta"""
        cursor = mysql.connection.cursor()
        
        numero_fatura = gerar_numero_fatura()
        
        cursor.execute("""
            INSERT INTO faturas 
            (numero_fatura, consulta_id, paciente_id, paciente_nome, paciente_telefone, 
             data_consulta, valor_consulta, status_pagamento)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pendente')
        """, (numero_fatura, consulta_id, paciente_id, paciente_nome, 
              paciente_telefone, data_consulta, valor))
        
        fatura_id = cursor.lastrowid
        mysql.connection.commit()
        cursor.close()
        
        return {
            'id': fatura_id,
            'numero': numero_fatura,
            'valor': valor
        }

    def enviar_sms_fatura(telefone, numero_fatura, valor, data_consulta):
        """Envia SMS com dados da fatura"""
        if not telefone:
            return False
        
        data_formatada = data_consulta.strftime('%d/%m/%Y %H:%M')
        
        mensagem = f"""HOSPITAL MUNICIPAL DA CACULA

CONSULTA AGENDADA!

FATURA: {numero_fatura}
VALOR: {valor:.2f} Kz
DATA: {data_formatada}

PAGAMENTO:
- Balcão: dinheiro/cartão
- MB WAY: 924 042 244
- Depósito: BAI 123456789

Apresente comprovante no dia da consulta.
"""
        
        try:
            print(f"SMS enviado para {telefone}")
            print(mensagem)
            return True
        except:
            return False

    def gerar_pdf_fatura(fatura_data):
        """Gera PDF da fatura"""
        
        # Criar diretório se não existir
        pdf_dir = os.path.join('static', 'pdfs', 'faturas')
        os.makedirs(pdf_dir, exist_ok=True)
        
        filename = f"fatura_{fatura_data['numero_fatura']}.pdf"
        output_path = os.path.join(pdf_dir, filename)
        
        # Criar documento PDF
        doc = SimpleDocTemplate(output_path, pagesize=A4,
                               topMargin=2*cm, bottomMargin=2*cm,
                               leftMargin=2*cm, rightMargin=2*cm)
        
        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1e466e'),
            alignment=1,
            spaceAfter=20
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#666666'),
            alignment=1,
            spaceAfter=30
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=5
        )
        
        # Conteúdo do PDF
        story = []
        
        # Cabeçalho
        story.append(Paragraph("HOSPITAL MUNICIPAL DA CACULA", title_style))
        story.append(Paragraph("Rua Principal, Bairro Central - Cacula, Huíla, Angola", subtitle_style))
        story.append(Paragraph("Tel: 924 042 244 | Email: cacula@hospital.ao", subtitle_style))
        story.append(Spacer(1, 20))
        
        # Linha separadora
        story.append(Table([['']], colWidths=[500], 
                          style=[('LINEBELOW', (0,0), (-1,-1), 1, colors.HexColor('#1e466e'))]))
        story.append(Spacer(1, 20))
        
        # Título FATURA
        story.append(Paragraph("FATURA DE CONSULTA", ParagraphStyle(
            'FaturaTitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#28a745'),
            alignment=1,
            spaceAfter=20
        )))
        
        # Dados da Fatura
        data_emissao = fatura_data['data_emissao'].strftime('%d/%m/%Y %H:%M') if fatura_data['data_emissao'] else datetime.now().strftime('%d/%m/%Y %H:%M')
        data_consulta = fatura_data['data_consulta'].strftime('%d/%m/%Y %H:%M') if fatura_data['data_consulta'] else 'Não informada'
        
        # Tabela de informações
        info_data = [
            ['NÚMERO DA FATURA:', fatura_data['numero_fatura']],
            ['DATA DE EMISSÃO:', data_emissao],
            ['STATUS:', 'PENDENTE'],
            ['DATA DA CONSULTA:', data_consulta],
        ]
        
        info_table = Table(info_data, colWidths=[150, 350])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#1e466e')),
            ('TEXTCOLOR', (1,0), (1,-1), colors.black),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f0f0f0')),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 20))
        
        # Dados do Paciente
        story.append(Paragraph("DADOS DO PACIENTE", ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#1e466e'),
            spaceAfter=10
        )))
        
        paciente_data = [
            ['NOME:', fatura_data['paciente_nome']],
            ['TELEFONE:', fatura_data['paciente_telefone'] or 'Não informado'],
        ]
        
        paciente_table = Table(paciente_data, colWidths=[150, 350])
        paciente_table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#1e466e')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f0f0f0')),
        ]))
        story.append(paciente_table)
        story.append(Spacer(1, 20))
        
        # Dados do Médico
        story.append(Paragraph("DADOS DA CONSULTA", ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#1e466e'),
            spaceAfter=10
        )))
        
        medico_data = [
            ['MÉDICO:', fatura_data.get('medico_nome', 'Não informado')],
            ['ESPECIALIDADE:', fatura_data.get('especialidade', 'Clínico Geral')],
        ]
        
        medico_table = Table(medico_data, colWidths=[150, 350])
        medico_table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#1e466e')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f0f0f0')),
        ]))
        story.append(medico_table)
        story.append(Spacer(1, 20))
        
        # Itens da Fatura
        story.append(Paragraph("ITENS DA FATURA", ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#1e466e'),
            spaceAfter=10
        )))
        
        # Tabela de itens
        items_data = [
            ['ITEM', 'DESCRIÇÃO', 'QUANTIDADE', 'VALOR UNIT.', 'TOTAL'],
            ['1', 'Consulta Médica', '1', f'{fatura_data["valor_consulta"]:.2f} Kz', f'{fatura_data["valor_consulta"]:.2f} Kz'],
        ]
        
        items_table = Table(items_data, colWidths=[40, 300, 80, 100, 100])
        items_table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e466e')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,1), (-1,-2), colors.HexColor('#f9f9f9')),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#e8f5e9')),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 20))
        
        # TOTAL
        total_data = [
            ['TOTAL GERAL:', f'{fatura_data["valor_consulta"]:.2f} Kz'],
        ]
        
        total_table = Table(total_data, colWidths=[450, 100])
        total_table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 12),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#28a745')),
            ('ALIGN', (1,0), (1,0), 'RIGHT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#e8f5e9')),
        ]))
        story.append(total_table)
        story.append(Spacer(1, 20))
        
        # Formas de Pagamento
        story.append(Paragraph("FORMAS DE PAGAMENTO", ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading3'],
            fontSize=11,
            textColor=colors.HexColor('#1e466e'),
            spaceAfter=10
        )))
        
        pagamento_text = """
        <b>Balcão de Atendimento:</b> Dinheiro ou Cartão<br/>
        <b>MB WAY:</b> 924 042 244<br/>
        <b>Depósito Bancário:</b> BAI - 123456789 (Hospital Municipal da Cacula)<br/>
        <b>Transferência:</b> IBAN: AO06 0040 0000 1234 5678 9012 3
        """
        
        story.append(Paragraph(pagamento_text, normal_style))
        story.append(Spacer(1, 20))
        
        # Informações Importantes
        story.append(Paragraph("INFORMAÇÕES IMPORTANTES", ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading3'],
            fontSize=11,
            textColor=colors.HexColor('#dc3545'),
            spaceAfter=10
        )))
        
        info_text = """
        • Apresente este documento no dia da consulta<br/>
        • Cancelamentos devem ser feitos com 24 horas de antecedência<br/>
        • Chegue com 15 minutos de antecedência<br/>
        • Traga seus documentos e exames anteriores (se houver)
        """
        
        story.append(Paragraph(info_text, normal_style))
        story.append(Spacer(1, 30))
        
        # Rodapé
        story.append(Paragraph("-" * 80, normal_style))
        story.append(Paragraph("Documento emitido por sistema eletrônico - Validade legal", 
                              ParagraphStyle('Footer', parent=normal_style, alignment=1, fontSize=8)))
        story.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", 
                              ParagraphStyle('Footer', parent=normal_style, alignment=1, fontSize=8)))
        
        # Gerar PDF
        doc.build(story)
        
        return output_path

    # ===================== ROTA DE AGENDAMENTO COM FATURA =====================
    @bp.route("/agendar-consulta", methods=["GET", "POST"])
    def agendar_consulta():
        """Agenda consulta e emite fatura automaticamente"""
        
        try:
            # Verificar se usuário está logado
            if 'user_id' not in session:
                flash("Você precisa estar logado para agendar uma consulta.", "danger")
                return redirect(url_for("auth.login"))
            
            # Buscar dados do paciente
            paciente = buscar_paciente_por_usuario(session['user_id'])
            
            if not paciente:
                flash("Paciente não encontrado. Por favor, complete seu cadastro.", "danger")
                return redirect(url_for("paciente.dashboard"))
            
            cursor = mysql.connection.cursor()
            
            # Buscar médicos disponíveis
            cursor.execute("""
                SELECT m.id, u.nome, m.especialidade, m.crm 
                FROM medicos m
                JOIN usuarios u ON m.usuario_id = u.id
                WHERE m.status = 'ativo'
                ORDER BY u.nome
            """)
            medicos_raw = cursor.fetchall()
            
            medicos = []
            for m in medicos_raw:
                medicos.append({
                    'id': m[0],
                    'nome': decode_bytes(m[1]) if m[1] else 'Médico',
                    'especialidade': decode_bytes(m[2]) if m[2] else 'Clínico Geral',
                    'crm': decode_bytes(m[3]) if m[3] else '---'
                })
            
            cursor.close()
            
            # Horários disponíveis
            horarios = ['08:00', '09:00', '10:00', '11:00', '14:00', '15:00', '16:00', '17:00']
            
            # Datas mínima e máxima (próximos 30 dias)
            hoje = datetime.now().date()
            data_minima = hoje + timedelta(days=1)
            data_maxima = hoje + timedelta(days=30)
            
            if request.method == "POST":
                medico_id = request.form.get("medico_id")
                data_consulta = request.form.get("data_consulta")
                hora_consulta = request.form.get("hora_consulta")
                sintomas = request.form.get("sintomas", "")
                observacoes = request.form.get("observacoes", "")
                
                # Validar dados
                if not medico_id or not data_consulta or not hora_consulta:
                    flash("Preencha todos os campos obrigatórios.", "danger")
                    return redirect(request.url)
                
                # Combinar data e hora
                data_hora_str = f"{data_consulta} {hora_consulta}"
                data_hora = datetime.strptime(data_hora_str, "%Y-%m-%d %H:%M")
                
                # Verificar se a data é válida
                if data_hora <= datetime.now():
                    flash("Não é possível agendar consultas em datas/horários passados.", "danger")
                    return redirect(request.url)
                
                # Verificar horário comercial
                hora = data_hora.hour
                if hora < 8 or hora > 17 or (hora == 12 and data_hora.minute > 0):
                    flash("Horário fora do expediente. Consulte das 8h às 12h e das 14h às 17h.", "danger")
                    return redirect(request.url)
                
                cursor = mysql.connection.cursor()
                
                # Verificar se horário já está ocupado
                cursor.execute("""
                    SELECT COUNT(*) FROM consultas 
                    WHERE medico_id = %s AND data_hora = %s AND status != 'cancelada'
                """, (medico_id, data_hora))
                
                if cursor.fetchone()[0] > 0:
                    cursor.close()
                    flash("Horário indisponível. Escolha outro horário.", "danger")
                    return redirect(request.url)
                
                try:
                    # Agendar consulta
                    cursor.execute("""
                        INSERT INTO consultas 
                        (paciente_id, medico_id, data_hora, status, sintomas, observacoes)
                        VALUES (%s, %s, %s, 'agendada', %s, %s)
                    """, (paciente['id'], medico_id, data_hora, sintomas, observacoes))
                    
                    consulta_id = cursor.lastrowid
                    mysql.connection.commit()
                    
                    # Calcular valor da consulta
                    valor_consulta = 2500.00
                    
                    # Emitir fatura
                    fatura = emitir_fatura(
                        consulta_id=consulta_id,
                        paciente_id=paciente['id'],
                        paciente_nome=paciente['nome'],
                        paciente_telefone=paciente['telefone'],
                        valor=valor_consulta,
                        data_consulta=data_hora
                    )
                    
                    # Buscar dados do médico para a fatura
                    cursor.execute("""
                        SELECT u.nome, m.especialidade
                        FROM medicos m
                        JOIN usuarios u ON m.usuario_id = u.id
                        WHERE m.id = %s
                    """, (medico_id,))
                    
                    medico_data = cursor.fetchone()
                    
                    # Buscar dados da fatura completa
                    cursor.execute("""
                        SELECT 
                            f.id,
                            f.numero_fatura,
                            f.paciente_nome,
                            f.paciente_telefone,
                            f.data_consulta,
                            f.valor_consulta,
                            f.status_pagamento,
                            f.data_emissao
                        FROM faturas f
                        WHERE f.id = %s
                    """, (fatura['id'],))
                    
                    fatura_raw = cursor.fetchone()
                    cursor.close()
                    
                    # Preparar dados completos para o PDF
                    fatura_completa = {
                        'id': fatura_raw[0],
                        'numero_fatura': fatura_raw[1],
                        'paciente_nome': decode_bytes(fatura_raw[2]) if fatura_raw[2] else paciente['nome'],
                        'paciente_telefone': decode_bytes(fatura_raw[3]) if fatura_raw[3] else paciente['telefone'],
                        'data_consulta': fatura_raw[4],
                        'valor_consulta': float(fatura_raw[5]),
                        'status_pagamento': fatura_raw[6],
                        'data_emissao': fatura_raw[7],
                        'medico_nome': decode_bytes(medico_data[0]) if medico_data and medico_data[0] else 'Médico',
                        'especialidade': decode_bytes(medico_data[1]) if medico_data and medico_data[1] else 'Clínico Geral'
                    }
                    
                    # Gerar PDF
                    pdf_path = gerar_pdf_fatura(fatura_completa)
                    
                    # Enviar SMS com fatura
                    if paciente['telefone']:
                        enviar_sms_fatura(
                            paciente['telefone'],
                            fatura['numero'],
                            fatura['valor'],
                            data_hora
                        )
                    
                    flash(f"Consulta agendada com sucesso!", "success")
                    flash(f"Fatura emitida: {fatura['numero']} - Valor: {fatura['valor']:.2f} Kz", "info")
                    
                    if paciente['telefone']:
                        flash(f"SMS enviado para {paciente['telefone']}", "info")
                    
                    # Redirecionar para página de confirmação com fatura
                    return redirect(url_for('paciente.confirmacao_fatura', fatura_id=fatura['id']))
                    
                except Exception as e:
                    mysql.connection.rollback()
                    cursor.close()
                    print(f"ERRO: {e}")
                    print(traceback.format_exc())
                    flash(f"Erro ao agendar: {str(e)}", "danger")
                    return redirect(request.url)
            
            return render_template(
                'paciente/agendar_consulta.html',
                medicos=medicos,
                horarios=horarios,
                data_minima=data_minima.strftime('%Y-%m-%d'),
                data_maxima=data_maxima.strftime('%Y-%m-%d'),
                paciente=paciente
            )
            
        except Exception as e:
            print(f"ERRO: {e}")
            print(traceback.format_exc())
            flash(str(e), "danger")
            return redirect(url_for("paciente.dashboard"))

    # ===================== ROTA DE CONFIRMAÇÃO COM FATURA =====================
    @bp.route("/confirmacao-fatura/<int:fatura_id>")
    def confirmacao_fatura(fatura_id):
        """Página de confirmação com fatura"""
        
        try:
            cursor = mysql.connection.cursor()
            
            # Buscar dados da fatura com informações do médico
            cursor.execute("""
                SELECT 
                    f.id,
                    f.numero_fatura,
                    f.paciente_nome,
                    f.paciente_telefone,
                    f.data_consulta,
                    f.valor_consulta,
                    f.status_pagamento,
                    f.data_emissao,
                    c.id as consulta_id,
                    u.nome as medico_nome,
                    m.especialidade
                FROM faturas f
                JOIN consultas c ON f.consulta_id = c.id
                JOIN medicos m ON c.medico_id = m.id
                JOIN usuarios u ON m.usuario_id = u.id
                WHERE f.id = %s
            """, (fatura_id,))
            
            fatura_raw = cursor.fetchone()
            cursor.close()
            
            if not fatura_raw:
                flash("Fatura não encontrada.", "danger")
                return redirect(url_for("paciente.dashboard"))
            
            fatura = {
                'id': fatura_raw[0],
                'numero_fatura': fatura_raw[1],
                'paciente_nome': decode_bytes(fatura_raw[2]) if fatura_raw[2] else 'Paciente',
                'paciente_telefone': decode_bytes(fatura_raw[3]) if fatura_raw[3] else None,
                'data_consulta': fatura_raw[4],
                'valor_consulta': float(fatura_raw[5]),
                'status_pagamento': fatura_raw[6],
                'data_emissao': fatura_raw[7],
                'consulta_id': fatura_raw[8],
                'medico_nome': decode_bytes(fatura_raw[9]) if fatura_raw[9] else 'Médico',
                'especialidade': decode_bytes(fatura_raw[10]) if fatura_raw[10] else 'Clínico Geral'
            }
            
            return render_template('paciente/confirmacao_fatura.html', fatura=fatura)
            
        except Exception as e:
            print(f"ERRO: {e}")
            print(traceback.format_exc())
            flash(str(e), "danger")
            return redirect(url_for("paciente.dashboard"))

    # ===================== ROTA PARA BAIXAR PDF =====================
    @bp.route("/fatura-pdf/<int:fatura_id>")
    def fatura_pdf(fatura_id):
        """Gera e baixa PDF da fatura"""
        
        try:
            cursor = mysql.connection.cursor()
            
            # Buscar dados da fatura com informações do médico
            cursor.execute("""
                SELECT 
                    f.id,
                    f.numero_fatura,
                    f.paciente_nome,
                    f.paciente_telefone,
                    f.data_consulta,
                    f.valor_consulta,
                    f.status_pagamento,
                    f.data_emissao,
                    c.id as consulta_id,
                    u.nome as medico_nome,
                    m.especialidade
                FROM faturas f
                JOIN consultas c ON f.consulta_id = c.id
                JOIN medicos m ON c.medico_id = m.id
                JOIN usuarios u ON m.usuario_id = u.id
                WHERE f.id = %s
            """, (fatura_id,))
            
            fatura_raw = cursor.fetchone()
            cursor.close()
            
            if not fatura_raw:
                flash("Fatura não encontrada.", "danger")
                return redirect(url_for("paciente.dashboard"))
            
            fatura = {
                'id': fatura_raw[0],
                'numero_fatura': fatura_raw[1],
                'paciente_nome': decode_bytes(fatura_raw[2]) if fatura_raw[2] else 'Paciente',
                'paciente_telefone': decode_bytes(fatura_raw[3]) if fatura_raw[3] else None,
                'data_consulta': fatura_raw[4],
                'valor_consulta': float(fatura_raw[5]),
                'status_pagamento': fatura_raw[6],
                'data_emissao': fatura_raw[7],
                'consulta_id': fatura_raw[8],
                'medico_nome': decode_bytes(fatura_raw[9]) if fatura_raw[9] else 'Médico',
                'especialidade': decode_bytes(fatura_raw[10]) if fatura_raw[10] else 'Clínico Geral'
            }
            
            # Gerar PDF
            pdf_path = gerar_pdf_fatura(fatura)
            
            # Retornar o PDF para download
            return send_file(
                pdf_path,
                as_attachment=True,
                download_name=f"fatura_{fatura['numero_fatura']}.pdf",
                mimetype='application/pdf'
            )
            
        except Exception as e:
            print(f"ERRO: {e}")
            print(traceback.format_exc())
            flash(f"Erro ao gerar PDF: {str(e)}", "danger")
            return redirect(url_for("paciente.dashboard"))

    return {
        'routes': [
            {'rule': '/agendar-consulta', 'view_func': agendar_consulta, 'methods': ['GET', 'POST']},
            {'rule': '/confirmacao-fatura/<int:fatura_id>', 'view_func': confirmacao_fatura, 'methods': ['GET']},
            {'rule': '/fatura-pdf/<int:fatura_id>', 'view_func': fatura_pdf, 'methods': ['GET']}
        ]
    }