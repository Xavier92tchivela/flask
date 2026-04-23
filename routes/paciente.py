from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, send_file, current_app
import pymysql
pymysql.install_as_MySQLdb()
import os
from datetime import datetime, timedelta, date
import traceback
import logging
from functools import wraps
import re
import uuid

logger = logging.getLogger(__name__)

def init_paciente(mysql, app):
    """Inicializa e retorna o blueprint do paciente"""
    
    paciente_bp = Blueprint('paciente', __name__, url_prefix='/paciente')
    
    # ========== FUNÇÃO PARA CONVERTER BYTES ==========
    def garantir_string(valor):
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
    
    # ========== FUNÇÕES DE FATURA ==========
    def gerar_numero_fatura():
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM faturas WHERE DATE(data_emissao) = CURDATE()")
        total_hoje = cursor.fetchone()[0] + 1
        cursor.close()
        agora = datetime.now()
        return f"FAT-{agora.strftime('%Y%m%d')}-{str(total_hoje).zfill(4)}"

    def emitir_fatura(consulta_id, paciente_id, paciente_nome, paciente_telefone, valor, data_consulta):
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
        return {'id': fatura_id, 'numero': numero_fatura, 'valor': valor}

    def gerar_pdf_fatura(fatura_data):
        pdf_dir = os.path.join(app.root_path, 'static', 'pdfs', 'faturas')
        os.makedirs(pdf_dir, exist_ok=True)
        filename = f"fatura_{fatura_data['numero_fatura']}.pdf"
        output_path = os.path.join(pdf_dir, filename)
        
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        
        doc = SimpleDocTemplate(output_path, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm,
                               leftMargin=2*cm, rightMargin=2*cm)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16,
                                     textColor=colors.HexColor('#1e466e'), alignment=1, spaceAfter=20)
        subtitle_style = ParagraphStyle('CustomSubtitle', parent=styles['Normal'], fontSize=12,
                                        textColor=colors.HexColor('#666666'), alignment=1, spaceAfter=30)
        normal_style = ParagraphStyle('CustomNormal', parent=styles['Normal'], fontSize=10, spaceAfter=5)
        
        story = []
        story.append(Paragraph("HOSPITAL MUNICIPAL DA CACULA", title_style))
        story.append(Paragraph("Rua Principal, Bairro Central - Cacula, Huíla, Angola", subtitle_style))
        story.append(Paragraph("Tel: 924 042 244 | Email: cacula@hospital.ao", subtitle_style))
        story.append(Spacer(1, 20))
        story.append(Table([['']], colWidths=[500], style=[('LINEBELOW', (0,0), (-1,-1), 1, colors.HexColor('#1e466e'))]))
        story.append(Spacer(1, 20))
        story.append(Paragraph("FATURA DE CONSULTA", ParagraphStyle('FaturaTitle', parent=styles['Heading2'],
                              fontSize=14, textColor=colors.HexColor('#28a745'), alignment=1, spaceAfter=20)))
        
        data_emissao = fatura_data['data_emissao'].strftime('%d/%m/%Y %H:%M') if fatura_data.get('data_emissao') else datetime.now().strftime('%d/%m/%Y %H:%M')
        data_consulta = fatura_data['data_consulta'].strftime('%d/%m/%Y %H:%M') if fatura_data.get('data_consulta') else 'Não informada'
        
        info_data = [
            ['NÚMERO DA FATURA:', fatura_data['numero_fatura']],
            ['DATA DE EMISSÃO:', data_emissao],
            ['STATUS:', 'PENDENTE'],
            ['DATA DA CONSULTA:', data_consulta],
        ]
        info_table = Table(info_data, colWidths=[150, 350])
        info_table.setStyle(TableStyle([('FONTNAME', (0,0), (-1,-1), 'Helvetica'), ('FONTSIZE', (0,0), (-1,-1), 10),
                                        ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#1e466e')),
                                        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                                        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f0f0f0'))]))
        story.append(info_table)
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("DADOS DO PACIENTE", ParagraphStyle('SectionTitle', parent=styles['Heading3'],
                              fontSize=12, textColor=colors.HexColor('#1e466e'), spaceAfter=10)))
        paciente_data = [['NOME:', fatura_data['paciente_nome']],
                        ['TELEFONE:', fatura_data.get('paciente_telefone', 'Não informado') or 'Não informado']]
        paciente_table = Table(paciente_data, colWidths=[150, 350])
        paciente_table.setStyle(TableStyle([('FONTNAME', (0,0), (-1,-1), 'Helvetica'), ('FONTSIZE', (0,0), (-1,-1), 10),
                                            ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#1e466e')),
                                            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                                            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f0f0f0'))]))
        story.append(paciente_table)
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("DADOS DA CONSULTA", ParagraphStyle('SectionTitle', parent=styles['Heading3'],
                              fontSize=12, textColor=colors.HexColor('#1e466e'), spaceAfter=10)))
        medico_data = [['MÉDICO:', fatura_data.get('medico_nome', 'Não informado')],
                       ['ESPECIALIDADE:', fatura_data.get('especialidade', 'Clínico Geral')]]
        medico_table = Table(medico_data, colWidths=[150, 350])
        medico_table.setStyle(TableStyle([('FONTNAME', (0,0), (-1,-1), 'Helvetica'), ('FONTSIZE', (0,0), (-1,-1), 10),
                                          ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#1e466e')),
                                          ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                                          ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f0f0f0'))]))
        story.append(medico_table)
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("ITENS DA FATURA", ParagraphStyle('SectionTitle', parent=styles['Heading3'],
                              fontSize=12, textColor=colors.HexColor('#1e466e'), spaceAfter=10)))
        items_data = [['ITEM', 'DESCRIÇÃO', 'QUANTIDADE', 'VALOR UNIT.', 'TOTAL'],
                      ['1', 'Consulta Médica', '1', f'{fatura_data["valor_consulta"]:.2f} Kz', f'{fatura_data["valor_consulta"]:.2f} Kz']]
        items_table = Table(items_data, colWidths=[40, 300, 80, 100, 100])
        items_table.setStyle(TableStyle([('FONTNAME', (0,0), (-1,-1), 'Helvetica'), ('FONTSIZE', (0,0), (-1,-1), 10),
                                         ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e466e')),
                                         ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                                         ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                                         ('BACKGROUND', (0,1), (-1,-2), colors.HexColor('#f9f9f9')),
                                         ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#e8f5e9')),
                                         ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold')]))
        story.append(items_table)
        story.append(Spacer(1, 20))
        
        total_data = [['TOTAL GERAL:', f'{fatura_data["valor_consulta"]:.2f} Kz']]
        total_table = Table(total_data, colWidths=[450, 100])
        total_table.setStyle(TableStyle([('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'), ('FONTSIZE', (0,0), (-1,-1), 12),
                                         ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#28a745')),
                                         ('ALIGN', (1,0), (1,0), 'RIGHT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                                         ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#e8f5e9'))]))
        story.append(total_table)
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("FORMAS DE PAGAMENTO", ParagraphStyle('SectionTitle', parent=styles['Heading3'],
                              fontSize=11, textColor=colors.HexColor('#1e466e'), spaceAfter=10)))
        pagamento_text = """<b>Balcão de Atendimento:</b> Dinheiro ou Cartão<br/>
        <b>MB WAY:</b> 924 042 244<br/>
        <b>Depósito Bancário:</b> BAI - 123456789 (Hospital Municipal da Cacula)<br/>
        <b>Transferência:</b> IBAN: AO06 0040 0000 1234 5678 9012 3"""
        story.append(Paragraph(pagamento_text, normal_style))
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("INFORMAÇÕES IMPORTANTES", ParagraphStyle('SectionTitle', parent=styles['Heading3'],
                              fontSize=11, textColor=colors.HexColor('#dc3545'), spaceAfter=10)))
        info_text = """• Apresente este documento no dia da consulta<br/>
        • Cancelamentos devem ser feitos com 24 horas de antecedência<br/>
        • Chegue com 15 minutos de antecedência<br/>
        • Traga seus documentos e exames anteriores (se houver)"""
        story.append(Paragraph(info_text, normal_style))
        story.append(Spacer(1, 30))
        
        story.append(Paragraph("-" * 80, normal_style))
        story.append(Paragraph("Documento emitido por sistema eletrônico - Validade legal", 
                              ParagraphStyle('Footer', parent=normal_style, alignment=1, fontSize=8)))
        story.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", 
                              ParagraphStyle('Footer', parent=normal_style, alignment=1, fontSize=8)))
        doc.build(story)
        return output_path

    def gerar_pdf_receita_completo(receita_data, app):
        pdf_dir = os.path.join(app.root_path, 'static', 'pdfs', 'receitas')
        os.makedirs(pdf_dir, exist_ok=True)
        filename = f"receita_{receita_data['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        output_path = os.path.join(pdf_dir, filename)
        
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        
        doc = SimpleDocTemplate(output_path, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm,
                               leftMargin=2*cm, rightMargin=2*cm)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16,
                                     textColor=colors.HexColor('#28a745'), alignment=1, spaceAfter=20)
        subtitle_style = ParagraphStyle('CustomSubtitle', parent=styles['Normal'], fontSize=10,
                                        textColor=colors.HexColor('#666666'), alignment=1, spaceAfter=30)
        normal_style = ParagraphStyle('CustomNormal', parent=styles['Normal'], fontSize=10, spaceAfter=5)
        
        story = []
        story.append(Paragraph("HOSPITAL MUNICIPAL DA CACULA", title_style))
        story.append(Paragraph("RECEITA MÉDICA", subtitle_style))
        story.append(Spacer(1, 20))
        
        info_data = [['NÚMERO DA RECEITA:', f"#{receita_data['id']}"],
                     ['DATA DE EMISSÃO:', receita_data['created_at'].strftime('%d/%m/%Y %H:%M') if receita_data['created_at'] else datetime.now().strftime('%d/%m/%Y %H:%M')],
                     ['STATUS:', receita_data['status'].upper() if receita_data['status'] else 'ATIVA']]
        info_table = Table(info_data, colWidths=[150, 350])
        info_table.setStyle(TableStyle([('FONTNAME', (0,0), (-1,-1), 'Helvetica'), ('FONTSIZE', (0,0), (-1,-1), 10),
                                        ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#1e466e')),
                                        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                                        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f0f0f0'))]))
        story.append(info_table)
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("MÉDICO RESPONSÁVEL", ParagraphStyle('SectionTitle', parent=styles['Heading3'],
                              fontSize=12, textColor=colors.HexColor('#1e466e'), spaceAfter=10)))
        medico_data = [['NOME:', receita_data['medico_nome']],
                       ['ESPECIALIDADE:', receita_data['especialidade']],
                       ['CRM:', receita_data['crm']]]
        medico_table = Table(medico_data, colWidths=[150, 350])
        medico_table.setStyle(TableStyle([('FONTNAME', (0,0), (-1,-1), 'Helvetica'), ('FONTSIZE', (0,0), (-1,-1), 10),
                                          ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#1e466e')),
                                          ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                                          ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f0f0f0'))]))
        story.append(medico_table)
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("PACIENTE", ParagraphStyle('SectionTitle', parent=styles['Heading3'],
                              fontSize=12, textColor=colors.HexColor('#1e466e'), spaceAfter=10)))
        idade_text = f"{receita_data.get('idade', 'N/I')} anos" if receita_data.get('idade') else 'Não informada'
        paciente_data = [['NOME:', receita_data['paciente_nome']],
                         ['IDADE:', idade_text],
                         ['GÊNERO:', receita_data.get('genero', 'Não informado')]]
        paciente_table = Table(paciente_data, colWidths=[150, 350])
        paciente_table.setStyle(TableStyle([('FONTNAME', (0,0), (-1,-1), 'Helvetica'), ('FONTSIZE', (0,0), (-1,-1), 10),
                                            ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#1e466e')),
                                            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                                            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f0f0f0'))]))
        story.append(paciente_table)
        story.append(Spacer(1, 20))
        
        if receita_data.get('diagnostico'):
            story.append(Paragraph("DIAGNÓSTICO", ParagraphStyle('SectionTitle', parent=styles['Heading3'],
                                  fontSize=12, textColor=colors.HexColor('#28a745'), spaceAfter=10)))
            diagnostico_text = receita_data['diagnostico'].replace('\n', '<br/>')
            story.append(Paragraph(diagnostico_text, normal_style))
            story.append(Spacer(1, 15))
        
        if receita_data.get('prescricao'):
            story.append(Paragraph("PRESCRIÇÃO MÉDICA", ParagraphStyle('SectionTitle', parent=styles['Heading3'],
                                  fontSize=12, textColor=colors.HexColor('#28a745'), spaceAfter=10)))
            prescricao_text = receita_data['prescricao'].replace('\n', '<br/>')
            story.append(Paragraph(prescricao_text, normal_style))
            story.append(Spacer(1, 15))
        
        if receita_data.get('recomendacoes'):
            story.append(Paragraph("RECOMENDAÇÕES", ParagraphStyle('SectionTitle', parent=styles['Heading3'],
                                  fontSize=12, textColor=colors.HexColor('#28a745'), spaceAfter=10)))
            recomendacoes_text = receita_data['recomendacoes'].replace('\n', '<br/>')
            story.append(Paragraph(recomendacoes_text, normal_style))
            story.append(Spacer(1, 15))
        
        story.append(Spacer(1, 30))
        story.append(Paragraph("-" * 80, normal_style))
        story.append(Paragraph("Documento eletrônico emitido por sistema validado", 
                              ParagraphStyle('Footer', parent=normal_style, alignment=1, fontSize=8)))
        story.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", 
                              ParagraphStyle('Footer', parent=normal_style, alignment=1, fontSize=8)))
        story.append(Spacer(1, 20))
        story.append(Paragraph("_________________________________________", 
                              ParagraphStyle('Signature', parent=normal_style, alignment=1, fontSize=10)))
        story.append(Paragraph(receita_data['medico_nome'], 
                              ParagraphStyle('SignatureName', parent=normal_style, alignment=1, fontSize=10, textColor=colors.HexColor('#1e466e'))))
        story.append(Paragraph("Assinatura do Médico", 
                              ParagraphStyle('SignatureLabel', parent=normal_style, alignment=1, fontSize=8)))
        doc.build(story)
        return f"static/pdfs/receitas/{filename}"
    
    # ========== DECORATOR ==========
    def paciente_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session or session.get('user_type') != 'paciente':
                flash('Acesso restrito a pacientes.', 'warning')
                return redirect('/login')
            return f(*args, **kwargs)
        return decorated_function
    
    # ========== FUNÇÕES AUXILIARES ==========
    def formatar_data(data, formato='%d/%m/%Y %H:%M'):
        if not data:
            return ''
        if isinstance(data, datetime):
            return data.strftime(formato)
        elif isinstance(data, date):
            return data.strftime(formato)
        return str(data)
    
    def obter_paciente_id():
        if 'user_id' not in session or session.get('user_type') != 'paciente':
            return None
        try:
            cur = mysql.connection.cursor()
            user_id = session['user_id']
            cur.execute("SELECT id FROM pacientes WHERE usuario_id = %s", (user_id,))
            result = cur.fetchone()
            cur.close()
            if result:
                return result['id']
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO pacientes (usuario_id) VALUES (%s)", (user_id,))
            mysql.connection.commit()
            cur.close()
            cur = mysql.connection.cursor()
            cur.execute("SELECT id FROM pacientes WHERE usuario_id = %s", (user_id,))
            result = cur.fetchone()
            cur.close()
            return result['id'] if result else None
        except Exception as e:
            print(f"Erro ao obter paciente_id: {e}")
            return None
    
    # ========== ROTA: DASHBOARD ==========
    @paciente_bp.route('/dashboard')
    @paciente_required
    def dashboard():
        paciente_id = obter_paciente_id()
        if not paciente_id:
            flash('Perfil de paciente não encontrado.', 'danger')
            return redirect('/logout')
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT p_u.nome, p.data_nascimento, p.genero, p.telefone, p.endereco, p_u.email
            FROM pacientes p JOIN usuarios p_u ON p.usuario_id = p_u.id WHERE p.id = %s
        """, (paciente_id,))
        paciente_info = cur.fetchone()
        
        paciente_nome = garantir_string(paciente_info['nome']) if paciente_info else session.get('user_name', 'Paciente')
        paciente_data_nasc = formatar_data(paciente_info.get('data_nascimento'), '%d/%m/%Y') if paciente_info else None
        paciente_genero = garantir_string(paciente_info.get('genero')) if paciente_info else None
        paciente_telefone = garantir_string(paciente_info.get('telefone')) if paciente_info else None
        paciente_endereco = garantir_string(paciente_info.get('endereco')) if paciente_info else None
        paciente_email = garantir_string(paciente_info.get('email')) if paciente_info else None
        
        cur.execute("""
            SELECT c.id, m_u.nome as medico_nome, m.especialidade, c.data_hora, c.status
            FROM consultas c 
            JOIN medicos m ON c.medico_id = m.id 
            JOIN usuarios m_u ON m.usuario_id = m_u.id 
            WHERE c.paciente_id = %s 
            ORDER BY c.data_hora DESC 
            LIMIT 10
        """, (paciente_id,))
        consultas_raw = cur.fetchall()
        
        cur.execute("""
            SELECT 
                SUM(CASE WHEN status = 'agendada' THEN 1 ELSE 0 END) as agendadas,
                SUM(CASE WHEN status = 'realizada' THEN 1 ELSE 0 END) as realizadas,
                SUM(CASE WHEN status = 'cancelada' THEN 1 ELSE 0 END) as canceladas,
                COUNT(*) as total
            FROM consultas WHERE paciente_id = %s
        """, (paciente_id,))
        stats_row = cur.fetchone()
        
        consultas_agendadas = stats_row['agendadas'] if stats_row else 0
        consultas_realizadas = stats_row['realizadas'] if stats_row else 0
        consultas_canceladas = stats_row['canceladas'] if stats_row else 0
        total_consultas = stats_row['total'] if stats_row else 0
        
        cur.execute("SELECT COUNT(*) as total FROM consultas WHERE paciente_id = %s AND DATE(data_hora) = CURDATE()", (paciente_id,))
        consultas_hoje = cur.fetchone()['total'] if cur.fetchone() else 0
        cur.close()
        
        consultas = []
        for c in consultas_raw:
            status = garantir_string(c['status'])
            consultas.append({
                'id': c['id'],
                'medico_nome': garantir_string(c['medico_nome']),
                'especialidade': garantir_string(c['especialidade']),
                'data_hora': formatar_data(c['data_hora']),
                'status': status,
                'status_class': {'agendada': 'warning', 'realizada': 'success', 'cancelada': 'danger'}.get(status, 'secondary')
            })
        
        stats = {'total_consultas': total_consultas, 'consultas_hoje': consultas_hoje}
        
        return render_template('paciente/dashboard.html', 
                               consultas=consultas, stats=stats,
                               consultas_agendadas=consultas_agendadas,
                               consultas_realizadas=consultas_realizadas,
                               consultas_canceladas=consultas_canceladas,
                               paciente_id=paciente_id, paciente_nome=paciente_nome,
                               paciente_data_nasc=paciente_data_nasc, paciente_genero=paciente_genero,
                               paciente_telefone=paciente_telefone, paciente_endereco=paciente_endereco,
                               paciente_email=paciente_email, user=session)
    
    # ========== ROTA: AGENDAR CONSULTA ==========
    @paciente_bp.route('/agendar', methods=['GET', 'POST'])
    @paciente_required
    def agendar_consulta():
        paciente_id = obter_paciente_id()
        
        if request.method == 'GET':
            cur = mysql.connection.cursor()
            cur.execute("SELECT m.id, u.nome, m.especialidade FROM medicos m JOIN usuarios u ON m.usuario_id = u.id WHERE u.ativo = 1 ORDER BY u.nome")
            medicos_raw = cur.fetchall()
            cur.close()
            medicos = [{'id': m['id'], 'nome': garantir_string(m['nome']), 'especialidade': garantir_string(m['especialidade'])} for m in medicos_raw]
            horarios = ['08:00', '09:00', '10:00', '11:00', '14:00', '15:00', '16:00', '17:00']
            data_minima = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            data_maxima = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            return render_template('paciente/agendar_consulta.html', medicos=medicos, horarios=horarios,
                                   data_minima=data_minima, data_maxima=data_maxima, user=session)
        
        medico_id = request.form.get('medico_id')
        data_consulta = request.form.get('data_consulta')
        hora_consulta = request.form.get('hora_consulta')
        sintomas = request.form.get('sintomas', '')
        observacoes = request.form.get('observacoes', '')
        
        if not medico_id or not data_consulta or not hora_consulta:
            flash('Preencha todos os campos obrigatórios.', 'danger')
            return redirect(request.url)
        
        data_hora = datetime.strptime(f"{data_consulta} {hora_consulta}", "%Y-%m-%d %H:%M")
        if data_hora <= datetime.now():
            flash('Não é possível agendar em datas passadas.', 'danger')
            return redirect(request.url)
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT COUNT(*) FROM consultas WHERE medico_id = %s AND data_hora = %s AND status != 'cancelada'", (medico_id, data_hora))
        if cur.fetchone()[0] > 0:
            cur.close()
            flash('Horário indisponível.', 'danger')
            return redirect(request.url)
        
        try:
            cur.execute("SELECT p.telefone, u.nome FROM pacientes p JOIN usuarios u ON p.usuario_id = u.id WHERE p.id = %s", (paciente_id,))
            paciente_info = cur.fetchone()
            paciente_telefone = garantir_string(paciente_info['telefone']) if paciente_info else None
            paciente_nome = garantir_string(paciente_info['nome']) if paciente_info else 'Paciente'
            
            cur.execute("""
                INSERT INTO consultas (paciente_id, medico_id, data_hora, status, sintomas, observacoes)
                VALUES (%s, %s, %s, 'agendada', %s, %s)
            """, (paciente_id, medico_id, data_hora, sintomas, observacoes))
            consulta_id = cur.lastrowid
            mysql.connection.commit()
            
            cur.execute("SELECT u.nome, m.especialidade FROM medicos m JOIN usuarios u ON m.usuario_id = u.id WHERE m.id = %s", (medico_id,))
            medico_info = cur.fetchone()
            medico_nome = garantir_string(medico_info['nome']) if medico_info else 'Médico'
            especialidade = garantir_string(medico_info['especialidade']) if medico_info else 'Clínico Geral'
            
            valor_consulta = 2500.00
            fatura = emitir_fatura(consulta_id, paciente_id, paciente_nome, paciente_telefone, valor_consulta, data_hora)
            cur.close()
            
            flash(f'Consulta agendada com sucesso!', 'success')
            flash(f'Fatura emitida: {fatura["numero"]} - Valor: {fatura["valor"]:.2f} Kz', 'info')
            return redirect(url_for('paciente.confirmacao_fatura', fatura_id=fatura['id']))
        except Exception as e:
            mysql.connection.rollback()
            cur.close()
            logger.error(f"Erro ao agendar: {e}")
            flash(f'Erro ao agendar: {str(e)}', 'danger')
            return redirect(request.url)
    
    # ========== ROTA: CONFIRMAÇÃO FATURA ==========
    @paciente_bp.route('/confirmacao-fatura/<int:fatura_id>')
    @paciente_required
    def confirmacao_fatura(fatura_id):
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT f.id, f.numero_fatura, f.paciente_nome, f.paciente_telefone,
                   f.data_consulta, f.valor_consulta, f.status_pagamento, f.data_emissao,
                   c.id as consulta_id, u.nome as medico_nome, m.especialidade
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
            'id': fatura_raw['id'], 'numero_fatura': fatura_raw['numero_fatura'],
            'paciente_nome': garantir_string(fatura_raw['paciente_nome']),
            'paciente_telefone': garantir_string(fatura_raw['paciente_telefone']) if fatura_raw['paciente_telefone'] else None,
            'data_consulta': fatura_raw['data_consulta'], 'valor_consulta': float(fatura_raw['valor_consulta']),
            'status_pagamento': fatura_raw['status_pagamento'], 'data_emissao': fatura_raw['data_emissao'],
            'consulta_id': fatura_raw['consulta_id'], 'medico_nome': garantir_string(fatura_raw['medico_nome']),
            'especialidade': garantir_string(fatura_raw['especialidade'])
        }
        return render_template('paciente/confirmacao_fatura.html', fatura=fatura)
    
    # ========== ROTA: MINHAS CONSULTAS ==========
    @paciente_bp.route('/consultas')
    @paciente_required
    def minhas_consultas():
        paciente_id = obter_paciente_id()
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT c.id, m_u.nome, m.especialidade, c.data_hora, c.status
            FROM consultas c 
            JOIN medicos m ON c.medico_id = m.id
            JOIN usuarios m_u ON m.usuario_id = m_u.id
            WHERE c.paciente_id = %s 
            ORDER BY c.data_hora DESC
        """, (paciente_id,))
        consultas_raw = cur.fetchall()
        cur.close()
        consultas = [{
            'id': c['id'], 'medico_nome': garantir_string(c['nome']),
            'especialidade': garantir_string(c['especialidade']),
            'data_hora': formatar_data(c['data_hora']), 'status': garantir_string(c['status']),
            'status_class': {'agendada': 'warning', 'realizada': 'success', 'cancelada': 'danger'}.get(c['status'], 'secondary')
        } for c in consultas_raw]
        return render_template('paciente/consultas.html', consultas=consultas, user=session)
    
    # ========== ROTA: PERFIL ==========
    @paciente_bp.route('/perfil', methods=['GET', 'POST'])
    @paciente_required
    def perfil():
        paciente_id = obter_paciente_id()
        if request.method == 'POST':
            telefone = request.form.get('telefone', '')
            endereco = request.form.get('endereco', '')
            data_nascimento = request.form.get('data_nascimento')
            genero = request.form.get('genero', '')
            cur = mysql.connection.cursor()
            cur.execute("UPDATE pacientes SET telefone=%s, endereco=%s, data_nascimento=%s, genero=%s WHERE id=%s",
                       (telefone, endereco, data_nascimento, genero, paciente_id))
            mysql.connection.commit()
            cur.close()
            flash('Perfil atualizado com sucesso!', 'success')
            return redirect(url_for('paciente.perfil'))
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT p_u.nome, p.data_nascimento, p.genero, p.telefone, p.endereco, p_u.email
            FROM pacientes p 
            JOIN usuarios p_u ON p.usuario_id = p_u.id 
            WHERE p.id = %s
        """, (paciente_id,))
        info = cur.fetchone()
        cur.close()
        return render_template('paciente/perfil.html',
                               paciente_nome=garantir_string(info['nome']) if info else '',
                               data_nascimento=info['data_nascimento'] if info else None,
                               genero=garantir_string(info['genero']) if info else '',
                               telefone=garantir_string(info['telefone']) if info else '',
                               endereco=garantir_string(info['endereco']) if info else '',
                               email=garantir_string(info['email']) if info else '', user=session)
    
    # ========== ROTA: DETALHES CONSULTA ==========
    @paciente_bp.route('/consultas/<int:consulta_id>')
    @paciente_required
    def detalhes_consulta(consulta_id):
        paciente_id = obter_paciente_id()
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT c.id, m_u.nome, m.especialidade, c.data_hora, c.status, c.observacoes
            FROM consultas c 
            JOIN medicos m ON c.medico_id = m.id
            JOIN usuarios m_u ON m.usuario_id = m_u.id
            WHERE c.id = %s AND c.paciente_id = %s
        """, (consulta_id, paciente_id))
        row = cur.fetchone()
        cur.close()
        if not row:
            flash('Consulta não encontrada.', 'danger')
            return redirect(url_for('paciente.minhas_consultas'))
        consulta = {
            'id': row['id'], 'medico_nome': garantir_string(row['nome']),
            'especialidade': garantir_string(row['especialidade']),
            'data_hora': formatar_data(row['data_hora']), 'status': garantir_string(row['status']),
            'observacoes': garantir_string(row['observacoes']) if row.get('observacoes') else ''
        }
        status_class = {'agendada': 'warning', 'realizada': 'success', 'cancelada': 'danger'}.get(consulta['status'], 'secondary')
        return render_template('paciente/detalhes_consulta.html', consulta=consulta, status_class=status_class, user=session)
    
    return paciente_bp
