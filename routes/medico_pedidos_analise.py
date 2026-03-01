# routes/medico_pedidos_analise.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from flask_mysqldb import MySQL
import os
import json
from werkzeug.utils import secure_filename
from datetime import datetime
import logging
from functools import wraps
import traceback

logger = logging.getLogger(__name__)

def init_medico_pedidos_analise(mysql, app):
    """Inicializa e retorna o blueprint de pedidos de análise do médico"""
    
    pedidos_bp = Blueprint('medico', __name__, url_prefix='/medico')
    
    # ========== DECORATORS ==========
    def medico_required(f):
        """Decorator para garantir que o usuário é um médico"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session or session.get('user_type') != 'medico':
                flash('Acesso restrito a médicos.', 'warning')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated_function
    
    # ========== FUNÇÕES AUXILIARES ==========
    def execute_query(query, params=None, fetch=False, one=False):
        """Função auxiliar para executar queries no banco de dados"""
        try:
            cur = mysql.connection.cursor()
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            
            if fetch:
                result = cur.fetchall()
                cur.close()
                if one:
                    return result[0] if result else None
                return result
            else:
                mysql.connection.commit()
                cur.close()
                return None
        except Exception as e:
            mysql.connection.rollback()
            logger.error(f"Database error: {e}")
            logger.error(traceback.format_exc())
            return None
    
    def allowed_file(filename):
        """Verifica se o arquivo é permitido"""
        ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'pdf', 'doc', 'docx', 'txt'}
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    
    def formatar_data(data, formato='%d/%m/%Y %H:%M'):
        """Formata data de forma segura"""
        if isinstance(data, datetime):
            return data.strftime(formato)
        elif isinstance(data, str):
            try:
                if 'T' in data:
                    return datetime.fromisoformat(data.replace('Z', '+00:00')).strftime(formato)
                else:
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                        try:
                            return datetime.strptime(data, fmt).strftime(formato)
                        except ValueError:
                            continue
                    return data
            except:
                return data
        return str(data)
    
    # ========== ROTAS DE PEDIDOS DE ANÁLISE ==========
    
    @pedidos_bp.route('/pedidos-analise')
    @medico_required
    def pedidos_analise():
        """Listar pedidos de análise do médico"""
        # Obter filtros da URL
        status_filter = request.args.get('status', '')
        urgencia_filter = request.args.get('urgencia', '')
        aprovacao_filter = request.args.get('status_aprovacao', '')
        
        # Construir query base
        query = """
            SELECT pa.*, 
                   p_u.nome as paciente_nome,
                   c.data_hora as data_consulta,
                   u.nome as analista_nome
            FROM pedidos_analise pa
            JOIN pacientes p ON pa.paciente_id = p.id
            JOIN usuarios p_u ON p.usuario_id = p_u.id
            JOIN consultas c ON pa.consulta_id = c.id
            LEFT JOIN usuarios u ON pa.analista_id = u.id
            WHERE pa.medico_id = (
                SELECT id FROM medicos WHERE usuario_id = %s
            )
        """
        
        params = [session['user_id']]
        
        # Adicionar filtros
        conditions = []
        if status_filter:
            conditions.append("pa.status = %s")
            params.append(status_filter)
        
        if urgencia_filter:
            conditions.append("pa.urgencia = %s")
            params.append(urgencia_filter)
        
        if aprovacao_filter:
            conditions.append("pa.status_aprovacao = %s")
            params.append(aprovacao_filter)
        
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        # Ordenação
        query += """
            ORDER BY 
                CASE pa.urgencia 
                    WHEN 'urgente' THEN 1
                    WHEN 'alta' THEN 2
                    WHEN 'normal' THEN 3
                    ELSE 4
                END,
                pa.data_solicitacao DESC
        """
        
        pedidos = execute_query(query, params, fetch=True)
        
        # Converter para lista de dicionários para facilitar no template
        pedidos_formatados = []
        for pedido in pedidos:
            pedidos_formatados.append({
                'id': pedido[0],
                'consulta_id': pedido[1],
                'medico_id': pedido[2],
                'paciente_id': pedido[3],
                'analista_id': pedido[4],
                'tipo_exame': pedido[5],
                'descricao': pedido[6],
                'observacoes': pedido[7],
                'urgencia': pedido[8],
                'status': pedido[9],
                'data_solicitacao': pedido[10],
                'data_conclusao': pedido[11],
                'resultado_analise': pedido[12],
                'diagnostico_analista': pedido[13],
                'recomendacoes_analista': pedido[14],
                'anexos': pedido[15],
                'status_aprovacao': pedido[16],
                'observacoes_medico': pedido[17],
                'paciente_nome': pedido[18],
                'data_consulta': pedido[19],
                'analista_nome': pedido[20]
            })
        
        return render_template('medico/pedidos_analise.html', 
                             pedidos=pedidos_formatados,
                             user=session)
    
    @pedidos_bp.route('/nova-analise')
    @medico_required
    def nova_analise():
        """Página para selecionar consulta para nova análise"""
        # Buscar consultas disponíveis para pedido de análise
        consultas = execute_query("""
            SELECT c.id, p_u.nome as paciente_nome, 
                   c.data_hora, c.status
            FROM consultas c
            JOIN pacientes p ON c.paciente_id = p.id
            JOIN usuarios p_u ON p.usuario_id = p_u.id
            WHERE c.medico_id = (SELECT id FROM medicos WHERE usuario_id = %s)
            AND c.status IN ('agendada', 'realizada')
            AND NOT EXISTS (
                SELECT 1 FROM pedidos_analise pa 
                WHERE pa.consulta_id = c.id 
                AND pa.status IN ('pendente', 'em_analise')
            )
            ORDER BY c.data_hora DESC
        """, (session['user_id'],), fetch=True)
        
        return render_template('medico/nova_analise.html', 
                             consultas=consultas,
                             user=session)
    
    @pedidos_bp.route('/solicitar-analise/<int:consulta_id>', methods=['GET', 'POST'])
    @medico_required
    def solicitar_analise(consulta_id):
        """Solicitar análise de exames para um analista"""
        # Verificar se a consulta pertence ao médico
        consulta = execute_query("""
            SELECT c.*, p.id as paciente_id, p_u.nome as paciente_nome,
                   p.data_nascimento, p.genero, p.endereco, p.telefone
            FROM consultas c
            JOIN pacientes p ON c.paciente_id = p.id
            JOIN usuarios p_u ON p.usuario_id = p_u.id
            WHERE c.id = %s AND c.medico_id = (
                SELECT id FROM medicos WHERE usuario_id = %s
            )
        """, (consulta_id, session['user_id']), fetch=True, one=True)
        
        if not consulta:
            flash('Consulta não encontrada ou não pertence a você.', 'danger')
            return redirect(url_for('medico.nova_analise'))
        
        # Obter informações do médico
        medico_info = execute_query("""
            SELECT id, especialidade, crm FROM medicos 
            WHERE usuario_id = %s
        """, (session['user_id'],), fetch=True, one=True)
        
        if not medico_info:
            flash('Informações do médico não encontradas.', 'danger')
            return redirect(url_for('medico.nova_analise'))
        
        # Obter analistas disponíveis (usuários com tipo 'analista')
        analistas = execute_query("""
            SELECT u.id, u.nome, u.email 
            FROM usuarios u
            WHERE u.tipo = 'analista' AND u.ativo = 1
            ORDER BY u.nome
        """, fetch=True)
        
        # Buscar histórico de exames do paciente
        historico_exames = execute_query("""
            SELECT pa.tipo_exame, pa.status, pa.data_solicitacao
            FROM pedidos_analise pa
            WHERE pa.paciente_id = %s
            ORDER BY pa.data_solicitacao DESC
            LIMIT 5
        """, (consulta[7],), fetch=True)  # consulta[7] é o paciente_id
        
        if request.method == 'POST':
            try:
                tipo_exame = request.form.get('tipo_exame', '').strip()
                descricao = request.form.get('descricao', '').strip()
                observacoes = request.form.get('observacoes', '').strip()
                urgencia = request.form.get('urgencia', 'normal')
                status_aprovacao = request.form.get('status_aprovacao', 'pendente')
                observacoes_medico = request.form.get('observacoes_medico', '').strip()
                analista_id = request.form.get('analista_id') or None
                
                # Validações
                if not tipo_exame:
                    flash('Tipo de exame é obrigatório.', 'danger')
                    return redirect(url_for('medico.solicitar_analise', consulta_id=consulta_id))
                
                if not descricao:
                    flash('Descrição do exame é obrigatória.', 'danger')
                    return redirect(url_for('medico.solicitar_analise', consulta_id=consulta_id))
                
                # Verificar se já existe pedido para esta consulta
                pedido_existente = execute_query("""
                    SELECT id FROM pedidos_analise 
                    WHERE consulta_id = %s AND status IN ('pendente', 'em_analise')
                """, (consulta_id,), fetch=True, one=True)
                
                if pedido_existente:
                    flash('Já existe um pedido de análise pendente para esta consulta.', 'warning')
                    return redirect(url_for('medico.pedidos_analise'))
                
                # Processar anexos
                anexos = []
                if 'anexos[]' in request.files:
                    files = request.files.getlist('anexos[]')
                    upload_folder = app.config.get('UPLOAD_FOLDER', 'static/uploads')
                    
                    # Criar pasta de uploads se não existir
                    if not os.path.exists(upload_folder):
                        os.makedirs(upload_folder)
                    
                    for file in files:
                        if file and file.filename and allowed_file(file.filename):
                            filename = secure_filename(file.filename)
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            unique_filename = f"{timestamp}_{filename}"
                            filepath = os.path.join(upload_folder, unique_filename)
                            
                            try:
                                file.save(filepath)
                                anexos.append({
                                    'nome': filename,
                                    'nome_arquivo': unique_filename,
                                    'tamanho': os.path.getsize(filepath),
                                    'tipo': file.content_type,
                                    'caminho': filepath,
                                    'url': f'/static/uploads/{unique_filename}'
                                })
                            except Exception as e:
                                logger.error(f"Erro ao salvar arquivo {filename}: {e}")
                
                # Criar pedido de análise
                result = execute_query("""
                    INSERT INTO pedidos_analise 
                    (consulta_id, medico_id, paciente_id, analista_id,
                     tipo_exame, descricao, observacoes, urgencia, 
                     status, status_aprovacao, observacoes_medico, anexos)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pendente', %s, %s, %s)
                """, (
                    consulta_id,
                    medico_info[0],  # ID do médico
                    consulta[7],     # paciente_id
                    analista_id,
                    tipo_exame,
                    descricao,
                    observacoes,
                    urgencia,
                    status_aprovacao,
                    observacoes_medico,
                    json.dumps(anexos) if anexos else None
                ))
                
                if result is None:
                    flash('Erro ao criar pedido de análise. Tente novamente.', 'danger')
                    return redirect(url_for('medico.solicitar_analise', consulta_id=consulta_id))
                
                flash('Pedido de análise criado com sucesso!', 'success')
                
                # Log da ação
                try:
                    execute_query("""
                        INSERT INTO logs (usuario_id, acao, detalhes)
                        VALUES (%s, %s, %s)
                    """, (
                        session['user_id'],
                        'pedido_analise_criado',
                        json.dumps({
                            'pedido_id': consulta_id,
                            'tipo_exame': tipo_exame,
                            'urgencia': urgencia,
                            'paciente_id': consulta[7]
                        })
                    ))
                except Exception as e:
                    logger.error(f"Erro ao criar log: {e}")
                
                return redirect(url_for('medico.pedidos_analise'))
                
            except Exception as e:
                logger.error(f"Erro ao processar solicitação de análise: {e}")
                logger.error(traceback.format_exc())
                flash(f'Erro ao processar solicitação: {str(e)}', 'danger')
                return redirect(url_for('medico.solicitar_analise', consulta_id=consulta_id))
        
        # Formatar dados da consulta para o template
        consulta_dict = {
            'id': consulta[0],
            'paciente_id': consulta[1],
            'medico_id': consulta[2],
            'data_hora': consulta[3],
            'status': consulta[4],
            'observacoes': consulta[5],
            'paciente_nome': consulta[9],
            'paciente_data_nascimento': consulta[10],
            'paciente_genero': consulta[11],
            'paciente_endereco': consulta[12],
            'paciente_telefone': consulta[13]
        }
        
        return render_template('medico/solicitar_analise.html', 
                             consulta=consulta_dict,
                             analistas=analistas or [],
                             historico_exames=historico_exames or [],
                             user=session)
    
    @pedidos_bp.route('/revisar-analise/<int:pedido_id>', methods=['GET', 'POST'])
    @medico_required
    def revisar_analise(pedido_id):
        """Revisar análise feita pelo analista"""
        pedido = execute_query("""
            SELECT pa.*, 
                   p_u.nome as paciente_nome, p.data_nascimento, p.genero,
                   c.data_hora as data_consulta, c.observacoes as obs_consulta,
                   u.nome as analista_nome,
                   m.especialidade, m.crm
            FROM pedidos_analise pa
            JOIN pacientes p ON pa.paciente_id = p.id
            JOIN usuarios p_u ON p.usuario_id = p_u.id
            JOIN consultas c ON pa.consulta_id = c.id
            LEFT JOIN usuarios u ON pa.analista_id = u.id
            JOIN medicos m ON pa.medico_id = m.id
            WHERE pa.id = %s AND pa.medico_id = (
                SELECT id FROM medicos WHERE usuario_id = %s
            )
        """, (pedido_id, session['user_id']), fetch=True, one=True)
        
        if not pedido:
            flash('Pedido não encontrado ou não pertence a você.', 'danger')
            return redirect(url_for('medico.pedidos_analise'))
        
        # Converter anexos de JSON para lista
        anexos = []
        if pedido[15]:  # campo anexos
            try:
                anexos = json.loads(pedido[15])
            except:
                anexos = []
        
        if request.method == 'POST':
            try:
                acao = request.form.get('acao')
                observacoes_medico = request.form.get('observacoes_medico', '').strip()
                
                if acao == 'aprovar':
                    # Aprovar análise
                    execute_query("""
                        UPDATE pedidos_analise 
                        SET status_aprovacao = 'aprovado',
                            observacoes_medico = %s,
                            atualizado_em = NOW()
                        WHERE id = %s
                    """, (observacoes_medico, pedido_id))
                    
                    # Atualizar consulta com diagnóstico aprovado
                    execute_query("""
                        UPDATE consultas 
                        SET diagnostico_final = %s,
                            data_diagnostico = NOW(),
                            status = 'realizada',
                            atualizado_em = NOW()
                        WHERE id = %s
                    """, (pedido[13], pedido[1]))  # diagnostico_analista, consulta_id
                    
                    flash('Análise aprovada com sucesso!', 'success')
                    
                elif acao == 'rejeitar':
                    # Rejeitar análise
                    execute_query("""
                        UPDATE pedidos_analise 
                        SET status_aprovacao = 'rejeitado',
                            observacoes_medico = %s,
                            status = 'pendente',
                            analista_id = NULL,
                            atualizado_em = NOW()
                        WHERE id = %s
                    """, (observacoes_medico, pedido_id))
                    
                    flash('Análise rejeitada. O pedido foi reaberto para nova análise.', 'warning')
                
                elif acao == 'ajustar':
                    # Ajustar manualmente
                    diagnostico_ajustado = request.form.get('diagnostico_ajustado', '').strip()
                    if diagnostico_ajustado:
                        execute_query("""
                            UPDATE pedidos_analise 
                            SET diagnostico_analista = %s,
                                status_aprovacao = 'ajustado',
                                observacoes_medico = %s,
                                atualizado_em = NOW()
                            WHERE id = %s
                        """, (diagnostico_ajustado, observacoes_medico, pedido_id))
                        
                        # Atualizar consulta
                        execute_query("""
                            UPDATE consultas 
                            SET diagnostico_final = %s,
                                data_diagnostico = NOW(),
                                status = 'realizada',
                                atualizado_em = NOW()
                            WHERE id = %s
                        """, (diagnostico_ajustado, pedido[1]))
                        
                        flash('Diagnóstico ajustado e aprovado com sucesso.', 'success')
                    else:
                        flash('Diagnóstico ajustado não pode estar vazio.', 'danger')
                        return redirect(url_for('medico.revisar_analise', pedido_id=pedido_id))
                
                # Log da ação
                try:
                    execute_query("""
                        INSERT INTO logs (usuario_id, acao, detalhes)
                        VALUES (%s, %s, %s)
                    """, (
                        session['user_id'],
                        f'pedido_analise_{acao}',
                        json.dumps({
                            'pedido_id': pedido_id,
                            'consulta_id': pedido[1],
                            'paciente_id': pedido[3]
                        })
                    ))
                except Exception as e:
                    logger.error(f"Erro ao criar log: {e}")
                
                return redirect(url_for('medico.pedidos_analise'))
                
            except Exception as e:
                logger.error(f"Erro ao processar revisão de análise: {e}")
                logger.error(traceback.format_exc())
                flash(f'Erro ao processar revisão: {str(e)}', 'danger')
                return redirect(url_for('medico.revisar_analise', pedido_id=pedido_id))
        
        # Formatar dados do pedido para o template
        pedido_dict = {
            'id': pedido[0],
            'consulta_id': pedido[1],
            'medico_id': pedido[2],
            'paciente_id': pedido[3],
            'analista_id': pedido[4],
            'tipo_exame': pedido[5],
            'descricao': pedido[6],
            'observacoes': pedido[7],
            'urgencia': pedido[8],
            'status': pedido[9],
            'data_solicitacao': pedido[10],
            'data_conclusao': pedido[11],
            'resultado_analise': pedido[12],
            'diagnostico_analista': pedido[13],
            'recomendacoes_analista': pedido[14],
            'anexos': anexos,
            'status_aprovacao': pedido[16],
            'observacoes_medico': pedido[17],
            'paciente_nome': pedido[18],
            'paciente_data_nascimento': pedido[19],
            'paciente_genero': pedido[20],
            'data_consulta': pedido[21],
            'obs_consulta': pedido[22],
            'analista_nome': pedido[23],
            'especialidade': pedido[24],
            'crm': pedido[25]
        }
        
        return render_template('medico/revisar_analise.html', 
                             pedido=pedido_dict,
                             anexos=anexos,
                             user=session)
    
    @pedidos_bp.route('/cancelar-pedido/<int:pedido_id>', methods=['POST'])
    @medico_required
    def cancelar_pedido(pedido_id):
        """Cancelar um pedido de análise"""
        # Verificar se o pedido pertence ao médico
        pedido = execute_query("""
            SELECT id, status FROM pedidos_analise 
            WHERE id = %s AND medico_id = (
                SELECT id FROM medicos WHERE usuario_id = %s
            )
        """, (pedido_id, session['user_id']), fetch=True, one=True)
        
        if not pedido:
            flash('Pedido não encontrado ou não pertence a você.', 'danger')
            return redirect(url_for('medico.pedidos_analise'))
        
        # Verificar se pode ser cancelado
        if pedido[1] not in ['pendente', 'em_analise']:
            flash('Este pedido não pode ser cancelado no seu estado atual.', 'warning')
            return redirect(url_for('medico.pedidos_analise'))
        
        try:
            # Cancelar pedido
            execute_query("""
                UPDATE pedidos_analise 
                SET status = 'cancelado',
                    atualizado_em = NOW()
                WHERE id = %s
            """, (pedido_id,))
            
            # Log da ação
            execute_query("""
                INSERT INTO logs (usuario_id, acao, detalhes)
                VALUES (%s, %s, %s)
            """, (
                session['user_id'],
                'pedido_analise_cancelado',
                json.dumps({'pedido_id': pedido_id})
            ))
            
            flash('Pedido cancelado com sucesso!', 'success')
            
        except Exception as e:
            logger.error(f"Erro ao cancelar pedido: {e}")
            flash('Erro ao cancelar pedido. Tente novamente.', 'danger')
        
        return redirect(url_for('medico.pedidos_analise'))
    
    @pedidos_bp.route('/gerar-receita/<int:consulta_id>')
    @medico_required
    def gerar_receita(consulta_id):
        """Gerar receita médica baseada no diagnóstico aprovado"""
        # Verificar se a consulta pertence ao médico
        consulta = execute_query("""
            SELECT c.*, p_u.nome as paciente_nome, 
                   p.data_nascimento, p.genero, p.endereco
            FROM consultas c
            JOIN pacientes p ON c.paciente_id = p.id
            JOIN usuarios p_u ON p.usuario_id = p_u.id
            WHERE c.id = %s AND c.medico_id = (
                SELECT id FROM medicos WHERE usuario_id = %s
            )
        """, (consulta_id, session['user_id']), fetch=True, one=True)
        
        if not consulta:
            flash('Consulta não encontrada.', 'danger')
            return redirect(url_for('medico.pedidos_analise'))
        
        # Buscar diagnóstico aprovado mais recente
        diagnostico = execute_query("""
            SELECT diagnostico_analista, recomendacoes_analista 
            FROM pedidos_analise 
            WHERE consulta_id = %s 
            AND status_aprovacao IN ('aprovado', 'ajustado')
            ORDER BY data_conclusao DESC 
            LIMIT 1
        """, (consulta_id,), fetch=True, one=True)
        
        # Se não houver diagnóstico aprovado, usar diagnóstico da consulta
        if not diagnostico:
            diagnostico_db = execute_query("""
                SELECT diagnostico_final FROM consultas 
                WHERE id = %s
            """, (consulta_id,), fetch=True, one=True)
            if diagnostico_db:
                diagnostico = (diagnostico_db[0], '')
        
        # Buscar informações do médico
        medico_info = execute_query("""
            SELECT especialidade, crm FROM medicos 
            WHERE usuario_id = %s
        """, (session['user_id'],), fetch=True, one=True)
        
        # Buscar medicamentos disponíveis
        medicamentos = execute_query("""
            SELECT id, nome, principio_ativo, dosagem, tipo 
            FROM medicamentos 
            ORDER BY nome
        """, fetch=True)
        
        return render_template('medico/gerar_receita.html',
                             consulta=consulta,
                             diagnostico=diagnostico,
                             medico_info=medico_info,
                             medicamentos=medicamentos or [],
                             user=session)
    
    @pedidos_bp.route('/api/pedidos/estatisticas')
    @medico_required
    def api_pedidos_estatisticas():
        """API para estatísticas de pedidos de análise"""
        try:
            # Total de pedidos por status
            pedidos_por_status = execute_query("""
                SELECT status, COUNT(*) as quantidade
                FROM pedidos_analise 
                WHERE medico_id = (SELECT id FROM medicos WHERE usuario_id = %s)
                GROUP BY status
            """, (session['user_id'],), fetch=True)
            
            # Pedidos urgentes pendentes
            urgentes_pendentes = execute_query("""
                SELECT COUNT(*) 
                FROM pedidos_analise 
                WHERE medico_id = (SELECT id FROM medicos WHERE usuario_id = %s)
                AND urgencia IN ('urgente', 'alta')
                AND status IN ('pendente', 'em_analise')
            """, (session['user_id'],), fetch=True, one=True)
            
            # Pedidos concluídos aguardando revisão
            aguardando_revisao = execute_query("""
                SELECT COUNT(*) 
                FROM pedidos_analise 
                WHERE medico_id = (SELECT id FROM medicos WHERE usuario_id = %s)
                AND status = 'concluido'
                AND status_aprovacao = 'pendente'
            """, (session['user_id'],), fetch=True, one=True)
            
            # Tempo médio de conclusão (apenas pedidos concluídos)
            tempo_medio = execute_query("""
                SELECT AVG(TIMESTAMPDIFF(HOUR, data_solicitacao, data_conclusao))
                FROM pedidos_analise 
                WHERE medico_id = (SELECT id FROM medicos WHERE usuario_id = %s)
                AND status = 'concluido'
                AND data_solicitacao IS NOT NULL
                AND data_conclusao IS NOT NULL
            """, (session['user_id'],), fetch=True, one=True)
            
            # Converter resultados
            status_dict = {}
            for status, quantidade in pedidos_por_status:
                status_dict[status] = quantidade
            
            return jsonify({
                'status': status_dict,
                'urgentes_pendentes': urgentes_pendentes[0] if urgentes_pendentes else 0,
                'aguardando_revisao': aguardando_revisao[0] if aguardando_revisao else 0,
                'tempo_medio_horas': round(tempo_medio[0], 2) if tempo_medio and tempo_medio[0] else 0
            })
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            return jsonify({'error': str(e)}), 500
    
    @pedidos_bp.route('/api/pedidos/ultimos')
    @medico_required
    def api_pedidos_ultimos():
        """API para últimos pedidos de análise"""
        try:
            pedidos = execute_query("""
                SELECT pa.id, pa.tipo_exame, pa.status, pa.data_solicitacao,
                       p_u.nome as paciente_nome, pa.status_aprovacao,
                       pa.urgencia
                FROM pedidos_analise pa
                JOIN pacientes p ON pa.paciente_id = p.id
                JOIN usuarios p_u ON p.usuario_id = p_u.id
                WHERE pa.medico_id = (SELECT id FROM medicos WHERE usuario_id = %s)
                ORDER BY pa.data_solicitacao DESC
                LIMIT 10
            """, (session['user_id'],), fetch=True)
            
            # Converter para dicionário
            pedidos_dict = []
            for pedido in pedidos:
                pedidos_dict.append({
                    'id': pedido[0],
                    'tipo_exame': pedido[1],
                    'status': pedido[2],
                    'data_solicitacao': pedido[3].strftime('%d/%m/%Y %H:%M') if pedido[3] else '',
                    'paciente_nome': pedido[4],
                    'status_aprovacao': pedido[5],
                    'urgencia': pedido[6]
                })
            
            return jsonify({'pedidos': pedidos_dict})
            
        except Exception as e:
            logger.error(f"Erro ao obter últimos pedidos: {e}")
            return jsonify({'error': str(e)}), 500
    
    return pedidos_bp