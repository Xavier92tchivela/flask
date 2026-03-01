"""Rotas de histórico para analista"""
from flask import render_template, session, flash, redirect, url_for
import logging

logger = logging.getLogger(__name__)

def register_historico_routes(bp, analista_required, execute_query, formatar_data):
    
    @bp.route('/minhas-analises')
    @analista_required
    def minhas_analises():
        """Histórico de análises do analista"""
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
            
            analises = execute_query("""
                SELECT 
                    pa.id, pa.tipo_exame, pa.status, pa.urgencia,
                    pa.data_solicitacao, pa.data_conclusao,
                    u.nome as paciente_nome, m_u.nome as medico_nome,
                    pa.diagnostico_analista
                FROM pedidos_analise pa
                LEFT JOIN pacientes p ON pa.paciente_id = p.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                LEFT JOIN medicos m ON pa.medico_id = m.id
                LEFT JOIN usuarios m_u ON m.usuario_id = m_u.id
                WHERE pa.analista_id = %s
                AND pa.status = 'concluido'
                ORDER BY pa.data_conclusao DESC
                LIMIT 20
            """, (analista_id,), fetch=True)
            
            analises_list = []
            if analises:
                for analise in analises:
                    analises_list.append({
                        'id': analise[0], 'tipo_exame': analise[1],
                        'status': analise[2], 'urgencia': analise[3],
                        'data_solicitacao': formatar_data(analise[4]),
                        'data_conclusao': formatar_data(analise[5]),
                        'paciente_nome': analise[6] or 'Não informado',
                        'medico_nome': analise[7] or 'Não informado',
                        'diagnostico_analista': analise[8] or ''
                    })
            
            return render_template('analista/minhas_analises.html',
                                 user=session, analises=analises_list)
            
        except Exception as e:
            logger.error(f"❌ Erro ao carregar histórico: {e}")
            flash('Erro ao carregar histórico.', 'danger')
            return redirect(url_for('analista.dashboard'))

    @bp.route('/historico')
    @analista_required
    def historico():
        """Alias para minhas_analises"""
        return redirect(url_for('analista.minhas_analises'))