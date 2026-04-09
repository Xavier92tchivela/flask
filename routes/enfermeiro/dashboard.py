from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from datetime import date, timedelta, datetime
from .utils import execute_query, enfermeiro_required, classificar_pressao, formatar_data, formatar_data_hora, decode_bytes
import logging
import traceback  

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

# Atributo para armazenar a conexão MySQL
dashboard_bp.mysql = None

def set_mysql(mysql_instance):
    """Configura a conexão MySQL para este módulo"""
    dashboard_bp.mysql = mysql_instance
    from .utils import set_mysql as set_utils_mysql
    set_utils_mysql(mysql_instance)

def buscar_pacientes_internados():
    """Busca pacientes internados para o dashboard"""
    try:
        if not dashboard_bp.mysql:
            logger.error("MySQL não configurado")
            return [], 0
            
        cursor = dashboard_bp.mysql.connection.cursor()
        
        # Query para buscar pacientes internados
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
            # Extrair dados
            internacao_id = row[0]
            prontuario = row[1] if row[1] else 'N/A'
            data_internacao = row[2]
            tipo_internacao = row[3]
            diagnostico_inicial = row[4]
            status = row[5]
            leito_id = row[6]
            paciente_id = row[7]
            paciente_nome = row[8]
            data_nasc = row[9]
            
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
                    cursor_leito.execute("SELECT alas, numero, tipo FROM leitos WHERE id = %s", (leito_id,))
                    leito = cursor_leito.fetchone()
                    cursor_leito.close()
                    if leito:
                        leito_alas = leito[0] if leito[0] else "Não definido"
                        if isinstance(leito_alas, bytes):
                            leito_alas = leito_alas.decode('utf-8', errors='ignore')
                        leito_numero = leito[1] if leito[1] else "?"
                        leito_tipo = leito[2] if leito[2] else "Não definido"
                        if isinstance(leito_tipo, bytes):
                            leito_tipo = leito_tipo.decode('utf-8', errors='ignore')
                except:
                    pass
            
            # Buscar últimos sinais vitais
            ultimos_sinais = None
            try:
                cursor_sinais = dashboard_bp.mysql.connection.cursor()
                cursor_sinais.execute("""
                    SELECT pressao_arterial, frequencia_cardiaca, temperatura, saturacao_oxigenio, glicemia, data_afericao
                    FROM sinais_vitais
                    WHERE consulta_id IN (SELECT id FROM consultas WHERE paciente_id = %s)
                    ORDER BY data_afericao DESC
                    LIMIT 1
                """, (paciente_id,))
                sinais = cursor_sinais.fetchone()
                cursor_sinais.close()
                
                if sinais:
                    pressao = sinais[0]
                    if isinstance(pressao, bytes):
                        pressao = pressao.decode('utf-8', errors='ignore')
                    
                    ultimos_sinais = {
                        'pressao_arterial': pressao,
                        'frequencia_cardiaca': sinais[1],
                        'temperatura': sinais[2],
                        'saturacao_oxigenio': sinais[3],
                        'glicemia': sinais[4],
                        'data_afericao': sinais[5]
                    }
            except:
                pass
            
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
        cursor = dashboard_bp.mysql.connection.cursor()
        
        # Testar query direta
        cursor.execute("SELECT COUNT(*) FROM internacoes WHERE status = 'ativa'")
        total = cursor.fetchone()[0]
        
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
            nome = internado[7]
            if isinstance(nome, bytes):
                nome = nome.decode('utf-8', errors='ignore')
            
            resultado.append({
                'id': internado[0],
                'prontuario': internado[1],
                'data': str(internado[2]),
                'tipo': internado[3],
                'diagnostico': internado[4],
                'status': internado[5],
                'paciente_id': internado[6],
                'paciente_nome': nome
            })
        
        return jsonify({
            'total': total,
            'internados': resultado
        })
        
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()})

@dashboard_bp.route('/')
@enfermeiro_required
def index():
    """Dashboard principal do enfermeiro"""
    enfermeiro_id = session.get('enfermeiro_id')
    hoje = date.today()
    hoje_str = hoje.strftime('%Y-%m-%d')
    data_selecionada = request.args.get('data_consulta', hoje_str)
    
    try:
        # Total de aferições hoje
        total_hoje = execute_query("""
            SELECT COUNT(*) as total FROM sinais_vitais 
            WHERE enfermeiro_id = %s AND DATE(data_afericao) = %s
        """, (enfermeiro_id, hoje), fetch=True, one=True)
        
        # Consultas pendentes de triagem
        pendentes = execute_query("""
            SELECT COUNT(*) as total FROM consultas c
            WHERE DATE(c.data_hora) = %s
            AND c.status IN ('agendada', 'AGUARDANDO', 'pendente', 'confirmada')
            AND (c.status_triagem IS NULL OR c.status_triagem = 'NAO_REALIZADA')
        """, (hoje,), fetch=True, one=True)
        
        # Total de consultas hoje
        total_consultas = execute_query("""
            SELECT COUNT(*) as total FROM consultas 
            WHERE DATE(data_hora) = %s
        """, (hoje,), fetch=True, one=True)
        
        # Triagens pendentes
        triagens = execute_query("""
            SELECT c.id, u.nome as paciente_nome, p.id as paciente_id, 
                   DATE_FORMAT(c.data_hora, '%%H:%%i') as hora_chegada
            FROM consultas c
            JOIN pacientes p ON c.paciente_id = p.id
            JOIN usuarios u ON p.usuario_id = u.id
            WHERE DATE(c.data_hora) = %s 
            AND c.status IN ('agendada', 'AGUARDANDO', 'pendente', 'confirmada')
            AND (c.status_triagem IS NULL OR c.status_triagem = 'NAO_REALIZADA')
            ORDER BY c.data_hora LIMIT 10
        """, (hoje,), fetch=True) or []
        
        # Últimas aferições
        ultimas = execute_query("""
            SELECT sv.id, sv.pressao_arterial, sv.frequencia_cardiaca,
                   sv.frequencia_respiratoria, sv.temperatura, sv.saturacao_oxigenio,
                   sv.glicemia, sv.peso, sv.data_afericao, sv.observacoes,
                   u.nome as paciente_nome, p.id as paciente_id
            FROM sinais_vitais sv
            JOIN consultas c ON sv.consulta_id = c.id
            JOIN pacientes p ON c.paciente_id = p.id
            JOIN usuarios u ON p.usuario_id = u.id
            WHERE sv.enfermeiro_id = %s
            ORDER BY sv.data_afericao DESC LIMIT 10
        """, (enfermeiro_id,), fetch=True) or []
        
        # Dados para o gráfico
        dias = []
        dados_grafico = []
        for i in range(6, -1, -1):
            dia = hoje - timedelta(days=i)
            dias.append(dia.strftime('%d/%m'))
            count = execute_query("""
                SELECT COUNT(*) as total FROM sinais_vitais 
                WHERE enfermeiro_id = %s AND DATE(data_afericao) = %s
            """, (enfermeiro_id, dia), fetch=True, one=True)
            dados_grafico.append(count['total'] if count else 0)
        
        # Consultas do dia selecionado
        consultas_data = execute_query("""
            SELECT 
                c.id,
                DATE_FORMAT(c.data_hora, '%%H:%%i') as hora,
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
        
        # ===================== BUSCAR PACIENTES INTERNADOS =====================
        internados_lista, pacientes_internados = buscar_pacientes_internados()
        
        # Decodificar nomes nas listas
        for triagem in triagens:
            if 'paciente_nome' in triagem and isinstance(triagem['paciente_nome'], bytes):
                triagem['paciente_nome'] = decode_bytes(triagem['paciente_nome'])
        
        for consulta in consultas_data:
            if 'paciente_nome' in consulta and isinstance(consulta['paciente_nome'], bytes):
                consulta['paciente_nome'] = decode_bytes(consulta['paciente_nome'])
            if 'medico_nome' in consulta and isinstance(consulta['medico_nome'], bytes):
                consulta['medico_nome'] = decode_bytes(consulta['medico_nome'])
        
        for vital in ultimas:
            if 'paciente_nome' in vital and isinstance(vital['paciente_nome'], bytes):
                vital['paciente_nome'] = decode_bytes(vital['paciente_nome'])
            if 'pressao_arterial' in vital and isinstance(vital['pressao_arterial'], bytes):
                vital['pressao_arterial'] = decode_bytes(vital['pressao_arterial'])
        
        logger.info(f"✅ Dashboard carregado: {pacientes_internados} internados encontrados")
        
        return render_template('enfermeiro/dashboard.html',
            total_afericoes_hoje=total_hoje['total'] if total_hoje else 0,
            pacientes_aguardando=pendentes['total'] if pendentes else 0,
            total_consultas_hoje=total_consultas['total'] if total_consultas else 0,
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