# routes/pedido_analise/__init__.py
from flask import Blueprint
from .routes import register_routes

def init_pedido_analise(mysql, app):
    """Inicializa o blueprint de pedidos de análise"""
    pedido_analise_bp = Blueprint('pedido_analise', __name__, url_prefix='/pedido-analise')
    
    # Registrar todas as rotas
    register_routes(pedido_analise_bp, mysql, app)
    
    return pedido_analise_bp