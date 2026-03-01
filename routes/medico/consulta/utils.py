# routes/medico/consulta/utils.py
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def execute_query(mysql, query, params=None, fetch=False):
    """Executa queries no banco de dados"""
    try:
        cur = mysql.connection.cursor()
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        
        if fetch:
            result = cur.fetchall()
        else:
            mysql.connection.commit()
            result = None
        
        cur.close()
        return result
    except Exception as e:
        if not fetch:
            mysql.connection.rollback()
        logger.error(f"Database error: {e}")
        return None

def formatar_data(data, formato='%d/%m/%Y %H:%M'):
    """Formata data de forma segura"""
    if isinstance(data, datetime):
        return data.strftime(formato)
    elif isinstance(data, str):
        try:
            if 'T' in data:
                return datetime.fromisoformat(data.replace('Z', '+00:00')).strftime(formato)
            else:
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                    try:
                        return datetime.strptime(data, fmt).strftime(formato)
                    except ValueError:
                        continue
                return data
        except:
            return data
    return str(data)

def obter_medico_id(mysql, session):
    """Obtém o ID do médico logado"""
    if session.get('user_type') != 'medico':
        return None
    
    try:
        medico = execute_query(mysql,
            "SELECT id FROM medicos WHERE usuario_id = %s", 
            (session['user_id'],), True
        )
        
        return medico[0][0] if medico else None
    except Exception as e:
        logger.error(f"Erro ao obter medico_id: {e}")
        return None

def obter_paciente_id(mysql, session):
    """Obtém o ID do paciente logado"""
    if session.get('user_type') != 'paciente':
        return None
    
    try:
        paciente = execute_query(mysql,
            "SELECT id FROM pacientes WHERE usuario_id = %s", 
            (session['user_id'],), True
        )
        
        return paciente[0][0] if paciente else None
    except Exception as e:
        logger.error(f"Erro ao obter paciente_id: {e}")
        return None

def processar_sintomas(sintomas_raw):
    """Processa string de sintomas para lista"""
    if not sintomas_raw:
        return []
    return [s.strip() for s in sintomas_raw.split(',') if s.strip()]

def mapear_dia_semana(dia_ingles):
    """Mapeia dia da semana de inglês para português"""
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

def mapear_mes(mes_num):
    """Mapeia número do mês para nome em português"""
    meses_map = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
        5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
        9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }
    return meses_map.get(mes_num, '')

def calcular_idade(data_nascimento):
    """Calcula idade a partir da data de nascimento"""
    if not data_nascimento:
        return None
    
    try:
        if isinstance(data_nascimento, datetime):
            data_nasc = data_nascimento
        else:
            data_nasc = datetime.strptime(str(data_nascimento), '%Y-%m-%d')
        
        hoje = datetime.now()
        idade = hoje.year - data_nasc.year
        
        if hoje.month < data_nasc.month or (hoje.month == data_nasc.month and hoje.day < data_nasc.day):
            idade -= 1
        
        return idade
    except:
        return None