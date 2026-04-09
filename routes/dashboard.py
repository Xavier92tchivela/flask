# routes/dashboard_api.py
from flask import Blueprint, jsonify, session
from datetime import datetime, timedelta
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def init_dashboard_api(mysql):
    
    dashboard_api_bp = Blueprint('dashboard_api', __name__, url_prefix='/medico/api')
    
    # ================= AUTH =================
    def medico_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session or session.get('user_type') != 'medico':
                return jsonify({'error': 'Não autorizado'}), 401
            return f(*args, **kwargs)
        return decorated_function

    # ================= DB =================
    def execute_query(query, params=None, fetch=False, one=False):
        try:
            cur = mysql.connection.cursor(dictionary=True)  # 🔥 dict cursor
            
            cur.execute(query, params or ())
            
            if fetch:
                result = cur.fetchall()
                cur.close()
                if one:
                    return result[0] if result else None
                return result
            
            cur.close()
            return None
        
        except Exception as e:
            logger.error(f"Database error: {e}")
            return None

    # ================= UTILS =================
    def formatar_data(data, formato='%d/%m/%Y'):
        if not data:
            return ''
        if isinstance(data, datetime):
            return data.strftime(formato)
        return str(data)

    def obter_medico_id():
        # 🔥 agora vem da session (zero queries)
        return session.get('medico_id')

    # ================= API: PEDIDOS RECENTES =================
    @dashboard_api_bp.route('/pedidos-recentes')
    @medico_required
    def pedidos_recentes():
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
                    COALESCE(u.nome, 'Não informado') as paciente_nome
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                WHERE pa.medico_id = %s
                ORDER BY pa.data_solicitacao DESC
                LIMIT 5
            """, (medico_id,), fetch=True)

            return jsonify({
                'pedidos': [
                    {
                        'id': p['id'],
                        'tipo_exame': p['tipo_exame'],
                        'status': p['status'],
                        'data_solicitacao': formatar_data(p['data_solicitacao']),
                        'status_aprovacao': p['status_aprovacao'],
                        'paciente_nome': p['paciente_nome']
                    }
                    for p in (pedidos or [])
                ]
            })

        except Exception as e:
            logger.error(f"Erro: {e}")
            return jsonify({'error': str(e)}), 500

    # ================= API: CONTADORES =================
    @dashboard_api_bp.route('/contadores')
    @medico_required
    def contadores():
        try:
            medico_id = obter_medico_id()
            if not medico_id:
                return jsonify({
                    'resultados_pendentes': 0,
                    'analises_solicitadas': 0,
                    'notificacoes': 0,
                    'consultas_hoje': 0
                })

            # 🔥 datas otimizadas (sem DATE())
            hoje_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            hoje_fim = hoje_inicio + timedelta(days=1)

            # 🔥 1 query para pedidos
            dados = execute_query("""
                SELECT 
                    SUM(CASE 
                        WHEN status = 'concluido' AND status_aprovacao = 'pendente' 
                        THEN 1 ELSE 0 END) as resultados_pendentes,

                    SUM(CASE 
                        WHEN status IN ('pendente', 'em_analise') 
                        THEN 1 ELSE 0 END) as analises_solicitadas

                FROM pedidos_analise
                WHERE medico_id = %s
            """, (medico_id,), fetch=True, one=True)

            # 🔥 consultas (com índice)
            consultas = execute_query("""
                SELECT COUNT(*) as total
                FROM consultas
                WHERE medico_id = %s
                AND data_hora BETWEEN %s AND %s
            """, (medico_id, hoje_inicio, hoje_fim), fetch=True, one=True)

            resultados_pendentes = dados['resultados_pendentes'] or 0 if dados else 0

            return jsonify({
                'resultados_pendentes': resultados_pendentes,
                'analises_solicitadas': dados['analises_solicitadas'] or 0 if dados else 0,
                'notificacoes': resultados_pendentes,
                'consultas_hoje': consultas['total'] if consultas else 0
            })

        except Exception as e:
            logger.error(f"Erro: {e}")
            return jsonify({'error': str(e)}), 500

    # ================= API: NOTIFICAÇÕES =================
    @dashboard_api_bp.route('/notificacoes')
    @medico_required
    def notificacoes():
        try:
            medico_id = obter_medico_id()
            if not medico_id:
                return jsonify({'notificacoes': []})

            pedidos = execute_query("""
                SELECT 
                    pa.id,
                    pa.tipo_exame,
                    pa.data_conclusao,
                    COALESCE(u.nome, 'Paciente') as paciente_nome
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                WHERE pa.medico_id = %s 
                AND pa.status = 'concluido' 
                AND pa.status_aprovacao = 'pendente'
                ORDER BY pa.data_conclusao DESC
                LIMIT 5
            """, (medico_id,), fetch=True)

            lista = []

            for p in (pedidos or []):
                data = p['data_conclusao'] or datetime.now()
                dias = (datetime.now() - data).days

                if dias == 0:
                    tempo = "Hoje"
                elif dias == 1:
                    tempo = "Ontem"
                else:
                    tempo = f"{dias} dias atrás"

                lista.append({
                    'id': p['id'],
                    'titulo': f"Resultado: {p['tipo_exame']}",
                    'mensagem': f"Resultado de {p['paciente_nome']} aguardando revisão",
                    'link': f"/medico/revisar-analise/{p['id']}",
                    'tempo': tempo
                })

            return jsonify({'notificacoes': lista})

        except Exception as e:
            logger.error(f"Erro: {e}")
            return jsonify({'error': str(e)}), 500

    return dashboard_api_bp