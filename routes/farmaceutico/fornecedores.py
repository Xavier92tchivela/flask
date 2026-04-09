from flask import render_template, session, redirect, url_for, flash
from routes.auth import execute_query_auth
from . import farmaceutico_bp
import logging

logger = logging.getLogger(__name__)


@farmaceutico_bp.route('/fornecedores')
def fornecedores():
    """Lista de fornecedores"""
    if not session.get('logged_in') or session.get('user_type') != 'farmaceutico':
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('auth.login'))
    
    try:
        fornecedores_raw = execute_query_auth("""
            SELECT id, nome, cnpj, telefone, email, endereco, contato
            FROM fornecedores
            ORDER BY nome
        """, fetch=True) or []
        
        fornecedores = []
        for f in fornecedores_raw:
            fornecedores.append({
                'id': f[0],
                'nome': f[1] if not isinstance(f[1], bytes) else f[1].decode('utf-8', errors='ignore'),
                'cnpj': f[2] if not isinstance(f[2], bytes) else f[2].decode('utf-8', errors='ignore'),
                'telefone': f[3] if not isinstance(f[3], bytes) else f[3].decode('utf-8', errors='ignore'),
                'email': f[4] if not isinstance(f[4], bytes) else f[4].decode('utf-8', errors='ignore'),
                'endereco': f[5] if not isinstance(f[5], bytes) else f[5].decode('utf-8', errors='ignore'),
                'contato': f[6] if not isinstance(f[6], bytes) else f[6].decode('utf-8', errors='ignore')
            })
        
        return render_template('farmaceutico/fornecedores.html',
                             fornecedores=fornecedores,
                             nome_usuario=session.get('user_name'))
    
    except Exception as e:
        logger.error(f"Erro ao listar fornecedores: {e}")
        flash('Erro ao carregar fornecedores.', 'danger')
        return redirect(url_for('farmaceutico.dashboard'))