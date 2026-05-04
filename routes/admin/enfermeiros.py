# routes/admin/enfermeiros.py - VERSÃO CORRIGIDA
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash
import logging
import traceback
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

def init_enfermeiros_routes(admin_bp, mysql):
    """Rotas para gerenciamento de enfermeiros"""
    
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
    
    # ==================== LISTAR ENFERMEIROS ====================
    @admin_bp.route('/enfermeiros')
    @admin_required
    def enfermeiros():
        """Lista todos os enfermeiros"""
        try:
            enfermeiros = execute_query("""
                SELECT 
                    u.id,
                    u.nome,
                    u.email,
                    u.telefone,
                    e.coren,
                    e.especialidade,
                    e.data_cadastro,
                    e.ativo
                FROM usuarios u
                JOIN enfermeiros e ON u.id = e.usuario_id
                WHERE u.tipo = 'enfermeiro'
                ORDER BY u.nome ASC
            """, fetch=True) or []
            
            # Converter para lista de dicionários (funciona com dict ou tuple)
            enfermeiros_list = []
            for e in enfermeiros:
                if isinstance(e, dict):
                    enfermeiros_list.append({
                        'id': e.get('id'),
                        'nome': e.get('nome'),
                        'email': e.get('email'),
                        'telefone': e.get('telefone'),
                        'coren': e.get('coren'),
                        'especialidade': e.get('especialidade'),
                        'data_cadastro': e.get('data_cadastro'),
                        'ativo': e.get('ativo')
                    })
                else:
                    enfermeiros_list.append({
                        'id': e[0],
                        'nome': e[1],
                        'email': e[2],
                        'telefone': e[3],
                        'coren': e[4],
                        'especialidade': e[5],
                        'data_cadastro': e[6],
                        'ativo': e[7]
                    })
            
            return render_template('admin/enfermeiros.html', 
                                 enfermeiros=enfermeiros_list, 
                                 user=session)
        except Exception as e:
            logger.error(f"Erro ao listar enfermeiros: {e}")
            flash('Erro ao carregar lista de enfermeiros.', 'danger')
            return render_template('admin/enfermeiros.html', enfermeiros=[], user=session)
    
    # ==================== CADASTRAR ENFERMEIRO ====================
    @admin_bp.route('/enfermeiros/cadastrar', methods=['GET', 'POST'])
    @admin_required
    def cadastrar_enfermeiro():
        """Cadastra um novo enfermeiro - CORRIGIDO"""
        if request.method == 'POST':
            nome = request.form.get('nome', '').strip()
            email = request.form.get('email', '').strip().lower()
            senha = request.form.get('senha', '').strip()
            telefone = request.form.get('telefone', '').strip()
            coren = request.form.get('coren', '').strip().upper()
            especialidade = request.form.get('especialidade', '').strip()
            
            if not all([nome, email, senha, coren]):
                flash('Nome, email, senha e COREN são obrigatórios.', 'danger')
                return redirect(url_for('admin.cadastrar_enfermeiro'))
            
            if len(senha) < 6:
                flash('A senha deve ter pelo menos 6 caracteres.', 'danger')
                return redirect(url_for('admin.cadastrar_enfermeiro'))
            
            # Verificar se email já existe
            existing = execute_query(
                "SELECT id FROM usuarios WHERE email = %s",
                (email,), fetch=True, one=True
            )
            
            if existing:
                # existing pode ser dict ou tuple
                existing_id = existing.get('id') if isinstance(existing, dict) else existing[0] if existing else None
                if existing_id:
                    flash('Email já cadastrado.', 'danger')
                    return redirect(url_for('admin.cadastrar_enfermeiro'))
            
            # Verificar se COREN já existe
            coren_existing = execute_query(
                "SELECT id FROM enfermeiros WHERE coren = %s",
                (coren,), fetch=True, one=True
            )
            
            if coren_existing:
                coren_id = coren_existing.get('id') if isinstance(coren_existing, dict) else coren_existing[0] if coren_existing else None
                if coren_id:
                    flash('COREN já cadastrado.', 'danger')
                    return redirect(url_for('admin.cadastrar_enfermeiro'))
            
            try:
                user_uuid = str(uuid.uuid4())
                senha_hash = generate_password_hash(senha)
                
                # Inserir usuário
                execute_query("""
                    INSERT INTO usuarios (uuid, nome, email, senha, telefone, tipo, ativo, criado_em)
                    VALUES (%s, %s, %s, %s, %s, 'enfermeiro', 1, NOW())
                """, (user_uuid, nome, email, senha_hash, telefone))
                
                # Pegar ID do usuário inserido (CORREÇÃO: suporta dict ou tuple)
                user = execute_query(
                    "SELECT id FROM usuarios WHERE email = %s",
                    (email,), fetch=True, one=True
                )
                
                if user:
                    # user pode ser dict ou tuple
                    user_id = user.get('id') if isinstance(user, dict) else user[0] if user else None
                    
                    if user_id:
                        # Inserir enfermeiro
                        execute_query("""
                            INSERT INTO enfermeiros (usuario_id, coren, especialidade, data_cadastro, ativo)
                            VALUES (%s, %s, %s, NOW(), 1)
                        """, (user_id, coren, especialidade))
                        
                        flash('Enfermeiro cadastrado com sucesso!', 'success')
                        return redirect(url_for('admin.enfermeiros'))
                    else:
                        flash('Erro ao obter ID do usuário.', 'danger')
                else:
                    flash('Erro ao cadastrar enfermeiro.', 'danger')
                    
            except Exception as e:
                logger.error(f"Erro ao cadastrar enfermeiro: {e}")
                flash(f'Erro ao cadastrar enfermeiro: {str(e)}', 'danger')
        
        return render_template('admin/cadastrar_enfermeiro.html', user=session)
    
    # ==================== EDITAR ENFERMEIRO ====================
    @admin_bp.route('/enfermeiros/<int:enfermeiro_id>/editar', methods=['GET', 'POST'])
    @admin_required
    def editar_enfermeiro(enfermeiro_id):
        """Edita um enfermeiro existente"""
        if request.method == 'POST':
            nome = request.form.get('nome', '').strip()
            email = request.form.get('email', '').strip().lower()
            telefone = request.form.get('telefone', '').strip()
            coren = request.form.get('coren', '').strip().upper()
            especialidade = request.form.get('especialidade', '').strip()
            ativo = 1 if request.form.get('ativo') else 0
            nova_senha = request.form.get('nova_senha', '').strip()
            
            if not all([nome, email, coren]):
                flash('Nome, email e COREN são obrigatórios.', 'danger')
                return redirect(url_for('admin.editar_enfermeiro', enfermeiro_id=enfermeiro_id))
            
            try:
                if nova_senha:
                    if len(nova_senha) < 6:
                        flash('A nova senha deve ter pelo menos 6 caracteres.', 'danger')
                        return redirect(url_for('admin.editar_enfermeiro', enfermeiro_id=enfermeiro_id))
                    
                    senha_hash = generate_password_hash(nova_senha)
                    execute_query("""
                        UPDATE usuarios 
                        SET nome = %s, email = %s, telefone = %s, senha = %s, ativo = %s
                        WHERE id = %s AND tipo = 'enfermeiro'
                    """, (nome, email, telefone, senha_hash, ativo, enfermeiro_id))
                else:
                    execute_query("""
                        UPDATE usuarios 
                        SET nome = %s, email = %s, telefone = %s, ativo = %s
                        WHERE id = %s AND tipo = 'enfermeiro'
                    """, (nome, email, telefone, ativo, enfermeiro_id))
                
                execute_query("""
                    UPDATE enfermeiros 
                    SET coren = %s, especialidade = %s
                    WHERE usuario_id = %s
                """, (coren, especialidade, enfermeiro_id))
                
                flash('Enfermeiro atualizado com sucesso!', 'success')
                return redirect(url_for('admin.enfermeiros'))
                
            except Exception as e:
                logger.error(f"Erro ao atualizar enfermeiro: {e}")
                flash(f'Erro ao atualizar enfermeiro: {str(e)}', 'danger')
        
        # Buscar dados do enfermeiro
        enfermeiro = execute_query("""
            SELECT 
                u.id, u.nome, u.email, u.telefone, u.ativo,
                e.coren, e.especialidade, e.data_cadastro
            FROM usuarios u
            JOIN enfermeiros e ON u.id = e.usuario_id
            WHERE u.id = %s AND u.tipo = 'enfermeiro'
        """, (enfermeiro_id,), fetch=True, one=True)
        
        if not enfermeiro:
            flash('Enfermeiro não encontrado.', 'danger')
            return redirect(url_for('admin.enfermeiros'))
        
        # Converter para dicionário (funciona com dict ou tuple)
        if isinstance(enfermeiro, dict):
            enfermeiro_dict = {
                'id': enfermeiro.get('id'),
                'nome': enfermeiro.get('nome'),
                'email': enfermeiro.get('email'),
                'telefone': enfermeiro.get('telefone'),
                'ativo': enfermeiro.get('ativo'),
                'coren': enfermeiro.get('coren'),
                'especialidade': enfermeiro.get('especialidade'),
                'data_cadastro': enfermeiro.get('data_cadastro')
            }
        else:
            enfermeiro_dict = {
                'id': enfermeiro[0],
                'nome': enfermeiro[1],
                'email': enfermeiro[2],
                'telefone': enfermeiro[3],
                'ativo': enfermeiro[4],
                'coren': enfermeiro[5],
                'especialidade': enfermeiro[6],
                'data_cadastro': enfermeiro[7]
            }
        
        return render_template('admin/editar_enfermeiro.html', 
                             enfermeiro=enfermeiro_dict, 
                             user=session)
    
    # ==================== VISUALIZAR ENFERMEIRO ====================
    @admin_bp.route('/enfermeiros/<int:enfermeiro_id>/visualizar')
    @admin_required
    def visualizar_enfermeiro(enfermeiro_id):
        """Retorna dados do enfermeiro em JSON"""
        try:
            enfermeiro = execute_query("""
                SELECT 
                    u.nome, u.email, u.telefone,
                    e.coren, e.especialidade, e.data_cadastro,
                    e.ativo
                FROM usuarios u
                JOIN enfermeiros e ON u.id = e.usuario_id
                WHERE u.id = %s AND u.tipo = 'enfermeiro'
            """, (enfermeiro_id,), fetch=True, one=True)
            
            if not enfermeiro:
                return jsonify({'error': 'Enfermeiro não encontrado'}), 404
            
            # Converter para dict (funciona com dict ou tuple)
            if isinstance(enfermeiro, dict):
                return jsonify({
                    'nome': enfermeiro.get('nome'),
                    'email': enfermeiro.get('email'),
                    'telefone': enfermeiro.get('telefone') or 'Não informado',
                    'coren': enfermeiro.get('coren'),
                    'especialidade': enfermeiro.get('especialidade') or 'Não informada',
                    'data_cadastro': enfermeiro.get('data_cadastro').strftime('%d/%m/%Y') if enfermeiro.get('data_cadastro') else '',
                    'ativo': bool(enfermeiro.get('ativo'))
                })
            else:
                return jsonify({
                    'nome': enfermeiro[0],
                    'email': enfermeiro[1],
                    'telefone': enfermeiro[2] or 'Não informado',
                    'coren': enfermeiro[3],
                    'especialidade': enfermeiro[4] or 'Não informada',
                    'data_cadastro': enfermeiro[5].strftime('%d/%m/%Y') if enfermeiro[5] else '',
                    'ativo': bool(enfermeiro[6])
                })
            
        except Exception as e:
            logger.error(f"Erro ao visualizar enfermeiro: {e}")
            return jsonify({'error': 'Erro ao carregar dados'}), 500
    
    # ==================== EXCLUIR ENFERMEIRO ====================
    @admin_bp.route('/enfermeiros/<int:enfermeiro_id>/excluir', methods=['POST'])
    @admin_required
    def excluir_enfermeiro(enfermeiro_id):
        """Exclui um enfermeiro"""
        try:
            # Verificar se tem registros de sinais vitais
            sinais = execute_query("""
                SELECT COUNT(*) FROM sinais_vitais 
                WHERE enfermeiro_id = %s
            """, (enfermeiro_id,), fetch=True, one=True)
            
            # Contar registros (funciona com dict ou tuple)
            if sinais:
                count = sinais.get('COUNT(*)') if isinstance(sinais, dict) else sinais[0] if sinais else 0
                
                if count > 0:
                    # Soft delete
                    execute_query(
                        "UPDATE usuarios SET ativo = 0 WHERE id = %s",
                        (enfermeiro_id,)
                    )
                    return jsonify({
                        'success': True,
                        'message': 'Enfermeiro desativado pois possui registros de sinais vitais.'
                    })
                else:
                    # Hard delete
                    execute_query(
                        "DELETE FROM enfermeiros WHERE usuario_id = %s",
                        (enfermeiro_id,)
                    )
                    execute_query(
                        "DELETE FROM usuarios WHERE id = %s AND tipo = 'enfermeiro'",
                        (enfermeiro_id,)
                    )
                    return jsonify({
                        'success': True,
                        'message': 'Enfermeiro excluído com sucesso!'
                    })
            else:
                # Hard delete
                execute_query(
                    "DELETE FROM enfermeiros WHERE usuario_id = %s",
                    (enfermeiro_id,)
                )
                execute_query(
                    "DELETE FROM usuarios WHERE id = %s AND tipo = 'enfermeiro'",
                    (enfermeiro_id,)
                )
                return jsonify({
                    'success': True,
                    'message': 'Enfermeiro excluído com sucesso!'
                })
                
        except Exception as e:
            logger.error(f"Erro ao excluir enfermeiro: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    return admin_bp
