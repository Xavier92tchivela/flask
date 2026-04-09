# routes/pedido_analise/decorators.py
from functools import wraps
from flask import session, flash, redirect, url_for

def medico_required(f):
    """Decorator para restringir acesso a médicos"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_type') != 'medico':
            flash('Acesso restrito a médicos.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function