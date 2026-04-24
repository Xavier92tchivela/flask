from flask import Blueprint, render_template, session, redirect, url_for, flash, jsonify
from datetime import datetime
import logging

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
    
    def formatar_data(data, formato='%d/%m/%Y %H:%M'):
        if not data:
            return ''
        if isinstance(data, datetime):
            return data.strftime(formato)
        return str(data)
    
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
                    'especialidade': garantir_string(resultado[2]) if resultado[2] else 'Clínico Geral',
                    'crm': garantir_string(resultado[3]) if resultado[3] else 'CRM não informado'
                }
            return None
        except Exception as e:
            logger.error(f"Erro ao obter info medico: {e}")
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
                        'agendada': 'warning',
                        'realizada': 'success',
                        'cancelada': 'danger'
                    }.get(c[3], 'secondary')
                })
            
            # Contagens
            cur.execute("SELECT COUNT(*) FROM consultas WHERE medico_id = %s AND DATE(data_hora) = CURDATE()", (medico_id,))
            consultas_hoje = cur.fetchone()[0] if cur.fetchone() else 0
            
            cur.execute("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status = 'concluido' AND status_aprovacao = 'pendente'
            """, (medico_id,))
            resultados_pendentes = cur.fetchone()[0] if cur.fetchone() else 0
            
            cur.execute("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status IN ('pendente', 'em_analise')
            """, (medico_id,))
            analises_solicitadas = cur.fetchone()[0] if cur.fetchone() else 0
            
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
    
    # ===== PERFIL =====
    @medico_bp.route('/perfil')
    @medico_required
    def perfil():
        try:
            medico_info = obter_info_medico()
            return render_template('medico/perfil.html', medico=medico_info, user=session)
        except Exception as e:
            logger.error(f"Erro no perfil: {e}")
            flash('Erro ao carregar perfil.', 'danger')
            return redirect(url_for('medico.dashboard'))
    
    # ===== PEDIDOS DE ANÁLISE =====
    @medico_bp.route('/pedidos_analise')
    @medico_required
    def pedidos_analise():
        try:
            medico_id = obter_medico_id()
            if not medico_id:
                flash('Perfil de médico não encontrado.', 'danger')
                return redirect(url_for('auth.logout'))
            
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
            
            return render_template('medico/pedidos_analise.html', pedidos=pedidos, user=session)
        except Exception as e:
            logger.error(f"Erro em pedidos_analise: {e}")
            flash('Erro ao carregar pedidos.', 'danger')
            return redirect(url_for('medico.dashboard'))
    
    # ===== MEUS PACIENTES =====
    @medico_bp.route('/meus_pacientes')
    @medico_required
    def meus_pacientes():
        try:
            medico_id = obter_medico_id()
            if not medico_id:
                flash('Perfil de médico não encontrado.', 'danger')
                return redirect(url_for('auth.logout'))
            
            cur = mysql.connection.cursor()
            cur.execute("""
                SELECT DISTINCT p.id, u.nome, u.email, COALESCE(p.telefone, '') as telefone
                FROM pacientes p
                JOIN usuarios u ON p.usuario_id = u.id
                JOIN consultas c ON c.paciente_id = p.id
                WHERE c.medico_id = %s
                ORDER BY u.nome
            """, (medico_id,))
            pacientes_raw = cur.fetchall()
            cur.close()
            
            pacientes = []
            for p in pacientes_raw:
                pacientes.append({
                    'id': p[0],
                    'nome': garantir_string(p[1]),
                    'email': garantir_string(p[2]),
                    'telefone': garantir_string(p[3]) if p[3] else ''
                })
            
            return render_template('medico/pacientes.html', pacientes=pacientes, user=session)
        except Exception as e:
            logger.error(f"Erro em meus_pacientes: {e}")
            flash('Erro ao carregar pacientes.', 'danger')
            return redirect(url_for('medico.dashboard'))
    
    # ===== API: CONTADORES =====
    @medico_bp.route('/api/contadores')
    @medico_required
    def api_contadores():
        try:
            medico_id = obter_medico_id()
            if not medico_id:
                return jsonify({'error': 'Médico não encontrado'}), 404
            
            cur = mysql.connection.cursor()
            cur.execute("SELECT COUNT(*) FROM consultas WHERE medico_id = %s AND DATE(data_hora) = CURDATE()", (medico_id,))
            consultas_hoje = cur.fetchone()[0] if cur.fetchone() else 0
            
            cur.execute("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status = 'concluido' AND status_aprovacao = 'pendente'
            """, (medico_id,))
            resultados_pendentes = cur.fetchone()[0] if cur.fetchone() else 0
            
            cur.execute("""
                SELECT COUNT(*) FROM pedidos_analise 
                WHERE medico_id = %s AND status IN ('pendente', 'em_analise')
            """, (medico_id,))
            analises_solicitadas = cur.fetchone()[0] if cur.fetchone() else 0
            
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
    
    # ===== API: PEDIDOS RECENTES =====
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
    
    # ===== API: NOTIFICAÇÕES =====
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
    
    # ===== REVISAR ANÁLISE =====
    @medico_bp.route('/revisar-analise/<int:pedido_id>')
    @medico_required
    def revisar_analise(pedido_id):
        try:
            return render_template('medico/revisar_analise.html', pedido_id=pedido_id, user=session)
        except Exception as e:
            logger.error(f"Erro em revisar_analise: {e}")
            flash('Erro ao carregar análise.', 'danger')
            return redirect(url_for('medico.pedidos_analise'))
    
    # ===== RECEITAS =====
    @medico_bp.route('/receitas')
    @medico_required
    def receitas():
        try:
            medico_id = obter_medico_id()
            if not medico_id:
                flash('Perfil de médico não encontrado.', 'danger')
                return redirect(url_for('auth.logout'))
            
            cur = mysql.connection.cursor()
            cur.execute("""
                SELECT r.id, r.diagnostico, r.prescricao, r.created_at, c.data_hora, u.nome as paciente_nome
                FROM receita r
                JOIN consultas c ON r.consulta_id = c.id
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE c.medico_id = %s
                ORDER BY r.created_at DESC
            """, (medico_id,))
            receitas_raw = cur.fetchall()
            cur.close()
            
            receitas_lista = []
            for r in receitas_raw:
                receitas_lista.append({
                    'id': r[0],
                    'diagnostico': garantir_string(r[1]) if r[1] else '',
                    'prescricao': garantir_string(r[2]) if r[2] else '',
                    'created_at': formatar_data(r[3]),
                    'data_consulta': formatar_data(r[4]),
                    'paciente_nome': garantir_string(r[5])
                })
            
            return render_template('medico/receitas.html', receitas=receitas_lista, user=session)
        except Exception as e:
            logger.error(f"Erro em receitas: {e}")
            flash('Erro ao carregar receitas.', 'danger')
            return redirect(url_for('medico.dashboard'))
    
    # ===== RECEITA DIGITAL =====
    @medico_bp.route('/receita-digital')
    @medico_required
    def receita_digital():
        try:
            return render_template('medico/receita_digital.html', user=session)
        except Exception as e:
            logger.error(f"Erro em receita_digital: {e}")
            flash('Erro ao carregar receita digital.', 'danger')
            return redirect(url_for('medico.dashboard'))
    
    # ===== INTERNADOS =====
    @medico_bp.route('/internados')
    @medico_required
    def internados():
        try:
            return render_template('medico/internados.html', user=session)
        except Exception as e:
            logger.error(f"Erro em internados: {e}")
            flash('Erro ao carregar internações.', 'danger')
            return redirect(url_for('medico.dashboard'))
    
    # ===== DEBUG: ROTAS =====
    @medico_bp.route('/debug-rotas')
    def debug_rotas():
        output = "<h1>Rotas do Médico</h1><ul>"
        for rule in app.url_map.iter_rules():
            if str(rule).startswith('/medico'):
                output += f"<li>{rule}</li>"
        output += "</ul><a href='/medico/dashboard'>Voltar ao Dashboard</a>"
        return output
    
    logger.info("✅ Blueprint médico inicializado com sucesso!")
    return medico_bp
