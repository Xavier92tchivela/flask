# routes/dashboard_api.py
from flask import Blueprint, jsonify, session
from datetime import datetime
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def init_dashboard_api(mysql):
    """Inicializa o blueprint de APIs do dashboard"""
    
    dashboard_api_bp = Blueprint('dashboard_api', __name__, url_prefix='/medico/api')
    
    def medico_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session or session.get('user_type') != 'medico':
                return jsonify({'error': 'Não autorizado'}), 401
            return f(*args, **kwargs)
        return decorated_function
    
    def execute_query(query, params=None, fetch=False, one=False):
        try:
            cur = mysql.connection.cursor()
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            
            if fetch:
                result = cur.fetchall()
                cur.close()
                if one:
                    return result[0] if result else None
                return result
            return None
        except Exception as e:
            logger.error(f"Database error: {e}")
            return None
    
    def formatar_data(data, formato='%d/%m/%Y'):
        if not data:
            return ''
        if isinstance(data, datetime):
            return data.strftime(formato)
        return str(data)
    
    def obter_medico_id():
        try:
            user_id = session.get('user_id')
            if not user_id:
                return None
            result = execute_query(
                "SELECT id FROM medicos WHERE usuario_id = %s",
                (user_id,), fetch=True, one=True
            )
            return result[0] if result else None
        except:
            return None
    
    # ========== API: PEDIDOS RECENTES ==========
    @dashboard_api_bp.route('/pedidos-recentes')
    @medico_required
    def pedidos_recentes():
        """API para carregar pedidos recentes"""
        try:
            medico_id = obter_medico_id()
            if not medico_id:
                return jsonify({'pedidos': []})
            
            pedidos = execute_query("""
                SELECT 
                    pa.id,
                    pa.tipo_exame,
                    pa.status,
                    pa.data_solicitacao,
                    pa.status_aprovacao,
                    COALESCE(p_u.nome, 'Não informado') as paciente_nome
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios p_u ON p.usuario_id = p_u.id
                WHERE pa.medico_id = %s
                ORDER BY pa.data_solicitacao DESC
                LIMIT 5
            """, (medico_id,), fetch=True)
            
            pedidos_lista = []
            if pedidos:
                for p in pedidos:
                    pedidos_lista.append({
                        'id': p[0],
                        'tipo_exame': p[1],
                        'status': p[2],
                        'data_solicitacao': formatar_data(p[3]),
                        'status_aprovacao': p[4],
                        'paciente_nome': p[5]
                    })
            
            return jsonify({'pedidos': pedidos_lista})
            
        except Exception as e:
            logger.error(f"Erro: {e}")
            return jsonify({'error': str(e)}), 500
    
    # ========== API: CONTADORES ==========
    @dashboard_api_bp.route('/contadores')
    @medico_required
    def contadores():
        """API para carregar contadores atualizados"""
        try:
            medico_id = obter_medico_id()
            if not medico_id:
                return jsonify({
                    'resultados_pendentes': 0,
                    'analises_solicitadas': 0,
                    'notificacoes': 0,
                    'consultas_hoje': 0
                })
            
            # Resultados pendentes
            resultados = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s 
                AND status = 'concluido' 
                AND status_aprovacao = 'pendente'
            """, (medico_id,), fetch=True, one=True)
            
            # Análises solicitadas
            analises = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s 
                AND status IN ('pendente', 'em_analise')
            """, (medico_id,), fetch=True, one=True)
            
            # Consultas hoje
            hoje = datetime.now().strftime('%Y-%m-%d')
            consultas = execute_query("""
                SELECT COUNT(*) FROM consultas 
                WHERE medico_id = %s 
                AND DATE(data_hora) = %s
            """, (medico_id, hoje), fetch=True, one=True)
            
            resultados_pendentes = resultados[0] if resultados else 0
            
            return jsonify({
                'resultados_pendentes': resultados_pendentes,
                'analises_solicitadas': analises[0] if analises else 0,
                'notificacoes': resultados_pendentes,
                'consultas_hoje': consultas[0] if consultas else 0
            })
            
        except Exception as e:
            logger.error(f"Erro: {e}")
            return jsonify({'error': str(e)}), 500
    
    # ========== API: NOTIFICAÇÕES ==========
    @dashboard_api_bp.route('/notificacoes')
    @medico_required
    def notificacoes():
        """API para carregar notificações"""
        try:
            medico_id = obter_medico_id()
            if not medico_id:
                return jsonify({'notificacoes': []})
            
            pedidos = execute_query("""
                SELECT 
                    pa.id,
                    pa.tipo_exame,
                    pa.data_solicitacao,
                    COALESCE(p_u.nome, 'Paciente') as paciente_nome
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios p_u ON p.usuario_id = p_u.id
                WHERE pa.medico_id = %s 
                AND pa.status = 'concluido' 
                AND pa.status_aprovacao = 'pendente'
                ORDER BY pa.data_conclusao DESC
                LIMIT 5
            """, (medico_id,), fetch=True)
            
            notificacoes_lista = []
            if pedidos:
                for p in pedidos:
                    data = p[2] if isinstance(p[2], datetime) else datetime.now()
                    dias = (datetime.now() - data).days
                    
                    if dias == 0:
                        tempo = "Hoje"
                    elif dias == 1:
                        tempo = "Ontem"
                    else:
                        tempo = f"{dias} dias atrás"
                    
                    notificacoes_lista.append({
                        'id': p[0],
                        'titulo': f"Resultado: {p[1]}",
                        'mensagem': f"Resultado de {p[3]} aguardando revisão",
                        'link': f"/medico/revisar-analise/{p[0]}",
                        'tempo': tempo
                    })
            
            return jsonify({'notificacoes': notificacoes_lista})
            
        except Exception as e:
            logger.error(f"Erro: {e}")
            return jsonify({'error': str(e)}), 500
    
    return dashboard_api_bp