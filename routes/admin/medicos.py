# routes/admin/medicos.py
from flask import render_template, request, redirect, url_for, flash, session, jsonify
import logging
import traceback
import uuid
from datetime import datetime
from werkzeug.security import generate_password_hash  # 👈 IMPORTANTE: Adicionar esta linha

logger = logging.getLogger(__name__)

def init_medicos_routes(admin_bp, mysql):
    """Rotas para gerenciamento de médicos"""
    
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
            logger.error(traceback.format_exc())
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
    
    # ======================================================================
    # LISTAR MÉDICOS (CORRIGIDO)
    # ======================================================================
    @admin_bp.route('/medicos')
    @admin_required
    def medicos():
        """Lista todos os médicos com todos os campos"""
        try:
            # CORREÇÃO: Ajustar os índices para corresponder à consulta
            medicos = execute_query("""
                SELECT 
                    u.id,                          -- [0] ID do usuário
                    u.uuid,                        -- [1] UUID
                    u.nome,                        -- [2] Nome
                    u.email,                       -- [3] Email
                    u.ativo,                       -- [4] Ativo (booleano)
                    m.especialidade,                -- [5] Especialidade
                    m.crm,                          -- [6] CRM
                    m.telefone,                     -- [7] Telefone
                    m.status,                       -- [8] Status (ativo/inativo/ferias/licenca)
                    u.criado_em,                    -- [9] Data de criação
                    (SELECT COUNT(*) FROM consultas WHERE medico_id = m.id) as total_consultas  -- [10]
                FROM usuarios u
                JOIN medicos m ON u.id = m.usuario_id
                WHERE u.tipo = 'medico'
                ORDER BY u.criado_em DESC
            """, fetch=True) or []
            
            # Log para debug
            logger.info(f"Total de médicos encontrados: {len(medicos)}")
            for medico in medicos:
                logger.debug(f"Médico ID: {medico[0]}, Nome: {medico[2]}, CRM: {medico[6]}, Status: {medico[8]}")
            
            return render_template('admin/medicos.html', medicos=medicos, user=session)
        except Exception as e:
            logger.error(f"Erro ao listar médicos: {e}")
            logger.error(traceback.format_exc())
            flash('Erro ao carregar lista de médicos.', 'danger')
            return render_template('admin/medicos.html', medicos=[], user=session)
    
    # ======================================================================
    # CADASTRAR MÉDICO (COM SENHA CRIPTOGRAFADA)
    # ======================================================================
    @admin_bp.route('/medicos/cadastrar', methods=['GET', 'POST'])
    @admin_required
    def cadastrar_medico():
        """Cadastra um novo médico com todos os campos da tabela"""
        if request.method == 'POST':
            # Receber todos os dados do formulário
            nome = request.form.get('nome', '').strip()
            email = request.form.get('email', '').strip().lower()
            senha = request.form.get('senha', '').strip()
            especialidade = request.form.get('especialidade', '').strip()
            crm = request.form.get('crm', '').strip().upper()
            telefone = request.form.get('telefone', '').strip()
            status = request.form.get('status', 'ativo')
            
            # Gerar UUID único
            user_uuid = str(uuid.uuid4())
            
            # Log para debug
            logger.info(f"Tentando cadastrar médico: {nome}, {email}, UUID: {user_uuid}")
            
            # Validações
            if not all([nome, email, senha, especialidade, crm]):
                flash('Nome, email, senha, especialidade e CRM são obrigatórios.', 'danger')
                return redirect(url_for('admin.cadastrar_medico'))
            
            if len(senha) < 6:
                flash('A senha deve ter pelo menos 6 caracteres.', 'danger')
                return redirect(url_for('admin.cadastrar_medico'))
            
            # Verificar se email já existe
            existing = execute_query(
                "SELECT id FROM usuarios WHERE email = %s",
                (email,), fetch=True, one=True
            )
            
            if existing:
                flash('Email já cadastrado.', 'danger')
                return redirect(url_for('admin.cadastrar_medico'))
            
            # Verificar se CRM já existe
            crm_existing = execute_query(
                "SELECT id FROM medicos WHERE crm = %s",
                (crm,), fetch=True, one=True
            )
            
            if crm_existing:
                flash('CRM já cadastrado.', 'danger')
                return redirect(url_for('admin.cadastrar_medico'))
            
            try:
                cur = mysql.connection.cursor()
                
                # 👇 GERAR HASH DA SENHA
                senha_hash = generate_password_hash(senha)
                logger.info(f"Senha criptografada gerada para {email}")
                
                # Inserir na tabela usuarios com UUID e senha HASH
                cur.execute("""
                    INSERT INTO usuarios (uuid, nome, email, senha, tipo, ativo, criado_em)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """, (user_uuid, nome, email, senha_hash, 'medico', True))
                
                mysql.connection.commit()
                usuario_id = cur.lastrowid
                
                # Inserir na tabela medicos
                cur.execute("""
                    INSERT INTO medicos (usuario_id, especialidade, crm, telefone, status)
                    VALUES (%s, %s, %s, %s, %s)
                """, (usuario_id, especialidade, crm, telefone, status))
                
                mysql.connection.commit()
                cur.close()
                
                logger.info(f"Médico cadastrado com sucesso: ID {usuario_id}, UUID {user_uuid} - {nome}")
                flash('Médico cadastrado com sucesso!', 'success')
                return redirect(url_for('admin.medicos'))
                
            except Exception as e:
                mysql.connection.rollback()
                logger.error(f"Erro ao cadastrar médico: {e}")
                logger.error(traceback.format_exc())
                flash(f'Erro ao cadastrar médico: {str(e)}', 'danger')
                return redirect(url_for('admin.cadastrar_medico'))
        
        return render_template('admin/cadastrar_medico.html', user=session)
    
    # ======================================================================
    # EDITAR MÉDICO (COM OPÇÃO DE ALTERAR SENHA)
    # ======================================================================
    @admin_bp.route('/medicos/<int:medico_id>/editar', methods=['GET', 'POST'])
    @admin_required
    def editar_medico(medico_id):
        """Edita um médico existente com todos os campos"""
        if request.method == 'POST':
            # Receber todos os dados do formulário
            nome = request.form.get('nome', '').strip()
            email = request.form.get('email', '').strip().lower()
            especialidade = request.form.get('especialidade', '').strip()
            crm = request.form.get('crm', '').strip().upper()
            telefone = request.form.get('telefone', '').strip()
            status = request.form.get('status', 'ativo')
            ativo = 1 if request.form.get('ativo') else 0
            nova_senha = request.form.get('nova_senha', '').strip()
            
            # Log para debug
            logger.info(f"Editando médico ID {medico_id}: {nome}, {email}")
            
            # Validações
            if not all([nome, email, especialidade, crm]):
                flash('Nome, email, especialidade e CRM são obrigatórios.', 'danger')
                return redirect(url_for('admin.editar_medico', medico_id=medico_id))
            
            try:
                # Se foi fornecida uma nova senha, atualizar com hash
                if nova_senha:
                    if len(nova_senha) < 6:
                        flash('A nova senha deve ter pelo menos 6 caracteres.', 'danger')
                        return redirect(url_for('admin.editar_medico', medico_id=medico_id))
                    
                    # 👇 GERAR HASH DA NOVA SENHA
                    senha_hash = generate_password_hash(nova_senha)
                    
                    # Atualizar usuário com nova senha
                    execute_query("""
                        UPDATE usuarios 
                        SET nome = %s, email = %s, senha = %s, ativo = %s
                        WHERE id = %s AND tipo = 'medico'
                    """, (nome, email, senha_hash, ativo, medico_id))
                    
                    logger.info(f"Senha atualizada para médico ID {medico_id}")
                else:
                    # Atualizar usuário sem alterar senha
                    execute_query("""
                        UPDATE usuarios 
                        SET nome = %s, email = %s, ativo = %s
                        WHERE id = %s AND tipo = 'medico'
                    """, (nome, email, ativo, medico_id))
                
                # Atualizar médico com telefone e status
                execute_query("""
                    UPDATE medicos 
                    SET especialidade = %s, crm = %s, telefone = %s, status = %s
                    WHERE usuario_id = %s
                """, (especialidade, crm, telefone, status, medico_id))
                
                logger.info(f"Médico atualizado com sucesso: ID {medico_id}")
                flash('Médico atualizado com sucesso!', 'success')
                return redirect(url_for('admin.medicos'))
                
            except Exception as e:
                logger.error(f"Erro ao atualizar médico: {e}")
                logger.error(traceback.format_exc())
                flash(f'Erro ao atualizar médico: {str(e)}', 'danger')
                return redirect(url_for('admin.editar_medico', medico_id=medico_id))
        
        # Buscar dados do médico
        medico = execute_query("""
            SELECT 
                u.id,        -- [0]
                u.uuid,      -- [1]
                u.nome,      -- [2]
                u.email,     -- [3]
                u.ativo,     -- [4]
                m.especialidade,  -- [5]
                m.crm,       -- [6]
                m.telefone,  -- [7]
                m.status     -- [8]
            FROM usuarios u
            JOIN medicos m ON u.id = m.usuario_id
            WHERE u.id = %s AND u.tipo = 'medico'
        """, (medico_id,), fetch=True, one=True)
        
        if not medico:
            flash('Médico não encontrado.', 'danger')
            return redirect(url_for('admin.medicos'))
        
        return render_template('admin/editar_medico.html', medico=medico, user=session)
    
    # ======================================================================
    # VISUALIZAR MÉDICO (API)
    # ======================================================================
    @admin_bp.route('/medicos/<int:medico_id>/visualizar')
    @admin_required
    def visualizar_medico(medico_id):
        """Visualiza detalhes de um médico (API)"""
        try:
            medico = execute_query("""
                SELECT 
                    u.id, u.uuid, u.nome, u.email, u.ativo, u.criado_em,
                    m.especialidade, m.crm, m.telefone, m.status,
                    (SELECT COUNT(*) FROM consultas WHERE medico_id = m.id) as total_consultas,
                    (SELECT COUNT(*) FROM consultas WHERE medico_id = m.id AND status = 'realizada') as consultas_realizadas,
                    (SELECT COUNT(*) FROM consultas WHERE medico_id = m.id AND status = 'cancelada') as consultas_canceladas
                FROM usuarios u
                JOIN medicos m ON u.id = m.usuario_id
                WHERE u.id = %s AND u.tipo = 'medico'
            """, (medico_id,), fetch=True, one=True)
            
            if not medico:
                return jsonify({'error': 'Médico não encontrado'}), 404
            
            # Formatar data de criação
            criado_em = medico[5].strftime('%d/%m/%Y %H:%M') if medico[5] else ''
            
            return jsonify({
                'id': medico[0],
                'uuid': medico[1],
                'nome': medico[2],
                'email': medico[3],
                'ativo': 'Sim' if medico[4] else 'Não',
                'criado_em': criado_em,
                'especialidade': medico[6] or 'Não definida',
                'crm': medico[7] or '---',
                'telefone': medico[8] or 'Não informado',
                'status': medico[9] or 'ativo',
                'total_consultas': medico[10] or 0,
                'consultas_realizadas': medico[11] or 0,
                'consultas_canceladas': medico[12] or 0
            })
            
        except Exception as e:
            logger.error(f"Erro ao visualizar médico: {e}")
            logger.error(traceback.format_exc())
            return jsonify({'error': 'Erro ao carregar dados'}), 500
    
    # ======================================================================
    # EXCLUIR MÉDICO (CORRIGIDO)
    # ======================================================================
    @admin_bp.route('/medicos/<int:medico_id>/excluir', methods=['POST'])
    @admin_required
    def excluir_medico(medico_id):
        """Exclui um médico (soft delete ou hard delete)"""
        try:
            # Verificar se tem consultas vinculadas
            consultas = execute_query(
                "SELECT COUNT(*) FROM consultas WHERE medico_id = (SELECT id FROM medicos WHERE usuario_id = %s)",
                (medico_id,), fetch=True, one=True
            )
            
            if consultas and consultas[0] > 0:
                # Soft delete - apenas desativa
                execute_query(
                    "UPDATE usuarios SET ativo = FALSE WHERE id = %s",
                    (medico_id,)
                )
                execute_query("""
                    UPDATE medicos SET status = 'inativo' 
                    WHERE usuario_id = %s
                """, (medico_id,))
                
                logger.info(f"Médico desativado (soft delete): ID {medico_id}")
                return jsonify({
                    'success': True, 
                    'message': 'Médico desativado pois possui consultas vinculadas.'
                })
            else:
                # Hard delete - remove completamente
                execute_query(
                    "DELETE FROM medicos WHERE usuario_id = %s",
                    (medico_id,)
                )
                execute_query(
                    "DELETE FROM usuarios WHERE id = %s AND tipo = 'medico'",
                    (medico_id,)
                )
                
                logger.info(f"Médico excluído permanentemente: ID {medico_id}")
                return jsonify({
                    'success': True, 
                    'message': 'Médico excluído com sucesso!'
                })
            
        except Exception as e:
            logger.error(f"Erro ao excluir médico: {e}")
            logger.error(traceback.format_exc())
            return jsonify({
                'success': False, 
                'error': f'Erro ao excluir médico: {str(e)}'
            }), 500