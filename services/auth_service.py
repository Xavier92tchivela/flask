# services/auth_service.py
"""
Serviço de autenticação otimizado com cache e rate limiting
"""

import time
import hashlib
import logging
from datetime import datetime
from werkzeug.security import check_password_hash
from flask import session

logger = logging.getLogger(__name__)

# Cache simples em memória (substituir por Redis em produção)
_login_attempts_cache = {}
_user_cache = {}

class AuthService:
    """Serviço de autenticação otimizado"""
    
    @staticmethod
    def get_usuario_by_email(email, mysql):
        """Busca usuário por email com cache simples"""
        cache_key = f"usuario:{hashlib.md5(email.encode()).hexdigest()}"
        
        # Verificar cache
        if cache_key in _user_cache:
            cached = _user_cache[cache_key]
            # Cache válido por 5 minutos
            if time.time() - cached['timestamp'] < 300:
                logger.debug(f"Cache hit para email: {email}")
                return cached['data']
        
        # Buscar no banco
        try:
            cur = mysql.connection.cursor()
            cur.execute("""
                SELECT id, uuid, nome, email, senha, tipo, ativo,
                       ultimo_login, foto_perfil, created_at
                FROM usuarios 
                WHERE email = %s AND ativo = 1
                LIMIT 1
            """, (email,))
            
            usuario = cur.fetchone()
            cur.close()
            
            if usuario:
                # Converter para dicionário
                usuario_dict = {
                    'id': usuario[0],
                    'uuid': usuario[1],
                    'nome': usuario[2],
                    'email': usuario[3],
                    'senha': usuario[4],
                    'tipo': usuario[5],
                    'ativo': usuario[6],
                    'ultimo_login': usuario[7],
                    'foto_perfil': usuario[8],
                    'created_at': usuario[9]
                }
                
                # Guardar em cache
                _user_cache[cache_key] = {
                    'data': usuario_dict,
                    'timestamp': time.time()
                }
                
                return usuario_dict
            return None
            
        except Exception as e:
            logger.error(f"Erro ao buscar usuário: {e}")
            return None
    
    @staticmethod
    def get_medico_info(usuario_id, mysql):
        """Busca informações do médico com cache"""
        cache_key = f"medico:usuario:{usuario_id}"
        
        # Verificar cache
        if cache_key in _user_cache:
            cached = _user_cache[cache_key]
            if time.time() - cached['timestamp'] < 600:  # 10 minutos
                return cached['data']
        
        try:
            cur = mysql.connection.cursor()
            cur.execute("""
                SELECT m.id, m.especialidade, m.crm, m.telefone,
                       u.nome, u.email, u.foto_perfil
                FROM medicos m
                JOIN usuarios u ON m.usuario_id = u.id
                WHERE m.usuario_id = %s
                LIMIT 1
            """, (usuario_id,))
            
            medico = cur.fetchone()
            cur.close()
            
            if medico:
                medico_dict = {
                    'id': medico[0],
                    'especialidade': medico[1] or 'Não especificada',
                    'crm': medico[2] or 'Não informado',
                    'telefone': medico[3] or '',
                    'nome': medico[4],
                    'email': medico[5],
                    'foto_perfil': medico[6]
                }
                
                # Guardar em cache
                _user_cache[cache_key] = {
                    'data': medico_dict,
                    'timestamp': time.time()
                }
                
                return medico_dict
            return None
            
        except Exception as e:
            logger.error(f"Erro ao buscar médico: {e}")
            return None
    
    @staticmethod
    def check_rate_limit(ip, max_attempts=5, window=300):
        """Verifica rate limiting por IP"""
        global _login_attempts_cache
        now = time.time()
        
        # Limpar tentativas antigas
        if ip in _login_attempts_cache:
            attempts = [t for t in _login_attempts_cache[ip] 
                       if now - t < window]
            _login_attempts_cache[ip] = attempts
        else:
            _login_attempts_cache[ip] = []
        
        return len(_login_attempts_cache[ip]) < max_attempts
    
    @staticmethod
    def register_attempt(ip):
        """Registra tentativa de login"""
        global _login_attempts_cache
        if ip not in _login_attempts_cache:
            _login_attempts_cache[ip] = []
        
        _login_attempts_cache[ip].append(time.time())
        
        # Limitar tamanho
        if len(_login_attempts_cache[ip]) > 10:
            _login_attempts_cache[ip] = _login_attempts_cache[ip][-10:]
    
    @staticmethod
    def update_ultimo_login(usuario_id, mysql):
        """Atualiza último login (sem cache)"""
        try:
            cur = mysql.connection.cursor()
            cur.execute("""
                UPDATE usuarios 
                SET ultimo_login = NOW() 
                WHERE id = %s
            """, (usuario_id,))
            mysql.connection.commit()
            cur.close()
            
            # Invalidar cache do usuário
            for key in list(_user_cache.keys()):
                if key.startswith('usuario:') or f"medico:usuario:{usuario_id}" in key:
                    _user_cache.pop(key, None)
                    
        except Exception as e:
            logger.error(f"Erro ao atualizar último login: {e}")
    
    @staticmethod
    def limpar_cache_usuario(usuario_id=None, email=None):
        """Limpa cache de um usuário específico"""
        global _user_cache
        if usuario_id:
            for key in list(_user_cache.keys()):
                if f"medico:usuario:{usuario_id}" in key:
                    _user_cache.pop(key, None)
        
        if email:
            cache_key = f"usuario:{hashlib.md5(email.encode()).hexdigest()}"
            _user_cache.pop(cache_key, None)