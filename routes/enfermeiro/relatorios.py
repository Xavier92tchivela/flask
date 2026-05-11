# routes/enfermeiro/relatorios.py
from flask import Blueprint, render_template, session, request, jsonify, send_file
from .utils import execute_query, enfermeiro_required, decode_bytes
from datetime import datetime, timedelta
import pandas as pd
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

relatorios_bp = Blueprint('relatorios', __name__, url_prefix='/relatorios')

_mysql = None

def set_mysql(mysql_instance):
    global _mysql
    _mysql = mysql_instance

@relatorios_bp.route('/')
@enfermeiro_required
def dashboard_relatorios():
    """Dashboard de relatórios"""
    return render_template('enfermeiro/relatorios/dashboard.html')


@relatorios_bp.route('/consultas')
@enfermeiro_required
def relatorio_consultas():
    """Relatório de consultas por período"""
    hoje = datetime.now()
    
    # Parâmetros
    tipo = request.args.get('tipo', 'diario')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    if not data_inicio:
        if tipo == 'diario':
            data_inicio = hoje.strftime('%Y-%m-%d')
            data_fim = hoje.strftime('%Y-%m-%d')
        elif tipo == 'semanal':
            inicio_semana = hoje - timedelta(days=hoje.weekday())
            data_inicio = inicio_semana.strftime('%Y-%m-%d')
            data_fim = hoje.strftime('%Y-%m-%d')
        elif tipo == 'mensal':
            data_inicio = hoje.replace(day=1).strftime('%Y-%m-%d')
            data_fim = hoje.strftime('%Y-%m-%d')
    
    # Buscar dados
    query = """
        SELECT 
            c.id,
            c.data_hora,
            c.status,
            DATE(c.data_hora) as data,
            TIME(c.data_hora) as hora,
            u.nome as paciente_nome,
            m_u.nome as medico_nome,
            m.especialidade,
            c.diagnostico_texto,
            c.diagnostico_final,
            CASE 
                WHEN c.status_triagem IS NOT NULL THEN 'Realizada'
                ELSE 'Pendente'
            END as triagem_status
        FROM consultas c
        JOIN pacientes p ON c.paciente_id = p.id
        JOIN usuarios u ON p.usuario_id = u.id
        JOIN medicos m ON c.medico_id = m.id
        JOIN usuarios m_u ON m.usuario_id = m_u.id
        WHERE DATE(c.data_hora) BETWEEN %s AND %s
        ORDER BY c.data_hora DESC
    """
    
    consultas = execute_query(query, (data_inicio, data_fim), fetch=True) or []
    
    # Estatísticas
    stats = {
        'total': len(consultas),
        'realizadas': sum(1 for c in consultas if c.get('status') == 'realizada'),
        'agendadas': sum(1 for c in consultas if c.get('status') == 'agendada'),
        'canceladas': sum(1 for c in consultas if c.get('status') == 'cancelada'),
        'com_triagem': sum(1 for c in consultas if c.get('triagem_status') == 'Realizada'),
        'com_diagnostico': sum(1 for c in consultas if c.get('diagnostico_final')),
        'medicos_ativos': len(set(c.get('medico_nome') for c in consultas if c.get('medico_nome')))
    }
    
    # Agrupar por dia
    dias = {}
    for c in consultas:
        data = str(c.get('data')) if c.get('data') else 'Sem data'
        if data not in dias:
            dias[data] = 0
        dias[data] += 1
    
    return render_template('enfermeiro/relatorios/consultas.html',
        consultas=consultas,
        stats=stats,
        dias=dias,
        tipo=tipo,
        data_inicio=data_inicio,
        data_fim=data_fim)


@relatorios_bp.route('/sinais-vitais')
@enfermeiro_required
def relatorio_sinais_vitais():
    """Relatório de sinais vitais"""
    tipo = request.args.get('tipo', 'diario')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    hoje = datetime.now()
    
    if not data_inicio:
        if tipo == 'diario':
            data_inicio = hoje.strftime('%Y-%m-%d')
            data_fim = hoje.strftime('%Y-%m-%d')
        elif tipo == 'semanal':
            inicio_semana = hoje - timedelta(days=hoje.weekday())
            data_inicio = inicio_semana.strftime('%Y-%m-%d')
            data_fim = hoje.strftime('%Y-%m-%d')
        elif tipo == 'mensal':
            data_inicio = hoje.replace(day=1).strftime('%Y-%m-%d')
            data_fim = hoje.strftime('%Y-%m-%d')
    
    query = """
        SELECT 
            sv.id,
            sv.data_afericao,
            sv.pressao_arterial,
            sv.frequencia_cardiaca,
            sv.frequencia_respiratoria,
            sv.temperatura,
            sv.saturacao_oxigenio,
            sv.glicemia,
            sv.peso,
            u.nome as paciente_nome,
            e.nome as enfermeiro_nome
        FROM sinais_vitais sv
        JOIN consultas c ON sv.consulta_id = c.id
        JOIN pacientes p ON c.paciente_id = p.id
        JOIN usuarios u ON p.usuario_id = u.id
        LEFT JOIN enfermeiros enf ON sv.enfermeiro_id = enf.id
        LEFT JOIN usuarios e ON enf.usuario_id = e.id
        WHERE DATE(sv.data_afericao) BETWEEN %s AND %s
        ORDER BY sv.data_afericao DESC
    """
    
    sinais = execute_query(query, (data_inicio, data_fim), fetch=True) or []
    
    # Estatísticas
    stats = {
        'total': len(sinais),
        'pressao_alterada': sum(1 for s in sinais if s.get('pressao_arterial') and 'x' in s.get('pressao_arterial', '')),
        'febre': sum(1 for s in sinais if s.get('temperatura') and float(s.get('temperatura')) > 37.5),
        'glicemia_alterada': sum(1 for s in sinais if s.get('glicemia') and (int(s.get('glicemia')) < 70 or int(s.get('glicemia')) > 140)),
        'media_fc': round(sum(float(s.get('frequencia_cardiaca') or 0) for s in sinais) / len(sinais) if sinais else 0, 1)
    }
    
    return render_template('enfermeiro/relatorios/sinais_vitais.html',
        sinais=sinais,
        stats=stats,
        tipo=tipo,
        data_inicio=data_inicio,
        data_fim=data_fim)


@relatorios_bp.route('/exportar-excel')
@enfermeiro_required
def exportar_excel():
    """Exportar dados para Excel"""
    tipo = request.args.get('tipo', 'consultas')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    if tipo == 'consultas':
        query = """
            SELECT 
                DATE(c.data_hora) as Data,
                TIME(c.data_hora) as Hora,
                u.nome as Paciente,
                m_u.nome as Médico,
                c.status as Status,
                c.diagnostico_final as Diagnóstico
            FROM consultas c
            JOIN pacientes p ON c.paciente_id = p.id
            JOIN usuarios u ON p.usuario_id = u.id
            JOIN medicos m ON c.medico_id = m.id
            JOIN usuarios m_u ON m.usuario_id = m_u.id
            WHERE DATE(c.data_hora) BETWEEN %s AND %s
            ORDER BY c.data_hora DESC
        """
        dados = execute_query(query, (data_inicio, data_fim), fetch=True) or []
        nome_arquivo = f"relatorio_consultas_{data_inicio}_a_{data_fim}.xlsx"
    
    elif tipo == 'sinais':
        query = """
            SELECT 
                DATE(sv.data_afericao) as Data,
                TIME(sv.data_afericao) as Hora,
                u.nome as Paciente,
                sv.pressao_arterial as Pressão,
                sv.frequencia_cardiaca as FC,
                sv.temperatura as Temperatura,
                sv.glicemia as Glicemia,
                sv.peso as Peso
            FROM sinais_vitais sv
            JOIN consultas c ON sv.consulta_id = c.id
            JOIN pacientes p ON c.paciente_id = p.id
            JOIN usuarios u ON p.usuario_id = u.id
            WHERE DATE(sv.data_afericao) BETWEEN %s AND %s
            ORDER BY sv.data_afericao DESC
        """
        dados = execute_query(query, (data_inicio, data_fim), fetch=True) or []
        nome_arquivo = f"relatorio_sinais_{data_inicio}_a_{data_fim}.xlsx"
    
    else:
        return jsonify({'error': 'Tipo inválido'}), 400
    
    # Criar DataFrame
    df = pd.DataFrame(dados)
    
    # Exportar para Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Relatório', index=False)
        
        # Ajustar largura das colunas
        worksheet = writer.sheets['Relatório']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=nome_arquivo
    )


@relatorios_bp.route('/exportar-pdf')
@enfermeiro_required
def exportar_pdf():
    """Exportar dados para PDF"""
    from weasyprint import HTML
    from flask import render_template_string
    
    tipo = request.args.get('tipo', 'consultas')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    # Buscar dados (mesma lógica do exportar_excel)
    if tipo == 'consultas':
        query = """
            SELECT 
                DATE(c.data_hora) as Data,
                TIME(c.data_hora) as Hora,
                u.nome as Paciente,
                m_u.nome as Médico,
                c.status as Status
            FROM consultas c
            JOIN pacientes p ON c.paciente_id = p.id
            JOIN usuarios u ON p.usuario_id = u.id
            JOIN medicos m ON c.medico_id = m.id
            JOIN usuarios m_u ON m.usuario_id = m_u.id
            WHERE DATE(c.data_hora) BETWEEN %s AND %s
            ORDER BY c.data_hora DESC
        """
        dados = execute_query(query, (data_inicio, data_fim), fetch=True) or []
        titulo = f"Relatório de Consultas - {data_inicio} a {data_fim}"
    
    else:
        query = """
            SELECT 
                DATE(sv.data_afericao) as Data,
                TIME(sv.data_afericao) as Hora,
                u.nome as Paciente,
                sv.pressao_arterial as Pressão,
                sv.frequencia_cardiaca as FC,
                sv.temperatura as Temperatura
            FROM sinais_vitais sv
            JOIN consultas c ON sv.consulta_id = c.id
            JOIN pacientes p ON c.paciente_id = p.id
            JOIN usuarios u ON p.usuario_id = u.id
            WHERE DATE(sv.data_afericao) BETWEEN %s AND %s
            ORDER BY sv.data_afericao DESC
        """
        dados = execute_query(query, (data_inicio, data_fim), fetch=True) or []
        titulo = f"Relatório de Sinais Vitais - {data_inicio} a {data_fim}"
    
    # Template HTML para PDF
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{titulo}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #4e73df; text-align: center; }}
            .header {{ text-align: center; margin-bottom: 20px; }}
            .periodo {{ color: #666; margin-bottom: 20px; text-align: center; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #4e73df; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            .footer {{ text-align: center; margin-top: 30px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>DoctorIA - Sistema Médico</h1>
            <h2>{titulo}</h2>
        </div>
        <div class="periodo">
            <strong>Período:</strong> {data_inicio} a {data_fim}<br>
            <strong>Data de emissão:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M')}
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>Data</th>
                    <th>Hora</th>
                    <th>Paciente</th>
                    <th>{'Médico' if tipo == 'consultas' else 'Pressão'}</th>
                    <th>{'Status' if tipo == 'consultas' else 'FC'}</th>
                    <th>{'--' if tipo == 'consultas' else 'Temperatura'}</th>
                </tr>
            </thead>
            <tbody>
                {''.join(f'''
                <tr>
                    <td>{d.get('Data', '')}</td>
                    <td>{d.get('Hora', '')}</td>
                    <td>{d.get('Paciente', '')}</td>
                    <td>{d.get('Médico', '') if tipo == 'consultas' else d.get('Pressão', '')}</td>
                    <td>{d.get('Status', '') if tipo == 'consultas' else d.get('FC', '')}</td>
                    <td>{'' if tipo == 'consultas' else d.get('Temperatura', '')}</td>
                </tr>
                ''' for d in dados)}
            </tbody>
        </table>
        
        <div class="footer">
            <p>DoctorIA - Sistema de Gestão Médica</p>
            <p>Documento gerado automaticamente</p>
        </div>
    </body>
    </html>
    """
    
    # Gerar PDF
    pdf = HTML(string=html_content).write_pdf()
    
    return send_file(
        BytesIO(pdf),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"{tipo}_{data_inicio}_a_{data_fim}.pdf"
    )
