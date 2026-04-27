# routes/medico/base.py
from flask import session, flash, redirect, url_for
from datetime import datetime
import logging
import traceback
from functools import wraps
from utils.database import execute_query as db_execute_query
from utils.helpers import formatar_data, calcular_idade

logger = logging.getLogger(__name__)

def init_medico_base(mysql):
    """Inicializa funções base compartilhadas do médico"""
    
    # ========== FUNÇÃO EXECUTE QUERY ==========
    def execute_query(query, params=None, fetch=False, one=False):
        """Wrapper para a função do utils.database"""
        try:
            return db_execute_query(mysql, query, params, fetch, one)
        except Exception as e:
            logger.error(f"Erro ao executar query: {e}")
            return None
    
    # ========== DECORATOR ==========
    def medico_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session or session.get('user_type') != 'medico':
                flash('Acesso restrito a médicos.', 'warning')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated_function
    
    # ========== OBTER INFO MÉDICO ==========
    def obter_info_medico():
        try:
            user_id = session.get('user_id')
            if not user_id:
                logger.error("Nenhum user_id na sessão")
                return None
            
            usuario = execute_query("""
                SELECT tipo, nome, email, telefone FROM usuarios WHERE id = %s
            """, (user_id,), fetch=True, one=True)
            
            if not usuario or usuario[0] != 'medico':
                return None
            
            medico = execute_query("""
                SELECT m.id, m.usuario_id, m.especialidade, m.crm, m.status,
                       u.nome, u.email, u.telefone
                FROM medicos m
                JOIN usuarios u ON m.usuario_id = u.id
                WHERE m.usuario_id = %s
            """, (user_id,), fetch=True, one=True)
            
            if medico:
                return {
                    'id': medico[0],
                    'usuario_id': medico[1],
                    'especialidade': medico[2] or "Clínico Geral",
                    'crm': medico[3] or "CRM não informado",
                    'status': medico[4] or 'ativo',
                    'nome': medico[5],
                    'email': medico[6],
                    'telefone': medico[7] or ''
                }
            
            return {
                'id': None,
                'usuario_id': user_id,
                'especialidade': "Clínico Geral",
                'crm': "CRM não informado",
                'status': 'ativo',
                'nome': usuario[1],
                'email': usuario[2],
                'telefone': usuario[3] or ''
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter info médico: {e}")
            logger.error(traceback.format_exc())
            return None
    
    return {
        'medico_required': medico_required,
        'obter_info_medico': obter_info_medico,
        'execute_query': execute_query,
        'formatar_data': formatar_data,
        'calcular_idade': calcular_idade
    }
