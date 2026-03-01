"""Rotas de perfil para analista"""
from flask import render_template, session, flash, redirect, url_for, request, jsonify
import logging
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

logger = logging.getLogger(__name__)

def register_perfil_routes(bp, analista_required, execute_query, formatar_data):
    
    @bp.route('/perfil')
    @analista_required
    def perfil():
        """Perfil do analista"""
        try:
            user_id = session.get('user_id')
            
            analista_info = execute_query("""
                SELECT 
                    a.id, a.usuario_id, a.especialidade, a.registro_profissional,
                    a.telefone as telefone_analista, a.is_supervisor, a.status,
                    a.experiencia, a.carga_horaria_semanal, a.data_contratacao,
                    a.data_desligamento, a.criado_em, a.atualizado_em,
                    u.nome, u.email, u.telefone as telefone_usuario, u.endereco,
                    u.data_cadastro, u.foto_perfil, u.cpf, u.rg
                FROM analistas a
                JOIN usuarios u ON a.usuario_id = u.id
                WHERE u.id = %s AND a.status = 'ativo'
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                flash('Perfil de analista não encontrado.', 'danger')
                return redirect(url_for('analista.dashboard'))
            
            analista_dict = {
                'id': analista_info[0], 'usuario_id': analista_info[1],
                'especialidade': analista_info[2] or 'Não informada',
                'registro_profissional': analista_info[3] or 'Não informado',
                'telefone_analista': analista_info[4] or '',
                'is_supervisor': bool(analista_info[5]), 'status': analista_info[6],
                'experiencia': analista_info[7] or '',
                'carga_horaria_semanal': analista_info[8] or 40,
                'data_contratacao': analista_info[9], 'data_desligamento': analista_info[10],
                'criado_em': analista_info[11], 'atualizado_em': analista_info[12],
                'nome': analista_info[13] or 'Analista', 'email': analista_info[14] or '',
                'telefone_usuario': analista_info[15] or '', 'endereco': analista_info[16] or '',
                'data_cadastro': analista_info[17],
                'foto_perfil': analista_info[18] or 'default-avatar.png',
                'cpf': analista_info[19] or '', 'rg': analista_info[20] or ''
            }
            
            analista_id = analista_dict['id']
            
            estatisticas = execute_query("""
                SELECT 
                    COUNT(*) as total_pedidos,
                    SUM(CASE WHEN status = 'concluido' THEN 1 ELSE 0 END) as concluidos,
                    SUM(CASE WHEN status = 'pendente' THEN 1 ELSE 0 END) as pendentes,
                    SUM(CASE WHEN status = 'em_analise' THEN 1 ELSE 0 END) as em_andamento,
                    SUM(CASE WHEN urgencia = 'urgente' THEN 1 ELSE 0 END) as urgentes,
                    AVG(CASE WHEN status = 'concluido' 
                        THEN TIMESTAMPDIFF(HOUR, data_solicitacao, data_conclusao) 
                        ELSE NULL END) as tempo_medio_horas
                FROM pedidos_analise 
                WHERE analista_id = %s
            """, (analista_id,), fetch=True, one=True)
            
            if estatisticas:
                analista_dict['estatisticas'] = {
                    'total_pedidos': estatisticas[0] or 0,
                    'concluidos': estatisticas[1] or 0,
                    'pendentes': estatisticas[2] or 0,
                    'em_andamento': estatisticas[3] or 0,
                    'urgentes': estatisticas[4] or 0,
                    'tempo_medio_horas': round(estatisticas[5] or 0, 1)
                }
            else:
                analista_dict['estatisticas'] = {
                    'total_pedidos': 0, 'concluidos': 0, 'pendentes': 0,
                    'em_andamento': 0, 'urgentes': 0, 'tempo_medio_horas': 0
                }
            
            ultimos_pedidos = execute_query("""
                SELECT 
                    pa.id, pa.tipo_exame, pa.data_conclusao, u.nome as paciente_nome
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                WHERE pa.analista_id = %s AND pa.status = 'concluido'
                ORDER BY pa.data_conclusao DESC
                LIMIT 5
            """, (analista_id,), fetch=True)
            
            analista_dict['ultimos_pedidos'] = []
            if ultimos_pedidos:
                for pedido in ultimos_pedidos:
                    analista_dict['ultimos_pedidos'].append({
                        'id': pedido[0], 'tipo_exame': pedido[1] or 'Exame',
                        'data_conclusao': formatar_data(pedido[2]) if pedido[2] else 'Data não informada',
                        'paciente_nome': pedido[3] or 'Paciente'
                    })
            
            return render_template('analista/perfil.html', user=session, analista=analista_dict)
            
        except Exception as e:
            logger.error(f"❌ Erro ao carregar perfil: {e}")
            flash('Erro ao carregar perfil.', 'danger')
            return redirect(url_for('analista.dashboard'))

    @bp.route('/perfil/editar', methods=['GET', 'POST'])
    @analista_required
    def editar_perfil():
        """Editar perfil do analista"""
        try:
            user_id = session.get('user_id')
            
            if request.method == 'POST':
                nome = request.form.get('nome', '').strip()
                email = request.form.get('email', '').strip()
                telefone = request.form.get('telefone', '').strip()
                endereco = request.form.get('endereco', '').strip()
                especialidade = request.form.get('especialidade', '').strip()
                registro_profissional = request.form.get('registro_profissional', '').strip()
                experiencia = request.form.get('experiencia', '').strip()
                carga_horaria = request.form.get('carga_horaria_semanal', 40)
                
                if not nome or not email:
                    flash('Nome e email são obrigatórios.', 'warning')
                    return redirect(url_for('analista.editar_perfil'))
                
                execute_query("""
                    UPDATE usuarios 
                    SET nome = %s, email = %s, telefone = %s, endereco = %s,
                        atualizado_em = NOW()
                    WHERE id = %s
                """, (nome, email, telefone, endereco, user_id), commit=True)
                
                execute_query("""
                    UPDATE analistas 
                    SET especialidade = %s, registro_profissional = %s,
                        experiencia = %s, carga_horaria_semanal = %s,
                        atualizado_em = NOW()
                    WHERE usuario_id = %s
                """, (especialidade, registro_profissional, experiencia, carga_horaria, user_id), commit=True)
                
                session['user_name'] = nome
                flash('Perfil atualizado com sucesso!', 'success')
                return redirect(url_for('analista.perfil'))
            
            analista_info = execute_query("""
                SELECT 
                    u.nome, u.email, u.telefone, u.endereco,
                    a.especialidade, a.registro_profissional, a.experiencia,
                    a.carga_horaria_semanal
                FROM analistas a
                JOIN usuarios u ON a.usuario_id = u.id
                WHERE u.id = %s
            """, (user_id,), fetch=True, one=True)
            
            if not analista_info:
                flash('Perfil não encontrado.', 'danger')
                return redirect(url_for('analista.dashboard'))
            
            dados = {
                'nome': analista_info[0] or '', 'email': analista_info[1] or '',
                'telefone': analista_info[2] or '', 'endereco': analista_info[3] or '',
                'especialidade': analista_info[4] or '', 'registro_profissional': analista_info[5] or '',
                'experiencia': analista_info[6] or '', 'carga_horaria_semanal': analista_info[7] or 40
            }
            
            return render_template('analista/editar_perfil.html', user=session, dados=dados)
            
        except Exception as e:
            logger.error(f" Erro ao editar perfil: {e}")
            flash('Erro ao processar edição.', 'danger')
            return redirect(url_for('analista.perfil'))

    @bp.route('/configuracoes')
    @analista_required
    def configuracoes():
        """Página de configurações do analista"""
        try:
            from ..gemini_service import _gemini_available, _model_name
            return render_template('analista/configuracoes.html',
                                 user=session,
                                 gemini_available=_gemini_available,
                                 MODEL_NAME=_model_name)
        except Exception as e:
            logger.error(f" Erro ao carregar configurações: {e}")
            flash('Erro ao carregar configurações.', 'danger')
            return redirect(url_for('analista.dashboard'))