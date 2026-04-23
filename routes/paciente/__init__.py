from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, send_file, current_app
import pymysql
pymysql.install_as_MySQLdb()
import os
from datetime import datetime, timedelta, date
import traceback
import logging
from functools import wraps
import re
import html
from bs4 import BeautifulSoup
from utils.pdf import html_to_pdf, gerar_pdf_receita_simples
from werkzeug.utils import secure_filename
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
import uuid

logger = logging.getLogger(__name__)

def init_paciente(mysql, app):
    """Inicializa e retorna o blueprint do paciente"""
    
    paciente_bp = Blueprint('paciente', __name__, url_prefix='/paciente')
    
    # ========== FUNÇÃO PARA CONVERTER STRING ==========
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
        if isinstance(valor, (datetime, date)):
            return formatar_data(valor)
        return str(valor) if valor is not None else ''
    
    def formatar_data(data, formato='%d/%m/%Y %H:%M'):
        if not data:
            return ''
        if isinstance(data, datetime):
            return data.strftime(formato)
        if isinstance(data, date):
            return data.strftime(formato)
        return str(data)
    
    # ========== FUNÇÕES DE FATURA ==========
    def gerar_numero_fatura():
        try:
            cursor = mysql.connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM faturas WHERE DATE(data_emissao) = CURDATE()")
            total_hoje = cursor.fetchone()[0] + 1
            cursor.close()
            return f"FAT-{datetime.now().strftime('%Y%m%d')}-{str(total_hoje).zfill(4)}"
        except:
            return f"FAT-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def emitir_fatura(consulta_id, paciente_id, paciente_nome, paciente_telefone, valor, data_consulta):
        cursor = mysql.connection.cursor()
        try:
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
            return {'id': fatura_id, 'numero': numero_fatura, 'valor': valor}
        except Exception as e:
            mysql.connection.rollback()
            raise e
        finally:
            cursor.close()

    def gerar_pdf_fatura(fatura_data):
        pdf_dir = os.path.join(app.root_path, 'static', 'pdfs', 'faturas')
        os.makedirs(pdf_dir, exist_ok=True)
        filename = f"fatura_{fatura_data['numero_fatura']}.pdf"
        output_path = os.path.join(pdf_dir, filename)
        
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
        
        info_data = [['NÚMERO DA FATURA:', fatura_data['numero_fatura']],
                     ['DATA DE EMISSÃO:', data_emissao],
                     ['STATUS:', 'PENDENTE'],
                     ['DATA DA CONSULTA:', data_consulta]]
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
                      ['1', 'Consulta Médica', '1', f"{fatura_data['valor_consulta']:.2f} Kz", f"{fatura_data['valor_consulta']:.2f} Kz"]]
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
        
        total_data = [['TOTAL GERAL:', f"{fatura_data['valor_consulta']:.2f} Kz"]]
        total_table = Table(total_data, colWidths=[450, 100])
        total_table.setStyle(TableStyle([('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'), ('FONTSIZE', (0,0), (-1,-1), 12),
                                         ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#28a745')),
                                         ('ALIGN', (1,0), (1,0), 'RIGHT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                                         ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#e8f5e9'))]))
        story.append(total_table)
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("FORMAS DE PAGAMENTO", ParagraphStyle('SectionTitle', parent=styles['Heading3'],
                              fontSize=11, textColor=colors.HexColor('#1e466e'), spaceAfter=10)))
        pagamento_text = """
        <b>Balcão de Atendimento:</b> Dinheiro ou Cartão<br/>
        <b>MB WAY:</b> 924 042 244<br/>
        <b>Depósito Bancário:</b> BAI - 123456789 (Hospital Municipal da Cacula)<br/>
        <b>Transferência:</b> IBAN: AO06 0040 0000 1234 5678 9012 3
        """
        story.append(Paragraph(pagamento_text, normal_style))
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("INFORMAÇÕES IMPORTANTES", ParagraphStyle('SectionTitle', parent=styles['Heading3'],
                              fontSize=11, textColor=colors.HexColor('#dc3545'), spaceAfter=10)))
        info_text = """
        • Apresente este documento no dia da consulta<br/>
        • Cancelamentos devem ser feitos com 24 horas de antecedência<br/>
        • Chegue com 15 minutos de antecedência<br/>
        • Traga seus documentos e exames anteriores (se houver)
        """
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
    
    # ========== DECORATORS ==========
    def paciente_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session or session.get('user_type') != 'paciente':
                flash('Acesso restrito a pacientes.', 'warning')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated_function
    
    # ========== FUNÇÃO PARA OBTER PACIENTE ID ==========
    def obter_paciente_id():
        if 'user_id' not in session or session.get('user_type') != 'paciente':
            return None
        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT id FROM pacientes WHERE usuario_id = %s", (session['user_id'],))
            resultado = cur.fetchone()
            cur.close()
            if resultado:
                return resultado[0]
            return None
        except Exception as e:
            logger.error(f"Erro ao obter paciente_id: {e}")
            return None
    
    # ========== DASHBOARD ==========
    @paciente_bp.route('/dashboard')
    @paciente_required
    def dashboard():
        try:
            paciente_id = obter_paciente_id()
            if not paciente_id:
                flash('Perfil de paciente não encontrado.', 'danger')
                return redirect(url_for('auth.logout'))
            
            cur = mysql.connection.cursor()
            
            # Buscar dados do paciente
            cur.execute("""
                SELECT p_u.nome, p.data_nascimento, p.genero, p.telefone, p.endereco, p_u.email
                FROM pacientes p 
                JOIN usuarios p_u ON p.usuario_id = p_u.id 
                WHERE p.id = %s
            """, (paciente_id,))
            paciente_info = cur.fetchone()
            
            # Buscar consultas
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
            cur.close()
            
            # Processar consultas
            consultas = []
            for c in consultas_raw:
                consultas.append({
                    'id': c[0],
                    'medico_nome': garantir_string(c[1]),
                    'especialidade': garantir_string(c[2]),
                    'data_hora': formatar_data(c[3]),
                    'status': garantir_string(c[4]),
                    'status_class': {
                        'agendada': 'warning',
                        'realizada': 'success',
                        'cancelada': 'danger'
                    }.get(c[4], 'secondary')
                })
            
            return render_template('paciente/dashboard.html', 
                                 consultas=consultas,
                                 paciente_nome=garantir_string(paciente_info[0]) if paciente_info else session.get('user_name', 'Paciente'),
                                 user=session)
        except Exception as e:
            logger.error(f"Erro no dashboard: {e}")
            flash(f'Erro ao carregar dashboard: {str(e)}', 'danger')
            return redirect(url_for('paciente.minhas_consultas'))
    
    # ========== AGENDAR CONSULTA ==========
    @paciente_bp.route('/agendar', methods=['GET', 'POST'])
    @paciente_required
    def agendar_consulta():
        paciente_id = obter_paciente_id()
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT m.id, u.nome, m.especialidade, m.crm
            FROM medicos m
            JOIN usuarios u ON m.usuario_id = u.id
            WHERE u.ativo = 1
            ORDER BY u.nome
        """)
        medicos_raw = cur.fetchall()
        cur.close()
        
        medicos = []
        for m in medicos_raw:
            medicos.append({
                'id': m[0],
                'nome': garantir_string(m[1]),
                'especialidade': garantir_string(m[2]),
                'crm': garantir_string(m[3])
            })
        
        horarios = ['08:00', '09:00', '10:00', '11:00', '14:00', '15:00', '16:00', '17:00']
        data_minima = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        data_maxima = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        
        if request.method == 'POST':
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
                flash('Não é possível agendar consultas em datas/horários passados.', 'danger')
                return redirect(request.url)
            
            cur = mysql.connection.cursor()
            cur.execute("SELECT COUNT(*) FROM consultas WHERE medico_id = %s AND data_hora = %s AND status != 'cancelada'",
                       (medico_id, data_hora))
            if cur.fetchone()[0] > 0:
                cur.close()
                flash('Horário indisponível. Escolha outro horário.', 'danger')
                return redirect(request.url)
            
            try:
                cur.execute("SELECT u.nome FROM pacientes p JOIN usuarios u ON p.usuario_id = u.id WHERE p.id = %s", (paciente_id,))
                paciente_nome = garantir_string(cur.fetchone()[0]) if cur.fetchone() else 'Paciente'
                
                cur.execute("""
                    INSERT INTO consultas (paciente_id, medico_id, data_hora, status, sintomas, observacoes)
                    VALUES (%s, %s, %s, 'agendada', %s, %s)
                """, (paciente_id, medico_id, data_hora, sintomas, observacoes))
                consulta_id = cur.lastrowid
                mysql.connection.commit()
                cur.close()
                
                flash('Consulta agendada com sucesso!', 'success')
                return redirect(url_for('paciente.minhas_consultas'))
                
            except Exception as e:
                mysql.connection.rollback()
                cur.close()
                logger.error(f"Erro ao agendar: {e}")
                flash(f'Erro ao agendar: {str(e)}', 'danger')
                return redirect(request.url)
        
        return render_template('paciente/agendar_consulta.html', medicos=medicos, horarios=horarios,
                               data_minima=data_minima, data_maxima=data_maxima, user=session, user_type='paciente')
    
    # ========== MINHAS CONSULTAS ==========
    @paciente_bp.route('/consultas')
    @paciente_required
    def minhas_consultas():
        paciente_id = obter_paciente_id()
        
        if not paciente_id:
            flash('Perfil de paciente não encontrado.', 'danger')
            return redirect(url_for('auth.logout'))
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT c.id, m_u.nome, m.especialidade, m.crm, c.data_hora, c.status
            FROM consultas c
            JOIN medicos m ON c.medico_id = m.id
            JOIN usuarios m_u ON m.usuario_id = m_u.id
            WHERE c.paciente_id = %s
            ORDER BY c.data_hora DESC
        """, (paciente_id,))
        consultas_raw = cur.fetchall()
        cur.close()
        
        consultas_formatadas = []
        for c in consultas_raw:
            consultas_formatadas.append({
                'id': c[0],
                'medico_nome': garantir_string(c[1]),
                'especialidade': garantir_string(c[2]),
                'crm': garantir_string(c[3]),
                'data_hora': formatar_data(c[4]),
                'status': garantir_string(c[5]),
                'status_class': {'agendada': 'warning', 'realizada': 'success', 'cancelada': 'danger'}.get(c[5], 'secondary')
            })
        
        return render_template('paciente/consultas.html', consultas=consultas_formatadas, user=session, user_type='paciente')
    
    # ========== DETALHES CONSULTA ==========
    @paciente_bp.route('/consultas/<int:consulta_id>')
    @paciente_required
    def detalhes_consulta(consulta_id):
        paciente_id = obter_paciente_id()
        cur = mysql.connection.cursor()
        
        cur.execute("""
            SELECT c.id, m_u.nome, m.especialidade, m.crm, c.data_hora, c.status,
                   c.observacoes, p_u.nome, p.data_nascimento, p.genero, p.telefone,
                   p.endereco, c.sintomas
            FROM consultas c
            JOIN medicos m ON m.id = c.medico_id
            JOIN usuarios m_u ON m_u.id = m.usuario_id
            JOIN pacientes p ON p.id = c.paciente_id
            JOIN usuarios p_u ON p_u.id = p.usuario_id
            WHERE c.id = %s AND c.paciente_id = %s
        """, (consulta_id, paciente_id))
        
        row = cur.fetchone()
        
        if not row:
            cur.close()
            flash('Consulta não encontrada.', 'danger')
            return redirect(url_for('paciente.minhas_consultas'))
        
        consulta = {
            'id': row[0],
            'medico_nome': garantir_string(row[1]),
            'especialidade': garantir_string(row[2]),
            'crm': garantir_string(row[3]),
            'data_hora': formatar_data(row[4]),
            'status': garantir_string(row[5]),
            'observacoes': garantir_string(row[6]),
            'paciente_nome': garantir_string(row[7]),
            'data_nascimento': formatar_data(row[8], '%d/%m/%Y') if row[8] else '',
            'genero': garantir_string(row[9]),
            'paciente_telefone': garantir_string(row[10]) if row[10] else '',
            'paciente_endereco': garantir_string(row[11]) if row[11] else '',
            'sintomas_raw': garantir_string(row[12]) if len(row) > 12 and row[12] else ''
        }
        
        # Buscar receitas
        cur.execute("SELECT id, diagnostico, prescricao, recomendacoes, status, created_at FROM receita WHERE consulta_id = %s ORDER BY created_at DESC", (consulta_id,))
        receitas_raw = cur.fetchall()
        cur.close()
        
        receitas = []
        for r in receitas_raw:
            receitas.append({
                'id': r[0],
                'diagnostico': garantir_string(r[1]) if r[1] else '',
                'prescricao': garantir_string(r[2]) if r[2] else '',
                'recomendacoes': garantir_string(r[3]) if r[3] else '',
                'status': garantir_string(r[4]) if r[4] else 'ativa',
                'created_at': formatar_data(r[5], '%d/%m/%Y %H:%M') if r[5] else ''
            })
        
        sintomas_lista = [s.strip() for s in consulta['sintomas_raw'].split(',') if s.strip()] if consulta.get('sintomas_raw') else []
        
        return render_template('paciente/detalhes_consulta.html', 
                             consulta=consulta, sintomas=sintomas_lista, receitas=receitas,
                             user=session, formatar_data=formatar_data, datetime=datetime, user_type='paciente')
    
    # ========== CANCELAR CONSULTA ==========
    @paciente_bp.route('/consultas/<int:consulta_id>/cancelar', methods=['POST'])
    @paciente_required
    def cancelar_consulta(consulta_id):
        paciente_id = obter_paciente_id()
        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT status FROM consultas WHERE id = %s AND paciente_id = %s", (consulta_id, paciente_id))
            consulta = cur.fetchone()
            if not consulta:
                flash('Consulta não encontrada.', 'danger')
                return redirect(url_for('paciente.minhas_consultas'))
            
            if consulta[0] != 'agendada':
                flash('Apenas consultas agendadas podem ser canceladas.', 'warning')
                return redirect(url_for('paciente.detalhes_consulta', consulta_id=consulta_id))
            
            cur.execute("UPDATE consultas SET status = 'cancelada' WHERE id = %s AND paciente_id = %s", (consulta_id, paciente_id))
            mysql.connection.commit()
            cur.close()
            
            flash('Consulta cancelada com sucesso!', 'success')
        except Exception as e:
            mysql.connection.rollback()
            logger.error(f"Erro ao cancelar consulta: {e}")
            flash('Erro ao cancelar consulta.', 'danger')
        
        return redirect(url_for('paciente.minhas_consultas'))
    
    # ========== PERFIL ==========
    @paciente_bp.route('/perfil', methods=['GET', 'POST'])
    @paciente_required
    def perfil():
        paciente_id = obter_paciente_id()
        
        if request.method == 'POST':
            telefone = request.form.get('telefone')
            endereco = request.form.get('endereco')
            data_nascimento = request.form.get('data_nascimento')
            genero = request.form.get('genero')
            
            cur = mysql.connection.cursor()
            cur.execute("""
                UPDATE pacientes 
                SET telefone=%s, endereco=%s, data_nascimento=%s, genero=%s
                WHERE id=%s
            """, (telefone, endereco, data_nascimento, genero, paciente_id))
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
        
        if info:
            return render_template('paciente/perfil.html',
                paciente_nome=garantir_string(info[0]),
                data_nascimento=info[1],
                genero=garantir_string(info[2]),
                telefone=garantir_string(info[3]),
                endereco=garantir_string(info[4]),
                email=garantir_string(info[5]),
                user=session)
        
        return render_template('paciente/perfil.html', user=session)
    
    # ========== VISUALIZAR RECEITA ==========
    @paciente_bp.route('/receita/<int:receita_id>')
    @paciente_required
    def visualizar_receita(receita_id):
        paciente_id = obter_paciente_id()
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT r.id, r.diagnostico, r.prescricao, r.recomendacoes, r.status, r.created_at,
                   c.id, c.data_hora, m_u.nome, m.especialidade, m.crm, p_u.nome, p.data_nascimento, p.genero
            FROM receita r
            JOIN consultas c ON r.consulta_id = c.id
            JOIN medicos m ON c.medico_id = m.id
            JOIN usuarios m_u ON m.usuario_id = m_u.id
            JOIN pacientes p ON c.paciente_id = p.id
            JOIN usuarios p_u ON p.usuario_id = p_u.id
            WHERE r.id = %s AND c.paciente_id = %s
        """, (receita_id, paciente_id))
        row = cur.fetchone()
        cur.close()
        
        if not row:
            flash('Receita não encontrada.', 'danger')
            return redirect(url_for('paciente.minhas_consultas'))
        
        receita = {
            'id': row[0],
            'diagnostico': garantir_string(row[1]),
            'prescricao': garantir_string(row[2]),
            'recomendacoes': garantir_string(row[3]),
            'status': garantir_string(row[4]),
            'created_at': row[5],
            'consulta_id': row[6],
            'data_consulta': formatar_data(row[7]),
            'medico_nome': garantir_string(row[8]),
            'especialidade': garantir_string(row[9]),
            'crm': garantir_string(row[10]),
            'paciente_nome': garantir_string(row[11]),
            'data_nascimento': formatar_data(row[12], '%d/%m/%Y') if row[12] else '',
            'genero': garantir_string(row[13])
        }
        
        return render_template('paciente/visualizar_receita.html', receita=receita, user=session)
    
    return paciente_bp
EOF
