# utils/pdf.py
from reportlab.lib.pagesizes import A4, letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm, mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from io import BytesIO
import html
import re
import logging
import traceback
from datetime import datetime

logger = logging.getLogger(__name__)

def html_to_pdf(html_content, paciente_nome, consulta_data, user_data):
    """
    Converte HTML de receita para PDF com formatação profissional
    Versão melhorada com suporte a estilos e formatação avançada
    """
    try:
        logger.info("Iniciando geração de PDF...")
        
        buffer = BytesIO()
        
        # Configurar documento com margens profissionais
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=A4,
            topMargin=2*cm,
            bottomMargin=2*cm,
            leftMargin=2*cm,
            rightMargin=2*cm
        )
        
        styles = getSampleStyleSheet()
        story = []

        # ===== ESTILOS PERSONALIZADOS =====
        
        # Título principal
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#0B3B5C'),  # Azul escuro profissional
            fontName='Helvetica-Bold',
            leading=22
        )

        # Subtítulos
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=10,
            textColor=colors.HexColor('#1E4A6F'),
            alignment=TA_LEFT,
            fontName='Helvetica-Bold',
            leading=18
        )

        # Cabeçalho de informações
        header_style = ParagraphStyle(
            'CustomHeader',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=4,
            textColor=colors.HexColor('#2C3E50'),
            fontName='Helvetica',
            leading=14
        )

        # Texto normal
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=6,
            textColor=colors.HexColor('#2C3E50'),
            alignment=TA_LEFT,
            fontName='Helvetica',
            leading=16
        )

        # Texto justificado (para diagnósticos longos)
        justified_style = ParagraphStyle(
            'CustomJustified',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=8,
            textColor=colors.HexColor('#2C3E50'),
            alignment=TA_JUSTIFY,
            fontName='Helvetica',
            leading=16
        )

        # Estilo para prescrição (com indentação)
        prescription_style = ParagraphStyle(
            'CustomPrescription',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=6,
            leftIndent=15,
            textColor=colors.HexColor('#1E3A5F'),
            fontName='Helvetica',
            leading=16
        )

        # Estilo para recomendações (itálico)
        recommendation_style = ParagraphStyle(
            'CustomRecommendation',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=4,
            leftIndent=10,
            textColor=colors.HexColor('#2C3E50'),
            fontName='Helvetica-Oblique',
            leading=14
        )

        # Rodapé
        footer_style = ParagraphStyle(
            'CustomFooter',
            parent=styles['Normal'],
            fontSize=9,
            spaceBefore=20,
            spaceAfter=2,
            textColor=colors.HexColor('#7F8C8D'),
            alignment=TA_CENTER,
            fontName='Helvetica',
            leading=12
        )

        # Assinatura
        signature_style = ParagraphStyle(
            'CustomSignature',
            parent=styles['Normal'],
            fontSize=11,
            spaceBefore=15,
            spaceAfter=5,
            textColor=colors.HexColor('#2C3E50'),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            leading=14
        )

        # ===== LINHA SEPARADORA =====
        def linha_separadora():
            return HRFlowable(
                width="100%",
                thickness=1,
                lineCap='round',
                color=colors.HexColor('#CCCCCC'),
                spaceBefore=5,
                spaceAfter=5,
                hAlign='CENTER'
            )

        # ===== CONSTRUÇÃO DO PDF =====
        
        # TÍTULO
        story.append(Paragraph("RECEITA MÉDICA", title_style))
        story.append(Spacer(1, 0.2*inch))
        story.append(linha_separadora())
        story.append(Spacer(1, 0.2*inch))

        # CABEÇALHO COM INFORMAÇÕES
        # Tabela para organizar informações lado a lado
        cabecalho_data = [
            [Paragraph(f"<b>Paciente:</b> {paciente_nome}", header_style),
             Paragraph(f"<b>Data:</b> {consulta_data}", header_style)],
            [Paragraph(f"<b>Médico:</b> Dr(a). {user_data.get('user_name', 'Médico')}", header_style),
             Paragraph(f"<b>CRM:</b> {user_data.get('crm', '')}", header_style)],
        ]
        
        tabela_cabecalho = Table(cabecalho_data, colWidths=['50%', '50%'])
        tabela_cabecalho.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(tabela_cabecalho)
        story.append(Spacer(1, 0.2*inch))

        # PROCESSAMENTO DO CONTEÚDO HTML
        # Remover tags HTML e CSS, mas preservar estrutura
        cleaned_html = re.sub(r'<style.*?>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        cleaned_html = re.sub(r'<script.*?>.*?</script>', '', cleaned_html, flags=re.DOTALL | re.IGNORECASE)
        
        # Converter quebras de linha para processamento
        cleaned_html = cleaned_html.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
        
        # Extrair texto sem tags
        text_content = re.sub(r'<[^>]+>', '', cleaned_html)
        text_content = html.unescape(text_content)
        
        # Dividir em linhas
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]

        # Processar linha por linha
        em_prescricao = False
        em_recomendacoes = False
        em_diagnostico = False
        
        for i, line in enumerate(lines):
            line_upper = line.upper()
            
            # Detectar seções principais
            if re.search(r'\b(DIAGNÓSTICO|DIAGNOSTICO)\b', line_upper):
                em_diagnostico = True
                em_prescricao = False
                em_recomendacoes = False
                story.append(Spacer(1, 0.15*inch))
                story.append(Paragraph(f"<b>1. {line}</b>", subtitle_style))
                
            elif re.search(r'\b(PRESCRIÇÃO|PRESCRICAO|MEDICAMENTOS)\b', line_upper):
                em_prescricao = True
                em_diagnostico = False
                em_recomendacoes = False
                story.append(Spacer(1, 0.15*inch))
                story.append(Paragraph(f"<b>2. {line}</b>", subtitle_style))
                
            elif re.search(r'\b(RECOMENDAÇÕES|RECOMENDACOES|ORIENTAÇÕES)\b', line_upper):
                em_recomendacoes = True
                em_diagnostico = False
                em_prescricao = False
                story.append(Spacer(1, 0.15*inch))
                story.append(Paragraph(f"<b>3. {line}</b>", subtitle_style))
                
            # Itens de lista numerada
            elif re.match(r'^\d+\.', line):
                if em_prescricao:
                    story.append(Paragraph(f"&nbsp;&nbsp;{line}", prescription_style))
                elif em_recomendacoes:
                    story.append(Paragraph(f"&nbsp;&nbsp;{line}", recommendation_style))
                else:
                    story.append(Paragraph(line, normal_style))
                    
            # Itens com marcadores
            elif re.match(r'^[•\-*]', line):
                if em_recomendacoes:
                    story.append(Paragraph(f"&nbsp;&nbsp;{line}", recommendation_style))
                else:
                    story.append(Paragraph(f"&nbsp;&nbsp;{line}", normal_style))
                    
            # Subitens com indentação
            elif line.startswith('   ') or line.startswith('  ') or line.startswith(' *'):
                if em_prescricao:
                    story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;{line.strip()}", prescription_style))
                else:
                    story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;{line.strip()}", normal_style))
                    
            # Texto normal
            else:
                if em_diagnostico and len(line) > 50:  # Diagnóstico longo
                    story.append(Paragraph(line, justified_style))
                elif em_prescricao:
                    story.append(Paragraph(line, prescription_style))
                elif em_recomendacoes:
                    story.append(Paragraph(line, recommendation_style))
                else:
                    story.append(Paragraph(line, normal_style))

        # ===== AVISO IMPORTANTE =====
        story.append(Spacer(1, 0.3*inch))
        aviso_data = [[Paragraph(
            "<b>IMPORTANTE:</b> Esta receita foi baseada no diagnóstico do paciente. "
            "Em caso de dúvidas, consultar o médico prescritor.", 
            recommendation_style
        )]]
        
        tabela_aviso = Table(aviso_data, colWidths=['100%'])
        tabela_aviso.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFF9E6')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#FFC107')),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(tabela_aviso)
        story.append(Spacer(1, 0.3*inch))

        # ===== ASSINATURA =====
        story.append(linha_separadora())
        story.append(Spacer(1, 0.2*inch))
        
        story.append(Paragraph(f"Dr(a). {user_data.get('user_name', 'Médico')}", signature_style))
        story.append(Paragraph(f"CRM: {user_data.get('crm', '')}", signature_style))
        
        story.append(Spacer(1, 0.2*inch))

        # ===== RODAPÉ =====
        data_emissao = datetime.now().strftime('%d/%m/%Y às %H:%M')
        story.append(Paragraph(f"Documento emitido em {data_emissao}", footer_style))
        story.append(Paragraph("Este documento é válido em todo território nacional", footer_style))
        story.append(Paragraph("DoctorIA - Sistema Médico © 2024", footer_style))

        # Gerar PDF
        logger.info("Construindo documento PDF...")
        doc.build(story)
        
        buffer.seek(0)
        
        # Verificar se o PDF não está vazio
        if buffer.getbuffer().nbytes == 0:
            raise Exception("PDF gerado está vazio")
        
        logger.info(f"PDF gerado com sucesso! Tamanho: {buffer.getbuffer().nbytes} bytes")
        return buffer

    except Exception as e:
        logger.error(f"Erro detalhado ao gerar PDF: {e}")
        logger.error(traceback.format_exc())

        # ===== PDF DE EMERGÊNCIA =====
        try:
            logger.info("Gerando PDF de emergência...")
            
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []
            
            # Título
            story.append(Paragraph("RECEITA MÉDICA", styles['Heading1']))
            story.append(Spacer(1, 0.3*inch))
            
            # Informações básicas
            story.append(Paragraph(f"<b>Paciente:</b> {paciente_nome}", styles['Normal']))
            story.append(Paragraph(f"<b>Data da Consulta:</b> {consulta_data}", styles['Normal']))
            story.append(Paragraph(f"<b>Médico:</b> Dr(a). {user_data.get('user_name', 'Médico')}", styles['Normal']))
            story.append(Spacer(1, 0.2*inch))
            
            # Mensagem de erro
            story.append(Paragraph(
                "Ocorreu um problema técnico ao gerar a receita completa.",
                styles['Normal']
            ))
            story.append(Paragraph(
                "Por favor, consulte o sistema para visualizar a receita original ou tente novamente.",
                styles['Normal']
            ))
            story.append(Spacer(1, 0.2*inch))
            
            # Extrair texto básico do HTML original
            try:
                text_only = re.sub(r'<[^>]+>', '', html_content)
                text_only = html.unescape(text_only)
                lines = text_only.split('\n')[:20]  # Primeiras 20 linhas
                
                story.append(Paragraph("<b>Conteúdo da receita (resumido):</b>", styles['Normal']))
                for line in lines:
                    if line.strip():
                        story.append(Paragraph(f"• {line[:100]}...", styles['Normal']))
            except:
                pass
            
            story.append(Spacer(1, 0.3*inch))
            story.append(Paragraph("_" * 40, styles['Normal']))
            story.append(Paragraph(f"Dr(a). {user_data.get('user_name', 'Médico')}", styles['Normal']))
            story.append(Paragraph(f"CRM: {user_data.get('crm', '')}", styles['Normal']))
            story.append(Spacer(1, 0.1*inch))
            story.append(Paragraph(f"Emitido em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", footer_style))
            
            doc.build(story)
            buffer.seek(0)
            
            logger.info("PDF de emergência gerado com sucesso")
            return buffer
            
        except Exception as fallback_error:
            logger.error(f"Erro no PDF de emergência: {fallback_error}")
            return None


def gerar_pdf_receita_simples(texto, paciente_nome, medico_nome, crm):
    """
    Função auxiliar para gerar PDF de receita de forma simples
    Útil para testes ou casos simples
    """
    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # Título
        story.append(Paragraph("RECEITA MÉDICA", styles['Title']))
        story.append(Spacer(1, 0.2*inch))
        
        # Informações
        story.append(Paragraph(f"<b>Paciente:</b> {paciente_nome}", styles['Normal']))
        story.append(Paragraph(f"<b>Médico:</b> Dr(a). {medico_nome}", styles['Normal']))
        story.append(Paragraph(f"<b>CRM:</b> {crm}", styles['Normal']))
        story.append(Paragraph(f"<b>Data:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Conteúdo
        story.append(Paragraph("PRESCRIÇÃO:", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        
        for linha in texto.split('\n'):
            if linha.strip():
                story.append(Paragraph(linha, styles['Normal']))
        
        # Assinatura
        story.append(Spacer(1, 0.3*inch))
        story.append(Paragraph("_" * 40, styles['Normal']))
        story.append(Paragraph(f"Dr(a). {medico_nome}", styles['Normal']))
        story.append(Paragraph(f"CRM: {crm}", styles['Normal']))
        
        doc.build(story)
        buffer.seek(0)
        
        return buffer
        
    except Exception as e:
        logger.error(f"Erro ao gerar PDF simples: {e}")
        return None


def html_to_texto_plano(html_content):
    """
    Converte HTML para texto plano, removendo todas as tags
    Útil para debugging ou fallback
    """
    try:
        # Remover tags HTML
        text = re.sub(r'<[^>]+>', '', html_content)
        # Decodificar entidades HTML
        text = html.unescape(text)
        # Remover linhas em branco extras
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text.strip()
    except Exception as e:
        logger.error(f"Erro ao converter HTML para texto: {e}")
        return html_content