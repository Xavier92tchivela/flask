# routes/admin/pacientes.py
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def init_pacientes_routes(admin_bp, mysql):
    """Rotas para gerenciamento de pacientes"""
    
    # ---------- FUNÇÃO AUXILIAR DE QUERY ----------
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
    
    # ---------- DECORATOR DE AUTENTICAÇÃO ----------
    def admin_required(f):
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Por favor, faça login para acessar o painel administrativo.', 'warning')
                return redirect(url_for('admin.login'))
            
            if session.get('user_type') != 'admin':
                flash('Acesso restrito a administradores.', 'danger')
                return redirect(url_for('admin.login'))
            
            return f(*args, **kwargs)
        return decorated_function
    
    # ---------- LISTAR PACIENTES ----------
    @admin_bp.route('/pacientes')
    @admin_required
    def pacientes():
        """Lista todos os pacientes"""
        try:
            pacientes = execute_query("""
                SELECT 
                    u.id, 
                    u.nome, 
                    u.email, 
                    u.ativo, 
                    p.telefone, 
                    p.data_nascimento,
                    p.genero,
                    u.criado_em,
                    (SELECT COUNT(*) FROM consultas WHERE paciente_id = p.id) as total_consultas
                FROM usuarios u
                JOIN pacientes p ON u.id = p.usuario_id
                WHERE u.tipo = 'paciente'
                ORDER BY u.criado_em DESC
            """, fetch=True) or []
            
            return render_template('admin/pacientes.html', pacientes=pacientes, user=session)
        except Exception as e:
            logger.error(f"Erro ao listar pacientes: {e}")
            flash('Erro ao carregar lista de pacientes.', 'danger')
            return render_template('admin/pacientes.html', pacientes=[], user=session)
    
    # ---------- EDITAR PACIENTE ----------
    @admin_bp.route('/pacientes/<int:paciente_id>/editar', methods=['GET', 'POST'])
    @admin_required
    def editar_paciente(paciente_id):
        """Edita um paciente existente"""
        if request.method == 'POST':
            nome = request.form.get('nome', '').strip()
            email = request.form.get('email', '').strip().lower()
            telefone = request.form.get('telefone', '').strip()
            data_nascimento = request.form.get('data_nascimento', '').strip()
            genero = request.form.get('genero', '').strip()
            ativo = 1 if request.form.get('ativo') else 0
            
            if not all([nome, email]):
                flash('Nome e email são obrigatórios.', 'danger')
                return redirect(url_for('admin.editar_paciente', paciente_id=paciente_id))
            
            try:
                execute_query("""
                    UPDATE usuarios 
                    SET nome = %s, email = %s, ativo = %s
                    WHERE id = %s AND tipo = 'paciente'
                """, (nome, email, ativo, paciente_id))
                
                execute_query("""
                    UPDATE pacientes 
                    SET telefone = %s, data_nascimento = %s, genero = %s
                    WHERE usuario_id = %s
                """, (telefone, data_nascimento, genero, paciente_id))
                
                logger.info(f"Paciente atualizado: ID {paciente_id}")
                flash('Paciente atualizado com sucesso!', 'success')
                return redirect(url_for('admin.pacientes'))
                
            except Exception as e:
                logger.error(f"Erro ao atualizar paciente: {e}")
                flash('Erro ao atualizar paciente.', 'danger')
                return redirect(url_for('admin.editar_paciente', paciente_id=paciente_id))
        
        paciente = execute_query("""
            SELECT u.id, u.nome, u.email, u.ativo, p.telefone, p.data_nascimento, p.genero
            FROM usuarios u
            JOIN pacientes p ON u.id = p.usuario_id
            WHERE u.id = %s AND u.tipo = 'paciente'
        """, (paciente_id,), fetch=True, one=True)
        
        if not paciente:
            flash('Paciente não encontrado.', 'danger')
            return redirect(url_for('admin.pacientes'))
        
        return render_template('admin/editar_paciente.html', paciente=paciente, user=session)
    
    # ---------- VISUALIZAR PACIENTE (API) ----------
    @admin_bp.route('/pacientes/<int:paciente_id>/visualizar')
    @admin_required
    def visualizar_paciente(paciente_id):
        """Visualiza detalhes de um paciente (API)"""
        try:
            paciente = execute_query("""
                SELECT 
                    u.id, u.nome, u.email, u.ativo, u.criado_em,
                    p.telefone, p.data_nascimento, p.genero,
                    (SELECT COUNT(*) FROM consultas WHERE paciente_id = p.id) as total_consultas,
                    (SELECT COUNT(*) FROM consultas WHERE paciente_id = p.id AND status = 'realizada') as consultas_realizadas
                FROM usuarios u
                JOIN pacientes p ON u.id = p.usuario_id
                WHERE u.id = %s AND u.tipo = 'paciente'
            """, (paciente_id,), fetch=True, one=True)
            
            if not paciente:
                return jsonify({'error': 'Paciente não encontrado'}), 404
            
            idade = None
            if paciente[6]:
                hoje = datetime.now().date()
                nascimento = paciente[6]
                idade = hoje.year - nascimento.year - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))
            
            consultas = execute_query("""
                SELECT 
                    c.id,
                    CONCAT('Dr. ', m_u.nome) as medico,
                    c.data_hora,
                    c.status
                FROM consultas c
                JOIN medicos m ON c.medico_id = m.id
                JOIN usuarios m_u ON m.usuario_id = m_u.id
                WHERE c.paciente_id = %s
                ORDER BY c.data_hora DESC
                LIMIT 5
            """, (paciente_id,), fetch=True) or []
            
            return jsonify({
                'id': paciente[0],
                'nome': paciente[1],
                'email': paciente[2],
                'ativo': paciente[3],
                'criado_em': paciente[4].strftime('%d/%m/%Y') if paciente[4] else '',
                'telefone': paciente[5] or 'Não informado',
                'data_nascimento': paciente[6].strftime('%d/%m/%Y') if paciente[6] else '',
                'idade': idade,
                'genero': paciente[7] or 'Não informado',
                'total_consultas': paciente[8] or 0,
                'consultas_realizadas': paciente[9] or 0,
                'ultimas_consultas': [
                    {
                        'id': c[0],
                        'medico': c[1],
                        'data': c[2].strftime('%d/%m/%Y %H:%M') if c[2] else '',
                        'status': c[3]
                    } for c in consultas
                ]
            })
            
        except Exception as e:
            logger.error(f"Erro ao visualizar paciente: {e}")
            return jsonify({'error': 'Erro ao carregar dados'}), 500