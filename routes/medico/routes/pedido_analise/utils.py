# routes/pedido_analise/utils.py
from datetime import datetime, date
import json
import logging
import os
from werkzeug.utils import secure_filename
from flask import flash

logger = logging.getLogger(__name__)

# Configurações
UPLOAD_FOLDER = None
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt', 'dcm', 'zip', 'rar'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def init_utils(app):
    """Inicializa as configurações de upload"""
    global UPLOAD_FOLDER
    UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads', 'analises')
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Verifica se o tipo de arquivo é permitido"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def execute_query(mysql, query, params=None, fetch=False, commit=True, one=False):
    """Executa consulta SQL de forma segura"""
    try:
        cur = mysql.connection.cursor()
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
            mysql.connection.commit()
        
        cur.close()
        return result
    except Exception as e:
        logger.error(f"Database error: {e}")
        logger.error(f"Query: {query}")
        logger.error(f"Params: {params}")
        try:
            mysql.connection.rollback()
        except:
            pass
        return None

def formatar_data(data, formato='%d/%m/%Y %H:%M'):
    """Formata data para exibição"""
    if not data:
        return ''
    try:
        if isinstance(data, datetime):
            return data.strftime(formato)
        elif isinstance(data, date):
            return data.strftime('%d/%m/%Y')
        elif isinstance(data, str):
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                try:
                    return datetime.strptime(data, fmt).strftime(formato)
                except ValueError:
                    continue
            return data
        return str(data)
    except Exception as e:
        return str(data)

def calcular_idade(data_nascimento):
    """Calcula idade a partir da data de nascimento"""
    if not data_nascimento:
        return None
    try:
        if isinstance(data_nascimento, str):
            nascimento = datetime.strptime(data_nascimento[:10], '%Y-%m-%d').date()
        elif isinstance(data_nascimento, date):
            nascimento = data_nascimento
        elif isinstance(data_nascimento, datetime):
            nascimento = data_nascimento.date()
        else:
            return None
        
        hoje = date.today()
        idade = hoje.year - nascimento.year
        
        if (hoje.month, hoje.day) < (nascimento.month, nascimento.day):
            idade -= 1
        
        return idade
    except Exception as e:
        return None

def buscar_sinais_vitais(mysql, consulta_id):
    """Busca os sinais vitais de uma consulta"""
    if not consulta_id:
        return None
    
    try:
        sinais_query = """
            SELECT id, pressao_arterial, frequencia_cardiaca, frequencia_respiratoria,
                   temperatura, saturacao_oxigenio, glicemia, peso, data_afericao, observacoes
            FROM sinais_vitais
            WHERE consulta_id = %s
            ORDER BY data_afericao DESC
            LIMIT 1
        """
        sinais_data = execute_query(mysql, sinais_query, (consulta_id,), fetch=True, one=True)
        
        if not sinais_data:
            return None
        
        # Tenta importar as funções de classificação
        try:
            from routes.consulta import (
                classificar_pressao_arterial, classificar_frequencia_cardiaca,
                classificar_frequencia_respiratoria, classificar_temperatura,
                classificar_saturacao_oxigenio, classificar_glicemia
            )
        except ImportError:
            # Se não conseguir importar, define funções simples
            def classificar_pressao_arterial(x): return None
            def classificar_frequencia_cardiaca(x): return None
            def classificar_frequencia_respiratoria(x): return None
            def classificar_temperatura(x): return None
            def classificar_saturacao_oxigenio(x): return None
            def classificar_glicemia(x): return None
        
        sinais_vitais = {
            'id': sinais_data[0],
            'pressao_arterial': sinais_data[1],
            'pa_classificacao': classificar_pressao_arterial(sinais_data[1]) if sinais_data[1] else None,
            'frequencia_cardiaca': sinais_data[2],
            'fc_classificacao': classificar_frequencia_cardiaca(sinais_data[2]) if sinais_data[2] else None,
            'frequencia_respiratoria': sinais_data[3],
            'fr_classificacao': classificar_frequencia_respiratoria(sinais_data[3]) if sinais_data[3] else None,
            'temperatura': float(sinais_data[4]) if sinais_data[4] else None,
            'temp_classificacao': classificar_temperatura(sinais_data[4]) if sinais_data[4] else None,
            'saturacao_oxigenio': sinais_data[5],
            'spo2_classificacao': classificar_saturacao_oxigenio(sinais_data[5]) if sinais_data[5] else None,
            'glicemia': sinais_data[6],
            'glicemia_classificacao': classificar_glicemia(sinais_data[6]) if sinais_data[6] else None,
            'peso': float(sinais_data[7]) if sinais_data[7] else None,
            'data_afericao': formatar_data(sinais_data[8], '%d/%m/%Y %H:%M') if sinais_data[8] else '',
            'observacoes': sinais_data[9] or ''
        }
        
        return sinais_vitais
        
    except Exception as e:
        logger.error(f"Erro ao buscar sinais vitais: {e}")
        return None

def processar_anexos(request):
    """Processa os arquivos anexados ao pedido"""
    anexos_info = []
    if 'anexos[]' in request.files:
        files = request.files.getlist('anexos[]')
        for file in files:
            if file and file.filename:
                # Verificar tamanho
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)
                
                if file_size > MAX_FILE_SIZE:
                    flash(f'Arquivo {file.filename} excede 10MB.', 'warning')
                    continue
                
                if allowed_file(file.filename):
                    # Gerar nome seguro
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = secure_filename(f"{timestamp}_{file.filename}")
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    
                    # Salvar arquivo
                    file.save(file_path)
                    
                    anexos_info.append({
                        'filename': filename,
                        'original_name': file.filename,
                        'path': f'/static/uploads/analises/{filename}',
                        'size': file_size,
                        'upload_time': datetime.now().isoformat()
                    })
                else:
                    flash(f'Tipo de arquivo não permitido: {file.filename}', 'warning')
    
    return json.dumps(anexos_info, ensure_ascii=False) if anexos_info else None

def get_medico_id(mysql, user_id):
    """Obtém o ID do médico a partir do user_id"""
    medico_result = execute_query(
        mysql,
        "SELECT id FROM medicos WHERE usuario_id = %s",
        (user_id,), fetch=True, one=True
    )
    return medico_result[0] if medico_result else None