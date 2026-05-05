# routes/enfermeiro/utils.py

from functools import wraps
from flask import session, flash, redirect, url_for
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

# Variável global para o MySQL
mysql = None

def set_mysql(mysql_instance):
    """Configura a conexão MySQL para este módulo"""
    global mysql
    mysql = mysql_instance

def decode_bytes(value):
    """Decodifica bytes para string UTF-8"""
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode('utf-8')
        except:
            return str(value)
    return value

def execute_query(query, params=None, fetch=False, one=False):
    """Executa uma query SQL com tratamento para MySQL"""
    global mysql
    
    if not mysql:
        logger.error("MySQL não configurado no módulo utils")
        return None if not fetch else (None if one else [])
    
    try:
        cursor = mysql.connection.cursor()
        cursor.execute(query, params or ())
        
        if fetch:
            if one:
                result = cursor.fetchone()
                cursor.close()
                if result:
                    # Converter tupla para dicionário se necessário
                    if isinstance(result, tuple) and hasattr(cursor, 'description'):
                        columns = [col[0] for col in cursor.description]
                        return dict(zip(columns, result))
                    return result
                return None
            else:
                results = cursor.fetchall()
                cursor.close()
                # Converter lista de tuplas para lista de dicionários
                if results and hasattr(cursor, 'description'):
                    columns = [col[0] for col in cursor.description]
                    return [dict(zip(columns, row)) for row in results]
                return results
        else:
            mysql.connection.commit()
            affected_rows = cursor.rowcount
            cursor.close()
            return affected_rows
            
    except Exception as e:
        logger.error(f"Erro na query: {e}")
        logger.error(f"Query: {query}")
        logger.error(f"Params: {params}")
        if not fetch:
            try:
                mysql.connection.rollback()
            except:
                pass
        return None if not fetch else (None if one else [])

def enfermeiro_required(f):
    """Decorator para verificar se o usuário é enfermeiro"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Você precisa estar logado para acessar esta página.', 'warning')
            return redirect(url_for('auth.login'))
        
        if session.get('user_type') != 'ENFERMEIRO':
            flash('Acesso restrito a enfermeiros.', 'danger')
            return redirect(url_for('index'))
        
        # Verificar se tem enfermeiro_id na sessão
        if 'enfermeiro_id' not in session:
            # Buscar enfermeiro_id baseado no user_id
            try:
                cursor = mysql.connection.cursor()
                cursor.execute("SELECT id FROM enfermeiros WHERE usuario_id = %s", (session['user_id'],))
                result = cursor.fetchone()
                cursor.close()
                if result:
                    session['enfermeiro_id'] = result[0]
                else:
                    flash('Perfil de enfermeiro não encontrado.', 'danger')
                    return redirect(url_for('auth.login'))
            except Exception as e:
                logger.error(f"Erro ao buscar enfermeiro_id: {e}")
                flash('Erro ao verificar perfil de enfermeiro.', 'danger')
                return redirect(url_for('auth.login'))
        
        return f(*args, **kwargs)
    return decorated_function

def classificar_pressao(pressao):
    """Classifica a pressão arterial"""
    if not pressao:
        return "Não informada", "secondary"
    
    # Limpar a string
    pressao = str(pressao).replace('x', '/').strip()
    
    try:
        if '/' in pressao:
            sist, diast = map(int, pressao.split('/'))
        else:
            return "Formato inválido", "secondary"
        
        if sist < 90 or diast < 60:
            return "Hipotensão", "warning"
        elif sist < 120 and diast < 80:
            return "Normal", "success"
        elif sist < 130 and diast < 85:
            return "Pré-hipertensão", "info"
        elif sist < 140 or diast < 90:
            return "Hipertensão Estágio 1", "warning"
        elif sist < 160 or diast < 100:
            return "Hipertensão Estágio 2", "danger"
        else:
            return "Crise Hipertensiva", "danger"
    except:
        return "Formato inválido", "secondary"

def formatar_data(data, formato='%d/%m/%Y'):
    """Formata uma data de forma segura"""
    if data is None:
        return ''
    if isinstance(data, datetime):
        return data.strftime(formato)
    if isinstance(data, date):
        return data.strftime(formato)
    if isinstance(data, str):
        try:
            # Tenta converter string para data
            dt = datetime.strptime(data[:10], '%Y-%m-%d')
            return dt.strftime(formato)
        except:
            return data
    return str(data)

def formatar_data_hora(data_hora, formato='%d/%m/%Y %H:%M'):
    """Formata uma data/hora de forma segura"""
    if data_hora is None:
        return ''
    if isinstance(data_hora, datetime):
        return data_hora.strftime(formato)
    if isinstance(data_hora, str):
        try:
            dt = datetime.strptime(data_hora, '%Y-%m-%d %H:%M:%S')
            return dt.strftime(formato)
        except:
            try:
                dt = datetime.strptime(data_hora, '%Y-%m-%d %H:%M')
                return dt.strftime(formato)
            except:
                return data_hora
    return str(data_hora)
