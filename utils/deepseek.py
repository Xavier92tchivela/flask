# utils/deepseek.py
import os
from openai import OpenAI
import logging

# Configurar logger
logger = logging.getLogger(__name__)

def configurar_deepseek(api_key=None):
    """
    Configura o cliente DeepSeek (compatível com API da OpenAI)
    Retorna: (cliente, disponível, nome_do_modelo)
    """
    if not api_key:
        api_key = os.environ.get('DEEPSEEK_API_KEY')
    
    if not api_key:
        logger.warning("⚠️ DEEPSEEK_API_KEY não encontrada")
        return None, False, None
    
    try:
        # Cliente compatível com OpenAI
        client = OpenAI(
            api_key=api_key.strip(),
            base_url="https://api.deepseek.com/v1"
        )
        
        # Testar conexão
        client.models.list()
        
        # Modelo disponível
        MODEL_NAME = "deepseek-chat"
        
        logger.info(f"✅ DeepSeek configurado com sucesso! Modelo: {MODEL_NAME}")
        
        # Retornar cliente no formato esperado
        deepseek_client = {
            'client': client,
            'model': MODEL_NAME
        }
        
        return deepseek_client, True, MODEL_NAME
        
    except Exception as e:
        logger.error(f"❌ Erro ao configurar DeepSeek: {e}")
        if hasattr(e, 'response'):
            try:
                logger.error(f"Detalhes: {e.response.text}")
            except:
                pass
        return None, False, None

def gerar_resposta_deepseek(deepseek_client, prompt, sistema=None, max_tokens=1000, temperatura=0.7):
    """
    Gera resposta usando DeepSeek
    """
    if not deepseek_client or not deepseek_client.get('client'):
        logger.error("Cliente DeepSeek não disponível")
        return None
    
    try:
        messages = []
        
        if sistema:
            messages.append({"role": "system", "content": sistema})
        
        messages.append({"role": "user", "content": prompt})
        
        logger.info(f"📤 Enviando prompt para DeepSeek ({len(prompt)} caracteres)")
        
        response = deepseek_client['client'].chat.completions.create(
            model=deepseek_client['model'],
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperatura
        )
        
        resposta = response.choices[0].message.content
        logger.info(f"📥 Resposta recebida ({len(resposta)} caracteres)")
        
        return resposta
        
    except Exception as e:
        logger.error(f"❌ Erro na geração DeepSeek: {e}")
        return None

# Função adicional para testar a conexão
def testar_conexao_deepseek(api_key):
    """
    Testa a conexão com a API DeepSeek
    """
    try:
        client = OpenAI(
            api_key=api_key.strip(),
            base_url="https://api.deepseek.com/v1"
        )
        
        # Tenta listar modelos
        models = client.models.list()
        
        return {
            'success': True,
            'message': f"Conexão bem sucedida! {len(models.data)} modelos disponíveis.",
            'models': [m.id for m in models.data]
        }
    except Exception as e:
        return {
            'success': False,
            'message': f"Erro na conexão: {str(e)}"
        }