from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from datetime import date, datetime
from .utils import execute_query, enfermeiro_required, classificar_pressao, formatar_data, formatar_data_hora
import logging
import re
from functools import wraps

logger = logging.getLogger(__name__)

# IMPORTANTE: O prefixo deve ser /enfermeiro/sinais-vitais
sinais_vitais_bp = Blueprint('sinais_vitais', __name__, url_prefix='/enfermeiro/sinais-vitais')

# Atributo para armazenar a conexão MySQL
sinais_vitais_bp.mysql = None

def set_mysql(mysql_instance):
    """Configura a conexão MySQL para este módulo"""
    sinais_vitais_bp.mysql = mysql_instance
    from .utils import set_mysql as set_utils_mysql
    set_utils_mysql(mysql_instance)


def enfermeiro_ou_medico_required(f):
    """Decorator que permite acesso para enfermeiros e médicos"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        user_type = session.get('user_type')  # USAR user_type em vez de perfil
        
        logger.info(f"Verificando acesso: user_id={user_id}, user_type={user_type}")
        
        if not user_id:
            logger.warning("Usuário não autenticado - redirecionando para login")
            flash('Você precisa estar logado para acessar esta página.', 'danger')
            return redirect(url_for('auth.login'))
        
        # Verificar user_type (mais confiável)
        if user_type and user_type.lower() in ['enfermeiro', 'enfermeira', 'medico']:
            logger.info(f"Acesso autorizado para {user_type}")
            return f(*args, **kwargs)
        
        logger.warning(f"Acesso negado: user_type={user_type}")
        flash('Acesso não autorizado. Apenas enfermeiros e médicos podem acessar.', 'danger')
        return redirect(url_for('auth.login'))
    return decorated_function


@sinais_vitais_bp.route('/')
@enfermeiro_required
def listar_sinais_vitais():
    """Lista todos os sinais vitais registrados"""
    enfermeiro_id = session.get('enfermeiro_id')
    
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    paciente = request.args.get('paciente', '')
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
    
    query_base = """
        FROM sinais_vitais sv
        INNER JOIN consultas c ON sv.consulta_id = c.id
        INNER JOIN pacientes p ON c.paciente_id = p.id
        INNER JOIN usuarios u ON p.usuario_id = u.id
        WHERE sv.enfermeiro_id = %s
    """
    params = [enfermeiro_id]
    
    if paciente:
        query_base += " AND u.nome LIKE %s"
        params.append(f'%{paciente}%')
    
    if data_inicio:
        query_base += " AND DATE(sv.data_afericao) >= %s"
        params.append(data_inicio)
    
    if data_fim:
        query_base += " AND DATE(sv.data_afericao) <= %s"
        params.append(data_fim)
    
    total_result = execute_query(f"SELECT COUNT(*) as total {query_base}", params, fetch=True, one=True)
    total = total_result['total'] if total_result else 0
    
    query = f"""
        SELECT 
            sv.id, 
            sv.pressao_arterial, 
            sv.frequencia_cardiaca,
            sv.frequencia_respiratoria, 
            sv.temperatura,
            sv.saturacao_oxigenio, 
            sv.glicemia, 
            sv.peso,
            sv.data_afericao,
            sv.observacoes,
            u.nome as paciente_nome, 
            p.id as paciente_id,
            p.data_nascimento,
            p.genero,
            c.data_hora as data_hora_consulta,
            c.status,
            c.status_triagem
        {query_base}
        ORDER BY sv.data_afericao DESC
        LIMIT %s OFFSET %s
    """
    params_extended = params + [per_page, offset]
    
    sinais_vitais = execute_query(query, params_extended, fetch=True) or []
    
    for sv in sinais_vitais:
        if sv.get('data_afericao'):
            if isinstance(sv['data_afericao'], datetime):
                sv['data_afericao_formatada'] = sv['data_afericao'].strftime('%d/%m/%Y %H:%M')
            else:
                sv['data_afericao_formatada'] = str(sv['data_afericao'])
        
        if sv.get('data_nascimento'):
            if isinstance(sv['data_nascimento'], (date, datetime)):
                sv['data_nascimento_formatada'] = sv['data_nascimento'].strftime('%d/%m/%Y')
                hoje = date.today()
                nascimento = sv['data_nascimento']
                if isinstance(nascimento, datetime):
                    nascimento = nascimento.date()
                idade = hoje.year - nascimento.year
                if (hoje.month, hoje.day) < (nascimento.month, nascimento.day):
                    idade -= 1
                sv['idade'] = idade
            else:
                sv['data_nascimento_formatada'] = str(sv['data_nascimento'])
        
        if sv.get('data_hora_consulta'):
            if isinstance(sv['data_hora_consulta'], datetime):
                sv['data_consulta_formatada'] = sv['data_hora_consulta'].strftime('%d/%m/%Y')
                sv['hora_consulta_formatada'] = sv['data_hora_consulta'].strftime('%H:%M')
            else:
                sv['data_consulta_formatada'] = str(sv['data_hora_consulta'])
    
    return render_template('enfermeiro/sinais_vitais/listar.html',
        sinais_vitais=sinais_vitais,
        pagination={
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': (total + per_page - 1) // per_page if total > 0 else 1
        },
        classificar_pressao=classificar_pressao,
        formatar_data=formatar_data,
        formatar_data_hora=formatar_data_hora)


@sinais_vitais_bp.route('/registrar', methods=['GET', 'POST'])
@sinais_vitais_bp.route('/registrar/<int:consulta_id>', methods=['GET', 'POST'])
@enfermeiro_ou_medico_required
def registrar_sinais_vitais(consulta_id=None):
    """Registra novos sinais vitais (enfermeiro ou médico)"""
    usuario_id = session.get('user_id')
    user_type = session.get('user_type')  # USAR user_type
    enfermeiro_id = session.get('enfermeiro_id')
    medico_id = session.get('medico_id')
    
    logger.info(f"Registrar SV - consulta_id={consulta_id}, user_type={user_type}, user_id={usuario_id}")
    
    # Responsável pelo registro (enfermeiro ou médico)
    responsavel_id = enfermeiro_id if enfermeiro_id else medico_id
    
    if request.method == 'POST':
        consulta_id_post = request.form.get('consulta_id')
        if not consulta_id_post and consulta_id:
            consulta_id_post = consulta_id
        
        pressao = request.form.get('pressao_arterial')
        fc = request.form.get('frequencia_cardiaca') or None
        fr = request.form.get('frequencia_respiratoria') or None
        temp = request.form.get('temperatura') or None
        sat = request.form.get('saturacao_oxigenio') or None
        glicemia = request.form.get('glicemia') or None
        peso = request.form.get('peso') or None
        observacoes = request.form.get('observacoes')
        
        if not consulta_id_post:
            flash('Selecione um paciente.', 'danger')
            return redirect(url_for('enfermeiro.sinais_vitais.registrar_sinais_vitais'))
        
        if pressao:
            pressao = pressao.replace('/', 'x')
            if not re.match(r'^\d{2,3}x\d{2,3}$', pressao):
                flash('Formato de pressão arterial inválido. Use: 120/80 ou 120x80', 'danger')
                return redirect(url_for('enfermeiro.sinais_vitais.registrar_sinais_vitais', consulta_id=consulta_id_post))
        
        try:
            result = execute_query("""
                INSERT INTO sinais_vitais (
                    consulta_id, enfermeiro_id, pressao_arterial,
                    frequencia_cardiaca, frequencia_respiratoria, temperatura,
                    saturacao_oxigenio, glicemia, peso, data_afericao, observacoes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
            """, (consulta_id_post, responsavel_id, pressao, fc, fr, temp, sat, glicemia, peso, observacoes))
            
            if result:
                execute_query("""
                    UPDATE consultas 
                    SET status_triagem = 'REALIZADA', 
                        enfermeiro_id = %s,
                        data_triagem = NOW()
                    WHERE id = %s
                """, (responsavel_id, consulta_id_post))
                
                flash('Sinais vitais registrados com sucesso!', 'success')
                logger.info(f"Sinais vitais registrados para consulta {consulta_id_post} por {user_type} {usuario_id}")
                
                origem = request.args.get('origem') or request.form.get('origem')
                if origem == 'medico' or user_type == 'medico':
                    # CORRIGIDO: usar a rota correta de detalhes da consulta
                    return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id_post))
            else:
                flash('Erro ao registrar sinais vitais.', 'danger')
                
        except Exception as e:
            logger.error(f"Erro ao registrar sinais vitais: {e}")
            flash(f'Erro ao registrar sinais vitais: {str(e)}', 'danger')
        
        if user_type == 'medico':
            return redirect(url_for('consulta.detalhes_consulta', consulta_id=consulta_id_post))
        return redirect(url_for('enfermeiro.sinais_vitais.listar_sinais_vitais'))
    
    # GET - Mostrar formulário
    if consulta_id:
        consulta_raw = execute_query("""
            SELECT 
                c.id, 
                u.nome as paciente_nome, 
                p.id as paciente_id,
                p.data_nascimento,
                p.genero,
                c.data_hora,
                c.status,
                c.status_triagem,
                c.medico_id
            FROM consultas c
            JOIN pacientes p ON c.paciente_id = p.id
            JOIN usuarios u ON p.usuario_id = u.id
            WHERE c.id = %s
        """, (consulta_id,), fetch=True, one=True)
        
        if not consulta_raw:
            flash('Consulta não encontrada.', 'danger')
            if user_type == 'medico':
                return redirect(url_for('medico.dashboard'))
            return redirect(url_for('enfermeiro.dashboard.index'))
        
        if user_type == 'medico' and consulta_raw.get('medico_id') != medico_id:
            flash('Você não tem permissão para registrar sinais vitais nesta consulta.', 'danger')
            return redirect(url_for('medico.dashboard'))
        
        consulta = dict(consulta_raw)
        
        if consulta.get('data_hora'):
            if isinstance(consulta['data_hora'], datetime):
                consulta['data_consulta'] = consulta['data_hora'].strftime('%d/%m/%Y')
                consulta['hora_consulta'] = consulta['data_hora'].strftime('%H:%M')
        
        if consulta.get('data_nascimento'):
            if isinstance(consulta['data_nascimento'], (date, datetime)):
                nascimento = consulta['data_nascimento']
                if isinstance(nascimento, datetime):
                    nascimento = nascimento.date()
                hoje = date.today()
                idade = hoje.year - nascimento.year
                if (hoje.month, hoje.day) < (nascimento.month, nascimento.day):
                    idade -= 1
                consulta['idade'] = idade
        
        return render_template('enfermeiro/sinais_vitais/registrar.html',
            consulta_especifica=consulta,
            consulta_selecionada=consulta,
            perfil=user_type,
            origem=request.args.get('origem', ''))
    
    # Sem consulta_id - mostrar lista
    consultas = execute_query("""
        SELECT 
            c.id, 
            u.nome as paciente_nome, 
            p.id as paciente_id,
            p.data_nascimento,
            p.genero,
            c.data_hora,
            c.status,
            c.status_triagem
        FROM consultas c
        JOIN pacientes p ON c.paciente_id = p.id
        JOIN usuarios u ON p.usuario_id = u.id
        WHERE c.status IN ('agendada', 'confirmada', 'AGENDADA', 'CONFIRMADA', 'Aguardando', 'Pendente', 'realizada', 'REALIZADA')
        ORDER BY c.data_hora DESC
        LIMIT 200
    """, fetch=True) or []
    
    consultas_formatadas = []
    for c in consultas:
        consulta_dict = dict(c)
        
        if consulta_dict.get('data_nascimento'):
            if isinstance(consulta_dict['data_nascimento'], (date, datetime)):
                nascimento = consulta_dict['data_nascimento']
                if isinstance(nascimento, datetime):
                    nascimento = nascimento.date()
                hoje = date.today()
                idade = hoje.year - nascimento.year
                if (hoje.month, hoje.day) < (nascimento.month, nascimento.day):
                    idade -= 1
                consulta_dict['idade'] = idade
        
        if consulta_dict.get('data_hora'):
            if isinstance(consulta_dict['data_hora'], datetime):
                consulta_dict['data_consulta'] = consulta_dict['data_hora'].strftime('%d/%m/%Y')
                consulta_dict['hora_consulta'] = consulta_dict['data_hora'].strftime('%H:%M')
        
        consultas_formatadas.append(consulta_dict)
    
    consultas_sem_triagem = [c for c in consultas_formatadas if c.get('status_triagem') != 'REALIZADA']
    consultas_com_triagem = [c for c in consultas_formatadas if c.get('status_triagem') == 'REALIZADA']
    
    return render_template('enfermeiro/sinais_vitais/registrar.html',
        consultas_pendentes=consultas_formatadas,
        consultas_sem_triagem=consultas_sem_triagem,
        consultas_com_triagem=consultas_com_triagem,
        consulta_selecionada=None,
        perfil=user_type,
        origem=request.args.get('origem', ''))


@sinais_vitais_bp.route('/<int:vital_id>')
@enfermeiro_ou_medico_required
def detalhes_sinais_vitais(vital_id):
    """Mostra detalhes de um registro de sinais vitais"""
    vital = execute_query("""
        SELECT 
            sv.*,
            u.nome as paciente_nome, 
            p.id as paciente_id,
            p.data_nascimento,
            p.genero,
            c.data_hora as data_hora_consulta,
            c.status,
            c.status_triagem,
            sv.enfermeiro_id as responsavel_id
        FROM sinais_vitais sv
        JOIN consultas c ON sv.consulta_id = c.id
        JOIN pacientes p ON c.paciente_id = p.id
        JOIN usuarios u ON p.usuario_id = u.id
        WHERE sv.id = %s
    """, (vital_id,), fetch=True, one=True)
    
    if not vital:
        flash('Registro não encontrado.', 'danger')
        return redirect(url_for('enfermeiro.sinais_vitais.listar_sinais_vitais'))
    
    if vital.get('data_afericao'):
        if isinstance(vital['data_afericao'], datetime):
            vital['data_afericao_formatada'] = vital['data_afericao'].strftime('%d/%m/%Y %H:%M')
    
    if vital.get('data_hora_consulta'):
        if isinstance(vital['data_hora_consulta'], datetime):
            vital['data_consulta_formatada'] = vital['data_hora_consulta'].strftime('%d/%m/%Y')
            vital['hora_consulta_formatada'] = vital['data_hora_consulta'].strftime('%H:%M')
    
    if vital.get('data_nascimento'):
        if isinstance(vital['data_nascimento'], (date, datetime)):
            nascimento = vital['data_nascimento']
            if isinstance(nascimento, datetime):
                nascimento = nascimento.date()
            hoje = date.today()
            idade = hoje.year - nascimento.year
            if (hoje.month, hoje.day) < (nascimento.month, nascimento.day):
                idade -= 1
            vital['idade'] = idade
            vital['data_nascimento_formatada'] = nascimento.strftime('%d/%m/%Y')
    
    return render_template('enfermeiro/sinais_vitais/detalhes.html',
        vital=vital,
        classificar_pressao=classificar_pressao,
        formatar_data=formatar_data,
        formatar_data_hora=formatar_data_hora)


@sinais_vitais_bp.route('/<int:vital_id>/editar', methods=['GET', 'POST'])
@enfermeiro_required
def editar_sinais_vitais(vital_id):
    """Edita um registro de sinais vitais (apenas enfermeiro)"""
    enfermeiro_id = session.get('enfermeiro_id')
    
    if request.method == 'POST':
        pressao = request.form.get('pressao_arterial')
        fc = request.form.get('frequencia_cardiaca') or None
        fr = request.form.get('frequencia_respiratoria') or None
        temp = request.form.get('temperatura') or None
        sat = request.form.get('saturacao_oxigenio') or None
        glicemia = request.form.get('glicemia') or None
        peso = request.form.get('peso') or None
        observacoes = request.form.get('observacoes')
        
        if pressao:
            pressao = pressao.replace('/', 'x')
            if not re.match(r'^\d{2,3}x\d{2,3}$', pressao):
                flash('Formato de pressão arterial inválido. Use: 120/80 ou 120x80', 'danger')
                return redirect(url_for('enfermeiro.sinais_vitais.editar_sinais_vitais', vital_id=vital_id))
        
        result = execute_query("""
            UPDATE sinais_vitais SET
                pressao_arterial = %s,
                frequencia_cardiaca = %s,
                frequencia_respiratoria = %s,
                temperatura = %s,
                saturacao_oxigenio = %s,
                glicemia = %s,
                peso = %s,
                observacoes = %s
            WHERE id = %s AND enfermeiro_id = %s
        """, (pressao, fc, fr, temp, sat, glicemia, peso, observacoes, vital_id, enfermeiro_id))
        
        if result:
            flash('Sinais vitais atualizados com sucesso!', 'success')
        else:
            flash('Erro ao atualizar sinais vitais.', 'danger')
        
        return redirect(url_for('enfermeiro.sinais_vitais.detalhes_sinais_vitais', vital_id=vital_id))
    
    vital = execute_query("""
        SELECT 
            sv.*,
            u.nome as paciente_nome,
            p.id as paciente_id,
            p.data_nascimento,
            c.data_hora as data_hora_consulta
        FROM sinais_vitais sv
        JOIN consultas c ON sv.consulta_id = c.id
        JOIN pacientes p ON c.paciente_id = p.id
        JOIN usuarios u ON p.usuario_id = u.id
        WHERE sv.id = %s AND sv.enfermeiro_id = %s
    """, (vital_id, enfermeiro_id), fetch=True, one=True)
    
    if not vital:
        flash('Registro não encontrado ou você não tem permissão para editá-lo.', 'danger')
        return redirect(url_for('enfermeiro.sinais_vitais.listar_sinais_vitais'))
    
    if vital.get('data_afericao'):
        if isinstance(vital['data_afericao'], datetime):
            vital['data_afericao_formatada'] = vital['data_afericao'].strftime('%d/%m/%Y %H:%M')
    
    if vital.get('data_hora_consulta'):
        if isinstance(vital['data_hora_consulta'], datetime):
            vital['data_consulta_formatada'] = vital['data_hora_consulta'].strftime('%d/%m/%Y')
    
    return render_template('enfermeiro/sinais_vitais/editar.html', vital=vital)


@sinais_vitais_bp.route('/<int:vital_id>/excluir', methods=['POST'])
@enfermeiro_required
def excluir_sinais_vitais(vital_id):
    """Exclui um registro de sinais vitais (apenas enfermeiro)"""
    enfermeiro_id = session.get('enfermeiro_id')
    
    try:
        registro = execute_query("""
            SELECT consulta_id FROM sinais_vitais 
            WHERE id = %s AND enfermeiro_id = %s
        """, (vital_id, enfermeiro_id), fetch=True, one=True)
        
        if registro:
            consulta_id = registro['consulta_id']
            
            execute_query("""
                DELETE FROM sinais_vitais 
                WHERE id = %s AND enfermeiro_id = %s
            """, (vital_id, enfermeiro_id))
            
            outros_registros = execute_query("""
                SELECT id FROM sinais_vitais 
                WHERE consulta_id = %s
            """, (consulta_id,), fetch=True)
            
            if not outros_registros:
                execute_query("""
                    UPDATE consultas 
                    SET status_triagem = NULL,
                        data_triagem = NULL
                    WHERE id = %s
                """, (consulta_id,))
            
            flash('Registro excluído com sucesso!', 'success')
        else:
            flash('Registro não encontrado.', 'danger')
            
    except Exception as e:
        logger.error(f"Erro ao excluir registro: {e}")
        flash('Erro ao excluir registro.', 'danger')
    
    return redirect(url_for('enfermeiro.sinais_vitais.listar_sinais_vitais'))


@sinais_vitais_bp.route('/excluir-por-consulta/<int:consulta_id>', methods=['POST'])
@enfermeiro_required
def excluir_sinais_vitais_por_consulta(consulta_id):
    """Exclui todos os sinais vitais de uma consulta específica (apenas enfermeiro)"""
    enfermeiro_id = session.get('enfermeiro_id')
    
    try:
        registros = execute_query("""
            SELECT id, pressao_arterial, data_afericao 
            FROM sinais_vitais 
            WHERE consulta_id = %s
        """, (consulta_id,), fetch=True)
        
        if registros:
            logger.info(f"Encontrados {len(registros)} registros para consulta {consulta_id}")
            
            execute_query("""
                DELETE FROM sinais_vitais 
                WHERE consulta_id = %s
            """, (consulta_id,))
            
            execute_query("""
                UPDATE consultas 
                SET status_triagem = NULL,
                    data_triagem = NULL
                WHERE id = %s
            """, (consulta_id,))
            
            flash(f'{len(registros)} registro(s) de sinais vitais excluído(s) da consulta {consulta_id}!', 'success')
            logger.info(f"Sinais vitais da consulta {consulta_id} excluídos pelo enfermeiro {enfermeiro_id}")
        else:
            flash(f'Nenhum registro de sinais vitais encontrado para a consulta {consulta_id}.', 'warning')
            
    except Exception as e:
        logger.error(f"Erro ao excluir sinais vitais: {e}")
        flash('Erro ao excluir sinais vitais.', 'danger')
    
    return redirect(url_for('enfermeiro.sinais_vitais.listar_sinais_vitais'))


@sinais_vitais_bp.route('/testar-exclusao/<int:consulta_id>')
@enfermeiro_required
def testar_exclusao(consulta_id):
    """Rota de teste para verificar e excluir sinais vitais"""
    try:
        registros = execute_query("""
            SELECT * FROM sinais_vitais WHERE consulta_id = %s
        """, (consulta_id,), fetch=True)
        
        if registros:
            registros_html = "<br>".join([str(r) for r in registros])
            
            return f"""
            <html>
            <head>
                <title>Teste de Exclusão</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    h2 {{ color: #333; }}
                    pre {{ background: #f4f4f4; padding: 15px; border-radius: 5px; }}
                    button {{ 
                        background: #dc3545; 
                        color: white; 
                        border: none; 
                        padding: 10px 20px; 
                        border-radius: 5px; 
                        cursor: pointer;
                        font-size: 16px;
                    }}
                    button:hover {{ background: #c82333; }}
                </style>
            </head>
            <body>
                <h2>Registros encontrados para consulta {consulta_id}:</h2>
                <pre>{registros_html}</pre>
                <form method="POST" action="{url_for('enfermeiro.sinais_vitais.excluir_sinais_vitais_por_consulta', consulta_id=consulta_id)}">
                    <button type="submit">EXCLUIR AGORA</button>
                </form>
                <p><a href="{url_for('enfermeiro.sinais_vitais.listar_sinais_vitais')}">Voltar para lista</a></p>
            </body>
            </html>
            """
        else:
            return f"""
            <html>
            <head>
                <title>Teste de Exclusão</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    h2 {{ color: #28a745; }}
                </style>
            </head>
            <body>
                <h2>Nenhum registro encontrado para consulta {consulta_id}</h2>
                <p><a href="{url_for('enfermeiro.sinais_vitais.listar_sinais_vitais')}">Voltar para lista</a></p>
            </body>
            </html>
            """
            
    except Exception as e:
        return f"""
        <html>
        <head>
            <title>Erro</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                h2 {{ color: #dc3545; }}
            </style>
        </head>
        <body>
            <h2>Erro: {e}</h2>
            <p><a href="{url_for('enfermeiro.sinais_vitais.listar_sinais_vitais')}">Voltar para lista</a></p>
        </body>
        </html>
        """


@sinais_vitais_bp.route('/diagnostico')
@enfermeiro_required
def diagnostico():
    """Rota de diagnóstico para verificar o banco de dados"""
    enfermeiro_id = session.get('enfermeiro_id')
    html = "<h1>DIAGNÓSTICO DO BANCO DE DADOS</h1>"
    
    try:
        if sinais_vitais_bp.mysql:
            html += "<p style='color:green'>✅ Conexão com MySQL OK</p>"
        else:
            html += "<p style='color:red'>❌ Sem conexão com MySQL</p>"
        
        tabela = execute_query("SHOW TABLES LIKE 'sinais_vitais'", fetch=True)
        if tabela:
            html += "<p style='color:green'>✅ Tabela 'sinais_vitais' existe</p>"
        else:
            html += "<p style='color:red'>❌ Tabela 'sinais_vitais' NÃO existe</p>"
        
        total = execute_query("SELECT COUNT(*) as total FROM sinais_vitais", fetch=True, one=True)
        if total:
            html += f"<p>📊 Total de registros em sinais_vitais: <strong>{total['total']}</strong></p>"
        
        html += '<br><a href="' + url_for('enfermeiro.sinais_vitais.listar_sinais_vitais') + '">Voltar para lista</a>'
        
    except Exception as e:
        html += f"<p style='color:red'>❌ Erro geral: {e}</p>"
    
    return html


@sinais_vitais_bp.route('/paciente/<int:paciente_id>')
@enfermeiro_ou_medico_required
def historico_paciente(paciente_id):
    """Mostra histórico de sinais vitais de um paciente"""
    historico = execute_query("""
        SELECT 
            sv.*,
            c.id as consulta_id,
            u.nome as paciente_nome,
            c.status,
            c.status_triagem,
            c.data_hora as data_hora_consulta
        FROM sinais_vitais sv
        JOIN consultas c ON sv.consulta_id = c.id
        JOIN pacientes p ON c.paciente_id = p.id
        JOIN usuarios u ON p.usuario_id = u.id
        WHERE p.id = %s
        ORDER BY sv.data_afericao DESC
    """, (paciente_id,), fetch=True) or []
    
    for item in historico:
        if item.get('data_afericao'):
            if isinstance(item['data_afericao'], datetime):
                item['data_afericao_formatada'] = item['data_afericao'].strftime('%d/%m/%Y %H:%M')
        
        if item.get('data_hora_consulta'):
            if isinstance(item['data_hora_consulta'], datetime):
                item['data_consulta_formatada'] = item['data_hora_consulta'].strftime('%d/%m/%Y')
                item['hora_consulta_formatada'] = item['data_hora_consulta'].strftime('%H:%M')
    
    paciente_nome = historico[0]['paciente_nome'] if historico else 'Paciente'
    
    return render_template('enfermeiro/sinais_vitais/historico.html',
        historico=historico,
        paciente_nome=paciente_nome,
        paciente_id=paciente_id,
        classificar_pressao=classificar_pressao,
        formatar_data=formatar_data,
        formatar_data_hora=formatar_data_hora)
