# routes/auth_otimizado.py
"""
Rotas de autenticação otimizadas
"""

from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, flash
import time
import logging
from services.auth_service import AuthService
from werkzeug.security import check_password_hash

logger = logging.getLogger(__name__)

def create_auth_blueprint_otimizado(mysql):
    """Cria blueprint de autenticação otimizado"""
    
    auth_bp = Blueprint('auth_otimizado', __name__, url_prefix='/auth')
    
    @auth_bp.route('/login/medico', methods=['GET', 'POST'])
    def login_medico():
        """Login otimizado para médicos"""
        start_time = time.time()
        
        if request.method == 'GET':
            return render_template('auth/login_medico.html')
        
        # Processar POST
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')
        ip = request.remote_addr or 'unknown'
        
        # 1. VALIDAÇÃO RÁPIDA
        if not email or not senha:
            flash('Email e senha são obrigatórios', 'danger')
            return redirect(url_for('auth_otimizado.login_medico'))
        
        # 2. RATE LIMITING
        if not AuthService.check_rate_limit(ip):
            logger.warning(f"Rate limit excedido para IP: {ip}")
            flash('Muitas tentativas. Tente novamente mais tarde.', 'danger')
            return redirect(url_for('auth_otimizado.login_medico'))
        
        # 3. BUSCAR USUÁRIO (COM CACHE)
        usuario = AuthService.get_usuario_by_email(email, mysql)
        
        if not usuario:
            AuthService.register_attempt(ip)
            logger.warning(f"Tentativa de login com email inexistente: {email}")
            flash('Email ou senha inválidos', 'danger')
            return redirect(url_for('auth_otimizado.login_medico'))
        
        # 4. VERIFICAR TIPO
        if usuario['tipo'] != 'medico':
            AuthService.register_attempt(ip)
            logger.warning(f"Usuário {usuario['id']} tentou login como médico mas é {usuario['tipo']}")
            flash('Acesso não autorizado', 'danger')
            return redirect(url_for('auth_otimizado.login_medico'))
        
        # 5. VERIFICAR SENHA
        if not check_password_hash(usuario['senha'], senha):
            AuthService.register_attempt(ip)
            logger.warning(f"Senha incorreta para usuário: {usuario['id']}")
            flash('Email ou senha inválidos', 'danger')
            return redirect(url_for('auth_otimizado.login_medico'))
        
        # 6. BUSCAR INFORMAÇÕES DO MÉDICO (COM CACHE)
        medico = AuthService.get_medico_info(usuario['id'], mysql)
        
        if not medico:
            logger.error(f"Médico não encontrado para usuário: {usuario['id']}")
            flash('Erro ao carregar dados do médico', 'danger')
            return redirect(url_for('auth_otimizado.login_medico'))
        
        # 7. CRIAR SESSÃO
        session.clear()
        session['user_id'] = usuario['id']
        session['user_uuid'] = usuario['uuid']
        session['user_name'] = usuario['nome']
        session['user_email'] = usuario['email']
        session['user_type'] = usuario['tipo']
        session['user_foto'] = usuario['foto_perfil']
        session['medico_id'] = medico['id']
        session['medico_especialidade'] = medico['especialidade']
        session['medico_crm'] = medico['crm']
        session['logged_in'] = True
        session.permanent = False
        
        # 8. ATUALIZAR ÚLTIMO LOGIN (ASSÍNCRONO - NÃO BLOQUEIA)
        AuthService.update_ultimo_login(usuario['id'], mysql)
        
        # 9. LOG DE TEMPO
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"Login bem-sucedido para médico {usuario['id']} em {elapsed:.2f}ms")
        
        flash(f'Bem-vindo, Dr(a). {medico["nome"]}!', 'success')
        return redirect(url_for('medico.dashboard'))
    
    @auth_bp.route('/logout')
    def logout():
        """Logout com limpeza de sessão"""
        user_id = session.get('user_id')
        email = session.get('user_email')
        
        # Limpar sessão
        session.clear()
        
        # Limpar cache do usuário
        if user_id and email:
            AuthService.limpar_cache_usuario(usuario_id=user_id, email=email)
        
        flash('Logout realizado com sucesso', 'success')
        return redirect(url_for('auth_otimizado.login_medico'))
    
    @auth_bp.route('/status')
    def status():
        """Verifica status da sessão (útil para AJAX)"""
        if session.get('logged_in'):
            return jsonify({
                'logged_in': True,
                'user_type': session.get('user_type'),
                'user_name': session.get('user_name'),
                'user_id': session.get('user_id')
            })
        return jsonify({'logged_in': False})
    
    return auth_bp