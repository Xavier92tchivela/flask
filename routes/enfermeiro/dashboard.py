# routes/enfermeiro/dashboard.py
from flask import Blueprint, render_template, session, request, jsonify
from datetime import datetime, timedelta
import logging
from functools import wraps

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

_mysql = None

def set_mysql(mysql_instance):
    global _mysql
    _mysql = mysql_instance

def enfermeiro_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return render_template('login.html', error='Faça login para continuar')
        if session.get('user_type') != 'enfermeiro':
            return render_template('error.html', error='Acesso restrito a enfermeiros'), 403
        return f(*args, **kwargs)
    return decorated_function

def execute_query(query, params=None, fetch=False, one=False, commit=False):
    """Executa queries no banco de dados com tratamento de erro"""
    try:
        if _mysql is None:
            logger.error("MySQL não inicializado")
            return [] if fetch else False
            
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
            return result if result else (None if one else [])
        
        if commit:
            _mysql.connection.commit()
        
        cur.close()
        return True if commit else None
        
    except Exception as e:
        logger.error(f"Database error: {e}")
        if commit and _mysql:
            _mysql.connection.rollback()
        return [] if fetch else False

@dashboard_bp.route('/')
@enfermeiro_required
def index():
    """Dashboard principal do enfermeiro"""
    try:
        hoje = datetime.now()
        hoje_inicio = hoje.replace(hour=0, minute=0, second=0, microsecond=0)
        hoje_fim = hoje_inicio + timedelta(days=1)
        
        # Buscar consultas de hoje
        consultas_hoje = execute_query("""
            SELECT 
                c.id,
                c.horario as hora,
                c.status,
                COALESCE(u.nome, 'Paciente') as paciente_nome,
                m.nome as medico_nome
            FROM consultas c
            LEFT JOIN pacientes p ON c.paciente_id = p.id
            LEFT JOIN usuarios u ON p.usuario_id = u.id
            LEFT JOIN medicos m ON c.medico_id = m.id
            WHERE c.data_hora >= %s AND c.data_hora < %s
            ORDER BY c.horario ASC
        """, (hoje_inicio, hoje_fim), fetch=True)
        
        # Buscar triagens pendentes (usando a tabela correta)
        triagens_pendentes = []
        try:
            triagens_pendentes = execute_query("""
                SELECT 
                    c.id,
                    c.horario as hora_chegada,
                    COALESCE(u.nome, 'Paciente') as paciente_nome,
                    c.status
                FROM consultas c
                LEFT JOIN pacientes p ON c.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                WHERE c.data_hora >= %s AND c.data_hora < %s
                AND c.status_triagem != 'realizada'
                AND c.status != 'cancelada'
                ORDER BY c.horario ASC
            """, (hoje_inicio, hoje_fim), fetch=True)
        except Exception as e:
            logger.warning(f"Erro ao buscar triagens pendentes: {e}")
            triagens_pendentes = []
        
        # Buscar pacientes internados
        internados_lista = []
        try:
            internados_lista = execute_query("""
                SELECT 
                    i.id,
                    i.data_internacao,
                    i.tipo_internacao,
                    i.diagnostico_inicial,
                    i.status,
                    p.id as paciente_id,
                    p.numero_prontuario,
                    COALESCE(u.nome, 'Paciente') as paciente_nome,
                    p.data_nascimento,
                    l.id as leito_id,
                    l.numero as leito_numero,
                    l.tipo as leito_tipo
                FROM internacoes i
                JOIN pacientes p ON i.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                JOIN leitos l ON i.leito_id = l.id
                WHERE i.status = 'internado'
                ORDER BY i.data_internacao DESC
            """, fetch=True)
        except Exception as e:
            logger.warning(f"Erro ao buscar internados: {e}")
            internados_lista = []
        
        # Calcular idade para cada internado
        for internado in internados_lista:
            if internado and internado.get('data_nascimento'):
                idade = hoje.year - internado['data_nascimento'].year
                if (hoje.month, hoje.day) < (internado['data_nascimento'].month, internado['data_nascimento'].day):
                    idade -= 1
                internado['idade'] = idade
            else:
                internado['idade'] = None
            
            # Buscar últimos sinais vitais
            try:
                ultimos_sinais = execute_query("""
                    SELECT 
                        pressao_arterial,
                        frequencia_cardiaca,
                        temperatura,
                        saturacao_oxigenio,
                        glicemia,
                        data_afericao
                    FROM sinais_vitais
                    WHERE paciente_id = %s
                    ORDER BY data_afericao DESC
                    LIMIT 1
                """, (internado['paciente_id'],), fetch=True, one=True)
                internado['ultimos_sinais'] = ultimos_sinais
            except Exception as e:
                internado['ultimos_sinais'] = None
        
        # Buscar últimas aferições
        ultimas_afericoes = execute_query("""
            SELECT 
                sv.id,
                sv.data_afericao,
                sv.pressao_arterial,
                sv.frequencia_cardiaca,
                sv.temperatura,
                sv.saturacao_oxigenio,
                sv.glicemia,
                COALESCE(u.nome, 'Paciente') as paciente_nome
            FROM sinais_vitais sv
            LEFT JOIN pacientes p ON sv.paciente_id = p.id
            LEFT JOIN usuarios u ON p.usuario_id = u.id
            ORDER BY sv.data_afericao DESC
            LIMIT 10
        """, fetch=True)
        
        # Preparar dados para o gráfico
        dias_semana = []
        dados_grafico = []
        for i in range(7):
            data = hoje - timedelta(days=6-i)
            dias_semana.append(data.strftime('%d/%m'))
            
            total = execute_query("""
                SELECT COUNT(*) as total
                FROM sinais_vitais
                WHERE DATE(data_afericao) = %s
            """, (data.date(),), fetch=True, one=True)
            
            dados_grafico.append(total['total'] if total else 0)
        
        # Contadores
        total_afericoes_hoje = execute_query("""
            SELECT COUNT(*) as total
            FROM sinais_vitais
            WHERE DATE(data_afericao) = CURDATE()
        """, fetch=True, one=True)
        
        total_consultas_hoje = execute_query("""
            SELECT COUNT(*) as total
            FROM consultas
            WHERE data_hora >= %s AND data_hora < %s
        """, (hoje_inicio, hoje_fim), fetch=True, one=True)
        
        pacientes_internados = len(internados_lista) if internados_lista else 0
        pacientes_aguardando = len(triagens_pendentes) if triagens_pendentes else 0
        
        # Criar lista de últimos atendimentos para o template
        ultimos_atendimentos = []
        
        # Adicionar triagens recentes
        if triagens_pendentes:
            for t in triagens_pendentes[:3]:
                ultimos_atendimentos.append({
                    'paciente': t.get('paciente_nome', 'Paciente'),
                    'tipo': 'Triagem Pendente',
                    'cor': 'warning',
                    'icone': 'stethoscope',
                    'data': str(t.get('hora_chegada', '')) if t.get('hora_chegada') else '',
                    'link': f"/enfermeiro/triagem/realizar/{t['id']}" if t.get('id') else '#'
                })
        
        # Adicionar aferições recentes
        if ultimas_afericoes:
            for a in ultimas_afericoes[:3]:
                ultimos_atendimentos.append({
                    'paciente': a.get('paciente_nome', 'Paciente'),
                    'tipo': 'Sinais Vitais',
                    'cor': 'success',
                    'icone': 'heartbeat',
                    'data': str(a.get('data_afericao', '')) if a.get('data_afericao') else '',
                    'detalhe': f"PA: {a.get('pressao_arterial', '-')} | FC: {a.get('frequencia_cardiaca', '-')}",
                    'link': f"/enfermeiro/sinais-vitais/{a['id']}" if a.get('id') else '#'
                })
        
        return render_template('enfermeiro/dashboard.html',
            hoje=hoje.strftime('%Y-%m-%d'),
            data_selecionada=hoje.strftime('%Y-%m-%d'),
            consultas_data=consultas_hoje if consultas_hoje else [],
            consultas_hoje=consultas_hoje if consultas_hoje else [],
            triagens_pendentes=triagens_pendentes if triagens_pendentes else [],
            internados_hoje=internados_lista if internados_lista else [],
            internados_lista=internados_lista if internados_lista else [],
            ultimas_afericoes=ultimas_afericoes if ultimas_afericoes else [],
            ultimos_atendimentos=ultimos_atendimentos,
            dias_semana=dias_semana,
            dados_grafico=dados_grafico,
            total_afericoes_hoje=total_afericoes_hoje['total'] if total_afericoes_hoje else 0,
            total_consultas_hoje=total_consultas_hoje['total'] if total_consultas_hoje else 0,
            pacientes_internados=pacientes_internados,
            pacientes_aguardando=pacientes_aguardando,
            # Métricas adicionais
            total_consultas=total_consultas_hoje['total'] if total_consultas_hoje else 0,
            triagens_realizadas=0,
            afericoes_semana=sum(dados_grafico) if dados_grafico else 0,
            taxa_ocupacao=0,
            meta_atual=total_consultas_hoje['total'] if total_consultas_hoje else 0,
            meta_semanal=50,
            triagens_hoje=0,
            meta_triagens_diaria=10,
            progresso_semanal=(total_consultas_hoje['total'] / 50 * 100) if total_consultas_hoje and total_consultas_hoje['total'] > 0 else 0,
            progresso_triagens=0
        )
        
    except Exception as e:
        logger.error(f"Erro no dashboard: {e}")
        import traceback
        traceback.print_exc()
        return render_template('enfermeiro/dashboard.html',
            error=str(e),
            hoje=datetime.now().strftime('%Y-%m-%d'),
            data_selecionada=datetime.now().strftime('%Y-%m-%d'),
            consultas_data=[],
            consultas_hoje=[],
            triagens_pendentes=[],
            internados_hoje=[],
            internados_lista=[],
            ultimas_afericoes=[],
            ultimos_atendimentos=[],
            dias_semana=[],
            dados_grafico=[],
            total_afericoes_hoje=0,
            total_consultas_hoje=0,
            pacientes_internados=0,
            pacientes_aguardando=0,
            total_consultas=0,
            triagens_realizadas=0,
            afericoes_semana=0,
            taxa_ocupacao=0,
            meta_atual=0,
            meta_semanal=50,
            triagens_hoje=0,
            meta_triagens_diaria=10,
            progresso_semanal=0,
            progresso_triagens=0
        )


# API endpoints para o dashboard
@dashboard_bp.route('/api/contadores')
@enfermeiro_required
def api_contadores():
    """API para contadores do dashboard"""
    try:
        hoje_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        hoje_fim = hoje_inicio + timedelta(days=1)
        
        consultas_hoje = execute_query("""
            SELECT COUNT(*) as total
            FROM consultas
            WHERE data_hora >= %s AND data_hora < %s
        """, (hoje_inicio, hoje_fim), fetch=True, one=True)
        
        triagens_pendentes = execute_query("""
            SELECT COUNT(*) as total
            FROM consultas c
            WHERE c.data_hora >= %s AND c.data_hora < %s
            AND c.status_triagem != 'realizada'
            AND c.status != 'cancelada'
        """, (hoje_inicio, hoje_fim), fetch=True, one=True)
        
        internados = execute_query("""
            SELECT COUNT(*) as total
            FROM internacoes
            WHERE status = 'internado'
        """, fetch=True, one=True)
        
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
        logger.error(f"Erro na API contadores: {e}")
        return jsonify({
            'consultas_hoje': 0,
            'triagens_pendentes': 0,
            'internados': 0,
            'afericoes_hoje': 0,
            'error': str(e)
        }), 500
