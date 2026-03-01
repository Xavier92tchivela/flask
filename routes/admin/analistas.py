# routes/admin/analistas.py
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime
import logging
import traceback
import uuid  # 👈 ADICIONADO PARA GERAR UUID

logger = logging.getLogger(__name__)

def init_analistas_routes(admin_bp, mysql):
    """Rotas para gerenciamento de analistas"""
    
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
    
    # ---------- LISTAR ANALISTAS ----------
    @admin_bp.route('/analistas')
    @admin_required
    def analistas():
        """Lista todos os analistas com os campos corretos da tabela"""
        try:
            analistas = execute_query("""
                SELECT 
                    u.id,                          -- [0]
                    u.nome,                         -- [1]
                    u.email,                        -- [2]
                    u.ativo,                        -- [3]
                    a.especialidade,                 -- [4]
                    a.registro_profissional,        -- [5]
                    a.telefone,                      -- [6]
                    a.is_supervisor,                 -- [7]
                    a.status,                        -- [8]
                    a.experiencia,                   -- [9]
                    a.carga_horaria_semanal,         -- [10]
                    a.data_contratacao,              -- [11]
                    a.data_desligamento,             -- [12]
                    u.criado_em,                      -- [13]
                    (SELECT COUNT(*) FROM pedidos_analise WHERE analista_id = a.id) as total_analises  -- [14]
                FROM usuarios u
                JOIN analistas a ON u.id = a.usuario_id
                WHERE u.tipo = 'analista'
                ORDER BY u.criado_em DESC
            """, fetch=True) or []
            
            logger.info(f"Total de analistas encontrados: {len(analistas)}")
            
            return render_template('admin/analistas.html', analistas=analistas, user=session)
            
        except Exception as e:
            logger.error(f"Erro ao listar analistas: {e}")
            logger.error(traceback.format_exc())
            flash('Erro ao carregar lista de analistas.', 'danger')
            return render_template('admin/analistas.html', analistas=[], user=session)
    
    # ---------- CADASTRAR ANALISTA (CORRIGIDO) ----------
    @admin_bp.route('/analistas/cadastrar', methods=['GET', 'POST'])
    @admin_required
    def cadastrar_analista():
        """Cadastra um novo analista com todos os campos da tabela"""
        if request.method == 'POST':
            # Receber todos os dados do formulário
            nome = request.form.get('nome', '').strip()
            email = request.form.get('email', '').strip().lower()
            senha = request.form.get('senha', '').strip()
            especialidade = request.form.get('especialidade', '').strip()
            registro_profissional = request.form.get('registro_profissional', '').strip().upper()
            telefone = request.form.get('telefone', '').strip()
            is_supervisor = 1 if request.form.get('is_supervisor') else 0
            experiencia = request.form.get('experiencia', '').strip()
            carga_horaria = request.form.get('carga_horaria', 40)
            
            # Gerar UUID para o usuário
            user_uuid = str(uuid.uuid4())
            
            # Log para debug
            logger.info(f"Tentando cadastrar analista: {nome}, {email}, UUID: {user_uuid}")
            
            # Validações
            if not all([nome, email, senha, especialidade]):
                flash('Nome, email, senha e especialidade são obrigatórios.', 'danger')
                return redirect(url_for('admin.cadastrar_analista'))
            
            if len(senha) < 6:
                flash('A senha deve ter pelo menos 6 caracteres.', 'danger')
                return redirect(url_for('admin.cadastrar_analista'))
            
            # Verificar se email já existe
            existing = execute_query(
                "SELECT id FROM usuarios WHERE email = %s",
                (email,), fetch=True, one=True
            )
            
            if existing:
                flash('Email já cadastrado.', 'danger')
                return redirect(url_for('admin.cadastrar_analista'))
            
            try:
                cur = mysql.connection.cursor()
                
                # Inserir na tabela usuarios com UUID
                cur.execute("""
                    INSERT INTO usuarios (uuid, nome, email, senha, tipo, ativo, criado_em)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """, (user_uuid, nome, email, senha, 'analista', True))
                
                mysql.connection.commit()
                usuario_id = cur.lastrowid
                
                # Inserir na tabela analistas com todos os campos
                cur.execute("""
                    INSERT INTO analistas (
                        usuario_id, 
                        especialidade, 
                        registro_profissional, 
                        telefone, 
                        is_supervisor, 
                        status, 
                        experiencia, 
                        carga_horaria_semanal, 
                        data_contratacao, 
                        criado_em
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                    )
                """, (
                    usuario_id, 
                    especialidade, 
                    registro_profissional, 
                    telefone, 
                    is_supervisor, 
                    'ativo', 
                    experiencia, 
                    carga_horaria, 
                    datetime.now().date()  # 👈 Usando datetime.now().date() em vez de CURDATE()
                ))
                
                mysql.connection.commit()
                cur.close()
                
                logger.info(f"Analista cadastrado com sucesso: ID {usuario_id}, UUID {user_uuid} - {nome}")
                flash('Analista cadastrado com sucesso!', 'success')
                return redirect(url_for('admin.analistas'))
                
            except Exception as e:
                mysql.connection.rollback()
                logger.error(f"Erro ao cadastrar analista: {e}")
                logger.error(traceback.format_exc())
                flash(f'Erro ao cadastrar analista: {str(e)}', 'danger')
                return redirect(url_for('admin.cadastrar_analista'))
        
        return render_template('admin/cadastrar_analista.html', user=session)
    
    # ---------- EDITAR ANALISTA (CORRIGIDO) ----------
    @admin_bp.route('/analistas/<int:analista_id>/editar', methods=['GET', 'POST'])
    @admin_required
    def editar_analista(analista_id):
        """Edita um analista existente"""
        if request.method == 'POST':
            nome = request.form.get('nome', '').strip()
            email = request.form.get('email', '').strip().lower()
            especialidade = request.form.get('especialidade', '').strip()
            registro_profissional = request.form.get('registro_profissional', '').strip().upper()
            telefone = request.form.get('telefone', '').strip()
            is_supervisor = 1 if request.form.get('is_supervisor') else 0
            status = request.form.get('status', 'ativo')
            experiencia = request.form.get('experiencia', '').strip()
            carga_horaria = request.form.get('carga_horaria', 40)
            ativo = 1 if request.form.get('ativo') else 0
            
            # Log para debug
            logger.info(f"Editando analista ID {analista_id}: {nome}, {email}")
            
            if not all([nome, email, especialidade]):
                flash('Nome, email e especialidade são obrigatórios.', 'danger')
                return redirect(url_for('admin.editar_analista', analista_id=analista_id))
            
            try:
                # Atualizar usuário
                execute_query("""
                    UPDATE usuarios 
                    SET nome = %s, email = %s, ativo = %s
                    WHERE id = %s AND tipo = 'analista'
                """, (nome, email, ativo, analista_id))
                
                # Atualizar analista
                execute_query("""
                    UPDATE analistas 
                    SET especialidade = %s, 
                        registro_profissional = %s, 
                        telefone = %s,
                        is_supervisor = %s, 
                        status = %s, 
                        experiencia = %s,
                        carga_horaria_semanal = %s,
                        atualizado_em = NOW()
                    WHERE usuario_id = %s
                """, (especialidade, registro_profissional, telefone, 
                      is_supervisor, status, experiencia, carga_horaria, analista_id))
                
                logger.info(f"Analista atualizado com sucesso: ID {analista_id}")
                flash('Analista atualizado com sucesso!', 'success')
                return redirect(url_for('admin.analistas'))
                
            except Exception as e:
                logger.error(f"Erro ao atualizar analista: {e}")
                logger.error(traceback.format_exc())
                flash(f'Erro ao atualizar analista: {str(e)}', 'danger')
                return redirect(url_for('admin.editar_analista', analista_id=analista_id))
        
        # Buscar dados do analista
        analista = execute_query("""
            SELECT 
                u.id, u.nome, u.email, u.ativo, 
                a.especialidade, a.registro_profissional, 
                a.telefone, a.is_supervisor, a.status,
                a.experiencia, a.carga_horaria_semanal,
                a.data_contratacao, a.data_desligamento
            FROM usuarios u
            JOIN analistas a ON u.id = a.usuario_id
            WHERE u.id = %s AND u.tipo = 'analista'
        """, (analista_id,), fetch=True, one=True)
        
        if not analista:
            flash('Analista não encontrado.', 'danger')
            return redirect(url_for('admin.analistas'))
        
        return render_template('admin/editar_analista.html', analista=analista, user=session)
    
    # ---------- VISUALIZAR ANALISTA (API) ----------
    @admin_bp.route('/analistas/<int:analista_id>/visualizar')
    @admin_required
    def visualizar_analista(analista_id):
        """Visualiza detalhes de um analista (API)"""
        try:
            analista = execute_query("""
                SELECT 
                    u.id, u.nome, u.email, u.ativo, u.criado_em,
                    a.especialidade, a.registro_profissional, 
                    a.telefone, a.is_supervisor, a.status,
                    a.experiencia, a.carga_horaria_semanal,
                    a.data_contratacao, a.data_desligamento,
                    (SELECT COUNT(*) FROM pedidos_analise WHERE analista_id = a.id) as total_analises,
                    (SELECT COUNT(*) FROM pedidos_analise WHERE analista_id = a.id AND status = 'concluido') as analises_concluidas,
                    (SELECT COUNT(*) FROM pedidos_analise WHERE analista_id = a.id AND status = 'pendente') as analises_pendentes
                FROM usuarios u
                JOIN analistas a ON u.id = a.usuario_id
                WHERE u.id = %s AND u.tipo = 'analista'
            """, (analista_id,), fetch=True, one=True)
            
            if not analista:
                return jsonify({'error': 'Analista não encontrado'}), 404
            
            # Calcular tempo de empresa
            tempo_empresa = None
            if analista[12]:
                dias = (datetime.now().date() - analista[12]).days
                anos = dias // 365
                meses = (dias % 365) // 30
                tempo_empresa = f"{anos} anos e {meses} meses"
            
            analises = execute_query("""
                SELECT 
                    pa.id,
                    CONCAT('Pedido #', pa.id) as pedido,
                    pa.status,
                    pa.data_solicitacao,
                    pa.data_conclusao
                FROM pedidos_analise pa
                WHERE pa.analista_id = %s
                ORDER BY pa.data_solicitacao DESC
                LIMIT 5
            """, (analista_id,), fetch=True) or []
            
            return jsonify({
                'id': analista[0],
                'nome': analista[1],
                'email': analista[2],
                'ativo': analista[3],
                'criado_em': analista[4].strftime('%d/%m/%Y') if analista[4] else '',
                'especialidade': analista[5],
                'registro_profissional': analista[6] or 'Não informado',
                'telefone': analista[7] or 'Não informado',
                'is_supervisor': 'Sim' if analista[8] == 1 else 'Não',
                'status': analista[9],
                'experiencia': analista[10] or 'Não informada',
                'carga_horaria': analista[11] or 40,
                'data_contratacao': analista[12].strftime('%d/%m/%Y') if analista[12] else '',
                'data_desligamento': analista[13].strftime('%d/%m/%Y') if analista[13] else '',
                'tempo_empresa': tempo_empresa,
                'total_analises': analista[14] or 0,
                'analises_concluidas': analista[15] or 0,
                'analises_pendentes': analista[16] or 0,
                'ultimas_analises': [
                    {
                        'id': a[0],
                        'pedido': a[1],
                        'status': a[2],
                        'solicitacao': a[3].strftime('%d/%m/%Y') if a[3] else '',
                        'conclusao': a[4].strftime('%d/%m/%Y') if a[4] else ''
                    } for a in analises
                ]
            })
            
        except Exception as e:
            logger.error(f"Erro ao visualizar analista: {e}")
            return jsonify({'error': 'Erro ao carregar dados'}), 500
    
    # ---------- EXCLUIR ANALISTA ----------
    @admin_bp.route('/analistas/<int:analista_id>/excluir', methods=['POST'])
    @admin_required
    def excluir_analista(analista_id):
        """Exclui um analista"""
        try:
            analises = execute_query(
                "SELECT COUNT(*) FROM pedidos_analise WHERE analista_id = %s",
                (analista_id,), fetch=True, one=True
            )
            
            if analises and analises[0] > 0:
                execute_query(
                    "UPDATE usuarios SET ativo = FALSE WHERE id = %s",
                    (analista_id,)
                )
                execute_query(
                    "UPDATE analistas SET status = 'inativo', data_desligamento = CURDATE() WHERE usuario_id = %s",
                    (analista_id,)
                )
                flash('Analista desativado pois possui análises vinculadas.', 'warning')
                return jsonify({'success': True, 'message': 'Analista desativado'})
            else:
                execute_query(
                    "DELETE FROM analistas WHERE usuario_id = %s",
                    (analista_id,)
                )
                execute_query(
                    "DELETE FROM usuarios WHERE id = %s AND tipo = 'analista'",
                    (analista_id,)
                )
                flash('Analista excluído com sucesso!', 'success')
                return jsonify({'success': True, 'message': 'Analista excluído'})
            
        except Exception as e:
            logger.error(f"Erro ao excluir analista: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500