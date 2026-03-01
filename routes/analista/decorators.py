# routes/analista/decorators.py
from functools import wraps
from flask import session, flash, redirect, url_for

def analista_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('auth.login'))
        
        if session.get('user_type') != 'analista':
            flash('Acesso restrito a analistas.', 'danger')
            # CORREÇÃO: usar 'dashboard_geral' em vez de 'dashboard'
            return redirect(url_for('dashboard_geral'))
        
        return f(*args, **kwargs)
    return decorated_function