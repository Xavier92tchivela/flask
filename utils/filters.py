# utils/filters.py
"""
Filtros personalizados para templates Jinja2
"""
from datetime import datetime, timedelta
import re

def time_ago(date):
    """
    Retorna uma string representando há quanto tempo uma data ocorreu
    Ex: "há 5 minutos", "há 2 horas", "ontem", "há 3 dias"
    """
    if not date:
        return ""
    
    # Se for string, converter para datetime
    if isinstance(date, str):
        try:
            # Tenta diferentes formatos
            for fmt in ['%d/%m/%Y %H:%M', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y']:
                try:
                    date = datetime.strptime(date, fmt)
                    break
                except ValueError:
                    continue
        except:
            return date
    
    if not isinstance(date, datetime):
        return str(date)
    
    now = datetime.now()
    diff = now - date
    
    if diff < timedelta(minutes=1):
        return "agora"
    elif diff < timedelta(hours=1):
        minutes = int(diff.total_seconds() / 60)
        return f"há {minutes} minuto{'s' if minutes > 1 else ''}"
    elif diff < timedelta(days=1):
        hours = int(diff.total_seconds() / 3600)
        return f"há {hours} hora{'s' if hours > 1 else ''}"
    elif diff < timedelta(days=2):
        return "ontem"
    elif diff < timedelta(days=7):
        days = diff.days
        return f"há {days} dia{'s' if days > 1 else ''}"
    elif diff < timedelta(days=30):
        weeks = diff.days // 7
        return f"há {weeks} semana{'s' if weeks > 1 else ''}"
    elif diff < timedelta(days=365):
        months = diff.days // 30
        return f"há {months} mês{'es' if months > 1 else ''}"
    else:
        years = diff.days // 365
        return f"há {years} ano{'s' if years > 1 else ''}"

def format_phone(phone):
    """Formata número de telefone"""
    if not phone:
        return ""
    
    # Remove tudo que não é dígito
    numbers = re.sub(r'\D', '', str(phone))
    
    if len(numbers) == 11:  # Celular com DDD
        return f"({numbers[:2]}) {numbers[2:7]}-{numbers[7:]}"
    elif len(numbers) == 10:  # Telefone fixo
        return f"({numbers[:2]}) {numbers[2:6]}-{numbers[6:]}"
    elif len(numbers) == 9:  # Celular sem DDD
        return f"{numbers[:5]}-{numbers[5:]}"
    elif len(numbers) == 8:  # Fixo sem DDD
        return f"{numbers[:4]}-{numbers[4:]}"
    else:
        return phone

def truncate_words(text, words=20):
    """Trunca texto por número de palavras"""
    if not text:
        return ""
    
    word_list = text.split()
    if len(word_list) <= words:
        return text
    
    return ' '.join(word_list[:words]) + '...'

def month_name(month_num):
    """Retorna nome do mês em português"""
    months = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
        5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
        9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }
    return months.get(month_num, '')

def day_name(day_english):
    """Retorna nome do dia em português"""
    days = {
        'Monday': 'Segunda',
        'Tuesday': 'Terça',
        'Wednesday': 'Quarta',
        'Thursday': 'Quinta',
        'Friday': 'Sexta',
        'Saturday': 'Sábado',
        'Sunday': 'Domingo'
    }
    return days.get(day_english, day_english)

def status_class(status):
    """Retorna classe CSS para status"""
    classes = {
        'agendada': 'warning',
        'confirmada': 'info',
        'realizada': 'success',
        'cancelada': 'danger',
        'pendente': 'warning',
        'concluido': 'success',
        'ativo': 'success',
        'inativo': 'secondary'
    }
    return classes.get(status.lower(), 'secondary')