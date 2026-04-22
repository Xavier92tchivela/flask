# routes/dashboard_api.py
from flask import Blueprint, jsonify, session, current_app
from datetime import datetime, timedelta
import logging
from functools import wraps

logger = logging.getLogger(__name__)

_mysql = None

def set_mysql(mysql_instance):
    global _mysql
    _mysql = mysql_instance

def init_dashboard_api(mysql):
    global _mysql
    _mysql = mysql
    
    dashboard_api_bp = Blueprint('dashboard_api', __name__, url_prefix='/medico/api')
    
    # ================= AUTH =================
    def medico_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'error': 'Usuário não autenticado'}), 401
            if session.get('user_type') != 'medico':
                return jsonify({'error': 'Acesso restrito a médicos'}), 403
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
            logger.error(f"Database error in dashboard_api: {e}")
            logger.error(f"Query: {query}")
            if commit and _mysql:
                _mysql.connection.rollback()
            return None if fetch else False

    # ================= UTILS =================
    def formatar_data(data, formato='%d/%m/%Y'):
        if not data:
            return ''
        if isinstance(data, datetime):
            return data.strftime(formato)
        return str(data)

    def obter_medico_id():
        return session.get('medico_id')

    # ================= API: PEDIDOS RECENTES =================
    @dashboard_api_bp.route('/pedidos-recentes')
    @medico_required
    def pedidos_recentes():
        try:
            medico_id = obter_medico_id()
            if not medico_id:
                logger.warning("Medico ID não encontrado na sessão")
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

            if not pedidos:
                return jsonify({'pedidos': []})

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
                    for p in pedidos
                ]
            })

        except Exception as e:
            logger.error(f"Erro em pedidos_recentes: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e), 'pedidos': []}), 500

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

            # Data de hoje
            hoje_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            hoje_fim = hoje_inicio + timedelta(days=1)

            # Buscar dados de pedidos
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

            # Buscar consultas de hoje
            consultas = execute_query("""
                SELECT COUNT(*) as total
                FROM consultas
                WHERE medico_id = %s
                AND data_hora >= %s AND data_hora < %s
            """, (medico_id, hoje_inicio, hoje_fim), fetch=True, one=True)

            resultados_pendentes = dados['resultados_pendentes'] if dados and dados['resultados_pendentes'] else 0
            analises_solicitadas = dados['analises_solicitadas'] if dados and dados['analises_solicitadas'] else 0
            consultas_hoje = consultas['total'] if consultas else 0

            return jsonify({
                'resultados_pendentes': resultados_pendentes,
                'analises_solicitadas': analises_solicitadas,
                'notificacoes': resultados_pendentes,
                'consultas_hoje': consultas_hoje
            })

        except Exception as e:
            logger.error(f"Erro em contadores: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'resultados_pendentes': 0,
                'analises_solicitadas': 0,
                'notificacoes': 0,
                'consultas_hoje': 0,
                'error': str(e)
            }), 500

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

            if not pedidos:
                return jsonify({'notificacoes': []})

            lista = []
            for p in pedidos:
                data_conclusao = p.get('data_conclusao')
                if data_conclusao:
                    if isinstance(data_conclusao, datetime):
                        dias = (datetime.now() - data_conclusao).days
                    else:
                        dias = 0
                else:
                    dias = 0

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
            logger.error(f"Erro em notificacoes: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e), 'notificacoes': []}), 500

    # ================= API: TESTE =================
    @dashboard_api_bp.route('/teste')
    @medico_required
    def teste():
        """Endpoint de teste para verificar se a API está funcionando"""
        return jsonify({
            'success': True,
            'message': 'Dashboard API está funcionando!',
            'medico_id': obter_medico_id(),
            'session': {
                'user_id': session.get('user_id'),
                'user_type': session.get('user_type'),
                'medico_id': session.get('medico_id')
            }
        })

    return dashboard_api_bp
