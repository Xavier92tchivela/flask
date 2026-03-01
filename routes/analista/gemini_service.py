"""Serviços de IA com Gemini para o módulo analista"""
import os
import logging
import traceback
from datetime import datetime
from PIL import Image
import google.generativeai as genai
from .file_utils import ensure_temp_folder, get_temp_folder

logger = logging.getLogger(__name__)

_gemini_available = False
_model_name = None
_app = None

def set_gemini_config(gemini_available, MODEL_NAME, app):
    """Configura o serviço Gemini"""
    global _gemini_available, _model_name, _app
    _gemini_available = gemini_available
    _model_name = MODEL_NAME
    _app = app

def salvar_imagem_temporaria(file):
    """Salva imagem temporariamente para análise"""
    try:
        temp_dir = ensure_temp_folder()
        
        filename = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        filepath = os.path.join(temp_dir, filename)
        
        file.save(filepath)
        logger.info(f"📸 Imagem temporária salva: {filepath}")
        return filepath
        
    except Exception as e:
        logger.error(f"❌ Erro ao salvar imagem: {e}")
        return None

def preparar_contexto_clinico(pedido_info, observacoes_analista=''):
    """Prepara contexto clínico para análise"""
    from .helpers import calcular_idade
    
    try:
        if not pedido_info or len(pedido_info) < 15:
            return "Informações do pedido não disponíveis."
        
        tipo_exame = pedido_info[1] or 'Não especificado'
        descricao = pedido_info[2] or 'Não informada'
        observacoes = pedido_info[3] or 'Nenhuma'
        urgencia = pedido_info[4] or 'normal'
        paciente_nome = pedido_info[12] or 'Não informado'
        data_nascimento = pedido_info[13] if len(pedido_info) > 13 else None
        genero = pedido_info[14] if len(pedido_info) > 14 else ''
        
        idade = calcular_idade(data_nascimento) if data_nascimento else ''
        
        contexto = f"""
INFORMAÇÕES DO PACIENTE:
- Nome: {paciente_nome}
- Idade: {idade}
- Gênero: {genero}
- Tipo de exame: {tipo_exame}
- Urgência: {urgencia.upper()}

DESCRIÇÃO DO EXAME:
{descricao}

OBSERVAÇÕES MÉDICAS:
{observacoes}

OBSERVAÇÕES DO ANALISTA:
{observacoes_analista or 'Nenhuma'}
"""
        
        return contexto
        
    except Exception as e:
        logger.error(f"❌ Erro ao preparar contexto: {e}")
        return "Erro ao preparar contexto clínico."

def analisar_imagem_com_gemini(imagem_path, contexto_clinico):
    """Analisa imagem usando Gemini AI"""
    try:
        if not _gemini_available:
            return None, "API Gemini não configurada"
        
        if not os.path.exists(imagem_path):
            return None, "Arquivo de imagem não encontrado"
        
        try:
            img = Image.open(imagem_path)
        except Exception as e:
            return None, f"Erro ao abrir imagem: {str(e)}"
        
        prompt = f"""
Você é um analista médico especialista. Analise esta imagem médica e forneça um diagnóstico detalhado.

CONTEXTO CLÍNICO:
{contexto_clinico}

Por favor, forneça um relatório estruturado com:
1. Descrição da imagem e qualidade técnica
2. Achados principais
3. Diagnóstico sugerido
4. Recomendações
5. Nível de urgência (baixa, média, alta, emergência)

Use linguagem médica apropriada mas clara. Seja objetivo e baseie-se apenas na imagem fornecida.
"""
        
        try:
            model_name = _model_name if _model_name else "gemini-1.5-pro-vision"
            model = genai.GenerativeModel(model_name)
            
            img_data = Image.open(imagem_path)
            response = model.generate_content([prompt, img_data])
            
            resultado = response.text if response and hasattr(response, 'text') else "Não foi possível gerar um diagnóstico."
            
            return resultado, None
            
        except Exception as e:
            logger.error(f"❌ Erro ao chamar Gemini: {e}")
            logger.error(traceback.format_exc())
            return None, f"Erro na API Gemini: {str(e)}"
            
    except Exception as e:
        logger.error(f"❌ Erro geral na análise: {e}")
        logger.error(traceback.format_exc())
        return None, f"Erro interno: {str(e)}"