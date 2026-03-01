"""Rotas de pedidos para analista"""
from flask import render_template, session, flash, redirect, url_for, request, send_file, jsonify
import os
import logging

logger = logging.getLogger(__name__)

def register_pedidos_routes(bp, analista_required, execute_query, formatar_data, calcular_idade):
    
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
            
            analista_id = analista_info[0]
            
            # Filtros
            status_filter = request.args.get('status', '')
            urgencia_filter = request.args.get('urgencia', '')
            
            query = """
                SELECT 
                    pa.id, pa.tipo_exame, pa.urgencia, pa.status, pa.data_solicitacao,
                    pa.data_conclusao, pa.descricao, pa.observacoes,
                    u.nome as paciente_nome, p.data_nascimento, p.genero,
                    m_u.nome as medico_nome, m.especialidade as medico_especialidade
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
                    idade = calcular_idade(pedido[9]) if pedido[9] else ''
                    
                    pedidos_list.append({
                        'id': pedido[0], 'tipo_exame': pedido[1] or '',
                        'urgencia': pedido[2] or 'normal', 'status': pedido[3] or 'pendente',
                        'data_solicitacao': formatar_data(pedido[4]),
                        'data_conclusao': formatar_data(pedido[5]),
                        'descricao': pedido[6] or '', 'observacoes': pedido[7] or '',
                        'paciente_nome': pedido[8] or 'Não informado',
                        'paciente_data_nascimento': formatar_data(pedido[9], '%d/%m/%Y') if pedido[9] else '',
                        'paciente_idade': idade, 'paciente_genero': pedido[10] or '',
                        'medico_nome': pedido[11] or 'Não informado',
                        'medico_especialidade': pedido[12] or ''
                    })
            
            return render_template('analista/pedidos.html',
                                 user=session,
                                 pedidos=pedidos_list,
                                 status_filter=status_filter,
                                 urgencia_filter=urgencia_filter)
            
        except Exception as e:
            logger.error(f"❌ Erro ao listar pedidos: {e}")
            flash('Erro ao carregar pedidos.', 'danger')
            return render_template('analista/pedidos.html', user=session, pedidos=[])

    @bp.route('/pedidos/<int:pedido_id>/anexo/<filename>')
    @analista_required
    def download_anexo(pedido_id, filename):
        """Download de anexo do pedido"""
        try:
            user_id = session.get('user_id')
            
            analista_info = execute_query("""
                SELECT a.id FROM analistas a
                WHERE a.usuario_id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                return jsonify({'error': 'Analista não encontrado'}), 404
            
            analista_id = analista_info[0]
            
            pedido = execute_query("""
                SELECT analista_id FROM pedidos_analise 
                WHERE id = %s
            """, (pedido_id,), fetch=True, one=True)
            
            if not pedido or (pedido[0] != analista_id and pedido[0] is not None):
                return jsonify({'error': 'Acesso negado'}), 403
            
            anexo = execute_query("""
                SELECT filename, original_name, tipo 
                FROM anexos_pedidos 
                WHERE pedido_id = %s AND filename = %s
            """, (pedido_id, filename), fetch=True, one=True)
            
            if not anexo:
                return jsonify({'error': 'Anexo não encontrado'}), 404
            
            from ..file_utils import get_pedido_anexo_path
            filepath = get_pedido_anexo_path(filename)
            
            if not os.path.exists(filepath):
                return jsonify({'error': 'Arquivo não encontrado'}), 404
            
            return send_file(
                filepath,
                as_attachment=True,
                download_name=anexo[1] or filename,
                mimetype=anexo[2] or 'application/octet-stream'
            )
            
        except Exception as e:
            logger.error(f"❌ Erro no download: {e}")
            return jsonify({'error': str(e)}), 500