# routes/enfermeiro/dashboard.py

from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from datetime import date, timedelta, datetime
from .utils import execute_query, enfermeiro_required, classificar_pressao, formatar_data, formatar_data_hora, decode_bytes
import logging
import traceback

logger = logging.getLogger(__name__)

# ===================== NOME CORRETO DO BLUEPRINT =====================
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

# Atributo para armazenar a conexão MySQL
dashboard_bp.mysql = None

def set_mysql(mysql_instance):
    """Configura a conexão MySQL para este módulo"""
    dashboard_bp.mysql = mysql_instance
    from .utils import set_mysql as set_utils_mysql
    set_utils_mysql(mysql_instance)

def dict_factory(cursor, row):
    """Converte uma tupla em dicionário"""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def buscar_pacientes_internados():
    """Busca pacientes internados para o dashboard"""
    try:
        if not dashboard_bp.mysql:
            logger.error("MySQL não configurado")
            return [], 0
            
        cursor = dashboard_bp.mysql.connection.cursor()
        cursor.row_factory = dict_factory
        
        query = """
            SELECT 
                i.id,
                i.numero_prontuario,
                i.data_internacao,
                i.tipo_internacao,
                i.diagnostico_inicial,
                i.status,
                i.leito_id,
                p.id as paciente_id,
                u.nome as paciente_nome,
                p.data_nascimento
            FROM internacoes i
            INNER JOIN pacientes p ON i.paciente_id = p.id
            INNER JOIN usuarios u ON p.usuario_id = u.id
            WHERE i.status = 'ativa'
            ORDER BY i.data_internacao DESC
            LIMIT 10
        """
        
        cursor.execute(query)
        internados_raw = cursor.fetchall()
        
        if not internados_raw:
            cursor.close()
            return [], 0
        
        internados_lista = []
        for row in internados_raw:
            internacao_id = row.get('id')
            prontuario = row.get('numero_prontuario') if row.get('numero_prontuario') else 'N/A'
            data_internacao = row.get('data_internacao')
            tipo_internacao = row.get('tipo_internacao')
            diagnostico_inicial = row.get('diagnostico_inicial')
            status = row.get('status')
            leito_id = row.get('leito_id')
            paciente_id = row.get('paciente_id')
            paciente_nome = row.get('paciente_nome')
            data_nasc = row.get('data_nascimento')
            
            # Decodificar se for bytes
            if isinstance(paciente_nome, bytes):
                paciente_nome = paciente_nome.decode('utf-8', errors='ignore')
            if isinstance(tipo_internacao, bytes):
                tipo_internacao = tipo_internacao.decode('utf-8', errors='ignore')
            if isinstance(diagnostico_inicial, bytes):
                diagnostico_inicial = diagnostico_inicial.decode('utf-8', errors='ignore')
            
            # Calcular idade
            idade = None
            if data_nasc:
                try:
                    if isinstance(data_nasc, datetime):
                        birth_date = data_nasc.date()
                    else:
                        birth_date = data_nasc
                    today = datetime.now().date()
                    idade = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                except:
                    pass
            
            # Buscar dados do leito
            leito_alas = "Não definido"
            leito_numero = "?"
            leito_tipo = "Não definido"
            
            if leito_id:
                try:
                    cursor_leito = dashboard_bp.mysql.connection.cursor()
                    cursor_leito.row_factory = dict_factory
                    cursor_leito.execute("SELECT alas, numero, tipo FROM leitos WHERE id = %s", (leito_id,))
                    leito = cursor_leito.fetchone()
                    cursor_leito.close()
                    if leito:
                        leito_alas = leito.get('alas') if leito.get('alas') else "Não definido"
                        if isinstance(leito_alas, bytes):
                            leito_alas = leito_alas.decode('utf-8', errors='ignore')
                        leito_numero = leito.get('numero') if leito.get('numero') else "?"
                        leito_tipo = leito.get('tipo') if leito.get('tipo') else "Não definido"
                        if isinstance(leito_tipo, bytes):
                            leito_tipo = leito_tipo.decode('utf-8', errors='ignore')
                except Exception as e:
                    logger.error(f"Erro ao buscar leito: {e}")
            
            # Buscar últimos sinais vitais
            ultimos_sinais = None
            try:
                cursor_sinais = dashboard_bp.mysql.connection.cursor()
                cursor_sinais.row_factory = dict_factory
                cursor_sinais.execute("""
                    SELECT pressao_arterial, frequencia_cardiaca, temperatura, 
                           saturacao_oxigenio, glicemia, data_afericao
                    FROM sinais_vitais sv
                    JOIN consultas c ON sv.consulta_id = c.id
                    WHERE c.paciente_id = %s
                    ORDER BY sv.data_afericao DESC
                    LIMIT 1
                """, (paciente_id,))
                sinais = cursor_sinais.fetchone()
                cursor_sinais.close()
                
                if sinais:
                    pressao = sinais.get('pressao_arterial')
                    if isinstance(pressao, bytes):
                        pressao = pressao.decode('utf-8', errors='ignore')
                    
                    ultimos_sinais = {
                        'pressao_arterial': pressao,
                        'frequencia_cardiaca': sinais.get('frequencia_cardiaca'),
                        'temperatura': sinais.get('temperatura'),
                        'saturacao_oxigenio': sinais.get('saturacao_oxigenio'),
                        'glicemia': sinais.get('glicemia'),
                        'data_afericao': sinais.get('data_afericao')
                    }
            except Exception as e:
                logger.error(f"Erro ao buscar sinais vitais: {e}")
            
            internados_lista.append({
                'id': internacao_id,
                'numero_prontuario': prontuario,
                'data_internacao': data_internacao,
                'tipo_internacao': tipo_internacao if tipo_internacao else 'Não informado',
                'diagnostico_inicial': diagnostico_inicial if diagnostico_inicial else 'Não informado',
                'status': status,
                'paciente_id': paciente_id,
                'paciente_nome': paciente_nome,
                'idade': idade,
                'leito_alas': leito_alas,
                'leito_numero': leito_numero,
                'leito_tipo': leito_tipo,
                'ultimos_sinais': ultimos_sinais
            })
        
        cursor.close()
        
        total_internados = len(internados_lista)
        logger.info(f"Total internados: {total_internados}")
        
        return internados_lista, total_internados
        
    except Exception as e:
        logger.error(f"Erro ao buscar internados: {e}")
        logger.error(traceback.format_exc())
        return [], 0

@dashboard_bp.route('/teste-internados')
@enfermeiro_required
def teste_internados():
    """Rota de teste para verificar internados"""
    try:
        if not dashboard_bp.mysql:
            return jsonify({'error': 'MySQL não configurado'})
            
        cursor = dashboard_bp.mysql.connection.cursor()
        cursor.row_factory = dict_factory
        
        cursor.execute("SELECT COUNT(*) as total FROM internacoes WHERE status = 'ativa'")
        total_result = cursor.fetchone()
        total = total_result['total'] if total_result else 0
        
        cursor.execute("""
            SELECT 
                i.id,
                i.numero_prontuario,
                i.data_internacao,
                i.tipo_internacao,
                i.diagnostico_inicial,
                i.status,
                p.id as paciente_id,
                u.nome as paciente_nome
            FROM internacoes i
            JOIN pacientes p ON i.paciente_id = p.id
            JOIN usuarios u ON p.usuario_id = u.id
            WHERE i.status = 'ativa'
        """)
        
        internados = cursor.fetchall()
        cursor.close()
        
        resultado = []
        for internado in internados:
            nome = internado.get('paciente_nome')
            if isinstance(nome, bytes):
                nome = nome.decode('utf-8', errors='ignore')
            
            resultado.append({
                'id': internado.get('id'),
                'prontuario': internado.get('numero_prontuario'),
                'data': str(internado.get('data_internacao')),
                'tipo': internado.get('tipo_internacao'),
                'diagnostico': internado.get('diagnostico_inicial'),
                'status': internado.get('status'),
                'paciente_id': internado.get('paciente_id'),
                'paciente_nome': nome
            })
        
        return jsonify({
            'total': total,
            'internados': resultado
        })
        
    except Exception as e:
        logger.error(f"Erro no teste: {e}")
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()})

@dashboard_bp.route('/')
@enfermeiro_required
def index():
    """Dashboard principal do enfermeiro"""
    enfermeiro_id = session.get('enfermeiro_id')
    hoje = date.today()
    hoje_str = hoje.strftime('%Y-%m-%d')
    data_selecionada = request.args.get('data_consulta', hoje_str)
    
    logger.info(f"=== DASHBOARD ENFERMEIRO ===")
    logger.info(f"Enfermeiro ID: {enfermeiro_id}")
    logger.info(f"Data selecionada: {data_selecionada}")
    
    # Valores padrão
    total_afericoes_hoje = 0
    pacientes_aguardando = 0
    total_consultas_hoje = 0
    triagens = []
    ultimas = []
    dias = []
    dados_grafico = []
    consultas_data = []
    internados_lista = []
    pacientes_internados = 0
    
    try:
        # Total de aferições hoje
        try:
            total_hoje_result = execute_query("""
                SELECT COUNT(*) as total FROM sinais_vitais 
                WHERE enfermeiro_id = %s AND DATE(data_afericao) = %s
            """, (enfermeiro_id, hoje), fetch=True, one=True)
            total_afericoes_hoje = total_hoje_result.get('total', 0) if total_hoje_result else 0
            logger.info(f"Total aferições hoje: {total_afericoes_hoje}")
        except Exception as e:
            logger.error(f"Erro ao buscar total aferições: {e}")
        
        # Consultas pendentes de triagem
        try:
            pendentes_result = execute_query("""
                SELECT COUNT(*) as total FROM consultas c
                WHERE DATE(c.data_hora) = %s
                AND c.status NOT IN ('cancelada', 'CANCELADA', 'realizada', 'REALIZADA')
                AND (c.status_triagem IS NULL OR c.status_triagem != 'REALIZADA')
            """, (hoje,), fetch=True, one=True)
            pacientes_aguardando = pendentes_result.get('total', 0) if pendentes_result else 0
            logger.info(f"Triagens pendentes: {pacientes_aguardando}")
        except Exception as e:
            logger.error(f"Erro ao buscar triagens pendentes: {e}")
        
        # Total de consultas hoje
        try:
            total_consultas_result = execute_query("""
                SELECT COUNT(*) as total FROM consultas 
                WHERE DATE(data_hora) = %s
            """, (hoje,), fetch=True, one=True)
            total_consultas_hoje = total_consultas_result.get('total', 0) if total_consultas_result else 0
            logger.info(f"Total consultas hoje: {total_consultas_hoje}")
        except Exception as e:
            logger.error(f"Erro ao buscar total consultas: {e}")
        
        # Triagens pendentes (detalhadas)
        try:
            triagens = execute_query("""
                SELECT 
                    c.id, 
                    u.nome as paciente_nome, 
                    p.id as paciente_id, 
                    TIME_FORMAT(c.data_hora, '%%H:%%i') as hora_chegada
                FROM consultas c
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE DATE(c.data_hora) = %s 
                AND c.status NOT IN ('cancelada', 'CANCELADA', 'realizada', 'REALIZADA')
                AND (c.status_triagem IS NULL OR c.status_triagem != 'REALIZADA')
                ORDER BY c.data_hora LIMIT 10
            """, (hoje,), fetch=True) or []
            logger.info(f"Triagens pendentes lista: {len(triagens)}")
        except Exception as e:
            logger.error(f"Erro ao buscar lista de triagens: {e}")
        
        # Últimas aferições
        try:
            ultimas = execute_query("""
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
                    p.id as paciente_id
                FROM sinais_vitais sv
                JOIN consultas c ON sv.consulta_id = c.id
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE sv.enfermeiro_id = %s
                ORDER BY sv.data_afericao DESC LIMIT 10
            """, (enfermeiro_id,), fetch=True) or []
            logger.info(f"Últimas aferições: {len(ultimas)}")
        except Exception as e:
            logger.error(f"Erro ao buscar últimas aferições: {e}")
        
        # Dados para o gráfico (últimos 7 dias)
        try:
            for i in range(6, -1, -1):
                dia = hoje - timedelta(days=i)
                dias.append(dia.strftime('%d/%m'))
                count_result = execute_query("""
                    SELECT COUNT(*) as total FROM sinais_vitais 
                    WHERE enfermeiro_id = %s AND DATE(data_afericao) = %s
                """, (enfermeiro_id, dia), fetch=True, one=True)
                count = count_result.get('total', 0) if count_result else 0
                dados_grafico.append(count)
            logger.info(f"Dados do gráfico: {dados_grafico}")
        except Exception as e:
            logger.error(f"Erro ao buscar dados do gráfico: {e}")
        
        # Consultas do dia selecionado
        try:
            consultas_data = execute_query("""
                SELECT 
                    c.id,
                    TIME_FORMAT(c.data_hora, '%%H:%%i') as hora,
                    u.nome as paciente_nome,
                    p.id as paciente_id,
                    COALESCE(m_u.nome, 'Não atribuído') as medico_nome,
                    c.status,
                    COALESCE(c.status_triagem, 'NAO_REALIZADA') as status_triagem,
                    (SELECT COUNT(*) FROM sinais_vitais WHERE consulta_id = c.id) as sinais_vitais_count,
                    (SELECT id FROM sinais_vitais WHERE consulta_id = c.id LIMIT 1) as vital_id
                FROM consultas c
                INNER JOIN pacientes p ON c.paciente_id = p.id
                INNER JOIN usuarios u ON p.usuario_id = u.id
                LEFT JOIN medicos m ON c.medico_id = m.id
                LEFT JOIN usuarios m_u ON m.usuario_id = m_u.id
                WHERE DATE(c.data_hora) = %s
                ORDER BY c.data_hora ASC
            """, (data_selecionada,), fetch=True) or []
            logger.info(f"Consultas do dia {data_selecionada}: {len(consultas_data)}")
        except Exception as e:
            logger.error(f"Erro ao buscar consultas do dia: {e}")
        
        # Buscar pacientes internados
        try:
            internados_lista, pacientes_internados = buscar_pacientes_internados()
            logger.info(f"Pacientes internados: {pacientes_internados}")
        except Exception as e:
            logger.error(f"Erro ao buscar pacientes internados: {e}")
        
        # Decodificar nomes nas listas
        for triagem in triagens:
            if 'paciente_nome' in triagem and isinstance(triagem['paciente_nome'], bytes):
                triagem['paciente_nome'] = decode_bytes(triagem['paciente_nome'])
            if 'hora_chegada' in triagem and isinstance(triagem['hora_chegada'], bytes):
                triagem['hora_chegada'] = decode_bytes(triagem['hora_chegada'])
        
        for consulta in consultas_data:
            if 'paciente_nome' in consulta and isinstance(consulta['paciente_nome'], bytes):
                consulta['paciente_nome'] = decode_bytes(consulta['paciente_nome'])
            if 'medico_nome' in consulta and isinstance(consulta['medico_nome'], bytes):
                consulta['medico_nome'] = decode_bytes(consulta['medico_nome'])
            if 'hora' in consulta and isinstance(consulta['hora'], bytes):
                consulta['hora'] = decode_bytes(consulta['hora'])
            if 'status' in consulta and isinstance(consulta['status'], bytes):
                consulta['status'] = decode_bytes(consulta['status'])
        
        for vital in ultimas:
            if 'paciente_nome' in vital and isinstance(vital['paciente_nome'], bytes):
                vital['paciente_nome'] = decode_bytes(vital['paciente_nome'])
            if 'pressao_arterial' in vital and isinstance(vital['pressao_arterial'], bytes):
                vital['pressao_arterial'] = decode_bytes(vital['pressao_arterial'])
        
        logger.info(f"✅ Dashboard carregado com sucesso!")
        
        return render_template('enfermeiro/dashboard.html',
            total_afericoes_hoje=total_afericoes_hoje,
            pacientes_aguardando=pacientes_aguardando,
            total_consultas_hoje=total_consultas_hoje,
            triagens_pendentes=triagens,
            ultimas_afericoes=ultimas,
            classificar_pressao=classificar_pressao,
            formatar_data=formatar_data,
            formatar_data_hora=formatar_data_hora,
            dias_semana=dias,
            dados_grafico=dados_grafico,
            hoje=hoje_str, 
            data_selecionada=data_selecionada,
            consultas_data=consultas_data,
            internados_lista=internados_lista,
            pacientes_internados=pacientes_internados)
            
    except Exception as e:
        logger.error(f"❌ Erro no dashboard: {e}")
        logger.error(traceback.format_exc())
        flash('Erro ao carregar dashboard', 'danger')
        return render_template('enfermeiro/dashboard.html',
            total_afericoes_hoje=0,
            pacientes_aguardando=0,
            total_consultas_hoje=0,
            triagens_pendentes=[],
            ultimas_afericoes=[],
            classificar_pressao=classificar_pressao,
            formatar_data=formatar_data,
            formatar_data_hora=formatar_data_hora,
            dias_semana=[],
            dados_grafico=[],
            hoje=hoje_str, 
            data_selecionada=data_selecionada,
            consultas_data=[],
            internados_lista=[],
            pacientes_internados=0)
