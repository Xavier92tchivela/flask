# utils/gemini.py - VERSAO LIMPA (SEM EMOJIS)
import google.generativeai as genai
import logging
import traceback
import time
from typing import Optional, Tuple, Dict, Any

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

logger = logging.getLogger(__name__)

PREFERRED_MODELS = [
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-1.0-pro",
    "gemini-pro",
    "gemini-2.5-flash",
]

def configurar_gemini(api_key: str, force_paid: bool = False) -> Tuple[Optional[Dict[str, Any]], bool, Optional[str]]:
    """
    Configura e testa conexão com Gemini AI
    
    Args:
        api_key: Chave da API
        force_paid: Se True, tenta apenas modelos pagos
    
    Returns:
        Tuple[client, disponivel, nome_do_modelo]
    """
    
    client = None
    gemini_available = False
    MODEL_NAME = None
    
    print("\n" + "=" * 70)
    print("INICIANDO CONFIGURACAO DO GEMINI AI")
    print("=" * 70)
    
    if not api_key or not api_key.strip() or api_key.lower() == 'root':
        print("ERRO: Chave API nao configurada ou invalida")
        return None, False, None
    
    try:
        print(f"Chave API: {api_key[:10]}...{api_key[-4:]}")
        print(f"Modo: {'Pago' if force_paid else 'Hibrido (pago + gratuito)'}")
        
        genai.configure(api_key=api_key)
        print("API Gemini configurada")
        
        print("Testando modelos...")
        
        modelos_testar = PREFERRED_MODELS
        if force_paid:
            modelos_testar = [m for m in PREFERRED_MODELS if 'pro' in m or 'flash' in m]
        
        for model_name in modelos_testar:
            try:
                print(f"  Tentando modelo: {model_name}")
                
                model = genai.GenerativeModel(model_name)
                
                response = model.generate_content(
                    "Responda apenas com a palavra 'CONECTADO'",
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.1,
                        max_output_tokens=10
                    )
                )
                
                if response and response.text:
                    resposta = response.text.strip()
                    print(f"  SUCESSO: Modelo {model_name} respondeu: {resposta}")
                    
                    MODEL_NAME = model_name
                    gemini_available = True
                    
                    client = {
                        'configured': True,
                        'model_name': model_name,
                        'model': model,
                        'genai': genai
                    }
                    break
                else:
                    print(f"  AVISO: Resposta vazia de: {model_name}")
                    
            except Exception as model_error:
                error_msg = str(model_error)
                if "not found" in error_msg.lower():
                    print(f"  INFO: Modelo {model_name} nao disponivel")
                elif "quota" in error_msg.lower():
                    print(f"  ERRO: Limite excedido para {model_name}")
                elif "permission" in error_msg.lower():
                    print(f"  ERRO: Permissao negada para {model_name}")
                elif "billing" in error_msg.lower():
                    print(f"  ERRO: Problema de faturamento para {model_name}")
                else:
                    print(f"  ERRO: {model_name} falhou: {error_msg[:100]}...")
                continue
        
        if not gemini_available:
            print("Tentando modelo generico...")
            try:
                model = genai.GenerativeModel('gemini-pro')
                response = model.generate_content("Teste de conexao")
                
                if response and response.text:
                    MODEL_NAME = 'gemini-pro'
                    gemini_available = True
                    client = {
                        'configured': True,
                        'model_name': 'gemini-pro',
                        'model': model,
                        'genai': genai
                    }
                    print(f"SUCESSO: Conexao com modelo generico: {MODEL_NAME}")
                else:
                    print("ERRO: Resposta vazia do modelo generico")
                    
            except Exception as generic_error:
                print(f"ERRO: Modelo generico tambem falhou: {generic_error}")
                gemini_available = False
                
    except Exception as e:
        print(f"ERRO CRITICO: Erro geral ao configurar Gemini: {str(e)[:200]}")
        gemini_available = False
        logger.error(f"Erro Gemini: {e}")
        logger.error(traceback.format_exc())

    print("\n" + "=" * 70)
    print("RESULTADO GEMINI:")
    print(f"  Disponivel: {'SIM' if gemini_available else 'NAO'}")
    print(f"  Modelo: {MODEL_NAME or 'Nenhum'}")
    print(f"  Cliente: {'Configurado' if client else 'Nao configurado'}")
    print("=" * 70)
    
    return client, gemini_available, MODEL_NAME


def testar_modelos_disponiveis(api_key: str):
    """
    Lista todos os modelos disponiveis na conta
    """
    try:
        genai.configure(api_key=api_key)
        
        print("\n" + "=" * 70)
        print("MODELOS DISPONIVEIS:")
        print("=" * 70)
        
        modelos = genai.list_models()
        
        pagos = []
        gratuitos = []
        
        for m in modelos:
            if 'generateContent' in m.supported_generation_methods:
                nome = m.name
                if 'pro' in nome and 'flash' not in nome:
                    pagos.append(nome)
                elif 'flash' in nome:
                    gratuitos.append(nome)
                else:
                    gratuitos.append(nome)
                print(f"  {nome}")
        
        print("\n" + "=" * 70)
        print(f"Total: {len(pagos) + len(gratuitos)} modelos")
        print(f"Modelos premium: {len(pagos)}")
        print(f"Modelos gratuitos: {len(gratuitos)}")
        print("=" * 70)
        
    except Exception as e:
        print(f"Erro ao listar modelos: {e}")


def gerar_com_retry(model, prompt, max_tentativas=3, delay_base=1):
    """
    Gera conteudo com retry automatico para erros de quota
    """
    for tentativa in range(max_tentativas):
        try:
            response = model.generate_content(prompt)
            return response
        except Exception as e:
            error_msg = str(e).lower()
            if '429' in error_msg or 'quota' in error_msg or 'resource exhausted' in error_msg:
                if tentativa < max_tentativas - 1:
                    delay = delay_base * (2 ** tentativa)
                    print(f"Erro de quota, tentando novamente em {delay}s...")
                    time.sleep(delay)
                    continue
            raise e
    raise Exception("Todas as tentativas falharam")


def verificar_status_conta(api_key: str):
    """
    Verifica se a conta tem acesso pago
    """
    try:
        genai.configure(api_key=api_key)
        
        # Tenta modelo premium
        try:
            model = genai.GenerativeModel('gemini-1.5-pro')
            response = model.generate_content(
                "teste",
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=5
                )
            )
            return "PAGA (acesso a modelos premium)"
        except Exception as e:
            error_msg = str(e).lower()
            if 'billing' in error_msg:
                return "PAGA (com problemas de faturamento)"
            elif 'quota' in error_msg:
                return "GRATUITA (com limites)"
            else:
                return "GRATUITA"
                
    except Exception as e:
        return f"ERRO: {e}"