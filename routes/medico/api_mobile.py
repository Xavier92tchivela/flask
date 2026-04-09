from flask import Blueprint, request, jsonify, session
from datetime import datetime, timedelta
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def init_mobile_api(mysql, base):
    """
    Inicializa API REST para o app mobile
    """
    
    execute_query = base['execute_query']
    
    mobile_api_bp = Blueprint('mobile_api', __name__, url_prefix='/api/mobile')
    
    # ===== DECORATOR PARA TOKEN =====
    def token_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = request.headers.get('Authorization')
            
            if not token or not token.startswith('Bearer '):
                return jsonify({'error': 'Token não fornecido'}), 401
            
            token = token.replace('Bearer ', '')
            
            # Verificar token no banco
            user = execute_query("""
                SELECT u.id, u.nome, u.email, u.tipo, t.expira_em
                FROM usuarios u
                JOIN tokens t ON u.id = t.usuario_id
                WHERE t.token = %s AND t.expira_em > NOW()
            """, (token,), fetch=True, one=True)
            
            if not user:
                return jsonify({'error': 'Token inválido ou expirado'}), 401
            
            request.user_id = user[0]
            request.user_nome = user[1]
            request.user_email = user[2]
            request.user_tipo = user[3]
            
            return f(*args, **kwargs)
        return decorated
    
    # ===== ROTAS DA API MOBILE =====
    
    @mobile_api_bp.route('/login', methods=['POST'])
    def mobile_login():
        """Login para app mobile - retorna token"""
        try:
            data = request.get_json()
            email = data.get('email')
            senha = data.get('senha')
            
            if not email or not senha:
                return jsonify({'error': 'Email e senha obrigatórios'}), 400
            
            # Buscar usuário
            user = execute_query("""
                SELECT id, nome, email, tipo, senha_hash
                FROM usuarios
                WHERE email = %s AND ativo = 1
            """, (email,), fetch=True, one=True)
            
            if not user:
                return jsonify({'error': 'Usuário não encontrado'}), 401
            
            # Verificar senha (usar check_password_hash)
            from werkzeug.security import check_password_hash
            if not check_password_hash(user[4], senha):
                return jsonify({'error': 'Senha incorreta'}), 401
            
            # Gerar token
            import secrets
            token = secrets.token_urlsafe(32)
            expira_em = datetime.now() + timedelta(days=30)
            
            # Salvar token
            execute_query("""
                INSERT INTO tokens (usuario_id, token, expira_em)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE token = %s, expira_em = %s
            """, (user[0], token, expira_em, token, expira_em))
            
            # Buscar info específica do médico
            medico_info = None
            if user[3] == 'medico':
                medico = execute_query("""
                    SELECT id, especialidade, crm
                    FROM medicos
                    WHERE usuario_id = %s
                """, (user[0],), fetch=True, one=True)
                
                if medico:
                    medico_info = {
                        'medico_id': medico[0],
                        'especialidade': medico[1],
                        'crm': medico[2]
                    }
            
            return jsonify({
                'success': True,
                'token': token,
                'user': {
                    'id': user[0],
                    'nome': user[1],
                    'email': user[2],
                    'tipo': user[3],
                    'medico_info': medico_info
                }
            })
            
        except Exception as e:
            logger.error(f"Erro no login mobile: {e}")
            return jsonify({'error': str(e)}), 500
    
    @mobile_api_bp.route('/dashboard', methods=['GET'])
    @token_required
    def mobile_dashboard():
        """Dados do dashboard para app mobile"""
        try:
            if request.user_tipo != 'medico':
                return jsonify({'error': 'Acesso restrito a médicos'}), 403
            
            # Buscar ID do médico
            medico = execute_query("""
                SELECT id FROM medicos WHERE usuario_id = %s
            """, (request.user_id,), fetch=True, one=True)
            
            if not medico:
                return jsonify({'error': 'Médico não encontrado'}), 404
            
            medico_id = medico[0]
            hoje = datetime.now().strftime('%Y-%m-%d')
            
            # Consultas de hoje
            consultas_hoje = execute_query("""
                SELECT 
                    c.id,
                    u.nome as paciente_nome,
                    TIME(c.data_hora) as hora,
                    c.status
                FROM consultas c
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE c.medico_id = %s AND DATE(c.data_hora) = %s
                ORDER BY c.data_hora
            """, (medico_id, hoje), fetch=True) or []
            
            # Contadores
            resultados_pendentes = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status = 'concluido' 
                AND status_aprovacao = 'pendente'
            """, (medico_id,), fetch=True, one=True)
            
            analises_solicitadas = execute_query("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status IN ('pendente', 'em_analise')
            """, (medico_id,), fetch=True, one=True)
            
            # Últimas notificações
            notificacoes = execute_query("""
                SELECT id, titulo, mensagem, link, criado_em
                FROM notificacoes
                WHERE usuario_id = %s
                ORDER BY criado_em DESC
                LIMIT 5
            """, (request.user_id,), fetch=True) or []
            
            return jsonify({
                'success': True,
                'dashboard': {
                    'consultas_hoje': len(consultas_hoje),
                    'consultas_lista': [
                        {
                            'id': c[0],
                            'paciente': c[1],
                            'hora': str(c[2])[:5] if c[2] else '',
                            'status': c[3]
                        } for c in consultas_hoje
                    ],
                    'resultados_pendentes': resultados_pendentes[0] if resultados_pendentes else 0,
                    'analises_solicitadas': analises_solicitadas[0] if analises_solicitadas else 0,
                    'notificacoes': [
                        {
                            'id': n[0],
                            'titulo': n[1],
                            'mensagem': n[2],
                            'link': n[3],
                            'data': n[4].strftime('%d/%m/%Y %H:%M') if n[4] else ''
                        } for n in notificacoes
                    ]
                }
            })
            
        except Exception as e:
            logger.error(f"Erro no dashboard mobile: {e}")
            return jsonify({'error': str(e)}), 500
    
    @mobile_api_bp.route('/consultas', methods=['GET'])
    @token_required
    def mobile_consultas():
        """Lista de consultas com filtros"""
        try:
            if request.user_tipo != 'medico':
                return jsonify({'error': 'Acesso restrito a médicos'}), 403
            
            medico = execute_query("""
                SELECT id FROM medicos WHERE usuario_id = %s
            """, (request.user_id,), fetch=True, one=True)
            
            if not medico:
                return jsonify({'error': 'Médico não encontrado'}), 404
            
            medico_id = medico[0]
            
            # Filtros
            status = request.args.get('status', '')
            data = request.args.get('data', '')
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 20))
            offset = (page - 1) * limit
            
            query = """
                SELECT 
                    c.id,
                    u.nome as paciente_nome,
                    c.data_hora,
                    c.status,
                    p.telefone,
                    (SELECT COUNT(*) FROM pedidos_analise WHERE consulta_id = c.id) as total_pedidos
                FROM consultas c
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE c.medico_id = %s
            """
            params = [medico_id]
            
            if status:
                query += " AND c.status = %s"
                params.append(status)
            
            if data:
                query += " AND DATE(c.data_hora) = %s"
                params.append(data)
            
            # Contar total para paginação
            count_query = f"SELECT COUNT(*) FROM ({query}) as total"
            total = execute_query(count_query, params, fetch=True, one=True)
            
            query += " ORDER BY c.data_hora DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            
            consultas = execute_query(query, params, fetch=True) or []
            
            return jsonify({
                'success': True,
                'consultas': [
                    {
                        'id': c[0],
                        'paciente_nome': c[1],
                        'data_hora': c[2].strftime('%d/%m/%Y %H:%M') if c[2] else '',
                        'status': c[3],
                        'telefone': c[4],
                        'total_pedidos': c[5]
                    } for c in consultas
                ],
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total[0] if total else 0,
                    'pages': (total[0] + limit - 1) // limit if total else 0
                }
            })
            
        except Exception as e:
            logger.error(f"Erro ao listar consultas mobile: {e}")
            return jsonify({'error': str(e)}), 500
    
    @mobile_api_bp.route('/pacientes', methods=['GET'])
    @token_required
    def mobile_pacientes():
        """Lista de pacientes do médico"""
        try:
            if request.user_tipo != 'medico':
                return jsonify({'error': 'Acesso restrito a médicos'}), 403
            
            medico = execute_query("""
                SELECT id FROM medicos WHERE usuario_id = %s
            """, (request.user_id,), fetch=True, one=True)
            
            if not medico:
                return jsonify({'error': 'Médico não encontrado'}), 404
            
            medico_id = medico[0]
            
            # Buscar pacientes com última consulta
            pacientes = execute_query("""
                SELECT 
                    p.id,
                    u.nome,
                    p.telefone,
                    MAX(c.data_hora) as ultima_consulta,
                    COUNT(c.id) as total_consultas
                FROM pacientes p
                JOIN usuarios u ON p.usuario_id = u.id
                JOIN consultas c ON c.paciente_id = p.id
                WHERE c.medico_id = %s
                GROUP BY p.id, u.nome, p.telefone
                ORDER BY ultima_consulta DESC
            """, (medico_id,), fetch=True) or []
            
            return jsonify({
                'success': True,
                'pacientes': [
                    {
                        'id': p[0],
                        'nome': p[1],
                        'telefone': p[2],
                        'ultima_consulta': p[3].strftime('%d/%m/%Y') if p[3] else '',
                        'total_consultas': p[4]
                    } for p in pacientes
                ]
            })
            
        except Exception as e:
            logger.error(f"Erro ao listar pacientes mobile: {e}")
            return jsonify({'error': str(e)}), 500
    
    @mobile_api_bp.route('/logout', methods=['POST'])
    @token_required
    def mobile_logout():
        """Invalidar token"""
        try:
            token = request.headers.get('Authorization').replace('Bearer ', '')
            
            execute_query("""
                DELETE FROM tokens WHERE token = %s
            """, (token,))
            
            return jsonify({'success': True, 'message': 'Logout realizado'})
            
        except Exception as e:
            logger.error(f"Erro no logout mobile: {e}")
            return jsonify({'error': str(e)}), 500
    
    return mobile_api_bp