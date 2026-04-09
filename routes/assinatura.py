# routes/assinatura.py
from flask import Blueprint, render_template

assinatura_bp = Blueprint('assinatura', __name__, url_prefix='/assinatura')

@assinatura_bp.route('/')
def index():
    """Página de planos de assinatura"""
    try:
        return render_template('assinatura/index.html')
    except Exception as e:
        return f"Erro ao carregar a página de assinatura: {e}", 500

@assinatura_bp.route('/teste')
def teste():
    """Rota de teste para verificar se o blueprint está funcionando"""
    return "Rota de teste do blueprint de assinatura funcionando perfeitamente!"