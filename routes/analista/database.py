"""Funções de banco de dados para o módulo analista"""
import logging

logger = logging.getLogger(__name__)
_mysql = None

def set_mysql(mysql):
    """Configura a conexão MySQL"""
    global _mysql
    _mysql = mysql

def get_mysql():
    """Retorna a conexão MySQL"""
    return _mysql

def execute_query(query, params=None, fetch=False, commit=True, one=False):
    """Executa consulta SQL"""
    global _mysql
    
    if not _mysql:
        logger.error("❌ MySQL não configurado")
        return None
    
    try:
        cur = _mysql.connection.cursor()
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        
        if fetch:
            if one:
                result = cur.fetchone()
            else:
                result = cur.fetchall()
        else:
            result = cur.lastrowid
        
        if not fetch and commit:
            _mysql.connection.commit()
        
        cur.close()
        return result
        
    except Exception as e:
        logger.error(f"❌ Database error: {e}")
        logger.error(f"Query: {query}")
        logger.error(f"Params: {params}")
        try:
            _mysql.connection.rollback()
        except:
            pass
        return None