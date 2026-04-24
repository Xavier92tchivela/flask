# routes/medico/__init__.py
from flask import Blueprint, render_template, session, redirect, url_for, flash
from datetime import datetime
import logging
import traceback

logger = logging.getLogger(__name__)

def init_medico(mysql, app, client, gemini_available, MODEL_NAME, receita_service):
    """Inicializa o blueprint do médico"""
    
    medico_bp = Blueprint('medico', __name__, url_prefix='/medico')
    
    # ===== FUNÇÕES AUXILIARES =====
    def garantir_string(valor):
        if valor is None:
            return ''
        if isinstance(valor, bytes):
            try:
                return valor.decode('utf-8')
            except:
                return str(valor)
        return str(valor)
    
    def obter_medico_id():
        if 'medico_id' in session:
            return session['medico_id']
        if 'user_id' not in session:
            return None
        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT id FROM medicos WHERE usuario_id = %s", (session['user_id'],))
            resultado = cur.fetchone()
            cur.close()
            if resultado:
                medico_id = resultado[0] if isinstance(resultado, (list, tuple)) else resultado.get('id')
                session['medico_id'] = medico_id
                return medico_id
            return None
        except Exception as e:
            logger.error(f"Erro ao obter medico_id: {e}")
            return None
    
    def medico_required(f):
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Faça login para acessar.', 'warning')
                return redirect(url_for('auth.login'))
            if session.get('user_type') != 'medico':
                flash('Acesso restrito a médicos.', 'danger')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated_function
    
    def obter_info_medico():
        medico_id = obter_medico_id()
        if not medico_id:
            return None
        try:
            cur = mysql.connection.cursor()
            cur.execute("""
                SELECT m.id, u.nome, m.especialidade, m.crm
                FROM medicos m
                JOIN usuarios u ON m.usuario_id = u.id
                WHERE m.id = %s
            """, (medico_id,))
            resultado = cur.fetchone()
            cur.close()
            if resultado:
                return {
                    'id': resultado[0],
                    'nome': garantir_string(resultado[1]),
                    'especialidade': garantir_string(resultado[2]),
                    'crm': garantir_string(resultado[3])
                }
            return None
        except Exception as e:
            logger.error(f"Erro ao obter info medico: {e}")
            return None
    
    def execute_query(query, params=None, fetch=False, one=False):
        try:
            cur = mysql.connection.cursor()
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            
            if fetch:
                result = cur.fetchall()
                if one and result:
                    result = result[0]
            else:
                mysql.connection.commit()
                result = None
            
            cur.close()
            return result
        except Exception as e:
            mysql.connection.rollback()
            logger.error(f"Database error: {e}")
            return None
    
    def formatar_data(data, formato='%d/%m/%Y %H:%M'):
        if not data:
            return ''
        if isinstance(data, datetime):
            return data.strftime(formato)
        return str(data)
    
    # ===== DASHBOARD =====
    @medico_bp.route('/dashboard')
    @medico_required
    def dashboard():
        try:
            medico_id = obter_medico_id()
            if not medico_id:
                flash('Perfil de médico não encontrado.', 'danger')
                return redirect(url_for('auth.logout'))
            
            cur = mysql.connection.cursor()
            
            # Buscar consultas recentes
            cur.execute("""
                SELECT c.id, u.nome as paciente_nome, c.data_hora, c.status
                FROM consultas c
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE c.medico_id = %s
                ORDER BY c.data_hora DESC
                LIMIT 10
            """, (medico_id,))
            consultas_raw = cur.fetchall()
            
            consultas = []
            for c in consultas_raw:
                consultas.append({
                    'id': c[0],
                    'paciente_nome': garantir_string(c[1]),
                    'data_hora': formatar_data(c[2]),
                    'status': c[3] or 'agendada',
                    'status_class': {
                        'agendada': 'primary',
                        'realizada': 'success',
                        'cancelada': 'danger'
                    }.get(c[3], 'secondary')
                })
            
            # Contagens
            cur.execute("SELECT COUNT(*) FROM consultas WHERE medico_id = %s AND DATE(data_hora) = CURDATE()", (medico_id,))
            consultas_hoje = cur.fetchone()[0] or 0
            
            cur.execute("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status = 'concluido' AND status_aprovacao = 'pendente'
            """, (medico_id,))
            resultados_pendentes = cur.fetchone()[0] or 0
            
            cur.execute("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status IN ('pendente', 'em_analise')
            """, (medico_id,))
            analises_solicitadas = cur.fetchone()[0] or 0
            
            cur.close()
            
            return render_template('medico/dashboard.html',
                                 consultas=consultas,
                                 consultasHoje=consultas_hoje,
                                 contadorResultados=resultados_pendentes,
                                 contadorAnalises=analises_solicitadas,
                                 contadorPedidos=analises_solicitadas + resultados_pendentes,
                                 user=session)
        except Exception as e:
            logger.error(f"Erro no dashboard médico: {e}")
            flash('Erro ao carregar dashboard.', 'danger')
            return redirect(url_for('medico.consultas'))
    
    # ===== CONSULTAS =====
    @medico_bp.route('/consultas')
    @medico_required
    def consultas():
        try:
            medico_id = obter_medico_id()
            if not medico_id:
                flash('Perfil de médico não encontrado.', 'danger')
                return redirect(url_for('auth.logout'))
            
            cur = mysql.connection.cursor()
            cur.execute("""
                SELECT c.id, u.nome as paciente_nome, c.data_hora, c.status
                FROM consultas c
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE c.medico_id = %s
                ORDER BY c.data_hora DESC
            """, (medico_id,))
            consultas_raw = cur.fetchall()
            cur.close()
            
            consultas = []
            for c in consultas_raw:
                consultas.append({
                    'id': c[0],
                    'paciente_nome': garantir_string(c[1]),
                    'data_hora': formatar_data(c[2]),
                    'status': c[3] or 'agendada'
                })
            
            return render_template('medico/consultas.html', consultas=consultas, user=session)
        except Exception as e:
            logger.error(f"Erro em consultas: {e}")
            flash('Erro ao carregar consultas.', 'danger')
            return redirect(url_for('medico.dashboard'))
    
    # ===== API PARA CONTADORES =====
    @medico_bp.route('/api/contadores')
    @medico_required
    def api_contadores():
        try:
            medico_id = obter_medico_id()
            if not medico_id:
                return jsonify({'error': 'Médico não encontrado'}), 404
            
            cur = mysql.connection.cursor()
            cur.execute("SELECT COUNT(*) FROM consultas WHERE medico_id = %s AND DATE(data_hora) = CURDATE()", (medico_id,))
            consultas_hoje = cur.fetchone()[0] or 0
            
            cur.execute("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status = 'concluido' AND status_aprovacao = 'pendente'
            """, (medico_id,))
            resultados_pendentes = cur.fetchone()[0] or 0
            
            cur.execute("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status IN ('pendente', 'em_analise')
            """, (medico_id,))
            analises_solicitadas = cur.fetchone()[0] or 0
            
            cur.close()
            
            return jsonify({
                'consultas_hoje': consultas_hoje,
                'resultados_pendentes': resultados_pendentes,
                'analises_solicitadas': analises_solicitadas,
                'notificacoes': resultados_pendentes
            })
        except Exception as e:
            logger.error(f"Erro na API contadores: {e}")
            return jsonify({'error': str(e)}), 500
    
    # ===== API PARA PEDIDOS RECENTES =====
    @medico_bp.route('/api/pedidos-recentes')
    @medico_required
    def api_pedidos_recentes():
        try:
            medico_id = obter_medico_id()
            if not medico_id:
                return jsonify({'pedidos': []})
            
            cur = mysql.connection.cursor()
            cur.execute("""
                SELECT pa.id, pa.tipo_exame, pa.status, pa.status_aprovacao,
                       DATE_FORMAT(pa.data_solicitacao, '%d/%m/%Y %H:%i') as data_solicitacao,
                       u.nome as paciente_nome
                FROM pedidos_analise pa
                JOIN pacientes p ON pa.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE pa.medico_id = %s
                ORDER BY pa.data_solicitacao DESC
                LIMIT 5
            """, (medico_id,))
            pedidos_raw = cur.fetchall()
            cur.close()
            
            pedidos = []
            for p in pedidos_raw:
                pedidos.append({
                    'id': p[0],
                    'tipo_exame': garantir_string(p[1]),
                    'status': p[2],
                    'status_aprovacao': p[3],
                    'data_solicitacao': p[4],
                    'paciente_nome': garantir_string(p[5])
                })
            
            return jsonify({'pedidos': pedidos})
        except Exception as e:
            logger.error(f"Erro na API pedidos recentes: {e}")
            return jsonify({'pedidos': []})
    
    # ===== API PARA NOTIFICAÇÕES =====
    @medico_bp.route('/api/notificacoes')
    @medico_required
    def api_notificacoes():
        try:
            medico_id = obter_medico_id()
            if not medico_id:
                return jsonify({'notificacoes': []})
            
            cur = mysql.connection.cursor()
            cur.execute("""
                SELECT pa.id, pa.tipo_exame, u.nome as paciente_nome,
                       DATE_FORMAT(pa.data_conclusao, '%d/%m/%Y %H:%i') as data_conclusao,
                       TIMESTAMPDIFF(HOUR, pa.data_conclusao, NOW()) as horas_atras
                FROM pedidos_analise pa
                JOIN pacientes p ON pa.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE pa.medico_id = %s 
                  AND pa.status = 'concluido' 
                  AND pa.status_aprovacao = 'pendente'
                  AND pa.data_conclusao >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                ORDER BY pa.data_conclusao DESC
                LIMIT 5
            """, (medico_id,))
            notificacoes_raw = cur.fetchall()
            cur.close()
            
            notificacoes = []
            for n in notificacoes_raw:
                tempo = f"há {n[4]} horas" if n[4] < 24 else f"há {n[4]//24} dias"
                notificacoes.append({
                    'id': n[0],
                    'titulo': f"Resultado: {garantir_string(n[1])}",
                    'mensagem': f"{garantir_string(n[2])} - Aguardando revisão",
                    'tempo': tempo,
                    'link': f"/medico/revisar-analise/{n[0]}"
                })
            
            return jsonify({'notificacoes': notificacoes})
        except Exception as e:
            logger.error(f"Erro na API notificacoes: {e}")
            return jsonify({'notificacoes': []})
    
    return medico_bp
