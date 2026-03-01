# utils/database.py
import logging
import traceback

logger = logging.getLogger(__name__)

def execute_query(mysql, query, params=None, fetch=False, one=False):
    """Executa consulta SQL com suporte a fetch e commit"""
    try:
        cur = mysql.connection.cursor()
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        
        if fetch:
            result = cur.fetchall()
            cur.close()
            if one:
                return result[0] if result else None
            return result
        else:
            mysql.connection.commit()
            cur.close()
            return True
    except Exception as e:
        mysql.connection.rollback()
        logger.error(f"Database error: {e}")
        logger.error(f"Query: {query}")
        logger.error(f"Params: {params}")
        logger.error(traceback.format_exc())
        return None

def execute_query_raw(mysql, query, params=None):
    """Executa query e retorna cursor para uso avançado"""
    try:
        cur = mysql.connection.cursor()
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        return cur
    except Exception as e:
        logger.error(f"Database error: {e}")
        return None