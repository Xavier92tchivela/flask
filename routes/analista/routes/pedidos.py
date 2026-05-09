"""Rotas de pedidos para analista"""
from flask import render_template, session, flash, redirect, url_for, request, send_file, jsonify
import os
import json
import logging
import traceback
from datetime import datetime 

logger = logging.getLogger(__name__)

def register_pedidos_routes(bp, analista_required, execute_query, formatar_data, calcular_idade):
    
    # ===== FUNÇÃO AUXILIAR PARA CONVERTER BYTES =====
    def garantir_string(valor):
        """Converte qualquer valor para string, especialmente bytes"""
        if valor is None:
            return ''
        if isinstance(valor, bytes):
            try:
                return valor.decode('utf-8')
            except:
                return str(valor)
        if isinstance(valor, (int, float)):
            return str(valor)
        return str(valor) if valor is not None else ''
    
    @bp.route('/pedidos')
    @analista_required
    def pedidos():
        """Lista todos os pedidos do analista"""
        try:
            user_id = session.get('user_id')
            
            analista_info = execute_query("""
                SELECT a.id FROM analistas a
                WHERE a.usuario_id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                flash('Perfil de analista não encontrado.', 'danger')
                return redirect(url_for('auth.login'))
            
            if isinstance(analista_info, dict):
                analista_id = analista_info.get('id')
            else:
                analista_id = analista_info[0] if len(analista_info) > 0 else None
            
            if not analista_id:
                flash('ID do analista não encontrado.', 'danger')
                return redirect(url_for('auth.login'))
            
            # Filtros
            status_filter = request.args.get('status', '')
            urgencia_filter = request.args.get('urgencia', '')
            
            query = """
                SELECT 
                    pa.id, 
                    pa.tipo_exame, 
                    pa.urgencia, 
                    pa.status, 
                    pa.data_solicitacao,
                    pa.data_conclusao, 
                    pa.descricao, 
                    pa.observacoes,
                    COALESCE(u.nome, 'Não informado') as paciente_nome, 
                    p.data_nascimento, 
                    COALESCE(p.genero, '') as genero,
                    COALESCE(m_u.nome, 'Não informado') as medico_nome, 
                    COALESCE(m.especialidade, '') as medico_especialidade,
                    pa.resultado_analise,
                    pa.diagnostico_analista,
                    pa.recomendacoes_analista
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                LEFT JOIN medicos m ON pa.medico_id = m.id
                LEFT JOIN usuarios m_u ON m.usuario_id = m_u.id
                WHERE pa.analista_id = %s OR pa.analista_id IS NULL
            """
            
            params = [analista_id]
            
            if status_filter:
                query += " AND pa.status = %s"
                params.append(status_filter)
            
            if urgencia_filter:
                query += " AND pa.urgencia = %s"
                params.append(urgencia_filter)
            
            query += " ORDER BY pa.data_solicitacao DESC"
            
            pedidos_db = execute_query(query, params, fetch=True)
            
            pedidos_list = []
            if pedidos_db:
                for pedido in pedidos_db:
                    if isinstance(pedido, dict):
                        data_nascimento = pedido.get('data_nascimento')
                        idade = calcular_idade(data_nascimento) if data_nascimento else ''
                        
                        pedidos_list.append({
                            'id': pedido.get('id'),
                            'tipo_exame': garantir_string(pedido.get('tipo_exame')) or 'Não especificado',
                            'urgencia': garantir_string(pedido.get('urgencia')) or 'normal',
                            'status': garantir_string(pedido.get('status')) or 'pendente',
                            'data_solicitacao': formatar_data(pedido.get('data_solicitacao')),
                            'data_conclusao': formatar_data(pedido.get('data_conclusao')),
                            'descricao': garantir_string(pedido.get('descricao')),
                            'observacoes': garantir_string(pedido.get('observacoes')),
                            'paciente_nome': garantir_string(pedido.get('paciente_nome')),
                            'paciente_data_nascimento': formatar_data(pedido.get('data_nascimento'), '%d/%m/%Y') if pedido.get('data_nascimento') else '',
                            'paciente_idade': idade,
                            'paciente_genero': garantir_string(pedido.get('genero')),
                            'medico_nome': garantir_string(pedido.get('medico_nome')),
                            'medico_especialidade': garantir_string(pedido.get('medico_especialidade')),
                            'resultado_analise': garantir_string(pedido.get('resultado_analise')),
                            'diagnostico_analista': garantir_string(pedido.get('diagnostico_analista')),
                            'recomendacoes_analista': garantir_string(pedido.get('recomendacoes_analista'))
                        })
                    else:
                        idade = calcular_idade(pedido[9]) if len(pedido) > 9 and pedido[9] else ''
                        
                        pedidos_list.append({
                            'id': pedido[0] if len(pedido) > 0 else None,
                            'tipo_exame': garantir_string(pedido[1]) if len(pedido) > 1 else 'Não especificado',
                            'urgencia': garantir_string(pedido[2]) if len(pedido) > 2 else 'normal',
                            'status': garantir_string(pedido[3]) if len(pedido) > 3 else 'pendente',
                            'data_solicitacao': formatar_data(pedido[4]) if len(pedido) > 4 else None,
                            'data_conclusao': formatar_data(pedido[5]) if len(pedido) > 5 else None,
                            'descricao': garantir_string(pedido[6]) if len(pedido) > 6 else '',
                            'observacoes': garantir_string(pedido[7]) if len(pedido) > 7 else '',
                            'paciente_nome': garantir_string(pedido[8]) if len(pedido) > 8 else 'Não informado',
                            'paciente_data_nascimento': formatar_data(pedido[9], '%d/%m/%Y') if len(pedido) > 9 and pedido[9] else '',
                            'paciente_idade': idade,
                            'paciente_genero': garantir_string(pedido[10]) if len(pedido) > 10 else '',
                            'medico_nome': garantir_string(pedido[11]) if len(pedido) > 11 else 'Não informado',
                            'medico_especialidade': garantir_string(pedido[12]) if len(pedido) > 12 else '',
                            'resultado_analise': garantir_string(pedido[13]) if len(pedido) > 13 else '',
                            'diagnostico_analista': garantir_string(pedido[14]) if len(pedido) > 14 else '',
                            'recomendacoes_analista': garantir_string(pedido[15]) if len(pedido) > 15 else ''
                        })
            
            print(f"[DEBUG] Pedidos encontrados: {len(pedidos_list)}")
            
            return render_template('analista/pedidos.html',
                                 user=session,
                                 pedidos=pedidos_list,
                                 status_filter=status_filter,
                                 urgencia_filter=urgencia_filter,
                                 now=datetime.now())
            
        except Exception as e:
            logger.error(f"❌ Erro ao listar pedidos: {e}")
            logger.error(traceback.format_exc())
            flash('Erro ao carregar pedidos.', 'danger')
            return render_template('analista/pedidos.html', 
                                 user=session, 
                                 pedidos=[], 
                                 status_filter='', 
                                 urgencia_filter='',
                                 now=datetime.now())

    # ========== ROTA: DOWNLOAD DE ANEXOS (USANDO JSON) ==========
    @bp.route('/pedidos/<int:pedido_id>/anexo/<int:anexo_index>')
    @analista_required
    def download_anexo(pedido_id, anexo_index):
        """Download de anexo do pedido - usando coluna JSON"""
        try:
            user_id = session.get('user_id')
            
            analista_info = execute_query("""
                SELECT a.id FROM analistas a
                WHERE a.usuario_id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                return jsonify({'error': 'Analista não encontrado'}), 404
            
            if isinstance(analista_info, dict):
                analista_id = analista_info.get('id')
            else:
                analista_id = analista_info[0] if len(analista_info) > 0 else None
            
            # Verificar permissão
            pedido = execute_query("""
                SELECT analista_id, anexos FROM pedidos_analise 
                WHERE id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido:
                return jsonify({'error': 'Pedido não encontrado'}), 404
            
            pedido_analista = pedido.get('analista_id') if isinstance(pedido, dict) else pedido[0]
            
            if pedido_analista is not None and pedido_analista != 0 and pedido_analista != analista_id:
                return jsonify({'error': 'Acesso negado'}), 403
            
            # Buscar anexos do JSON
            anexos_json = pedido.get('anexos') if isinstance(pedido, dict) else pedido[1] if len(pedido) > 1 else None
            
            if not anexos_json:
                return jsonify({'error': 'Nenhum anexo encontrado'}), 404
            
            # Converter para lista se for string JSON
            if isinstance(anexos_json, str):
                try:
                    anexos_lista = json.loads(anexos_json)
                except:
                    return jsonify({'error': 'Erro ao processar anexos'}), 500
            else:
                anexos_lista = anexos_json
            
            if not isinstance(anexos_lista, list):
                return jsonify({'error': 'Formato de anexos inválido'}), 500
            
            if anexo_index >= len(anexos_lista):
                return jsonify({'error': 'Anexo não encontrado'}), 404
            
            anexo = anexos_lista[anexo_index]
            
            # Obter informações do anexo
            anexo_filename = anexo.get('filename') if isinstance(anexo, dict) else anexo[0] if isinstance(anexo, (list, tuple)) else None
            anexo_nome = anexo.get('original_name') if isinstance(anexo, dict) else anexo[1] if len(anexo) > 1 else anexo_filename
            anexo_tipo = anexo.get('tipo') if isinstance(anexo, dict) else anexo[2] if len(anexo) > 2 else 'application/octet-stream'
            
            if not anexo_filename:
                return jsonify({'error': 'Arquivo não encontrado'}), 404
            
            # Buscar arquivo no sistema
            from ..file_utils import get_pedido_anexo_path
            filepath = get_pedido_anexo_path(anexo_filename)
            
            if not os.path.exists(filepath):
                return jsonify({'error': 'Arquivo não encontrado no servidor'}), 404
            
            return send_file(
                filepath,
                as_attachment=True,
                download_name=anexo_nome or anexo_filename,
                mimetype=anexo_tipo or 'application/octet-stream'
            )
            
        except Exception as e:
            logger.error(f"❌ Erro no download: {e}")
            logger.error(traceback.format_exc())
            return jsonify({'error': str(e)}), 500

    # ========== ROTA: PROXIMO PEDIDO ==========
    @bp.route('/proximo-pedido')
    @analista_required
    def proximo_pedido():
        """Atribui o próximo pedido pendente ao analista"""
        try:
            print("[DEBUG] Acessando proximo pedido")
            user_id = session.get('user_id')
            
            analista_info = execute_query("""
                SELECT a.id FROM analistas a
                WHERE a.usuario_id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                flash('Perfil de analista não encontrado.', 'danger')
                return redirect(url_for('auth.login'))
            
            if isinstance(analista_info, dict):
                analista_id = analista_info.get('id')
            else:
                analista_id = analista_info[0] if len(analista_info) > 0 else None
            
            if not analista_id:
                flash('ID do analista não encontrado.', 'danger')
                return redirect(url_for('analista.pedidos'))
            
            # Buscar próximo pedido pendente
            pedido = execute_query("""
                SELECT id FROM pedidos_analise 
                WHERE (analista_id IS NULL OR analista_id = 0)
                AND status = 'pendente'
                ORDER BY 
                    CASE urgencia 
                        WHEN 'urgente' THEN 1
                        WHEN 'alta' THEN 2
                        WHEN 'normal' THEN 3
                        ELSE 4
                    END,
                    data_solicitacao ASC
                LIMIT 1
            """, fetch=True, one=True)
            
            if not pedido:
                flash('Não há pedidos pendentes disponíveis.', 'info')
                return redirect(url_for('analista.pedidos'))
            
            pedido_id = pedido['id'] if isinstance(pedido, dict) else pedido[0]
            
            # Atribuir pedido ao analista
            execute_query("""
                UPDATE pedidos_analise 
                SET analista_id = %s, 
                    status = 'em_analise', 
                    atualizado_em = NOW()
                WHERE id = %s
            """, (analista_id, pedido_id), commit=True)
            
            flash(f'Pedido #{pedido_id} atribuído a você!', 'success')
            return redirect(url_for('analista.analisar_pedido', pedido_id=pedido_id))
            
        except Exception as e:
            logger.error(f"[ERRO] proximo_pedido: {e}")
            logger.error(traceback.format_exc())
            flash('Erro ao buscar próximo pedido.', 'danger')
            return redirect(url_for('analista.pedidos'))

    # ========== ROTA: VER DETALHES DO PEDIDO ==========
    @bp.route('/pedido/<int:pedido_id>')
    @analista_required
    def ver_detalhes_pedido(pedido_id):
        """Visualiza detalhes de um pedido específico"""
        try:
            logger.info(f"Visualizando detalhes do pedido #{pedido_id}")
            
            user_id = session.get('user_id')
            
            analista_info = execute_query("""
                SELECT a.id FROM analistas a
                WHERE a.usuario_id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                flash('Perfil de analista não encontrado.', 'danger')
                return redirect(url_for('auth.login'))
            
            if isinstance(analista_info, dict):
                analista_id = analista_info.get('id')
            else:
                analista_id = analista_info[0] if len(analista_info) > 0 else None
            
            # Buscar detalhes do pedido
            pedido = execute_query("""
                SELECT 
                    pa.id,
                    pa.paciente_id,
                    pa.medico_id,
                    pa.tipo_exame,
                    pa.descricao,
                    pa.observacoes,
                    pa.urgencia,
                    pa.status,
                    pa.data_solicitacao,
                    pa.data_conclusao,
                    pa.resultado_analise,
                    pa.diagnostico_analista,
                    pa.recomendacoes_analista,
                    pa.analista_id,
                    pa.status_aprovacao,
                    pa.observacoes_medico,
                    pa.consulta_id,
                    COALESCE(u.nome, 'Não informado') as paciente_nome,
                    p.data_nascimento,
                    COALESCE(p.genero, '') as paciente_genero,
                    COALESCE(p.telefone, '') as paciente_telefone,
                    COALESCE(p.endereco, '') as paciente_endereco,
                    COALESCE(m_u.nome, 'Não informado') as medico_nome,
                    COALESCE(m.especialidade, '') as medico_especialidade,
                    COALESCE(m.crm, '') as medico_crm,
                    COALESCE(a_u.nome, 'Não atribuído') as analista_nome,
                    c.data_hora as data_consulta,
                    c.observacoes as observacoes_consulta,
                    pa.anexos
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                LEFT JOIN medicos m ON pa.medico_id = m.id
                LEFT JOIN usuarios m_u ON m.usuario_id = m_u.id
                LEFT JOIN analistas a ON pa.analista_id = a.id
                LEFT JOIN usuarios a_u ON a.usuario_id = a_u.id
                LEFT JOIN consultas c ON pa.consulta_id = c.id
                WHERE pa.id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido:
                flash('Pedido não encontrado.', 'danger')
                return redirect(url_for('analista.pedidos'))
            
            # Verificar permissão
            if isinstance(pedido, dict):
                pedido_analista = pedido.get('analista_id')
            else:
                pedido_analista = pedido[13] if len(pedido) > 13 else None
            
            if pedido_analista is not None and pedido_analista != 0 and pedido_analista != analista_id:
                flash('Você não tem permissão para acessar este pedido.', 'danger')
                return redirect(url_for('analista.pedidos'))
            
            # Calcular idade
            idade = ''
            if isinstance(pedido, dict):
                data_nasc = pedido.get('data_nascimento')
                if data_nasc:
                    try:
                        if isinstance(data_nasc, str):
                            data_nasc = datetime.strptime(data_nasc, '%Y-%m-%d')
                        hoje = datetime.now()
                        idade_calc = hoje.year - data_nasc.year
                        if (hoje.month, hoje.day) < (data_nasc.month, data_nasc.day):
                            idade_calc -= 1
                        idade = f"{idade_calc} anos"
                    except:
                        idade = ''
            else:
                if len(pedido) > 18 and pedido[18]:
                    data_nasc = pedido[18]
                    try:
                        if isinstance(data_nasc, str):
                            data_nasc = datetime.strptime(data_nasc, '%Y-%m-%d')
                        hoje = datetime.now()
                        idade_calc = hoje.year - data_nasc.year
                        if (hoje.month, hoje.day) < (data_nasc.month, data_nasc.day):
                            idade_calc -= 1
                        idade = f"{idade_calc} anos"
                    except:
                        idade = ''
            
            # Processar anexos do JSON
            anexos_lista = []
            if isinstance(pedido, dict):
                anexos_json = pedido.get('anexos')
            else:
                anexos_json = pedido[28] if len(pedido) > 28 else None
            
            if anexos_json:
                if isinstance(anexos_json, str):
                    try:
                        anexos_data = json.loads(anexos_json)
                    except:
                        anexos_data = []
                else:
                    anexos_data = anexos_json
                
                if isinstance(anexos_data, list):
                    for idx, a in enumerate(anexos_data):
                        if isinstance(a, dict):
                            anexos_lista.append({
                                'index': idx,
                                'arquivo': a.get('filename', ''),
                                'nome': a.get('original_name', 'Arquivo'),
                                'tipo': a.get('tipo', 'unknown'),
                                'tamanho': a.get('size', 0),
                                'data': a.get('upload_date', ''),
                                'analisado_ia': a.get('analisado_ia', False)
                            })
                        elif isinstance(a, (list, tuple)):
                            anexos_lista.append({
                                'index': idx,
                                'arquivo': a[0] if len(a) > 0 else '',
                                'nome': a[1] if len(a) > 1 else 'Arquivo',
                                'tipo': a[2] if len(a) > 2 else 'unknown',
                                'tamanho': a[3] if len(a) > 3 else 0,
                                'data': a[4] if len(a) > 4 else '',
                                'analisado_ia': a[5] if len(a) > 5 else False
                            })
            
            # Construir dicionário do pedido
            if isinstance(pedido, dict):
                pedido_dict = {
                    'id': pedido.get('id'),
                    'paciente_id': pedido.get('paciente_id'),
                    'medico_id': pedido.get('medico_id'),
                    'tipo_exame': garantir_string(pedido.get('tipo_exame')) or 'Não especificado',
                    'descricao': garantir_string(pedido.get('descricao')) or '',
                    'observacoes': garantir_string(pedido.get('observacoes')) or '',
                    'urgencia': garantir_string(pedido.get('urgencia')) or 'normal',
                    'status': garantir_string(pedido.get('status')) or 'pendente',
                    'data_solicitacao': pedido.get('data_solicitacao'),
                    'data_conclusao': pedido.get('data_conclusao'),
                    'resultado_analise': garantir_string(pedido.get('resultado_analise')) or '',
                    'diagnostico_analista': garantir_string(pedido.get('diagnostico_analista')) or '',
                    'recomendacoes_analista': garantir_string(pedido.get('recomendacoes_analista')) or '',
                    'analista_id': pedido.get('analista_id'),
                    'status_aprovacao': garantir_string(pedido.get('status_aprovacao')) or 'pendente',
                    'observacoes_medico': garantir_string(pedido.get('observacoes_medico')) or '',
                    'consulta_id': pedido.get('consulta_id'),
                    'paciente_nome': garantir_string(pedido.get('paciente_nome')) or 'Não informado',
                    'paciente_data_nascimento': pedido.get('data_nascimento').strftime('%d/%m/%Y') if pedido.get('data_nascimento') else '',
                    'paciente_idade': idade,
                    'paciente_genero': garantir_string(pedido.get('paciente_genero')) or '',
                    'paciente_telefone': garantir_string(pedido.get('paciente_telefone')) or '',
                    'paciente_endereco': garantir_string(pedido.get('paciente_endereco')) or '',
                    'medico_nome': garantir_string(pedido.get('medico_nome')) or 'Não informado',
                    'medico_especialidade': garantir_string(pedido.get('medico_especialidade')) or '',
                    'medico_crm': garantir_string(pedido.get('medico_crm')) or '',
                    'analista_nome': garantir_string(pedido.get('analista_nome')) or 'Não atribuído',
                    'data_consulta': pedido.get('data_consulta'),
                    'observacoes_consulta': garantir_string(pedido.get('observacoes_consulta')) or ''
                }
            else:
                pedido_dict = {
                    'id': pedido[0],
                    'paciente_id': pedido[1],
                    'medico_id': pedido[2],
                    'tipo_exame': garantir_string(pedido[3]) or 'Não especificado',
                    'descricao': garantir_string(pedido[4]) or '',
                    'observacoes': garantir_string(pedido[5]) or '',
                    'urgencia': garantir_string(pedido[6]) or 'normal',
                    'status': garantir_string(pedido[7]) or 'pendente',
                    'data_solicitacao': pedido[8] if len(pedido) > 8 and isinstance(pedido[8], datetime) else None,
                    'data_conclusao': pedido[9] if len(pedido) > 9 and isinstance(pedido[9], datetime) else None,
                    'resultado_analise': garantir_string(pedido[10]) if len(pedido) > 10 else '',
                    'diagnostico_analista': garantir_string(pedido[11]) if len(pedido) > 11 else '',
                    'recomendacoes_analista': garantir_string(pedido[12]) if len(pedido) > 12 else '',
                    'analista_id': pedido[13] if len(pedido) > 13 else None,
                    'status_aprovacao': garantir_string(pedido[14]) if len(pedido) > 14 else 'pendente',
                    'observacoes_medico': garantir_string(pedido[15]) if len(pedido) > 15 else '',
                    'consulta_id': pedido[16] if len(pedido) > 16 else None,
                    'paciente_nome': garantir_string(pedido[17]) if len(pedido) > 17 else 'Não informado',
                    'paciente_data_nascimento': pedido[18].strftime('%d/%m/%Y') if len(pedido) > 18 and pedido[18] else '',
                    'paciente_idade': idade,
                    'paciente_genero': garantir_string(pedido[19]) if len(pedido) > 19 else '',
                    'paciente_telefone': garantir_string(pedido[20]) if len(pedido) > 20 else '',
                    'paciente_endereco': garantir_string(pedido[21]) if len(pedido) > 21 else '',
                    'medico_nome': garantir_string(pedido[22]) if len(pedido) > 22 else 'Não informado',
                    'medico_especialidade': garantir_string(pedido[23]) if len(pedido) > 23 else '',
                    'medico_crm': garantir_string(pedido[24]) if len(pedido) > 24 else '',
                    'analista_nome': garantir_string(pedido[25]) if len(pedido) > 25 else 'Não atribuído',
                    'data_consulta': pedido[26] if len(pedido) > 26 and isinstance(pedido[26], datetime) else None,
                    'observacoes_consulta': garantir_string(pedido[27]) if len(pedido) > 27 else ''
                }
            
            return render_template('analista/ver_detalhes_pedido.html',
                                 pedido=pedido_dict,
                                 anexos=anexos_lista,
                                 now=datetime.now(),
                                 user=session,
                                 user_type='analista')
            
        except Exception as e:
            logger.error(f"❌ Erro ao ver detalhes do pedido: {e}")
            logger.error(traceback.format_exc())
            flash(f'Erro ao carregar pedido: {str(e)}', 'danger')
            return redirect(url_for('analista.pedidos'))

    # ========== ROTA: INICIAR ANÁLISE ==========
    @bp.route('/pedido/<int:pedido_id>/iniciar', methods=['POST'])
    @analista_required
    def iniciar_analise(pedido_id):
        """Inicia a análise de um pedido"""
        try:
            user_id = session.get('user_id')
            
            analista_info = execute_query("""
                SELECT a.id FROM analistas a
                WHERE a.usuario_id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                return jsonify({'error': 'Analista não encontrado'}), 404
            
            if isinstance(analista_info, dict):
                analista_id = analista_info.get('id')
            else:
                analista_id = analista_info[0] if len(analista_info) > 0 else None
            
            # Verificar se o pedido existe e está pendente
            pedido = execute_query("""
                SELECT status FROM pedidos_analise 
                WHERE id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido:
                return jsonify({'error': 'Pedido não encontrado'}), 404
            
            pedido_status = pedido.get('status') if isinstance(pedido, dict) else pedido[0]
            
            if pedido_status != 'pendente':
                return jsonify({'error': 'Este pedido não pode ser iniciado'}), 400
            
            # Iniciar análise
            execute_query("""
                UPDATE pedidos_analise 
                SET status = 'em_analise', analista_id = %s, atualizado_em = NOW()
                WHERE id = %s
            """, (analista_id, pedido_id), commit=True)
            
            flash('Análise iniciada com sucesso!', 'success')
            return redirect(url_for('analista.ver_detalhes_pedido', pedido_id=pedido_id))
            
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar análise: {e}")
            logger.error(traceback.format_exc())
            flash(f'Erro ao iniciar análise: {str(e)}', 'danger')
            return redirect(url_for('analista.pedidos'))

    # ========== ROTA: UPLOAD DE ANEXOS ==========
    @bp.route('/pedido/<int:pedido_id>/upload', methods=['POST'])
    @analista_required
    def upload_anexo(pedido_id):
        """Upload de anexos para o pedido (armazena em JSON)"""
        try:
            user_id = session.get('user_id')
            
            analista_info = execute_query("""
                SELECT a.id FROM analistas a
                WHERE a.usuario_id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                flash('Perfil de analista não encontrado.', 'danger')
                return redirect(url_for('auth.login'))
            
            if isinstance(analista_info, dict):
                analista_id = analista_info.get('id')
            else:
                analista_id = analista_info[0] if len(analista_info) > 0 else None
            
            # Verificar permissão
            pedido = execute_query("""
                SELECT analista_id, status, anexos FROM pedidos_analise 
                WHERE id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido:
                flash('Pedido não encontrado.', 'danger')
                return redirect(url_for('analista.pedidos'))
            
            if isinstance(pedido, dict):
                pedido_analista = pedido.get('analista_id')
                pedido_status = pedido.get('status')
                anexos_atual = pedido.get('anexos')
            else:
                pedido_analista = pedido[0] if len(pedido) > 0 else None
                pedido_status = pedido[1] if len(pedido) > 1 else None
                anexos_atual = pedido[2] if len(pedido) > 2 else None
            
            if pedido_analista and pedido_analista != analista_id:
                flash('Você não tem permissão para este pedido.', 'danger')
                return redirect(url_for('analista.pedidos'))
            
            if pedido_status not in ['em_analise', 'pendente']:
                flash('Não é possível adicionar anexos a este pedido.', 'warning')
                return redirect(url_for('analista.ver_detalhes_pedido', pedido_id=pedido_id))
            
            # Processar upload
            files = request.files.getlist('anexos')
            if not files or files[0].filename == '':
                flash('Nenhum arquivo selecionado.', 'warning')
                return redirect(url_for('analista.ver_detalhes_pedido', pedido_id=pedido_id))
            
            from ..file_utils import save_uploaded_file
            
            # Carregar anexos existentes
            anexos_lista = []
            if anexos_atual:
                if isinstance(anexos_atual, str):
                    try:
                        anexos_lista = json.loads(anexos_atual)
                    except:
                        anexos_lista = []
                elif isinstance(anexos_atual, list):
                    anexos_lista = anexos_atual
            
            saved_files = []
            for file in files:
                if file and file.filename:
                    filename, original_name, size, filepath = save_uploaded_file(
                        file, 
                        subfolder='pedidos',
                        custom_filename=f"pedido_{pedido_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
                    )
                    
                    novo_anexo = {
                        'filename': filename,
                        'original_name': original_name,
                        'tipo': file.content_type,
                        'size': size,
                        'upload_date': datetime.now().isoformat(),
                        'analisado_ia': False
                    }
                    anexos_lista.append(novo_anexo)
                    saved_files.append(original_name)
            
            if saved_files:
                # Salvar lista de anexos como JSON
                execute_query("""
                    UPDATE pedidos_analise 
                    SET anexos = %s, atualizado_em = NOW()
                    WHERE id = %s
                """, (json.dumps(anexos_lista, ensure_ascii=False), pedido_id), commit=True)
                
                flash(f'Arquivos enviados com sucesso: {", ".join(saved_files)}', 'success')
            else:
                flash('Nenhum arquivo foi salvo.', 'warning')
            
            return redirect(url_for('analista.ver_detalhes_pedido', pedido_id=pedido_id))
            
        except Exception as e:
            logger.error(f"❌ Erro no upload: {e}")
            logger.error(traceback.format_exc())
            flash(f'Erro no upload: {str(e)}', 'danger')
            return redirect(url_for('analista.ver_detalhes_pedido', pedido_id=pedido_id))

    # ========== ROTA: CONCLUIR ANÁLISE ==========
    @bp.route('/pedido/<int:pedido_id>/concluir', methods=['POST'])
    @analista_required
    def concluir_analise(pedido_id):
        """Conclui a análise de um pedido"""
        try:
            user_id = session.get('user_id')
            
            analista_info = execute_query("""
                SELECT a.id FROM analistas a
                WHERE a.usuario_id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                flash('Perfil de analista não encontrado.', 'danger')
                return redirect(url_for('auth.login'))
            
            if isinstance(analista_info, dict):
                analista_id = analista_info.get('id')
            else:
                analista_id = analista_info[0] if len(analista_info) > 0 else None
            
            # Verificar permissão
            pedido = execute_query("""
                SELECT analista_id, status FROM pedidos_analise 
                WHERE id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido:
                flash('Pedido não encontrado.', 'danger')
                return redirect(url_for('analista.pedidos'))
            
            if isinstance(pedido, dict):
                pedido_analista = pedido.get('analista_id')
                pedido_status = pedido.get('status')
            else:
                pedido_analista = pedido[0] if len(pedido) > 0 else None
                pedido_status = pedido[1] if len(pedido) > 1 else None
            
            if pedido_analista != analista_id:
                flash('Você não tem permissão para este pedido.', 'danger')
                return redirect(url_for('analista.pedidos'))
            
            if pedido_status != 'em_analise':
                flash('Este pedido não está em análise.', 'warning')
                return redirect(url_for('analista.ver_detalhes_pedido', pedido_id=pedido_id))
            
            # Validar campos
            diagnostico = request.form.get('diagnostico', '').strip()
            if not diagnostico:
                flash('O campo de diagnóstico é obrigatório.', 'warning')
                return redirect(url_for('analista.ver_detalhes_pedido', pedido_id=pedido_id))
            
            recomendacoes = request.form.get('recomendacoes', '').strip()
            
            # Atualizar pedido
            execute_query("""
                UPDATE pedidos_analise 
                SET status = 'concluido',
                    diagnostico_analista = %s,
                    recomendacoes_analista = %s,
                    data_conclusao = NOW(),
                    atualizado_em = NOW()
                WHERE id = %s
            """, (diagnostico, recomendacoes, pedido_id), commit=True)
            
            flash('Análise concluída com sucesso! O médico será notificado.', 'success')
            return redirect(url_for('analista.ver_detalhes_pedido', pedido_id=pedido_id))
            
        except Exception as e:
            logger.error(f"❌ Erro ao concluir análise: {e}")
            logger.error(traceback.format_exc())
            flash(f'Erro ao concluir análise: {str(e)}', 'danger')
            return redirect(url_for('analista.pedidos'))

    # ========== ROTA: ANALISAR IMAGEM COM IA ==========
    @bp.route('/analisar-imagem/<int:pedido_id>', methods=['POST'])
    @analista_required
    def analisar_imagem(pedido_id):
        """Analisa uma imagem usando IA"""
        try:
            user_id = session.get('user_id')
            
            analista_info = execute_query("""
                SELECT a.id FROM analistas a
                WHERE a.usuario_id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                return jsonify({'error': 'Analista não encontrado'}), 404
            
            if 'imagem' not in request.files:
                return jsonify({'error': 'Nenhuma imagem enviada'}), 400
            
            file = request.files['imagem']
            if file.filename == '':
                return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
            
            from ..file_utils import save_uploaded_file
            
            filename, original_name, size, filepath = save_uploaded_file(
                file, 
                subfolder='temp',
                custom_filename=f"analise_{pedido_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            )
            
            from ..gemini_service import analisar_imagem_com_gemini
            
            # Obter informações do paciente
            paciente_info = execute_query("""
                SELECT u.nome, p.data_nascimento, p.genero
                FROM pedidos_analise pa
                JOIN pacientes p ON pa.paciente_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                WHERE pa.id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if paciente_info:
                if isinstance(paciente_info, dict):
                    paciente_nome = garantir_string(paciente_info.get('nome')) or 'Paciente'
                    data_nasc = paciente_info.get('data_nascimento')
                    genero = garantir_string(paciente_info.get('genero')) or ''
                else:
                    paciente_nome = garantir_string(paciente_info[0]) if len(paciente_info) > 0 else 'Paciente'
                    data_nasc = paciente_info[1] if len(paciente_info) > 1 else None
                    genero = garantir_string(paciente_info[2]) if len(paciente_info) > 2 else ''
            else:
                paciente_nome = 'Paciente'
                data_nasc = None
                genero = ''
            
            idade = ''
            if data_nasc:
                try:
                    if isinstance(data_nasc, str):
                        data_nasc = datetime.strptime(data_nasc, '%Y-%m-%d')
                    hoje = datetime.now()
                    idade_calc = hoje.year - data_nasc.year
                    if (hoje.month, hoje.day) < (data_nasc.month, data_nasc.day):
                        idade_calc -= 1
                    idade = f"{idade_calc} anos"
                except:
                    idade = ''
            
            contexto = f"""
            Paciente: {paciente_nome}
            Idade: {idade}
            Gênero: {genero}
            Tipo de Exame: {request.form.get('tipo_exame', 'Não especificado')}
            """
            
            from flask import current_app
            gemini_available = current_app.config.get('GEMINI_AVAILABLE', False)
            
            if not gemini_available:
                return jsonify({'error': 'API Gemini não disponível'}), 503
            
            resultado = analisar_imagem_com_gemini(filepath, contexto)
            
            try:
                os.remove(filepath)
            except:
                pass
            
            if resultado and 'error' not in resultado:
                return jsonify({'diagnostico': resultado.get('diagnostico', '')})
            else:
                return jsonify({'error': resultado.get('error', 'Erro na análise')}), 500
            
        except Exception as e:
            logger.error(f"❌ Erro na análise de imagem: {e}")
            logger.error(traceback.format_exc())
            return jsonify({'error': str(e)}), 500

    # ========== ROTA: LISTAR ANEXOS ==========
    @bp.route('/pedido/<int:pedido_id>/anexos')
    @analista_required
    def listar_anexos(pedido_id):
        """Lista os anexos de um pedido"""
        try:
            pedido = execute_query("""
                SELECT anexos FROM pedidos_analise WHERE id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido:
                return jsonify({'error': 'Pedido não encontrado'}), 404
            
            anexos_json = pedido.get('anexos') if isinstance(pedido, dict) else pedido[0]
            
            anexos_lista = []
            if anexos_json:
                if isinstance(anexos_json, str):
                    try:
                        anexos_lista = json.loads(anexos_json)
                    except:
                        anexos_lista = []
                else:
                    anexos_lista = anexos_json
            
            return jsonify({'success': True, 'anexos': anexos_lista})
            
        except Exception as e:
            logger.error(f"❌ Erro ao listar anexos: {e}")
            return jsonify({'error': str(e)}), 500

    # ========== ROTA: REMOVER ANEXO ==========
    @bp.route('/pedido/<int:pedido_id>/anexo/<int:anexo_index>/remover', methods=['DELETE'])
    @analista_required
    def remover_anexo(pedido_id, anexo_index):
        """Remove um anexo do pedido"""
        try:
            user_id = session.get('user_id')
            
            analista_info = execute_query("""
                SELECT a.id FROM analistas a
                WHERE a.usuario_id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                return jsonify({'error': 'Analista não encontrado'}), 404
            
            pedido = execute_query("""
                SELECT analista_id, anexos FROM pedidos_analise WHERE id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido:
                return jsonify({'error': 'Pedido não encontrado'}), 404
            
            pedido_analista = pedido.get('analista_id') if isinstance(pedido, dict) else pedido[0]
            anexos_json = pedido.get('anexos') if isinstance(pedido, dict) else pedido[1] if len(pedido) > 1 else None
            
            if pedido_analista and pedido_analista != analista_id:
                return jsonify({'error': 'Acesso negado'}), 403
            
            if not anexos_json:
                return jsonify({'error': 'Nenhum anexo encontrado'}), 404
            
            if isinstance(anexos_json, str):
                try:
                    anexos_lista = json.loads(anexos_json)
                except:
                    return jsonify({'error': 'Erro ao processar anexos'}), 500
            else:
                anexos_lista = anexos_json
            
            if anexo_index >= len(anexos_lista):
                return jsonify({'error': 'Anexo não encontrado'}), 404
            
            # Remover arquivo físico
            anexo = anexos_lista[anexo_index]
            filename = anexo.get('filename') if isinstance(anexo, dict) else anexo[0] if len(anexo) > 0 else None
            
            if filename:
                from ..file_utils import get_pedido_anexo_path
                filepath = get_pedido_anexo_path(filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
            
            # Remover do JSON
            anexos_lista.pop(anexo_index)
            
            # Salvar lista atualizada
            execute_query("""
                UPDATE pedidos_analise 
                SET anexos = %s, atualizado_em = NOW()
                WHERE id = %s
            """, (json.dumps(anexos_lista, ensure_ascii=False), pedido_id), commit=True)
            
            return jsonify({'success': True, 'message': 'Anexo removido com sucesso'})
            
        except Exception as e:
            logger.error(f"❌ Erro ao remover anexo: {e}")
            logger.error(traceback.format_exc())
            return jsonify({'error': str(e)}), 500

    # ========== FIM DAS ROTAS ==========
