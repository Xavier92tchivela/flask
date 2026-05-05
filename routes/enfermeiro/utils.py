"""Utilitários compartilhados entre os módulos do enfermeiro"""
from functools import wraps
from flask import session, flash, redirect, url_for
import logging
import re

logger = logging.getLogger(__name__)

# Conexão MySQL global
_mysql = None

def set_mysql(mysql_instance):
    """Configura a conexão MySQL para os utilitários"""
    global _mysql
    _mysql = mysql_instance

def dict_factory(cursor, row):
    """Converte uma tupla em dicionário"""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def decode_bytes(data):
    """
    Decodifica recursivamente qualquer valor bytes para string
    Funciona com dicionários, listas, tuplas e valores simples
    """
    if data is None:
        return None
    if isinstance(data, bytes):
        try:
            return data.decode('utf-8')
        except:
            return str(data)
    if isinstance(data, dict):
        return {key: decode_bytes(value) for key, value in data.items()}
    if isinstance(data, (list, tuple)):
        return [decode_bytes(item) for item in data]
    if isinstance(data, (int, float, bool)):
        return data
    return data

def execute_query(query, params=None, fetch=False, one=False):
    """Executa uma query no banco de dados com decodificação automática"""
    try:
        if not _mysql:
            logger.error("MySQL connection not configured")
            return None if fetch else False
        
        # CORREÇÃO: Usar cursor com row_factory
        cur = _mysql.connection.cursor()
        cur.row_factory = dict_factory
        
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)

        if fetch:
            result = cur.fetchall()
            cur.close()
            
            if not result:
                return None if one else []
            
            if one:
                # Retorna o primeiro resultado como dicionário
                return decode_bytes(result[0])
            
            # Retorna lista de dicionários
            return decode_bytes(result)
        else:
            _mysql.connection.commit()
            cur.close()
            return True
            
    except Exception as e:
        logger.error(f"Database error: {e}")
        logger.error(f"Query: {query}")
        logger.error(f"Params: {params}")
        if _mysql:
            try:
                _mysql.connection.rollback()
            except:
                pass
        return None if fetch else False

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
        
        if 'enfermeiro_id' not in session:
            # Tentar buscar o ID do enfermeiro novamente
            enfermeiro = execute_query("""
                SELECT id FROM enfermeiros 
                WHERE usuario_id = %s AND ativo = TRUE
            """, (session['user_id'],), fetch=True, one=True)
            
            if enfermeiro:
                if isinstance(enfermeiro, dict):
                    session['enfermeiro_id'] = enfermeiro.get('id')
                else:
                    session['enfermeiro_id'] = enfermeiro[0] if isinstance(enfermeiro, (list, tuple)) else enfermeiro
                
                # Buscar também o COREN
                coren = execute_query("""
                    SELECT coren FROM enfermeiros WHERE id = %s
                """, (session['enfermeiro_id'],), fetch=True, one=True)
                if coren:
                    if isinstance(coren, dict):
                        session['enfermeiro_coren'] = coren.get('coren')
                    else:
                        session['enfermeiro_coren'] = coren[0] if isinstance(coren, (list, tuple)) else coren
            else:
                flash('Perfil de enfermeiro não encontrado.', 'danger')
                return redirect(url_for('auth.logout'))
        
        return f(*args, **kwargs)
    return decorated_function

def classificar_pressao(pressao):
    """Classifica a pressão arterial"""
    if not pressao:
        return {'class': 'secondary', 'text': 'Não informado'}
    
    # Garantir que pressao é string
    pressao = str(pressao)
    
    # Aceitar tanto / quanto x como separador
    pressao = pressao.replace('/', 'x')
    
    if not re.match(r'^\d{2,3}x\d{2,3}$', pressao):
        return {'class': 'secondary', 'text': 'Não classificado'}
    
    try:
        sistolica, diastolica = map(int, pressao.split('x'))
        
        if sistolica < 120 and diastolica < 80:
            return {'class': 'success', 'text': 'Normal'}
        elif 120 <= sistolica < 130 and diastolica < 80:
            return {'class': 'warning', 'text': 'Pré-hipertensão'}
        elif 130 <= sistolica < 140 or 80 <= diastolica < 90:
            return {'class': 'warning', 'text': 'Hipertensão Estágio 1'}
        elif sistolica >= 140 or diastolica >= 90:
            return {'class': 'danger', 'text': 'Hipertensão Estágio 2'}
        else:
            return {'class': 'secondary', 'text': 'Não classificado'}
    except:
        return {'class': 'secondary', 'text': 'Erro na leitura'}

def formatar_data(data):
    """Formata uma data para o formato brasileiro"""
    if not data:
        return ''
    if hasattr(data, 'strftime'):
        return data.strftime('%d/%m/%Y')
    return str(data)

def formatar_data_hora(data):
    """Formata uma data e hora para o formato brasileiro"""
    if not data:
        return ''
    if hasattr(data, 'strftime'):
        return data.strftime('%d/%m/%Y %H:%M')
    return str(data)
