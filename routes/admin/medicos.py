# routes/admin/medicos.py
from flask import render_template, request, redirect, url_for, flash, session, jsonify
import logging
import traceback
import uuid
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

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
    # LISTAR MÉDICOS
    # ======================================================================
    @admin_bp.route('/medicos')
    @admin_required
    def medicos():
        """Lista todos os médicos com todos os campos"""
        try:
            medicos = execute_query("""
                SELECT 
                    u.id,
                    u.uuid,
                    u.nome,
                    u.email,
                    u.ativo,
                    m.especialidade,
                    m.crm,
                    m.telefone,
                    m.status,
                    u.criado_em,
                    (SELECT COUNT(*) FROM consultas WHERE medico_id = m.id) as total_consultas
                FROM usuarios u
                JOIN medicos m ON u.id = m.usuario_id
                WHERE u.tipo = 'medico'
                ORDER BY u.criado_em DESC
            """, fetch=True) or []
            
            logger.info(f"Total de médicos encontrados: {len(medicos)}")
            return render_template('admin/medicos.html', medicos=medicos, user=session)
        except Exception as e:
            logger.error(f"Erro ao listar médicos: {e}")
            flash('Erro ao carregar lista de médicos.', 'danger')
            return render_template('admin/medicos.html', medicos=[], user=session)
    
    # ======================================================================
    # CADASTRAR MÉDICO (USANDO pbkdf2:sha256)
    # ======================================================================
    @admin_bp.route('/medicos/cadastrar', methods=['GET', 'POST'])
    @admin_required
    def cadastrar_medico():
        """Cadastra um novo médico com formulário completo"""
        if request.method == 'POST':
            # Receber todos os dados do formulário
            nome = request.form.get('nome', '').strip()
            email = request.form.get('email', '').strip().lower()
            senha = request.form.get('senha', '').strip()
            confirmar_senha = request.form.get('confirmar_senha', '').strip()
            especialidade = request.form.get('especialidade', '').strip()
            crm = request.form.get('crm', '').strip().upper()
            telefone = request.form.get('telefone', '').strip()
            status = request.form.get('status', 'ativo')
            data_nascimento = request.form.get('data_nascimento', '').strip()
            genero = request.form.get('genero', '').strip()
            endereco = request.form.get('endereco', '').strip()
            
            # Gerar UUID único
            user_uuid = str(uuid.uuid4())
            
            # Log para debug
            logger.info(f"Tentando cadastrar médico: {nome}, {email}")
            
            # Validações
            if not all([nome, email, senha, confirmar_senha, especialidade, crm]):
                flash('Todos os campos marcados com * são obrigatórios.', 'danger')
                return redirect(url_for('admin.cadastrar_medico'))
            
            if senha != confirmar_senha:
                flash('As senhas não coincidem.', 'danger')
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
                
                # Usando pbkdf2:sha256 (mesmo método do paciente)
                senha_hash = generate_password_hash(senha, method='pbkdf2:sha256')
                logger.info(f"Senha criptografada com pbkdf2:sha256 para {email}")
                
                # Inserir na tabela usuarios
                cur.execute("""
                    INSERT INTO usuarios (uuid, nome, email, senha, telefone, tipo, ativo, criado_em)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """, (user_uuid, nome, email, senha_hash, telefone, 'medico', True))
                
                mysql.connection.commit()
                usuario_id = cur.lastrowid
                
                # Inserir na tabela medicos com todos os campos
                cur.execute("""
                    INSERT INTO medicos (usuario_id, especialidade, crm, telefone, status, data_nascimento, genero, endereco)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (usuario_id, especialidade, crm, telefone, status, 
                      data_nascimento if data_nascimento else None,
                      genero if genero else None,
                      endereco if endereco else None))
                
                mysql.connection.commit()
                cur.close()
                
                logger.info(f"Médico cadastrado com sucesso: ID {usuario_id}")
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
    # EDITAR MÉDICO
    # ======================================================================
    @admin_bp.route('/medicos/<int:medico_id>/editar', methods=['GET', 'POST'])
    @admin_required
    def editar_medico(medico_id):
        """Edita um médico existente"""
        if request.method == 'POST':
            nome = request.form.get('nome', '').strip()
            email = request.form.get('email', '').strip().lower()
            especialidade = request.form.get('especialidade', '').strip()
            crm = request.form.get('crm', '').strip().upper()
            telefone = request.form.get('telefone', '').strip()
            status = request.form.get('status', 'ativo')
            ativo = 1 if request.form.get('ativo') else 0
            nova_senha = request.form.get('nova_senha', '').strip()
            data_nascimento = request.form.get('data_nascimento', '').strip()
            genero = request.form.get('genero', '').strip()
            endereco = request.form.get('endereco', '').strip()
            
            logger.info(f"Editando médico ID {medico_id}: {nome}")
            
            if not all([nome, email, especialidade, crm]):
                flash('Nome, email, especialidade e CRM são obrigatórios.', 'danger')
                return redirect(url_for('admin.editar_medico', medico_id=medico_id))
            
            try:
                # Atualizar senha se fornecida
                if nova_senha:
                    if len(nova_senha) < 6:
                        flash('A nova senha deve ter pelo menos 6 caracteres.', 'danger')
                        return redirect(url_for('admin.editar_medico', medico_id=medico_id))
                    
                    senha_hash = generate_password_hash(nova_senha, method='pbkdf2:sha256')
                    
                    execute_query("""
                        UPDATE usuarios 
                        SET nome = %s, email = %s, senha = %s, ativo = %s, telefone = %s
                        WHERE id = %s AND tipo = 'medico'
                    """, (nome, email, senha_hash, ativo, telefone, medico_id))
                    
                    logger.info(f"Senha atualizada para médico ID {medico_id}")
                else:
                    execute_query("""
                        UPDATE usuarios 
                        SET nome = %s, email = %s, ativo = %s, telefone = %s
                        WHERE id = %s AND tipo = 'medico'
                    """, (nome, email, ativo, telefone, medico_id))
                
                # Atualizar médico
                execute_query("""
                    UPDATE medicos 
                    SET especialidade = %s, crm = %s, status = %s,
                        data_nascimento = %s, genero = %s, endereco = %s
                    WHERE usuario_id = %s
                """, (especialidade, crm, status, 
                      data_nascimento if data_nascimento else None,
                      genero if genero else None,
                      endereco if endereco else None, medico_id))
                
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
                u.id, u.uuid, u.nome, u.email, u.ativo, u.telefone,
                m.especialidade, m.crm, m.status, m.data_nascimento, m.genero, m.endereco
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
            # Buscar o ID do médico na tabela medicos
            medico_data = execute_query("""
                SELECT 
                    u.id as usuario_id,
                    m.id as medico_id,
                    u.uuid, 
                    u.nome, 
                    u.email, 
                    u.ativo, 
                    u.criado_em,
                    u.telefone,
                    m.especialidade, 
                    m.crm, 
                    m.status,
                    m.data_nascimento,
                    m.genero,
                    m.endereco
                FROM usuarios u
                JOIN medicos m ON u.id = m.usuario_id
                WHERE u.id = %s AND u.tipo = 'medico'
            """, (medico_id,), fetch=True, one=True)
            
            if not medico_data:
                return jsonify({'error': 'Médico não encontrado'}), 404
            
            # Buscar estatísticas usando o medico_id correto
            stats = execute_query("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'realizada' THEN 1 ELSE 0 END) as realizadas,
                    SUM(CASE WHEN status = 'cancelada' THEN 1 ELSE 0 END) as canceladas
                FROM consultas 
                WHERE medico_id = %s
            """, (medico_data['medico_id'],), fetch=True, one=True)
            
            # Formatar data de criação
            criado_em = medico_data['criado_em'].strftime('%d/%m/%Y %H:%M') if medico_data['criado_em'] else ''
            data_nascimento = medico_data['data_nascimento'].strftime('%d/%m/%Y') if medico_data['data_nascimento'] else ''
            
            return jsonify({
                'id': medico_data['usuario_id'],
                'uuid': medico_data['uuid'],
                'nome': medico_data['nome'],
                'email': medico_data['email'],
                'telefone': medico_data['telefone'] or 'Não informado',
                'ativo': 'Sim' if medico_data['ativo'] else 'Não',
                'criado_em': criado_em,
                'especialidade': medico_data['especialidade'] or 'Não definida',
                'crm': medico_data['crm'] or '---',
                'status': medico_data['status'] or 'ativo',
                'data_nascimento': data_nascimento or 'Não informada',
                'genero': medico_data['genero'] or 'Não informado',
                'endereco': medico_data['endereco'] or 'Não informado',
                'total_consultas': stats['total'] if stats else 0,
                'consultas_realizadas': stats['realizadas'] if stats else 0,
                'consultas_canceladas': stats['canceladas'] if stats else 0
            })
            
        except Exception as e:
            logger.error(f"Erro ao visualizar médico: {e}")
            logger.error(traceback.format_exc())
            return jsonify({'error': 'Erro ao carregar dados'}), 500
    
    # ======================================================================
    # EXCLUIR MÉDICO
    # ======================================================================
    @admin_bp.route('/medicos/<int:medico_id>/excluir', methods=['POST'])
    @admin_required
    def excluir_medico(medico_id):
        """Exclui um médico (soft delete ou hard delete)"""
        try:
            # Buscar o id da tabela medicos
            medico_data = execute_query(
                "SELECT m.id FROM medicos m WHERE m.usuario_id = %s",
                (medico_id,), fetch=True, one=True
            )
            
            if not medico_data:
                return jsonify({'success': False, 'error': 'Médico não encontrado'}), 404
            
            medico_table_id = medico_data['id']
            
            # Verificar se tem consultas vinculadas
            consultas = execute_query(
                "SELECT COUNT(*) as total FROM consultas WHERE medico_id = %s",
                (medico_table_id,), fetch=True, one=True
            )
            
            if consultas and consultas['total'] > 0:
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
