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
            return render_template('login.html', error='Faça login para continuar')
        if session.get('user_type') != 'enfermeiro':
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
        logger.error(f"Database error in dashboard: {e}")
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
                c.horario as hora,
                c.status,
                COALESCE(u.nome, 'Paciente') as paciente_nome,
                m.nome as medico_nome,
                (SELECT COUNT(*) FROM triagem t WHERE t.consulta_id = c.id) as tem_triagem
            FROM consultas c
            LEFT JOIN pacientes p ON c.paciente_id = p.id
            LEFT JOIN usuarios u ON p.usuario_id = u.id
            LEFT JOIN medicos m ON c.medico_id = m.id
            WHERE c.data_hora >= %s AND c.data_hora < %s
            ORDER BY c.horario ASC
        """, (hoje_inicio, hoje_fim), fetch=True)
        
        # Buscar triagens pendentes
        triagens_pendentes = execute_query("""
            SELECT 
                c.id,
                c.horario as hora_chegada,
                COALESCE(u.nome, 'Paciente') as paciente_nome,
                c.status
            FROM consultas c
            LEFT JOIN pacientes p ON c.paciente_id = p.id
            LEFT JOIN usuarios u ON p.usuario_id = u.id
            LEFT JOIN triagem t ON c.id = t.consulta_id
            WHERE c.data_hora >= %s AND c.data_hora < %s
            AND t.id IS NULL
            AND c.status != 'cancelada'
            ORDER BY c.horario ASC
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
                p.numero_prontuario,
                COALESCE(u.nome, 'Paciente') as paciente_nome,
                p.data_nascimento,
                l.id as leito_id,
                l.numero as leito_numero,
                l.tipo as leito_tipo,
                a.nome as leito_alas
            FROM internacoes i
            JOIN pacientes p ON i.paciente_id = p.id
            JOIN usuarios u ON p.usuario_id = u.id
            JOIN leitos l ON i.leito_id = l.id
            JOIN alas a ON l.alas_id = a.id
            WHERE i.status = 'internado'
            ORDER BY i.data_internacao DESC
        """, fetch=True)
        
        # Calcular idade para cada internado
        for internado in internados_lista:
            if internado.get('data_nascimento'):
                idade = hoje.year - internado['data_nascimento'].year
                if (hoje.month, hoje.day) < (internado['data_nascimento'].month, internado['data_nascimento'].day):
                    idade -= 1
                internado['idade'] = idade
            else:
                internado['idade'] = None
            
            # Buscar últimos sinais vitais
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
        
        pacientes_internados = len(internados_lista)
        pacientes_aguardando = len(triagens_pendentes)
        
        return render_template('enfermeiro/dashboard.html',
            hoje=hoje.strftime('%Y-%m-%d'),
            data_selecionada=hoje.strftime('%Y-%m-%d'),
            consultas_data=consultas_hoje,
            triagens_pendentes=triagens_pendentes,
            internados_lista=internados_lista,
            ultimas_afericoes=ultimas_afericoes,
            dias_semana=dias_semana,
            dados_grafico=dados_grafico,
            total_afericoes_hoje=total_afericoes_hoje['total'] if total_afericoes_hoje else 0,
            total_consultas_hoje=total_consultas_hoje['total'] if total_consultas_hoje else 0,
            pacientes_internados=pacientes_internados,
            pacientes_aguardando=pacientes_aguardando
        )
        
    except Exception as e:
        logger.error(f"Erro no dashboard: {e}")
        import traceback
        traceback.print_exc()
        return render_template('enfermeiro/dashboard.html',
            error=str(e),
            consultas_data=[],
            triagens_pendentes=[],
            internados_lista=[],
            ultimas_afericoes=[],
            dias_semana=[],
            dados_grafico=[],
            total_afericoes_hoje=0,
            total_consultas_hoje=0,
            pacientes_internados=0,
            pacientes_aguardando=0
        )
