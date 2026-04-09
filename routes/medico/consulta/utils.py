from datetime import datetime
import logging
import pymysql

logger = logging.getLogger(__name__)


# ===================== EXECUTE QUERY (BLINDADO) =====================
def execute_query(mysql, query, params=None, fetch=False, fetch_one=False):
    """
    Executa queries de forma segura, removendo bytes automaticamente
    e evitando erros SQL (ex: b'3')
    """

    conn = mysql.connection
    cur = conn.cursor(pymysql.cursors.DictCursor)

    try:

        # 🔥 LIMPEZA GLOBAL DE PARAMS (REMOVE b'3')
        clean_params = None

        if params:
            clean_params = []

            for p in params:
                # remove bytes
                if isinstance(p, (bytes, bytearray)):
                    p = p.decode()

                # remove espaços e normaliza
                if isinstance(p, str):
                    p = p.strip()

                clean_params.append(p)

            clean_params = tuple(clean_params)

        # EXECUTA QUERY
        if clean_params:
            cur.execute(query, clean_params)
        else:
            cur.execute(query)

        # RESULTADO
        result = None

        if fetch_one:
            result = cur.fetchone()
        elif fetch:
            result = cur.fetchall()
        else:
            conn.commit()

        return result

    except Exception as e:
        conn.rollback()
        logger.error("========== DATABASE ERROR ==========")
        logger.error(f"Erro: {e}")
        logger.error(f"Query: {query}")
        logger.error(f"Params: {params}")
        logger.error("===================================")
        return None

    finally:
        cur.close()


# ===================== FORMATAR DATA =====================
def formatar_data(data, formato='%d/%m/%Y %H:%M'):

    if isinstance(data, datetime):
        return data.strftime(formato)

    if isinstance(data, str):
        try:
            if 'T' in data:
                return datetime.fromisoformat(data.replace('Z', '+00:00')).strftime(formato)

            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                try:
                    return datetime.strptime(data, fmt).strftime(formato)
                except:
                    pass

            return data
        except:
            return data

    return str(data)


# ===================== MÉDICO ID =====================
def obter_medico_id(mysql, session):

    if session.get('user_type') != 'medico':
        return None

    try:
        result = execute_query(
            mysql,
            "SELECT id FROM medicos WHERE usuario_id = %s",
            (session['user_id'],),
            fetch_one=True
        )

        return result['id'] if result else None

    except Exception as e:
        logger.error(f"Erro obter medico_id: {e}")
        return None


# ===================== PACIENTE ID =====================
def obter_paciente_id(mysql, session):

    if session.get('user_type') != 'paciente':
        return None

    try:
        result = execute_query(
            mysql,
            "SELECT id FROM pacientes WHERE usuario_id = %s",
            (session['user_id'],),
            fetch_one=True
        )

        return result['id'] if result else None

    except Exception as e:
        logger.error(f"Erro obter paciente_id: {e}")
        return None


# ===================== SINTOMAS =====================
def processar_sintomas(sintomas_raw):

    if not sintomas_raw:
        return []

    return [s.strip() for s in sintomas_raw.split(',') if s.strip()]


# ===================== DIA DA SEMANA =====================
def mapear_dia_semana(dia_ingles):

    dias_map = {
        'Monday': 'Segunda',
        'Tuesday': 'Terça',
        'Wednesday': 'Quarta',
        'Thursday': 'Quinta',
        'Friday': 'Sexta',
        'Saturday': 'Sábado',
        'Sunday': 'Domingo'
    }

    return dias_map.get(dia_ingles, dia_ingles)


# ===================== MÊS =====================
def mapear_mes(mes_num):

    meses_map = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março',
        4: 'Abril', 5: 'Maio', 6: 'Junho',
        7: 'Julho', 8: 'Agosto', 9: 'Setembro',
        10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }

    return meses_map.get(mes_num, '')


# ===================== IDADE =====================
def calcular_idade(data_nascimento):

    if not data_nascimento:
        return None

    try:
        if isinstance(data_nascimento, datetime):
            data_nasc = data_nascimento
        else:
            data_nasc = datetime.strptime(str(data_nascimento), '%Y-%m-%d')

        hoje = datetime.now()
        idade = hoje.year - data_nasc.year

        if (hoje.month, hoje.day) < (data_nasc.month, data_nasc.day):
            idade -= 1

        return idade

    except:
        return None