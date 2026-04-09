# routes/paciente/fatura_pdf.py

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.pdfgen import canvas
from reportlab.lib.fonts import addMapping
from datetime import datetime
import os
import traceback

def gerar_pdf_fatura(fatura_data, output_path=None):
    """
    Gera PDF da fatura
    
    Args:
        fatura_data: Dicionário com dados da fatura
        output_path: Caminho para salvar o PDF (opcional)
    
    Returns:
        Caminho do arquivo PDF gerado
    """
    
    if output_path is None:
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
        alignment=1,  # Centralizado
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
    
    bold_style = ParagraphStyle(
        'CustomBold',
        parent=styles['Normal'],
        fontSize=10,
        fontName='Helvetica-Bold',
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