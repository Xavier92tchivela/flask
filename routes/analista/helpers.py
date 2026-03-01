"""Funções auxiliares para o módulo analista"""
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
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d']:
                try:
                    return datetime.strptime(data, fmt).strftime(formato)
                except ValueError:
                    continue
            return data
        return str(data)
    except Exception as e:
        logger.error(f"❌ Erro ao formatar data: {e}")
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
        
        if (hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day):
            idade -= 1
            
        return f"{idade} anos"
    except Exception as e:
        logger.error(f"❌ Erro ao calcular idade: {e}")
        return ''