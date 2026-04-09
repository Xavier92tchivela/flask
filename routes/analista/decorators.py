# routes/analista/decorators.py
from functools import wraps
from flask import session, flash, redirect, url_for, request, jsonify

def analista_required(f):
    """
    Decorator para verificar se o usuário é um analista
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('auth.login'))
        
        if session.get('user_type') != 'analista':
            flash('Acesso restrito a analistas.', 'danger')
            # Redirecionar para o dashboard apropriado
            user_type = session.get('user_type')
            if user_type == 'medico':
                return redirect(url_for('medico.dashboard'))
            elif user_type == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user_type == 'paciente':
                return redirect(url_for('paciente.dashboard'))
            else:
                return redirect(url_for('dashboard_geral'))
        
        return f(*args, **kwargs)
    return decorated_function


def login_required(f):
    """
    Decorator para verificar se o usuário está logado
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    Decorator para verificar se o usuário é um administrador
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('auth.login'))
        
        if session.get('user_type') != 'admin':
            flash('Acesso restrito a administradores.', 'danger')
            return redirect(url_for('dashboard_geral'))
        
        return f(*args, **kwargs)
    return decorated_function


def any_user_required(allowed_types=['analista', 'admin']):
    """
    Decorator para verificar se o usuário é um dos tipos permitidos
    Uso: @any_user_required(['analista', 'admin'])
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Por favor, faça login para acessar esta página.', 'warning')
                return redirect(url_for('auth.login'))
            
            user_type = session.get('user_type')
            if user_type not in allowed_types:
                flash(f'Acesso restrito a {", ".join(allowed_types)}.', 'danger')
                return redirect(url_for('dashboard_geral'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# Exportar todas as funções
__all__ = ['analista_required', 'login_required', 'admin_required', 'any_user_required']