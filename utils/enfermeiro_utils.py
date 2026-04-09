# utils/enfermeiro_utils.py
import re
from flask import session, flash, redirect, url_for
from functools import wraps
import pymysql
import logging

# Configurar logger
logger = logging.getLogger(__name__)

# Variável global para conexão MySQL
_mysql = None

def set_mysql(mysql_instance):
    """Configura a instância do MySQL para este módulo"""
    global _mysql
    _mysql = mysql_instance
    logger.info("MySQL configurado no enfermeiro_utils")

def get_db_connection():
    """Obtém a conexão com o banco de dados"""
    if _mysql is None:
        logger.error("MySQL não foi configurado! _mysql é None em enfermeiro_utils")
        raise Exception("MySQL não foi configurado. Certifique-se de que set_mysql() foi chamado.")
    return _mysql.connection

def execute_query(query, params=None, fetch=False, one=False):
    """Executa queries no banco de dados"""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(pymysql.cursors.DictCursor)
        
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)

        if fetch:
            result = cur.fetchall()
            if one and result:
                return result[0]
            return result
        else:
            conn.commit()
            return cur.lastrowid if cur.lastrowid else True
            
    except Exception as e:
        logger.error(f"Database error: {e}")
        if conn:
            conn.rollback()
        return None if fetch else False
    finally:
        if cur:
            cur.close()

def enfermeiro_required(f):
    """Decorator para verificar se o usuário é enfermeiro"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Faça login para acessar esta página.', 'warning')
            return redirect(url_for('auth.login'))
        
        if session.get('user_type') != 'enfermeiro':
            flash('Acesso não autorizado.', 'danger')
            return redirect(url_for('auth.index'))
        
        # Se não tiver enfermeiro_id na sessão, buscar do banco
        if 'enfermeiro_id' not in session:
            try:
                enfermeiro = execute_query("""
                    SELECT id FROM enfermeiros 
                    WHERE usuario_id = %s AND ativo = TRUE
                """, (session['user_id'],), fetch=True, one=True)
                
                if enfermeiro:
                    session['enfermeiro_id'] = enfermeiro['id']
                    # Buscar também o coren
                    coren_data = execute_query("""
                        SELECT coren FROM enfermeiros WHERE id = %s
                    """, (enfermeiro['id'],), fetch=True, one=True)
                    if coren_data:
                        session['enfermeiro_coren'] = coren_data['coren']
                else:
                    flash('Perfil de enfermeiro não encontrado.', 'danger')
                    return redirect(url_for('auth.logout'))
            except Exception as e:
                logger.error(f"Erro ao buscar dados do enfermeiro: {e}")
                flash('Erro ao carregar perfil.', 'danger')
                return redirect(url_for('auth.logout'))
        
        return f(*args, **kwargs)
    return decorated_function

def classificar_pressao(pressao):
    """Classifica a pressão arterial"""
    if not pressao:
        return {'class': 'secondary', 'text': 'Não informado'}
    
    # Handle different formats (120/80 or 120x80)
    if '/' in pressao:
        partes = pressao.split('/')
    elif 'x' in pressao:
        partes = pressao.split('x')
    else:
        return {'class': 'secondary', 'text': 'Formato inválido'}
    
    try:
        sistolica = int(partes[0].strip())
        diastolica = int(partes[1].strip())
        
        if sistolica < 120 and diastolica < 80:
            return {'class': 'success', 'text': 'Normal'}
        elif 120 <= sistolica <= 129 and diastolica < 80:
            return {'class': 'info', 'text': 'Elevada'}
        elif 130 <= sistolica <= 139 or 80 <= diastolica <= 89:
            return {'class': 'warning', 'text': 'Hipertensão Estágio 1'}
        elif sistolica >= 140 or diastolica >= 90:
            return {'class': 'danger', 'text': 'Hipertensão Estágio 2'}
        elif sistolica > 180 or diastolica > 120:
            return {'class': 'danger', 'text': 'Crise Hipertensiva'}
        else:
            return {'class': 'secondary', 'text': 'Normal'}
    except (ValueError, IndexError):
        return {'class': 'secondary', 'text': 'Erro na leitura'}

def formatar_data(data):
    """Formata data para exibição"""
    if not data:
        return ""
    if hasattr(data, 'strftime'):
        return data.strftime('%d/%m/%Y')
    return str(data)

def formatar_data_hora(data_hora):
    """Formata data e hora para exibição"""
    if not data_hora:
        return ""
    if hasattr(data_hora, 'strftime'):
        return data_hora.strftime('%d/%m/%Y %H:%M')
    return str(data_hora)