from flask import render_template, session, redirect, url_for, flash
from routes.auth import execute_query_auth
from . import farmaceutico_bp
import logging

logger = logging.getLogger(__name__)


@farmaceutico_bp.route('/relatorios')
def relatorios():
    """Relatórios do farmacêutico"""
    if not session.get('logged_in') or session.get('user_type') != 'farmaceutico':
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('auth.login'))
    
    return render_template('farmaceutico/relatorios.html',
                         nome_usuario=session.get('user_name'))