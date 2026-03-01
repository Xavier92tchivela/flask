# routes/pedido_analise_fallback.py
from flask import Blueprint, render_template, redirect, url_for, flash, session
from functools import wraps

def create_pedido_analise_fallback():
    """Cria blueprint de fallback para pedido de análise"""
    
    pedido_analise_fallback = Blueprint('pedido_analise', __name__, url_prefix='/pedido-analise')
    
    def medico_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session or session.get('user_type') != 'medico':
                flash('Acesso restrito a médicos.', 'warning')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated_function
    
    @pedido_analise_fallback.route('/novo')
    @medico_required
    def novo_pedido():
        """Página de novo pedido (fallback)"""
        flash('Módulo de pedidos de análise não está totalmente configurado.', 'warning')
        return redirect(url_for('medico.nova_analise'))
    
    @pedido_analise_fallback.route('/criar', methods=['POST'])
    @medico_required
    def criar_pedido():
        """Criar pedido (fallback)"""
        flash('Módulo de pedidos não disponível no momento.', 'warning')
        return redirect(url_for('medico.dashboard'))
    
    @pedido_analise_fallback.route('/meus-pedidos')
    @medico_required
    def meus_pedidos():
        """Lista de pedidos (fallback)"""
        flash('Módulo de pedidos não disponível no momento.', 'warning')
        return redirect(url_for('medico.dashboard'))
    
    @pedido_analise_fallback.route('/pedido/<int:pedido_id>')
    @medico_required
    def ver_pedido(pedido_id):
        """Detalhes do pedido (fallback)"""
        flash('Módulo de pedidos não disponível no momento.', 'warning')
        return redirect(url_for('medico.dashboard'))
    
    @pedido_analise_fallback.route('/cancelar/<int:pedido_id>', methods=['POST'])
    @medico_required
    def cancelar_pedido(pedido_id):
        """Cancelar pedido (fallback)"""
        flash('Módulo de pedidos não disponível no momento.', 'warning')
        return redirect(url_for('medico.dashboard'))
    
    @pedido_analise_fallback.route('/debug-analistas')
    @medico_required
    def debug_analistas():
        """Debug de analistas (fallback)"""
        return "Módulo de debug não disponível", 503
    
    @pedido_analise_fallback.route('/api/estatisticas')
    @medico_required
    def api_estatisticas():
        """API de estatísticas (fallback)"""
        from flask import jsonify
        return jsonify({'error': 'Módulo não disponível'}), 503
    
    @pedido_analise_fallback.route('/solicitar-analise/<int:consulta_id>')
    @medico_required
    def solicitar_analise(consulta_id):
        """Solicitar análise (fallback)"""
        flash('Módulo de pedidos não disponível no momento.', 'warning')
        return redirect(url_for('medico.dashboard'))
    
    return pedido_analise_fallback