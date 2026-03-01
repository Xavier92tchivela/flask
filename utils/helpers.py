# utils/helpers.py
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def formatar_data(data, formato='%d/%m/%Y %H:%M'):
    """Formata data para exibição"""
    if not data:
        return ''
    
    try:
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
    except Exception as e:
        logger.error(f"Erro ao formatar data {data}: {e}")
        return str(data)

def calcular_idade(data_nascimento):
    """Calcula idade a partir da data de nascimento"""
    if not data_nascimento:
        return ''
    try:
        if isinstance(data_nascimento, str):
            try:
                data_nascimento = datetime.strptime(data_nascimento, '%Y-%m-%d')
            except:
                try:
                    data_nascimento = datetime.strptime(data_nascimento, '%d/%m/%Y')
                except:
                    return ''
        
        hoje = datetime.now()
        idade = hoje.year - data_nascimento.year
        if hoje.month < data_nascimento.month or (hoje.month == data_nascimento.month and hoje.day < data_nascimento.day):
            idade -= 1
        return f"{idade} anos"
    except:
        return ''

def allowed_file(filename):
    """Verifica se o arquivo tem extensão permitida"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS