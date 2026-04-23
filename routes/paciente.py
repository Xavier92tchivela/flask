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
    
    # ========== FUNÇÃO PARA CONVERTER BYTES ==========
    def garantir_string(valor):
        """Converte bytes para string se necessário"""
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

    def gerar_pdf_fatura(fatura_data):
        """Gera PDF da fatura"""
        
        # Criar diretório se não existir
        pdf_dir = os.path.join(app.root_path, 'static', 'pdfs', 'faturas')
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
        data_emissao = fatura_data['data_emissao'].strftime('%d/%m/%Y %H:%M') if fatura_data.get('data_emissao') else datetime.now().strftime('%d/%m/%Y %H:%M')
        data_consulta = fatura_data['data_consulta'].strftime('%d/%m/%Y %H:%M') if fatura_data.get('data_consulta') else 'Não informada'
        
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
            ['TELEFONE:', fatura_data.get('paciente_telefone', 'Não informado') or 'Não informado'],
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

    def gerar_pdf_receita_completo(receita_data, app):
        """Gera PDF completo da receita"""
        
        # Criar diretório se não existir
        pdf_dir = os.path.join(app.root_path, 'static', 'pdfs', 'receitas')
        os.makedirs(pdf_dir, exist_ok=True)
        
        filename = f"receita_{receita_data['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
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
            textColor=colors.HexColor('#28a745'),
            alignment=1,
            spaceAfter=20
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=10,
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
        story.append(Paragraph("RECEITA MÉDICA", subtitle_style))
        story.append(Spacer(1, 20))
        
        # Dados da Receita
        info_data = [
            ['NÚMERO DA RECEITA:', f"#{receita_data['id']}"],
            ['DATA DE EMISSÃO:', receita_data['created_at'].strftime('%d/%m/%Y %H:%M') if receita_data['created_at'] else datetime.now().strftime('%d/%m/%Y %H:%M')],
            ['STATUS:', receita_data['status'].upper() if receita_data['status'] else 'ATIVA'],
        ]
        
        info_table = Table(info_data, colWidths=[150, 350])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#1e466e')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f0f0f0')),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 20))
        
        # Dados do Médico
        story.append(Paragraph("MÉDICO RESPONSÁVEL", ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#1e466e'),
            spaceAfter=10
        )))
        
        medico_data = [
            ['NOME:', receita_data['medico_nome']],
            ['ESPECIALIDADE:', receita_data['especialidade']],
            ['CRM:', receita_data['crm']],
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
        
        # Dados do Paciente
        story.append(Paragraph("PACIENTE", ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#1e466e'),
            spaceAfter=10
        )))
        
        idade_text = f"{receita_data.get('idade', 'N/I')} anos" if receita_data.get('idade') else 'Não informada'
        paciente_data = [
            ['NOME:', receita_data['paciente_nome']],
            ['IDADE:', idade_text],
            ['GÊNERO:', receita_data.get('genero', 'Não informado')],
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
        
        # Diagnóstico
        if receita_data['diagnostico']:
            story.append(Paragraph("DIAGNÓSTICO", ParagraphStyle(
                'SectionTitle',
                parent=styles['Heading3'],
                fontSize=12,
                textColor=colors.HexColor('#28a745'),
                spaceAfter=10
            )))
            
            diagnostico_text = receita_data['diagnostico'].replace('\n', '<br/>')
            story.append(Paragraph(diagnostico_text, normal_style))
            story.append(Spacer(1, 15))
        
        # Prescrição
        if receita_data['prescricao']:
            story.append(Paragraph("PRESCRIÇÃO MÉDICA", ParagraphStyle(
                'SectionTitle',
                parent=styles['Heading3'],
                fontSize=12,
                textColor=colors.HexColor('#28a745'),
                spaceAfter=10
            )))
            
            prescricao_text = receita_data['prescricao'].replace('\n', '<br/>')
            story.append(Paragraph(prescricao_text, normal_style))
            story.append(Spacer(1, 15))
        
        # Recomendações
        if receita_data['recomendacoes']:
            story.append(Paragraph("RECOMENDAÇÕES", ParagraphStyle(
                'SectionTitle',
                parent=styles['Heading3'],
                fontSize=12,
                textColor=colors.HexColor('#28a745'),
                spaceAfter=10
            )))
            
            recomendacoes_text = receita_data['recomendacoes'].replace('\n', '<br/>')
            story.append(Paragraph(recomendacoes_text, normal_style))
            story.append(Spacer(1, 15))
        
        # Rodapé
        story.append(Spacer(1, 30))
        story.append(Paragraph("-" * 80, normal_style))
        story.append(Paragraph("Documento eletrônico emitido por sistema validado", 
                              ParagraphStyle('Footer', parent=normal_style, alignment=1, fontSize=8)))
        story.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", 
                              ParagraphStyle('Footer', parent=normal_style, alignment=1, fontSize=8)))
        
        # Assinatura
        story.append(Spacer(1, 20))
        story.append(Paragraph("_________________________________________", 
                              ParagraphStyle('Signature', parent=normal_style, alignment=1, fontSize=10)))
        story.append(Paragraph(receita_data['medico_nome'], 
                              ParagraphStyle('SignatureName', parent=normal_style, alignment=1, fontSize=10, textColor=colors.HexColor('#1e466e'))))
        story.append(Paragraph("Assinatura do Médico", 
                              ParagraphStyle('SignatureLabel', parent=normal_style, alignment=1, fontSize=8)))
        
        # Gerar PDF
        doc.build(story)
        
        # Retornar caminho relativo
        return f"static/pdfs/receitas/{filename}"
    
    # ========== DECORATORS ==========
    def paciente_required(f):
        """Decorator para garantir que o usuário é um paciente"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session or session.get('user_type') != 'paciente':
                flash('Acesso restrito a pacientes.', 'warning')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated_function
    
    # ========== FUNÇÕES AUXILIARES ==========
    def execute_query(query, params=None, fetch=False):
        """Função auxiliar para executar queries no banco de dados"""
        try:
            cur = mysql.connection.cursor()
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            
            if fetch:
                result = cur.fetchall()
            else:
                mysql.connection.commit()
                result = None
            
            cur.close()
            return result
        except Exception as e:
            mysql.connection.rollback()
            logger.error(f"Database error: {e}")
            logger.error(traceback.format_exc())
            return None
    
    def formatar_data(data, formato='%d/%m/%Y %H:%M'):
        """Formata data de forma segura"""
        if not data:
            return ''
        if isinstance(data, datetime):
            return data.strftime(formato)
        elif isinstance(data, date):
            return data.strftime(formato)
        elif isinstance(data, str):
            try:
                if 'T' in data:
                    return datetime.fromisoformat(data.replace('Z', '+00:00')).strftime(formato)
                else:
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                        try:
                            return datetime.strptime(data, fmt).strftime(formato)
                        except ValueError:
                            continue
                    return data
            except:
                return data
        return str(data)
    
    def obter_paciente_id():
        """Obtém o ID do paciente logado"""
        if 'user_id' not in session or session.get('user_type') != 'paciente':
            return None
        
        paciente = execute_query(
            "SELECT id FROM pacientes WHERE usuario_id = %s", 
            (session['user_id'],), True
        )
        
        return paciente[0][0] if paciente else None
    
    # ========== ROTAS ==========
    
    # Dashboard do paciente
    @paciente_bp.route('/dashboard')
    @paciente_required
    def dashboard():
        paciente_id = obter_paciente_id()
        if not paciente_id:
            flash('Perfil de paciente não encontrado.', 'danger')
            return redirect(url_for('auth.logout'))
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT p_u.nome, p.data_nascimento, p.genero, p.telefone, p.endereco, p_u.email
            FROM pacientes p 
            JOIN usuarios p_u ON p.usuario_id = p_u.id 
            WHERE p.id = %s
        """, (paciente_id,))
        paciente_info = cur.fetchone()
        cur.close()
        
        paciente_nome = garantir_string(paciente_info[0]) if paciente_info else session.get('user_name')
        paciente_data_nasc = formatar_data(paciente_info[1], '%d/%m/%Y') if paciente_info and paciente_info[1] else None
        paciente_genero = garantir_string(paciente_info[2]) if paciente_info else None
        paciente_telefone = garantir_string(paciente_info[3]) if paciente_info else None
        paciente_endereco = garantir_string(paciente_info[4]) if paciente_info else None
        paciente_email = garantir_string(paciente_info[5]) if paciente_info else None
        
        cur = mysql.connection.cursor()
        # CORRIGIDO: m_u.id (sem ponto!)
        cur.execute("""
            SELECT c.id, m_u.nome as medico_nome, m.especialidade, 
                   c.data_hora, c.status, c.sintomas
            FROM consultas c 
            JOIN medicos m ON c.medico_id = m.id 
            JOIN usuarios m_u ON m.usuario_id = m_u.id 
            WHERE c.paciente_id = %s 
            ORDER BY c.data_hora DESC
            LIMIT 10
        """, (paciente_id,))
        consultas_raw = cur.fetchall()
        cur.close()
        
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
                    'cancelada': 'danger',
                    'confirmada': 'info'
                }.get(c[4], 'secondary')
            })
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT COUNT(*) FROM consultas WHERE paciente_id = %s", (paciente_id,))
        total_consultas = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM consultas WHERE paciente_id = %s AND DATE(data_hora) = CURDATE()", (paciente_id,))
        consultas_hoje = cur.fetchone()[0] or 0
        cur.close()
        
        stats = {'total_consultas': total_consultas, 'consultas_hoje': consultas_hoje}
        
        return render_template('paciente/dashboard.html', 
                               consultas=consultas,
                               stats=stats,
                               paciente_id=paciente_id,
                               paciente_nome=paciente_nome,
                               paciente_data_nasc=paciente_data_nasc,
                               paciente_genero=paciente_genero,
                               paciente_telefone=paciente_telefone,
                               paciente_endereco=paciente_endereco,
                               paciente_email=paciente_email,
                               user=session)
    
    # Agendar consulta com fatura
    @paciente_bp.route('/agendar', methods=['GET', 'POST'])
    @paciente_required
    def agendar_consulta():
        paciente_id = obter_paciente_id()
        
        # GET: Mostrar formulário
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
            
            # Validar dados
            if not medico_id or not data_consulta or not hora_consulta:
                flash('Preencha todos os campos obrigatórios.', 'danger')
                return redirect(request.url)
            
            # Combinar data e hora
            data_hora_str = f"{data_consulta} {hora_consulta}"
            data_hora = datetime.strptime(data_hora_str, "%Y-%m-%d %H:%M")
            
            # Verificar se a data é válida
            if data_hora <= datetime.now():
                flash('Não é possível agendar consultas em datas/horários passados.', 'danger')
                return redirect(request.url)
            
            # Verificar horário comercial
            hora = data_hora.hour
            if hora < 8 or hora > 17 or (hora == 12 and data_hora.minute > 0):
                flash('Horário fora do expediente. Consulte das 8h às 12h e das 14h às 17h.', 'danger')
                return redirect(request.url)
            
            cur = mysql.connection.cursor()
            
            # Verificar se horário já está ocupado
            cur.execute("""
                SELECT COUNT(*) FROM consultas 
                WHERE medico_id = %s AND data_hora = %s AND status != 'cancelada'
            """, (medico_id, data_hora))
            
            if cur.fetchone()[0] > 0:
                cur.close()
                flash('Horário indisponível. Escolha outro horário.', 'danger')
                return redirect(request.url)
            
            try:
                # Buscar dados do paciente para a fatura
                cur.execute("""
                    SELECT p.telefone, u.nome, u.email
                    FROM pacientes p
                    JOIN usuarios u ON p.usuario_id = u.id
                    WHERE p.id = %s
                """, (paciente_id,))
                paciente_info = cur.fetchone()
                
                paciente_telefone = garantir_string(paciente_info[0]) if paciente_info else None
                paciente_nome = garantir_string(paciente_info[1]) if paciente_info else 'Paciente'
                
                # Agendar consulta
                cur.execute("""
                    INSERT INTO consultas 
                    (paciente_id, medico_id, data_hora, status, sintomas, observacoes)
                    VALUES (%s, %s, %s, 'agendada', %s, %s)
                """, (paciente_id, medico_id, data_hora, sintomas, observacoes))
                
                consulta_id = cur.lastrowid
                mysql.connection.commit()
                
                # Buscar dados do médico para a fatura
                cur.execute("""
                    SELECT u.nome, m.especialidade
                    FROM medicos m
                    JOIN usuarios u ON m.usuario_id = u.id
                    WHERE m.id = %s
                """, (medico_id,))
                medico_info = cur.fetchone()
                
                medico_nome = garantir_string(medico_info[0]) if medico_info else 'Médico'
                especialidade = garantir_string(medico_info[1]) if medico_info else 'Clínico Geral'
                
                # Emitir fatura
                valor_consulta = 2500.00
                fatura = emitir_fatura(
                    consulta_id=consulta_id,
                    paciente_id=paciente_id,
                    paciente_nome=paciente_nome,
                    paciente_telefone=paciente_telefone,
                    valor=valor_consulta,
                    data_consulta=data_hora
                )
                
                cur.close()
                
                flash(f'Consulta agendada com sucesso!', 'success')
                flash(f'Fatura emitida: {fatura["numero"]} - Valor: {fatura["valor"]:.2f} Kz', 'info')
                
                if paciente_telefone:
                    flash(f'SMS enviado para {paciente_telefone}', 'info')
                
                # Redirecionar para página de confirmação com fatura
                return redirect(url_for('paciente.confirmacao_fatura', fatura_id=fatura['id']))
                
            except Exception as e:
                mysql.connection.rollback()
                cur.close()
                logger.error(f"Erro ao agendar consulta: {e}")
                logger.error(traceback.format_exc())
                flash(f'Erro ao agendar: {str(e)}', 'danger')
                return redirect(request.url)
        
        return render_template('paciente/agendar_consulta.html',
                               medicos=medicos,
                               horarios=horarios,
                               data_minima=data_minima,
                               data_maxima=data_maxima,
                               user=session,
                               user_type='paciente')
    
    # Página de confirmação com fatura
    @paciente_bp.route('/confirmacao-fatura/<int:fatura_id>')
    @paciente_required
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
                'paciente_nome': garantir_string(fatura_raw[2]) if fatura_raw[2] else 'Paciente',
                'paciente_telefone': garantir_string(fatura_raw[3]) if fatura_raw[3] else None,
                'data_consulta': fatura_raw[4],
                'valor_consulta': float(fatura_raw[5]),
                'status_pagamento': fatura_raw[6],
                'data_emissao': fatura_raw[7],
                'consulta_id': fatura_raw[8],
                'medico_nome': garantir_string(fatura_raw[9]) if fatura_raw[9] else 'Médico',
                'especialidade': garantir_string(fatura_raw[10]) if fatura_raw[10] else 'Clínico Geral'
            }
            
            return render_template('paciente/confirmacao_fatura.html', fatura=fatura)
            
        except Exception as e:
            logger.error(f"ERRO: {e}")
            logger.error(traceback.format_exc())
            flash(str(e), "danger")
            return redirect(url_for("paciente.dashboard"))
    
    # Download do PDF da fatura
    @paciente_bp.route('/fatura-pdf/<int:fatura_id>')
    @paciente_required
    def fatura_pdf(fatura_id):
        """Baixa o PDF da fatura"""
        
        try:
            cursor = mysql.connection.cursor()
            
            # Buscar dados da fatura
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
            
            fatura_data = {
                'id': fatura_raw[0],
                'numero_fatura': fatura_raw[1],
                'paciente_nome': garantir_string(fatura_raw[2]),
                'paciente_telefone': garantir_string(fatura_raw[3]),
                'data_consulta': fatura_raw[4],
                'valor_consulta': float(fatura_raw[5]),
                'status_pagamento': fatura_raw[6],
                'data_emissao': fatura_raw[7],
                'consulta_id': fatura_raw[8],
                'medico_nome': garantir_string(fatura_raw[9]),
                'especialidade': garantir_string(fatura_raw[10])
            }
            
            # Gerar PDF
            pdf_path = gerar_pdf_fatura(fatura_data)
            
            if not pdf_path or not os.path.exists(pdf_path):
                flash("Erro ao gerar PDF.", "danger")
                return redirect(url_for("paciente.dashboard"))
            
            return send_file(
                pdf_path,
                as_attachment=True,
                download_name=f"fatura_{fatura_data['numero_fatura']}.pdf",
                mimetype='application/pdf'
            )
            
        except Exception as e:
            logger.error(f"ERRO: {e}")
            logger.error(traceback.format_exc())
            flash(f"Erro ao gerar PDF: {str(e)}", "danger")
            return redirect(url_for("paciente.dashboard"))
    
    # Minhas consultas
    @paciente_bp.route('/consultas')
    @paciente_required
    def minhas_consultas():
        paciente_id = obter_paciente_id()
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT c.id, m_u.nome, m.especialidade, m.crm, c.data_hora, c.status, c.sintomas
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
            status_classes = {
                'agendada': 'warning',
                'realizada': 'success',
                'cancelada': 'danger',
                'confirmada': 'info'
            }
            
            consultas_formatadas.append({
                'id': c[0],
                'medico_nome': garantir_string(c[1]),
                'especialidade': garantir_string(c[2]),
                'crm': garantir_string(c[3]),
                'data_hora': formatar_data(c[4]),
                'data_short': formatar_data(c[4], '%d/%m/%Y'),
                'hora': formatar_data(c[4], '%H:%M'),
                'status': garantir_string(c[5]),
                'status_class': status_classes.get(c[5], 'secondary')
            })
        
        return render_template('paciente/consultas.html',
                               consultas=consultas_formatadas,
                               user=session,
                               user_type='paciente')
    
    # ========== ROTA CORRIGIDA: Detalhes da consulta ==========
    @paciente_bp.route('/consultas/<int:consulta_id>')
    @paciente_required
    def detalhes_consulta(consulta_id):
        paciente_id = obter_paciente_id()
        
        cur = mysql.connection.cursor()
        
        # Buscar dados da consulta (APENAS colunas que existem na tabela)
        cur.execute("""
            SELECT 
                c.id, 
                m_u.nome, 
                m.especialidade, 
                m.crm, 
                c.data_hora, 
                c.status,
                c.observacoes, 
                p_u.nome, 
                p.data_nascimento, 
                p.genero,
                p.telefone,
                p.endereco,
                c.sintomas
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
            flash('Consulta não encontrada ou você não tem acesso.', 'danger')
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
        
        # ========== BUSCAR TODAS AS RECEITAS DA TABELA receita ==========
        cur.execute("""
            SELECT 
                r.id,
                r.diagnostico,
                r.prescricao,
                r.recomendacoes,
                r.status,
                r.created_at,
                r.receita_pdf_path,
                r.pdf_gerado,
                r.data_geracao_pdf
            FROM receita r
            WHERE r.consulta_id = %s
            ORDER BY r.created_at DESC
        """, (consulta_id,))
        
        receitas_raw = cur.fetchall()
        cur.close()
        
        # Log para debug
        logger.info(f"Busca de receitas para consulta {consulta_id}: encontradas {len(receitas_raw)} receitas")
        
        receitas = []
        for r in receitas_raw:
            receitas.append({
                'id': r[0],
                'diagnostico': garantir_string(r[1]) if r[1] else '',
                'prescricao': garantir_string(r[2]) if r[2] else '',
                'recomendacoes': garantir_string(r[3]) if r[3] else '',
                'status': garantir_string(r[4]) if r[4] else 'ativa',
                'created_at': formatar_data(r[5], '%d/%m/%Y %H:%M') if r[5] else '',
                'receita_pdf_path': r[6],
                'pdf_gerado': r[7] if r[7] else 0,
                'data_geracao_pdf': r[8]
            })
        
        # Processar sintomas
        sintomas_lista = []
        if consulta['sintomas_raw']:
            sintomas_lista = [s.strip() for s in consulta['sintomas_raw'].split(',') if s.strip()]
        
        # Classe de status
        status_class = {
            'agendada': 'warning',
            'realizada': 'success',
            'cancelada': 'danger',
            'confirmada': 'info'
        }.get(consulta['status'], 'secondary')
        
        return render_template('paciente/detalhes_consulta.html', 
                             consulta=consulta,
                             sintomas=sintomas_lista,
                             receitas=receitas,
                             status_class=status_class,
                             user=session,
                             formatar_data=formatar_data,
                             datetime=datetime,
                             user_type='paciente')
    
    # Cancelar consulta
    @paciente_bp.route('/consultas/<int:consulta_id>/cancelar', methods=['POST'])
    @paciente_required
    def cancelar_consulta(consulta_id):
        paciente_id = obter_paciente_id()
        
        try:
            cur = mysql.connection.cursor()
            cur.execute("""
                SELECT status, data_hora FROM consultas 
                WHERE id = %s AND paciente_id = %s
            """, (consulta_id, paciente_id))
            consulta = cur.fetchone()
            
            if not consulta:
                flash('Consulta não encontrada.', 'danger')
                return redirect(url_for('paciente.minhas_consultas'))
            
            if consulta[0] != 'agendada':
                flash('Apenas consultas agendadas podem ser canceladas.', 'warning')
                return redirect(url_for('paciente.detalhes_consulta', consulta_id=consulta_id))
            
            cur.execute("""
                UPDATE consultas 
                SET status = 'cancelada' 
                WHERE id = %s AND paciente_id = %s
            """, (consulta_id, paciente_id))
            mysql.connection.commit()
            cur.close()
            
            flash('Consulta cancelada com sucesso!', 'success')
            
        except Exception as e:
            mysql.connection.rollback()
            logger.error(f"Erro ao cancelar consulta: {e}")
            flash('Erro ao cancelar consulta. Tente novamente.', 'danger')
        
        return redirect(url_for('paciente.minhas_consultas'))
    
    # Visualizar receita
    @paciente_bp.route('/receita/<int:receita_id>')
    @paciente_required
    def visualizar_receita(receita_id):
        """Visualiza uma receita específica"""
        paciente_id = obter_paciente_id()
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT 
                r.id,
                r.diagnostico,
                r.prescricao,
                r.recomendacoes,
                r.status,
                r.created_at,
                r.receita_pdf_path,
                r.pdf_gerado,
                c.id as consulta_id,
                c.data_hora,
                m_u.nome as medico_nome,
                m.especialidade,
                m.crm,
                p_u.nome as paciente_nome,
                p.data_nascimento,
                p.genero
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
            flash('Receita não encontrada ou você não tem acesso.', 'danger')
            return redirect(url_for('paciente.minhas_consultas'))
        
        # Calcular idade
        idade = None
        if row[14]:
            hoje = datetime.now().date()
            nascimento = row[14] if isinstance(row[14], (datetime, date)) else datetime.strptime(str(row[14]), '%Y-%m-%d').date()
            if isinstance(nascimento, datetime):
                nascimento = nascimento.date()
            idade = hoje.year - nascimento.year
            if hoje.month < nascimento.month or (hoje.month == nascimento.month and hoje.day < nascimento.day):
                idade -= 1
        
        receita = {
            'id': row[0],
            'diagnostico': garantir_string(row[1]) if row[1] else '',
            'prescricao': garantir_string(row[2]) if row[2] else '',
            'recomendacoes': garantir_string(row[3]) if row[3] else '',
            'status': garantir_string(row[4]) if row[4] else '',
            'created_at': row[5],
            'receita_pdf_path': row[6],
            'pdf_gerado': row[7] if row[7] else 0,
            'consulta_id': row[8],
            'data_consulta': formatar_data(row[9]) if row[9] else '',
            'medico_nome': garantir_string(row[10]) if row[10] else '',
            'especialidade': garantir_string(row[11]) if row[11] else '',
            'crm': garantir_string(row[12]) if row[12] else '',
            'paciente_nome': garantir_string(row[13]) if row[13] else '',
            'data_nascimento': formatar_data(row[14], '%d/%m/%Y') if row[14] else '',
            'genero': garantir_string(row[15]) if row[15] else '',
            'idade': idade
        }
        
        return render_template('paciente/visualizar_receita.html',
                             receita=receita,
                             user=session)
    
    # Gerar PDF da receita
    @paciente_bp.route('/receita/<int:receita_id>/gerar-pdf', methods=['POST'])
    @paciente_required
    def gerar_pdf_receita(receita_id):
        """Gera o PDF da receita"""
        paciente_id = obter_paciente_id()
        
        try:
            cursor = mysql.connection.cursor()
            
            # Buscar dados da receita
            cursor.execute("""
                SELECT 
                    r.id,
                    r.diagnostico,
                    r.prescricao,
                    r.recomendacoes,
                    r.status,
                    r.created_at,
                    c.id as consulta_id,
                    c.data_hora,
                    m_u.nome as medico_nome,
                    m.especialidade,
                    m.crm,
                    p_u.nome as paciente_nome,
                    p.data_nascimento,
                    p.genero
                FROM receita r
                JOIN consultas c ON r.consulta_id = c.id
                JOIN medicos m ON c.medico_id = m.id
                JOIN usuarios m_u ON m.usuario_id = m_u.id
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios p_u ON p.usuario_id = p_u.id
                WHERE r.id = %s AND c.paciente_id = %s
            """, (receita_id, paciente_id))
            
            row = cursor.fetchone()
            
            if not row:
                cursor.close()
                return jsonify({'success': False, 'message': 'Receita não encontrada'}), 404
            
            # Preparar dados para o PDF
            receita_data = {
                'id': row[0],
                'diagnostico': garantir_string(row[1]) if row[1] else '',
                'prescricao': garantir_string(row[2]) if row[2] else '',
                'recomendacoes': garantir_string(row[3]) if row[3] else '',
                'status': garantir_string(row[4]) if row[4] else '',
                'created_at': row[5],
                'consulta_id': row[6],
                'data_consulta': row[7],
                'medico_nome': garantir_string(row[8]) if row[8] else '',
                'especialidade': garantir_string(row[9]) if row[9] else '',
                'crm': garantir_string(row[10]) if row[10] else '',
                'paciente_nome': garantir_string(row[11]) if row[11] else '',
                'data_nascimento': row[12],
                'genero': garantir_string(row[13]) if row[13] else ''
            }
            
            # Calcular idade
            if receita_data['data_nascimento']:
                hoje = datetime.now()
                nascimento = receita_data['data_nascimento']
                if isinstance(nascimento, datetime):
                    nascimento = nascimento.date()
                elif isinstance(nascimento, date):
                    pass
                else:
                    nascimento = datetime.strptime(str(nascimento), '%Y-%m-%d').date()
                
                idade = hoje.year - nascimento.year
                if hoje.month < nascimento.month or \
                   (hoje.month == nascimento.month and hoje.day < nascimento.day):
                    idade -= 1
                receita_data['idade'] = idade
            
            # Gerar PDF
            pdf_path = gerar_pdf_receita_completo(receita_data, app)
            
            if pdf_path:
                # Atualizar caminho do PDF no banco
                cursor.execute("""
                    UPDATE receita 
                    SET receita_pdf_path = %s, pdf_gerado = 1, data_geracao_pdf = NOW()
                    WHERE id = %s
                """, (pdf_path, receita_id))
                mysql.connection.commit()
                cursor.close()
                
                return jsonify({
                    'success': True, 
                    'message': 'PDF gerado com sucesso',
                    'pdf_url': url_for('paciente.download_receita_pdf', receita_id=receita_id)
                })
            else:
                cursor.close()
                return jsonify({'success': False, 'message': 'Erro ao gerar PDF'}), 500
                
        except Exception as e:
            logger.error(f"Erro ao gerar PDF da receita: {e}")
            logger.error(traceback.format_exc())
            return jsonify({'success': False, 'message': str(e)}), 500
    
    # Download PDF da receita
    @paciente_bp.route('/receita/<int:receita_id>/download')
    @paciente_required
    def download_receita_pdf(receita_id):
        """Download do PDF da receita"""
        paciente_id = obter_paciente_id()
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT r.receita_pdf_path, r.pdf_gerado
            FROM receita r
            JOIN consultas c ON r.consulta_id = c.id
            WHERE r.id = %s AND c.paciente_id = %s
        """, (receita_id, paciente_id))
        
        row = cur.fetchone()
        cur.close()
        
        if not row:
            flash('Receita não encontrada.', 'danger')
            return redirect(url_for('paciente.minhas_consultas'))
        
        if not row[1] or not row[0]:
            flash('PDF não disponível para esta receita.', 'warning')
            return redirect(url_for('paciente.visualizar_receita', receita_id=receita_id))
        
        pdf_path = row[0]
        
        # Verificar se o caminho é absoluto ou relativo
        if not os.path.isabs(pdf_path):
            pdf_path = os.path.join(app.root_path, pdf_path)
        
        if not os.path.exists(pdf_path):
            flash('Arquivo PDF não encontrado no servidor.', 'danger')
            return redirect(url_for('paciente.visualizar_receita', receita_id=receita_id))
        
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f"receita_{receita_id}.pdf",
            mimetype='application/pdf'
        )
    
    # Visualizar receita da consulta
    @paciente_bp.route('/consultas/<int:consulta_id>/receita')
    @paciente_required
    def visualizar_receita_consulta(consulta_id):
        """Redireciona para a receita mais recente da consulta"""
        paciente_id = obter_paciente_id()
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT id FROM receita
            WHERE consulta_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (consulta_id,))
        
        row = cur.fetchone()
        cur.close()
        
        if not row:
            flash('Nenhuma receita encontrada para esta consulta.', 'warning')
            return redirect(url_for('paciente.detalhes_consulta', consulta_id=consulta_id))
        
        return redirect(url_for('paciente.visualizar_receita', receita_id=row[0]))
    
    # Perfil do paciente
    @paciente_bp.route('/perfil', methods=['GET', 'POST'])
    @paciente_required
    def perfil():
        paciente_id = obter_paciente_id()
        
        if request.method == 'POST':
            telefone = request.form.get('telefone')
            endereco = request.form.get('endereco')
            data_nascimento = request.form.get('data_nascimento')
            genero = request.form.get('genero')
            alergias = request.form.get('alergias', '')
            medicamentos_uso = request.form.get('medicamentos_uso', '')
            historico_doencas = request.form.get('historico_doencas', '')
            contato_emergencia = request.form.get('contato_emergencia', '')
            
            execute_query("""
                UPDATE pacientes 
                SET telefone=%s, endereco=%s, data_nascimento=%s, genero=%s,
                    alergias=%s, medicamentos_uso=%s, historico_doencas=%s, contato_emergencia=%s
                WHERE id=%s
            """, (telefone, endereco, data_nascimento, genero,
                  alergias, medicamentos_uso, historico_doencas, contato_emergencia, paciente_id))
            flash('Perfil atualizado com sucesso!', 'success')
            return redirect(url_for('paciente.perfil'))
        
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT p_u.nome, p.data_nascimento, p.genero, p.telefone, p.endereco, p_u.email,
                   p.alergias, p.medicamentos_uso, p.historico_doencas, p.contato_emergencia
            FROM pacientes p
            JOIN usuarios p_u ON p.usuario_id = p_u.id
            WHERE p.id = %s
        """, (paciente_id,))
        info = cur.fetchone()
        cur.close()
        
        return render_template('paciente/perfil.html',
                               paciente_nome=garantir_string(info[0]),
                               data_nascimento=info[1],
                               genero=garantir_string(info[2]),
                               telefone=garantir_string(info[3]),
                               endereco=garantir_string(info[4]),
                               email=garantir_string(info[5]),
                               alergias=garantir_string(info[6]),
                               medicamentos_uso=garantir_string(info[7]),
                               historico_doencas=garantir_string(info[8]),
                               contato_emergencia=garantir_string(info[9]),
                               user=session)
    
    return paciente_bp
