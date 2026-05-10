# routes/enfermeiro/dashboard.py
from flask import Blueprint, render_template, session, request, jsonify
from datetime import datetime, timedelta
import logging
from functools import wraps

logger = logging.getLogger(__name__)

# Criar o blueprint
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

_mysql = None

def set_mysql(mysql_instance):
    global _mysql
    _mysql = mysql_instance

def enfermeiro_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # Para APIs, retornar JSON em vez de redirecionar
            if request.path.startswith('/dashboard/api/'):
                return jsonify({'error': 'Não autorizado', 'authenticated': False}), 401
            return render_template('login.html', error='Faça login para continuar')
        if session.get('user_type') != 'enfermeiro':
            if request.path.startswith('/dashboard/api/'):
                return jsonify({'error': 'Acesso restrito a enfermeiros'}), 403
            return render_template('error.html', error='Acesso restrito a enfermeiros'), 403
        return f(*args, **kwargs)
    return decorated_function

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
        logger.error(f"Database error: {e}")
        if commit and _mysql:
            _mysql.connection.rollback()
        return None if fetch else False


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
                TIME(c.data_hora) as hora,
                c.status,
                COALESCE(u.nome, 'Paciente') as paciente_nome
            FROM consultas c
            LEFT JOIN pacientes p ON c.paciente_id = p.id
            LEFT JOIN usuarios u ON p.usuario_id = u.id
            WHERE c.data_hora >= %s AND c.data_hora < %s
            ORDER BY c.data_hora ASC
        """, (hoje_inicio, hoje_fim), fetch=True)
        
        # Buscar triagens pendentes
        triagens_pendentes = execute_query("""
            SELECT 
                c.id,
                TIME(c.data_hora) as hora_chegada,
                COALESCE(u.nome, 'Paciente') as paciente_nome,
                c.status
            FROM consultas c
            LEFT JOIN pacientes p ON c.paciente_id = p.id
            LEFT JOIN usuarios u ON p.usuario_id = u.id
            WHERE c.data_hora >= %s AND c.data_hora < %s
            AND (c.status_triagem IS NULL OR c.status_triagem = 'pendente')
            AND c.status != 'cancelada'
            ORDER BY c.data_hora ASC
        """, (hoje_inicio, hoje_fim), fetch=True)
        
        # Buscar pacientes internados
        internados_lista = execute_query("""
            SELECT 
                i.id,
                i.data_internacao,
                i.tipo_internacao,
                i.diagnostico_inicial,
                i.status,
                p.id as paciente_id,
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
        
        if internados_lista is None:
            internados_lista = []
        
        # Calcular idade
        for internado in internados_lista:
            if internado and internado.get('data_nascimento'):
                idade = hoje.year - internado['data_nascimento'].year
                if (hoje.month, hoje.day) < (internado['data_nascimento'].month, internado['data_nascimento'].day):
                    idade -= 1
                internado['idade'] = idade
            else:
                internado['idade'] = None
        
        # Buscar últimas aferições - CORRIGIDO: usar consulta_id em vez de paciente_id
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
            LEFT JOIN consultas c ON sv.consulta_id = c.id
            LEFT JOIN pacientes p ON c.paciente_id = p.id
            LEFT JOIN usuarios u ON p.usuario_id = u.id
            ORDER BY sv.data_afericao DESC
            LIMIT 10
        """, fetch=True)
        
        if ultimas_afericoes is None:
            ultimas_afericoes = []
        
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
        
        return render_template('enfermeiro/dashboard.html',
            hoje=hoje.strftime('%Y-%m-%d'),
            data_selecionada=hoje.strftime('%Y-%m-%d'),
            consultas_data=consultas_hoje if consultas_hoje else [],
            consultas_hoje=consultas_hoje if consultas_hoje else [],
            triagens_pendentes=triagens_pendentes if triagens_pendentes else [],
            internados_hoje=internados_lista if internados_lista else [],
            ultimas_afericoes=ultimas_afericoes if ultimas_afericoes else [],
            total_afericoes_hoje=total_afericoes_hoje['total'] if total_afericoes_hoje else 0,
            total_consultas_hoje=total_consultas_hoje['total'] if total_consultas_hoje else 0,
            pacientes_internados=pacientes_internados,
            pacientes_aguardando=pacientes_aguardando,
            total_consultas=total_consultas_hoje['total'] if total_consultas_hoje else 0,
            triagens_hoje=0,
            consultas_semana=0,
            taxa_ocupacao=0,
            total_triagens=0,
            media_diaria=0,
            eficiencia=0,
            progresso_semanal=0,
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
            ultimas_afericoes=[],
            total_afericoes_hoje=0,
            total_consultas_hoje=0,
            pacientes_internados=0,
            pacientes_aguardando=0,
            total_consultas=0,
            triagens_hoje=0,
            consultas_semana=0,
            taxa_ocupacao=0,
            total_triagens=0,
            media_diaria=0,
            eficiencia=0,
            progresso_semanal=0,
            progresso_triagens=0
        )


# ============================================================
# API ENDPOINTS - CORRIGIDOS
# ============================================================

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
            AND (c.status_triagem IS NULL OR c.status_triagem = 'pendente')
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
            'success': True,
            'consultas_hoje': consultas_hoje['total'] if consultas_hoje else 0,
            'triagens_pendentes': triagens_pendentes['total'] if triagens_pendentes else 0,
            'internados': internados['total'] if internados else 0,
            'afericoes_hoje': afericoes_hoje['total'] if afericoes_hoje else 0
        })
        
    except Exception as e:
        logger.error(f"Erro na API contadores: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'consultas_hoje': 0,
            'triagens_pendentes': 0,
            'internados': 0,
            'afericoes_hoje': 0
        }), 200  # Retornar 200 mesmo com erro para não quebrar o frontend
