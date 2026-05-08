# routes/dashboard_api_enfermeiro.py
from flask import Blueprint, jsonify, session, current_app
from datetime import datetime, timedelta
import logging
from functools import wraps

logger = logging.getLogger(__name__)

_mysql = None

def set_mysql(mysql_instance):
    global _mysql
    _mysql = mysql_instance

def init_dashboard_api_enfermeiro(mysql):
    global _mysql
    _mysql = mysql
    
    dashboard_api_bp = Blueprint('dashboard_api_enfermeiro', __name__, url_prefix='/enfermeiro/api')
    
    # ================= AUTH =================
    def enfermeiro_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'error': 'Usuário não autenticado'}), 401
            if session.get('user_type') != 'enfermeiro':
                return jsonify({'error': 'Acesso restrito a enfermeiros'}), 403
            return f(*args, **kwargs)
        return decorated_function

    # ================= DB =================
    def execute_query(query, params=None, fetch=False, one=False, commit=False):
        """Executa queries no banco de dados"""
        try:
            if _mysql is None:
                logger.error("MySQL não inicializado")
                return None if fetch else False
                
            cur = _mysql.connection.cursor()
            
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            
            if fetch:
                if one:
                    result = cur.fetchone()
                else:
                    result = cur.fetchall()
                cur.close()
                return result
            
            if commit:
                _mysql.connection.commit()
            
            cur.close()
            return True if commit else None
            
        except Exception as e:
            logger.error(f"Database error in dashboard_api_enfermeiro: {e}")
            logger.error(f"Query: {query}")
            if commit and _mysql:
                _mysql.connection.rollback()
            return None if fetch else False

    # ================= UTILS =================
    def formatar_data(data, formato='%d/%m/%Y %H:%M'):
        if not data:
            return ''
        if isinstance(data, datetime):
            return data.strftime(formato)
        return str(data)

    def obter_enfermeiro_id():
        return session.get('enfermeiro_id')

    # ================= API: CONTADORES =================
    @dashboard_api_bp.route('/contadores')
    @enfermeiro_required
    def contadores():
        """Retorna contadores para o dashboard do enfermeiro"""
        try:
            enfermeiro_id = obter_enfermeiro_id()
            hoje_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            hoje_fim = hoje_inicio + timedelta(days=1)
            
            # Consultas de hoje
            consultas_hoje = execute_query("""
                SELECT COUNT(*) as total
                FROM consultas
                WHERE data_hora >= %s AND data_hora < %s
            """, (hoje_inicio, hoje_fim), fetch=True, one=True)
            
            # Triagens pendentes (consultas sem triagem)
            triagens_pendentes = execute_query("""
                SELECT COUNT(*) as total
                FROM consultas c
                LEFT JOIN triagem t ON c.id = t.consulta_id
                WHERE c.data_hora >= %s AND c.data_hora < %s
                AND t.id IS NULL
                AND c.status = 'agendada'
            """, (hoje_inicio, hoje_fim), fetch=True, one=True)
            
            # Pacientes internados
            internados = execute_query("""
                SELECT COUNT(*) as total
                FROM internacoes
                WHERE status = 'internado'
                AND data_internacao <= NOW()
            """, fetch=True, one=True)
            
            # Aferições de hoje
            afericoes_hoje = execute_query("""
                SELECT COUNT(*) as total
                FROM sinais_vitais
                WHERE DATE(data_afericao) = CURDATE()
            """, fetch=True, one=True)
            
            return jsonify({
                'consultas_hoje': consultas_hoje['total'] if consultas_hoje else 0,
                'triagens_pendentes': triagens_pendentes['total'] if triagens_pendentes else 0,
                'internados': internados['total'] if internados else 0,
                'afericoes_hoje': afericoes_hoje['total'] if afericoes_hoje else 0
            })
            
        except Exception as e:
            logger.error(f"Erro em contadores: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    # ================= API: ULTIMOS REGISTROS =================
    @dashboard_api_bp.route('/ultimos-registros')
    @enfermeiro_required
    def ultimos_registros():
        """Retorna os últimos registros do enfermeiro"""
        try:
            enfermeiro_id = obter_enfermeiro_id()
            
            # Últimas triagens realizadas
            triagens = execute_query("""
                SELECT 
                    t.id,
                    t.data_triagem,
                    t.classificacao_risco,
                    COALESCE(u.nome, 'Paciente') as paciente_nome,
                    'triagem' as tipo
                FROM triagem t
                LEFT JOIN consultas c ON t.consulta_id = c.id
                LEFT JOIN pacientes p ON c.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                WHERE t.enfermeiro_id = %s
                ORDER BY t.data_triagem DESC
                LIMIT 5
            """, (enfermeiro_id,), fetch=True)
            
            # Últimas aferições
            afericoes = execute_query("""
                SELECT 
                    sv.id,
                    sv.data_afericao,
                    sv.pressao_arterial,
                    sv.frequencia_cardiaca,
                    COALESCE(u.nome, 'Paciente') as paciente_nome,
                    'afericao' as tipo
                FROM sinais_vitais sv
                LEFT JOIN pacientes p ON sv.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                WHERE sv.enfermeiro_id = %s
                ORDER BY sv.data_afericao DESC
                LIMIT 5
            """, (enfermeiro_id,), fetch=True)
            
            # Combinar e ordenar
            todos_registros = []
            
            for t in triagens:
                todos_registros.append({
                    'id': t['id'],
                    'paciente': t['paciente_nome'],
                    'tipo': 'Triagem',
                    'cor': 'warning',
                    'icone': 'stethoscope',
                    'data': formatar_data(t['data_triagem']),
                    'detalhe': f"Classificação: {t['classificacao_risco']}",
                    'link': f"/enfermeiro/triagem/detalhes/{t['id']}"
                })
            
            for a in afericoes:
                todos_registros.append({
                    'id': a['id'],
                    'paciente': a['paciente_nome'],
                    'tipo': 'Sinais Vitais',
                    'cor': 'info',
                    'icone': 'heartbeat',
                    'data': formatar_data(a['data_afericao']),
                    'detalhe': f"PA: {a['pressao_arterial']} | FC: {a['frequencia_cardiaca']}",
                    'link': f"/enfermeiro/sinais-vitais/{a['id']}"
                })
            
            # Ordenar por data mais recente
            todos_registros.sort(key=lambda x: x['data'], reverse=True)
            
            return jsonify({'registros': todos_registros[:10]})
            
        except Exception as e:
            logger.error(f"Erro em ultimos_registros: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e), 'registros': []}), 500

    # ================= API: TRIAGENS PENDENTES =================
    @dashboard_api_bp.route('/triagens-pendentes')
    @enfermeiro_required
    def triagens_pendentes():
        """Retorna lista de triagens pendentes"""
        try:
            hoje_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            hoje_fim = hoje_inicio + timedelta(days=1)
            
            pendentes = execute_query("""
                SELECT 
                    c.id as consulta_id,
                    c.horario as horario_consulta,
                    COALESCE(u.nome, 'Paciente') as paciente_nome,
                    p.idade,
                    p.genero
                FROM consultas c
                LEFT JOIN pacientes p ON c.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                LEFT JOIN triagem t ON c.id = t.consulta_id
                WHERE c.data_hora >= %s AND c.data_hora < %s
                AND t.id IS NULL
                AND c.status = 'agendada'
                ORDER BY c.horario ASC
                LIMIT 10
            """, (hoje_inicio, hoje_fim), fetch=True)
            
            lista = []
            for p in pendentes:
                lista.append({
                    'consulta_id': p['consulta_id'],
                    'paciente_nome': p['paciente_nome'],
                    'horario': str(p['horario_consulta']) if p['horario_consulta'] else '',
                    'idade': p['idade'] if p['idade'] else 'N/I',
                    'genero': p['genero'] if p['genero'] else 'N/I'
                })
            
            return jsonify({'triagens': lista})
            
        except Exception as e:
            logger.error(f"Erro em triagens_pendentes: {e}")
            return jsonify({'error': str(e), 'triagens': []}), 500

    # ================= API: TAREFAS DO DIA =================
    @dashboard_api_bp.route('/tarefas-dia')
    @enfermeiro_required
    def tarefas_dia():
        """Retorna tarefas programadas para o dia"""
        try:
            hoje_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            hoje_fim = hoje_inicio + timedelta(days=1)
            
            # Medicações agendadas para hoje
            medicamentos = execute_query("""
                SELECT 
                    m.id,
                    m.nome_medicamento,
                    m.dosagem,
                    m.horario,
                    COALESCE(u.nome, 'Paciente') as paciente_nome,
                    'medicamento' as tipo
                FROM medicamentos m
                LEFT JOIN internacoes i ON m.internacao_id = i.id
                LEFT JOIN pacientes p ON i.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                WHERE DATE(m.horario) = CURDATE()
                AND m.status = 'pendente'
                ORDER BY m.horario ASC
                LIMIT 5
            """, fetch=True)
            
            # Procedimentos agendados
            procedimentos = execute_query("""
                SELECT 
                    cp.id,
                    cp.tipo_procedimento,
                    cp.horario,
                    COALESCE(u.nome, 'Paciente') as paciente_nome,
                    'procedimento' as tipo
                FROM consultas_procedimentos cp
                LEFT JOIN consultas c ON cp.consulta_id = c.id
                LEFT JOIN pacientes p ON c.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                WHERE DATE(cp.horario) = CURDATE()
                AND cp.status = 'pendente'
                ORDER BY cp.horario ASC
                LIMIT 5
            """, fetch=True)
            
            tarefas = []
            
            for m in medicamentos:
                tarefas.append({
                    'id': m['id'],
                    'paciente': m['paciente_nome'],
                    'tipo': 'Medicação',
                    'descricao': f"{m['nome_medicamento']} - {m['dosagem']}",
                    'horario': str(m['horario']) if m['horario'] else '',
                    'link': f"/enfermeiro/medicamentos/{m['id']}"
                })
            
            for p in procedimentos:
                tarefas.append({
                    'id': p['id'],
                    'paciente': p['paciente_nome'],
                    'tipo': 'Procedimento',
                    'descricao': p['tipo_procedimento'],
                    'horario': str(p['horario']) if p['horario'] else '',
                    'link': f"/enfermeiro/procedimentos/{p['id']}"
                })
            
            # Ordenar por horário
            tarefas.sort(key=lambda x: x['horario'])
            
            return jsonify({'tarefas': tarefas})
            
        except Exception as e:
            logger.error(f"Erro em tarefas_dia: {e}")
            return jsonify({'error': str(e), 'tarefas': []}), 500

    # ================= API: GRAFICO AFERICOES =================
    @dashboard_api_bp.route('/grafico-afericoes')
    @enfermeiro_required
    def grafico_afericoes():
        """Retorna dados para o gráfico de aferições dos últimos 7 dias"""
        try:
            dias = []
            dados = []
            
            for i in range(7):
                data = datetime.now() - timedelta(days=6-i)
                dias.append(data.strftime('%d/%m'))
                
                # Contar aferições do dia
                total = execute_query("""
                    SELECT COUNT(*) as total
                    FROM sinais_vitais
                    WHERE DATE(data_afericao) = %s
                """, (data.date(),), fetch=True, one=True)
                
                dados.append(total['total'] if total else 0)
            
            return jsonify({
                'dias': dias,
                'dados': dados
            })
            
        except Exception as e:
            logger.error(f"Erro em grafico_afericoes: {e}")
            return jsonify({'error': str(e), 'dias': [], 'dados': []}), 500

    # ================= API: TESTE =================
    @dashboard_api_bp.route('/teste')
    @enfermeiro_required
    def teste():
        """Endpoint de teste para verificar se a API está funcionando"""
        return jsonify({
            'success': True,
            'message': 'Dashboard API do Enfermeiro está funcionando!',
            'enfermeiro_id': obter_enfermeiro_id(),
            'session': {
                'user_id': session.get('user_id'),
                'user_type': session.get('user_type'),
                'enfermeiro_id': session.get('enfermeiro_id')
            }
        })

    return dashboard_api_bp
