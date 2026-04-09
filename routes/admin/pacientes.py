# routes/admin/pacientes.py
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash
import logging
import traceback
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

def init_pacientes_routes(admin_bp, mysql):
    """Rotas para gerenciamento de pacientes"""
    
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
            logger.error(traceback.format_exc())
            return None
    
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
    
    # ==================== LISTAR PACIENTES ====================
    @admin_bp.route('/pacientes')
    @admin_required
    def pacientes():
        """Lista todos os pacientes com as colunas corretas"""
        try:
            pacientes = execute_query("""
                SELECT 
                    u.id,                          -- [0] ID do usuário
                    u.nome,                        -- [1] Nome
                    u.email,                       -- [2] Email
                    u.ativo,                       -- [3] Status
                    p.telefone,                     -- [4] Telefone
                    p.data_nascimento,               -- [5] Data nascimento
                    u.criado_em,                     -- [6] Data cadastro
                    p.genero,                        -- [7] Gênero
                    p.endereco,                      -- [8] Endereço
                    p.alergias,                      -- [9] Alergias
                    p.medicamentos_uso,               -- [10] Medicamentos
                    p.historico_doencas,              -- [11] Histórico
                    p.contato_emergencia              -- [12] Contato emergência
                FROM usuarios u
                JOIN pacientes p ON u.id = p.usuario_id
                WHERE u.tipo = 'paciente'
                ORDER BY u.criado_em DESC
            """, fetch=True) or []
            
            logger.info(f"Total de pacientes encontrados: {len(pacientes)}")
            
            return render_template('admin/pacientes.html', pacientes=pacientes, user=session)
        except Exception as e:
            logger.error(f"Erro ao listar pacientes: {e}")
            logger.error(traceback.format_exc())
            flash('Erro ao carregar lista de pacientes.', 'danger')
            return render_template('admin/pacientes.html', pacientes=[], user=session)
    
    # ==================== CADASTRAR PACIENTE ====================
    @admin_bp.route('/pacientes/cadastrar', methods=['GET', 'POST'])
    @admin_required
    def cadastrar_paciente():
        """Cadastra um novo paciente"""
        if request.method == 'POST':
            nome = request.form.get('nome', '').strip()
            email = request.form.get('email', '').strip().lower()
            senha = request.form.get('senha', '').strip()
            telefone = request.form.get('telefone', '').strip()
            data_nascimento = request.form.get('data_nascimento', '').strip()
            genero = request.form.get('genero', '').strip()
            endereco = request.form.get('endereco', '').strip()
            alergias = request.form.get('alergias', '').strip()
            medicamentos_uso = request.form.get('medicamentos_uso', '').strip()
            historico_doencas = request.form.get('historico_doencas', '').strip()
            contato_emergencia = request.form.get('contato_emergencia', '').strip()
            
            if not all([nome, email, senha, data_nascimento]):
                flash('Nome, email, senha e data de nascimento são obrigatórios.', 'danger')
                return redirect(url_for('admin.cadastrar_paciente'))
            
            if len(senha) < 6:
                flash('A senha deve ter pelo menos 6 caracteres.', 'danger')
                return redirect(url_for('admin.cadastrar_paciente'))
            
            # Verificar se email já existe
            existing = execute_query(
                "SELECT id FROM usuarios WHERE email = %s",
                (email,), fetch=True, one=True
            )
            
            if existing:
                flash('Email já cadastrado.', 'danger')
                return redirect(url_for('admin.cadastrar_paciente'))
            
            try:
                user_uuid = str(uuid.uuid4())
                senha_hash = generate_password_hash(senha)
                
                # Inserir usuário
                execute_query("""
                    INSERT INTO usuarios (uuid, nome, email, senha, tipo, ativo, criado_em)
                    VALUES (%s, %s, %s, %s, 'paciente', 1, NOW())
                """, (user_uuid, nome, email, senha_hash))
                
                # Pegar ID do usuário inserido
                user = execute_query(
                    "SELECT id FROM usuarios WHERE email = %s",
                    (email,), fetch=True, one=True
                )
                
                if user:
                    # Inserir paciente com todas as colunas
                    execute_query("""
                        INSERT INTO pacientes (
                            usuario_id, 
                            data_nascimento, 
                            endereco, 
                            genero, 
                            telefone, 
                            alergias, 
                            medicamentos_uso, 
                            historico_doencas, 
                            contato_emergencia
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        user[0], 
                        data_nascimento, 
                        endereco, 
                        genero, 
                        telefone, 
                        alergias, 
                        medicamentos_uso, 
                        historico_doencas, 
                        contato_emergencia
                    ))
                    
                    flash('Paciente cadastrado com sucesso!', 'success')
                    return redirect(url_for('admin.pacientes'))
                else:
                    flash('Erro ao cadastrar paciente.', 'danger')
                    
            except Exception as e:
                logger.error(f"Erro ao cadastrar paciente: {e}")
                flash(f'Erro ao cadastrar paciente: {str(e)}', 'danger')
        
        return render_template('admin/cadastrar_paciente.html', user=session)
    
    # ==================== EDITAR PACIENTE ====================
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
            endereco = request.form.get('endereco', '').strip()
            alergias = request.form.get('alergias', '').strip()
            medicamentos_uso = request.form.get('medicamentos_uso', '').strip()
            historico_doencas = request.form.get('historico_doencas', '').strip()
            contato_emergencia = request.form.get('contato_emergencia', '').strip()
            ativo = 1 if request.form.get('ativo') else 0
            nova_senha = request.form.get('nova_senha', '').strip()
            
            if not all([nome, email, data_nascimento]):
                flash('Nome, email e data de nascimento são obrigatórios.', 'danger')
                return redirect(url_for('admin.editar_paciente', paciente_id=paciente_id))
            
            try:
                if nova_senha:
                    if len(nova_senha) < 6:
                        flash('A nova senha deve ter pelo menos 6 caracteres.', 'danger')
                        return redirect(url_for('admin.editar_paciente', paciente_id=paciente_id))
                    
                    senha_hash = generate_password_hash(nova_senha)
                    execute_query("""
                        UPDATE usuarios 
                        SET nome = %s, email = %s, senha = %s, ativo = %s
                        WHERE id = %s AND tipo = 'paciente'
                    """, (nome, email, senha_hash, ativo, paciente_id))
                else:
                    execute_query("""
                        UPDATE usuarios 
                        SET nome = %s, email = %s, ativo = %s
                        WHERE id = %s AND tipo = 'paciente'
                    """, (nome, email, ativo, paciente_id))
                
                # Atualizar todas as colunas da tabela pacientes
                execute_query("""
                    UPDATE pacientes 
                    SET data_nascimento = %s, 
                        endereco = %s, 
                        genero = %s, 
                        telefone = %s,
                        alergias = %s,
                        medicamentos_uso = %s,
                        historico_doencas = %s,
                        contato_emergencia = %s
                    WHERE usuario_id = %s
                """, (
                    data_nascimento, 
                    endereco, 
                    genero, 
                    telefone,
                    alergias,
                    medicamentos_uso,
                    historico_doencas,
                    contato_emergencia,
                    paciente_id
                ))
                
                flash('Paciente atualizado com sucesso!', 'success')
                return redirect(url_for('admin.pacientes'))
                
            except Exception as e:
                logger.error(f"Erro ao atualizar paciente: {e}")
                flash(f'Erro ao atualizar paciente: {str(e)}', 'danger')
        
        # Buscar dados do paciente
        paciente = execute_query("""
            SELECT 
                u.id, u.nome, u.email, u.ativo, u.criado_em,
                p.data_nascimento, p.endereco, p.genero, p.telefone,
                p.alergias, p.medicamentos_uso, p.historico_doencas, p.contato_emergencia
            FROM usuarios u
            JOIN pacientes p ON u.id = p.usuario_id
            WHERE u.id = %s AND u.tipo = 'paciente'
        """, (paciente_id,), fetch=True, one=True)
        
        if not paciente:
            flash('Paciente não encontrado.', 'danger')
            return redirect(url_for('admin.pacientes'))
        
        return render_template('admin/editar_paciente.html', paciente=paciente, user=session)
    
    # ==================== VISUALIZAR PACIENTE ====================
    @admin_bp.route('/pacientes/<int:paciente_id>/visualizar')
    @admin_required
    def visualizar_paciente(paciente_id):
        """Retorna dados do paciente em JSON"""
        try:
            paciente = execute_query("""
                SELECT 
                    u.nome, u.email, u.ativo,
                    p.data_nascimento, p.endereco, p.genero, p.telefone,
                    p.alergias, p.medicamentos_uso, p.historico_doencas, p.contato_emergencia,
                    u.criado_em,
                    (SELECT COUNT(*) FROM consultas WHERE paciente_id = p.id) as total_consultas
                FROM usuarios u
                JOIN pacientes p ON u.id = p.usuario_id
                WHERE u.id = %s AND u.tipo = 'paciente'
            """, (paciente_id,), fetch=True, one=True)
            
            if not paciente:
                return jsonify({'error': 'Paciente não encontrado'}), 404
            
            # Calcular idade
            idade = None
            if paciente[3]:  # data_nascimento
                hoje = datetime.now().date()
                nascimento = paciente[3]
                idade = hoje.year - nascimento.year
                if (hoje.month, hoje.day) < (nascimento.month, nascimento.day):
                    idade -= 1
            
            return jsonify({
                'nome': paciente[0],
                'email': paciente[1],
                'ativo': bool(paciente[2]),
                'data_nascimento': paciente[3].strftime('%d/%m/%Y') if paciente[3] else '',
                'idade': idade,
                'endereco': paciente[4] or 'Não informado',
                'genero': paciente[5] or 'Não informado',
                'telefone': paciente[6] or 'Não informado',
                'alergias': paciente[7] or 'Não informado',
                'medicamentos_uso': paciente[8] or 'Não informado',
                'historico_doencas': paciente[9] or 'Não informado',
                'contato_emergencia': paciente[10] or 'Não informado',
                'criado_em': paciente[11].strftime('%d/%m/%Y %H:%M') if paciente[11] else '',
                'total_consultas': paciente[12] or 0
            })
            
        except Exception as e:
            logger.error(f"Erro ao visualizar paciente: {e}")
            return jsonify({'error': 'Erro ao carregar dados'}), 500
    
    # ==================== EXCLUIR PACIENTE ====================
    @admin_bp.route('/pacientes/<int:paciente_id>/excluir', methods=['POST'])
    @admin_required
    def excluir_paciente(paciente_id):
        """Exclui um paciente"""
        try:
            # Verificar se tem consultas
            consultas = execute_query(
                "SELECT COUNT(*) FROM consultas WHERE paciente_id = %s",
                (paciente_id,), fetch=True, one=True
            )
            
            if consultas and consultas[0] > 0:
                # Soft delete - apenas desativa
                execute_query(
                    "UPDATE usuarios SET ativo = 0 WHERE id = %s",
                    (paciente_id,)
                )
                return jsonify({
                    'success': True,
                    'message': 'Paciente desativado pois possui consultas vinculadas.'
                })
            else:
                # Hard delete - remove completamente
                execute_query(
                    "DELETE FROM pacientes WHERE usuario_id = %s",
                    (paciente_id,)
                )
                execute_query(
                    "DELETE FROM usuarios WHERE id = %s AND tipo = 'paciente'",
                    (paciente_id,)
                )
                return jsonify({
                    'success': True,
                    'message': 'Paciente excluído com sucesso!'
                })
                
        except Exception as e:
            logger.error(f"Erro ao excluir paciente: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    return admin_bp