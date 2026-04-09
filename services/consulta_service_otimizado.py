# routes/medico/consultas_otimizadas.py
"""
Rotas otimizadas para consultas médicas
"""

from flask import render_template, request, jsonify, session, redirect, url_for, flash
import logging,datetime
from services.consulta_service_otimizado import ConsultaServiceOtimizado

logger = logging.getLogger(__name__)

def init_consultas_otimizadas(mysql, base, medico_required):
    """Inicializa rotas de consultas otimizadas"""
    
    execute_query = base['execute_query']
    formatar_data = base['formatar_data']
    obter_info_medico = base['obter_info_medico']
    
    @medico_required
    def listar_consultas_otimizado():
        """Lista consultas do médico com paginação e filtros"""
        
        medico_info = obter_info_medico()
        if not medico_info:
            flash('Informações do médico não encontradas.', 'danger')
            return redirect(url_for('auth.login'))
        
        medico_id = medico_info.get('id')
        
        # Parâmetros de paginação
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Filtros
        filtros = {}
        if request.args.get('status'):
            filtros['status'] = request.args.get('status')
        if request.args.get('data_inicio'):
            filtros['data_inicio'] = request.args.get('data_inicio')
        if request.args.get('data_fim'):
            filtros['data_fim'] = request.args.get('data_fim')
        if request.args.get('paciente'):
            filtros['paciente_nome'] = request.args.get('paciente')
        
        # Usar serviço otimizado
        resultado = ConsultaServiceOtimizado.get_consultas_medico(
            medico_id, mysql, page, per_page, filtros
        )
        
        # Estatísticas rápidas
        estatisticas = ConsultaServiceOtimizado.get_estatisticas_rapidas(medico_id, mysql)
        
        return render_template('medico/consultas_otimizado.html',
                             consultas=resultado['consultas'],
                             pagination={
                                 'page': resultado['pagina'],
                                 'per_page': resultado['por_pagina'],
                                 'total': resultado['total'],
                                 'pages': resultado['total_paginas']
                             },
                             filtros=filtros,
                             estatisticas=estatisticas,
                             medico=medico_info,
                             user=session)
    
    @medico_required
    def detalhes_consulta_otimizado(consulta_id):
        """Detalhes da consulta com dados em cache"""
        
        medico_info = obter_info_medico()
        if not medico_info:
            flash('Informações do médico não encontradas.', 'danger')
            return redirect(url_for('auth.login'))
        
        # Buscar detalhes da consulta (com cache)
        consulta = ConsultaServiceOtimizado.get_detalhes_consulta(consulta_id, mysql)
        
        if not consulta:
            flash('Consulta não encontrada.', 'danger')
            return redirect(url_for('medico.consultas'))
        
        # Verificar permissão
        if consulta['medico_id'] != medico_info.get('id'):
            flash('Acesso negado a esta consulta.', 'danger')
            return redirect(url_for('medico.consultas'))
        
        # Buscar sinais vitais (com cache)
        sinais_vitais = ConsultaServiceOtimizado.get_sinais_vitais_consulta(consulta_id, mysql)
        
        # Buscar diagnóstico (com cache)
        diagnostico = ConsultaServiceOtimizado.get_diagnostico_consulta(consulta_id, mysql)
        
        # Buscar receitas
        receitas = ConsultaServiceOtimizado.get_receitas_consulta(consulta_id, mysql)
        
        return render_template('consulta/detalhes_consulta.html',
                             consulta=consulta,
                             sinais_vitais=sinais_vitais,
                             diagnostico=diagnostico,
                             receitas=receitas,
                             sintomas=consulta.get('sintomas_lista', []),
                             usuario_tipo='medico',
                             user=session,
                             agora=datetime.now().strftime('%d/%m/%Y %H:%M'))
    
    @medico_required
    def api_consultas_rapidas(medico_id):
        """API para consultas rápidas (para AJAX)"""
        
        page = request.args.get('page', 1, type=int)
        status = request.args.get('status')
        
        filtros = {}
        if status:
            filtros['status'] = status
        
        resultado = ConsultaServiceOtimizado.get_consultas_medico(
            medico_id, mysql, page, 10, filtros
        )
        
        return jsonify({
            'success': True,
            'consultas': resultado['consultas'],
            'total': resultado['total'],
            'pagina': resultado['pagina']
        })
    
    @medico_required
    def atualizar_status_consulta(consulta_id):
        """Atualiza status da consulta e invalida cache"""
        
        novo_status = request.json.get('status')
        
        if novo_status not in ['agendada', 'confirmada', 'realizada', 'cancelada']:
            return jsonify({'success': False, 'error': 'Status inválido'}), 400
        
        try:
            execute_query("""
                UPDATE consultas SET status = %s WHERE id = %s
            """, (novo_status, consulta_id))
            
            # Invalidar cache
            ConsultaServiceOtimizado.invalidar_cache_consulta(consulta_id)
            
            return jsonify({'success': True})
            
        except Exception as e:
            logger.error(f"Erro ao atualizar status: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # Retornar as rotas
    return {
        'routes': [
            {'rule': '/consultas', 'view_func': listar_consultas_otimizado, 'methods': ['GET']},
            {'rule': '/consulta/<int:consulta_id>', 'view_func': detalhes_consulta_otimizado, 'methods': ['GET']},
            {'rule': '/api/consultas/<int:medico_id>', 'view_func': api_consultas_rapidas, 'methods': ['GET']},
            {'rule': '/api/consulta/<int:consulta_id>/status', 'view_func': atualizar_status_consulta, 'methods': ['POST']}
        ]
    }